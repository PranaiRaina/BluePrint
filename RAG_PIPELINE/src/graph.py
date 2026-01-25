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

from langchain_groq import ChatGroq

# --- Initialization ---
def get_llm():
    """
    Returns the configured LLM based on settings.LLM_PROVIDER.
    """
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set.")
        # Using Llama 3 8B optimized for Groq
        return ChatGroq(model="llama3-8b-8192", groq_api_key=settings.GROQ_API_KEY)
    
    else: # Default to Gemini
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")
        # Using gemini-flash-latest as verified from list_models()
        return ChatGoogleGenerativeAI(model="gemini-flash-latest", google_api_key=settings.GOOGLE_API_KEY)

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
    vectorstore = get_vectorstore()
    
    results = vectorstore.similarity_search_with_relevance_scores(question, k=4)
    
    # Filter by Threshold
    THRESHOLD = 0.45
    documents = []
    
    for doc, score in results:
        print(f"Doc Score: {score}")
        if score >= THRESHOLD:
            documents.append(doc)
        else:
            print(f"Skipping low relevance doc (Score: {score})")
            
    return {"documents": documents, "question": question}

def grade_documents(state: GraphState):
    """
    Determines if the retrieved documents are relevant to the question.
    If not, we will set a flag to run web search.
    """
    print("---CHECK RELEVANCE---")
    question = state["question"]
    documents = state["documents"]
    
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
    template = """Answer the question based strictly on the following context.
    
    Context:
    {context}
    
    Question: {question}
    
    Instructions:
    - If the context contains the answer, provide it clearly.
    - If the context comes from a "Global Summary" of a PDF, mention that.
    - If the context comes from "Web search", mention that you fetched this information online.
    - If the question asks for advice (e.g., "Should X do Y?"), use the general definitions/rules in the context to provide a qualified recommendation, even if the specific person is not mentioned in the context.
    - Only answer "I do not have enough information" if the context is completely irrelevant.
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
