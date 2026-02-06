from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_tavily import TavilySearch
from langchain_core.documents import Document
from .config import settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


# --- State Definition ---
class GraphState(TypedDict):
    question: str
    generation: str
    documents: List[Document]
    user_id: str
    history: str # Added history for rephrasing


# --- Initialization ---
def get_llm():
    """
    Returns the configured LLM (Gemini).
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")

    # Using gemini-2.5-flash for high speed and reasoning
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
    )


llm = get_llm()

# Tool: Tavily Search
web_search_tool = None
if settings.TAVILY_API_KEY:
    web_search_tool = TavilySearch(max_results=3, tavily_api_key=settings.TAVILY_API_KEY)

# --- Nodes ---

def rephrase_query(state: GraphState):
    """
    Rephrase the user question based on chat history to produce a standalone question.
    """
    question = state["question"]
    history = state.get("history", "")

    if not history:
        return {"question": question}

    print("DEBUG [RAG]: Rephrasing query with history context...")
    
    system = """You are a query rephraser for a financial RAG system. 
    Given a chat history and a follow-up user question, rephrase the question to be a standalone search query.
    If the question is already standalone, return it as is.
    Maintain the core intent and specific mentions (tickers, dates, etc.)."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Chat History:\n{history}\n\nFollow-up question: {question}")
    ])
    rephrase_chain = prompt | llm | StrOutputParser()
    
    standalone_query = rephrase_chain.invoke({"history": history, "question": question})
    print(f"DEBUG [RAG]: Rephrased '{question}' -> '{standalone_query}'")
    
    return {"question": standalone_query}


def retrieve(state: GraphState):
    """
    Retrieve documents based on the question.
    """
    question = state["question"]
    user_id = state.get("user_id")

    # --- BROAD QUERY DETECTION ---
    is_broad = any(
        word in question.lower()
        for word in ["summarize", "analyze", "overview", "everything", "my document"]
    )

    # If broad, use a VERY LOW threshold to ensure we get context
    THRESHOLD = 0.15 if is_broad else 0.35

    # --- AGGRESSIVE RETRIEVAL FOR BROAD QUERIES ---
    documents = []

    # New implementation: Use direct RPC wrapper 'perform_similarity_search'
    
    from .ingestion import perform_similarity_search
    
    # Run Search
    print(f"DEBUG [RAG]: Retrieving for user_id: {user_id}, query: {question}")
    results = perform_similarity_search(
        query=question,
        user_id=user_id,
        k=15 if is_broad else 6,
        threshold=THRESHOLD
    )
    
    # Process Results
    print(f"DEBUG [RAG]: Found {len(results)} raw results.")
    for doc, score in results:
        # Avoid duplicates based on content
        if not any(d.page_content == doc.page_content for d in documents):
            documents.append(doc)
            print(f"DEBUG [RAG]: Retrieved Doc from {doc.metadata.get('source')} (Score: {score:.4f})")

    # --- [NEW] Verified Holdings Injection ---
    try:
        from .local_store import load_holdings
        verified_holdings = [h for h in load_holdings() if h.get("status") == "verified"]
        
        if verified_holdings:
            print(f"DEBUG [RAG]: Checking {len(verified_holdings)} verified holdings for relevance...")
            # Simple ticker match or keyword match
            relevant_holdings = []
            for h in verified_holdings:
                ticker = h.get("ticker", "").upper()
                name = h.get("asset_name", "").lower()
                if ticker in question.upper() or (name and name in question.lower()) or "holding" in question.lower() or "own" in question.lower():
                    relevant_holdings.append(h)
            
            if relevant_holdings:
                print(f"DEBUG [RAG]: Injecting {len(relevant_holdings)} verified holdings into context.")
                for h in relevant_holdings:
                    content = f"VERIFIED HOLDING: {h.get('asset_name')} ({h.get('ticker')}). Quantity: {h.get('quantity')}. Price: {h.get('price')}."
                    documents.append(Document(page_content=content, metadata={"source": "Verified Portfolio", "type": "holdings"}))
    except Exception as e:
        print(f"DEBUG [RAG]: Failed to inject holdings: {e}")

    return {"documents": documents, "question": question, "user_id": user_id}


def grade_documents(state: GraphState):
    """
    Determines if the retrieved documents are relevant to the question.
    """
    question = state["question"].lower()
    documents = state["documents"]

    # --- SUMMARIZATION/BROAD OVERRIDE ---
    if any(
        word in question
        for word in [
            "summarize",
            "analyze",
            "overview",
            "what is in my",
            "tell me about my",
        ]
    ):
        return {"documents": documents, "question": state["question"]}

    # Simple grader prompt
    system = """You are a grader assessing relevance of a retrieved document to a user question. 
    If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. 
    Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.
    Return only 'yes' or 'no'."""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                "Retrieved document: \n\n {document} \n\n User question: {question}",
            ),
        ]
    )
    grader_chain = prompt | llm | StrOutputParser()

    filtered_docs = []
    has_relevant = False

    print(f"DEBUG [RAG]: Grading {len(documents)} documents...")
    for doc in documents:
        score = grader_chain.invoke(
            {"question": question, "document": doc.page_content}
        )
        print(f"DEBUG [RAG]: Doc from {doc.metadata.get('source')} Grade: {score}")
        if "yes" in score.lower():
            filtered_docs.append(doc)
            has_relevant = True

    if not has_relevant:
        print("DEBUG [RAG]: No relevant documents found after grading.")
        return {"documents": [], "question": question}

    print(f"DEBUG [RAG]: {len(filtered_docs)} documents passed grading.")
    return {"documents": filtered_docs, "question": question}


def web_search(state: GraphState):
    """
    Web search based on the re-phrased question.
    """
    question = state["question"]
    documents = state["documents"] if state.get("documents") else []

    if web_search_tool:
        try:
            docs = web_search_tool.invoke({"query": question})
            web_results = ""
            if isinstance(docs, list):
                for d in docs:
                    if isinstance(d, dict):
                         web_results += d.get("content", "") + "\n"
                    elif hasattr(d, "page_content"):
                         web_results += d.page_content + "\n"
                    else:
                         web_results += str(d) + "\n"
            else:
                web_results = str(docs)
                
            web_doc = Document(
                page_content=web_results, metadata={"source": "Tavily Search"}
            )
            documents.append(web_doc)
        except Exception as e:
            print(f"Web search error: {e}")
            # Fallback if search fails
            documents.append(
                Document(
                    page_content="Web search failed.", metadata={"source": "Error"}
                )
            )
    else:
        documents.append(
            Document(
                page_content="Web search tool is not configured (missing API Key).",
                metadata={"source": "System"},
            )
        )

    return {"documents": documents, "question": question}


def generate(state: GraphState):
    """
    Generate answer
    """
    question = state["question"]
    documents = state["documents"]

    # Format context
    context = "\n\n".join([doc.page_content for doc in documents])
    print(f"DEBUG [RAG]: Generating answer with {len(documents)} docs. Context length: {len(context)}")

    # Prompt
    template = """You are a helpful financial assistant. Answer the user's question based on the following context from their documents.

Context:
{context}

Question: {question}

Instructions:
- Use the provided context to answer the question as accurately as possible.
- If the context contains specific dates, prices, or quantities, include them in your answer.
- Provide a complete, conversational response in full sentences.
- DO NOT say "I don't have access to your data" if context is provided above. 
- You ARE allowed to see the user's private data for the purpose of answering this question.
- Reference "your document" or "your uploaded statement" when presenting info from the context.
- If the answer is not in the context at all, only then explain that you couldn't find specific details for that query.
- Append `<<LEGAL_DISCLAIMER>>` ONLY if the response contains specific investment recommendations or forward-looking projections. Do NOT append for factual document summaries.
"""

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm.with_config({"tags": ["final_generation"]}) | StrOutputParser()
    generation = chain.invoke({"context": context, "question": question})

    return {"generation": generation, "documents": documents}


# --- Conditional Logic ---
def decide_to_generate(state: GraphState):
    """
    Determines whether to generate an answer, or re-generate a question for web search.
    """
    documents = state["documents"]

    if not documents:
        # No relevant documents found -> Fetch from Web
        return "web_search"
    else:
        # We have relevant documents, so generate answer
        return "generate"


# --- Graph Construction ---
workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("rephrase", rephrase_query)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate", generate)

# Build graph
workflow.set_entry_point("rephrase")
workflow.add_edge("rephrase", "retrieve")
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

# --- Checkpointer Initialization ---
checkpointer = None
rag_pool = None

if settings.SUPABASE_DB_URL:
    try:
        # Create a connection pool for LangGraph checkpointers
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": None,
        }
        # Use AsyncConnectionPool for ainvoke compatibility
        # We Initialize with open=False so it doesn't fail at module import time (no loop)
        rag_pool = AsyncConnectionPool(
            conninfo=settings.SUPABASE_DB_URL,
            max_size=10,
            kwargs=connection_kwargs,
            open=False # Defer connection opening
        )
        checkpointer = AsyncPostgresSaver(rag_pool)
        
        print("LangGraph AsyncPostgresSaver initialized (Pool deferred).")
    except Exception as e:
        print(f"Failed to initialize AsyncPostgresSaver: {e}")

# Compile
app_graph = workflow.compile(checkpointer=checkpointer)
