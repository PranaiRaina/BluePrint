from typing import Dict, TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.documents import Document
from .ingestion import get_vectorstore
from .config import settings

# --- State Definition ---
class GraphState(TypedDict):
    question: str
    generation: str
    documents: List[Document]
    user_id: str


# --- Initialization ---
def get_llm():
    """
    Returns the configured LLM (Gemini).
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")
    
    # Using gemini-2.0-flash for high speed and reasoning
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=settings.GOOGLE_API_KEY)

llm = get_llm()

from langchain_community.tools.tavily_search import TavilySearchResults

# ... (get_llm is above) ...

# Tool: Tavily Search
web_search_tool = None
if settings.TAVILY_API_KEY:
    web_search_tool = TavilySearchResults(tavily_api_key=settings.TAVILY_API_KEY, k=3)

# --- Nodes ---

def retrieve(state: GraphState):
    """
    Retrieve documents based on the question.
    """
    print("---RETRIEVE---")
    question = state["question"]
    user_id = state.get("user_id")
    
    # --- BROAD QUERY DETECTION ---
    is_broad = any(word in question.lower() for word in ["summarize", "analyze", "overview", "everything", "my document"])
    
    # 2. Similarity Search
    # If broad, use a VERY LOW threshold to ensure we get context
    THRESHOLD = 0.15 if is_broad else 0.35
    
    print(f"RAG: Searching for user_id == {user_id} (Broad={is_broad})")
    vectorstore = get_vectorstore()
    
    # --- AGGRESSIVE RETRIEVAL FOR BROAD QUERIES ---
    documents = []
    
    if is_broad:
        print("--- BROAD QUERY DETECTED: Fetching user documents directly ---")
        try:
            # We fetch up to 15 recent chunks for this user regardless of semantic score
            broad_results = vectorstore.get(
                where={"user_id": user_id},
                limit=15,
                include=["documents", "metadatas"]
            )
            
            if broad_results and broad_results['documents']:
                from langchain_core.documents import Document
                for i in range(len(broad_results['documents'])):
                    documents.append(Document(
                        page_content=broad_results['documents'][i],
                        metadata=broad_results['metadatas'][i]
                    ))
                print(f"Direct retrieval found {len(documents)} context chunks.")
        except Exception as e:
            print(f"Direct Fetch Error: {e}")

    # Fallback/Supplemental: Similarity Search
    if len(documents) < 5:
        results = vectorstore.similarity_search_with_relevance_scores(
            question, 
            k=10 if is_broad else 6,
            filter={"user_id": user_id}
        )
        
        for doc, score in results:
            if score >= THRESHOLD:
                # Avoid duplicates
                if not any(d.page_content == doc.page_content for d in documents):
                    documents.append(doc)
            
    return {"documents": documents, "question": question, "user_id": user_id}

def grade_documents(state: GraphState):
    """
    Determines if the retrieved documents are relevant to the question.
    """
    print("---CHECK RELEVANCE---")
    question = state["question"].lower()
    documents = state["documents"]
    
    # --- SUMMARIZATION/BROAD OVERRIDE ---
    if any(word in question for word in ["summarize", "analyze", "overview", "what is in my", "tell me about my"]):
        print(f"--- BROAD QUERY DETECTED: Auto-accepting {len(documents)} documents ---")
        return {"documents": documents, "question": state["question"]}

    # Simple grader prompt
    system = """You are a grader assessing relevance of a retrieved document to a user question. 
    If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. 
    Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.
    Return only 'yes' or 'no'."""
    
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", "Retrieved document: \n\n {document} \n\n User question: {question}")])
    grader_chain = prompt | llm | StrOutputParser()
    
    filtered_docs = []
    has_relevant = False
    
    for doc in documents:
        score = grader_chain.invoke({"question": question, "document": doc.page_content})
        if "yes" in score.lower():
            filtered_docs.append(doc)
            has_relevant = True
    
    if not has_relevant:
        print("---NO RELEVANT DOCS FOUND -> WILL SEARCH---")
        return {"documents": [], "question": question}
    
    return {"documents": filtered_docs, "question": question}

def web_search(state: GraphState):
    """
    Web search based on the re-phrased question.
    """
    print("---WEB SEARCH---")
    question = state["question"]
    documents = state["documents"] if state.get("documents") else []

    if web_search_tool:
        try:
            docs = web_search_tool.invoke({"query": question})
            # Tavily returns a list of dictionaries, we convert to Documents
            web_results = "\n".join([d["content"] for d in docs])
            print(f"---WEB RESULTS SAMPLE---\n{web_results[:500]}\n------------------------")
            web_doc = Document(page_content=web_results, metadata={"source": "Tavily Search"})
            documents.append(web_doc)
        except Exception as e:
            print(f"Web search error: {e}")
            # Fallback if search fails
            documents.append(Document(page_content="Web search failed.", metadata={"source": "Error"}))
    else:
        documents.append(Document(page_content="Web search tool is not configured (missing API Key).", metadata={"source": "System"}))

    return {"documents": documents, "question": question}

def generate(state: GraphState):
    """
    Generate answer
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state["documents"]
    
    # Format context
    context = "\n\n".join([doc.page_content for doc in documents])
    
    # Prompt
    template = """You are a helpful financial assistant. Answer the user's question based on the following context from their documents.

Context:
{context}

Question: {question}

Instructions:
- Provide a complete, conversational response in full sentences.
- DO NOT give one-word or number-only answers. Always explain the answer in context.
- For example, instead of just "10", say "Based on your document, you have 10 shares of Apple stock."
- If the context contains the answer, provide it clearly with relevant details.
- If the context comes from a "Global Summary" of a PDF, you can reference "your document" or "your uploaded file".
- If the context comes from "Web search", mention that you fetched this information online.
- DO NOT add disclaimers when simply presenting factual information from the user's documents.
- Only add a disclaimer if the user is asking for investment advice or recommendations.
- Only say "I couldn't find that information in your documents" if the context is completely irrelevant.
"""
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()
    generation = chain.invoke({"context": context, "question": question})
    
    return {"generation": generation}

# --- Conditional Logic ---
def decide_to_generate(state: GraphState):
    """
    Determines whether to generate an answer, or re-generate a question for web search.
    """
    print("---ASSESS GRADED DOCUMENTS---")
    documents = state["documents"]

    if not documents:
        # No relevant documents found -> Fetch from Web
        print("---DECISION: WEB SEARCH---")
        return "web_search"
    else:
        # We have relevant documents, so generate answer
        print("---DECISION: GENERATE---")
        return "generate"

# --- Graph Construction ---
workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate", generate)

# Build graph
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")

workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "web_search": "web_search",
        "generate": "generate",
    },
)
workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", END)

# Compile
app_graph = workflow.compile()
