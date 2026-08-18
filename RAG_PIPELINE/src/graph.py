import asyncio
import os
from datetime import date
from typing import Any, TypedDict, List

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from .config import settings
from .doc_metadata import doc_type_label, period_label
from .llm_retry import with_retry
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


# --- State Definition ---
class GraphState(TypedDict):
    question: str        # what the user asked, verbatim - what we answer
    search_query: str    # the part a document could answer - what we retrieve on
    period_from: int | None   # YYYYMM date filter, None means no filter at all
    period_to: int | None
    coverage: dict       # what was actually searched, for the reply's footer
    generation: str
    documents: List[Document]
    user_id: str
    history: str # Added history for rephrasing


# Retrieval width. A narrow month or two needs few chunks; a year needs more,
# because the answer is spread across statements rather than sitting in one.
K_NO_RANGE = 9
K_SHORT_RANGE = 12
K_LONG_RANGE = 21
SHORT_RANGE_MONTHS = 3

# What "recently", "lately", "these days" resolve to when the user gives no
# dates of their own.
VAGUE_RECENT_MONTHS = 3


def ym(d: date) -> int:
    """date -> YYYYMM."""
    return d.year * 100 + d.month


def months_before(period_ym: int, n: int) -> int:
    """YYYYMM n months earlier. 202501 back 3 is 202410."""
    year, month = divmod(period_ym, 100)
    total = year * 12 + (month - 1) - n
    return (total // 12) * 100 + (total % 12) + 1


def month_span(period_from: int | None, period_to: int | None) -> int | None:
    """Inclusive month count of a range, or None when there is no range."""
    if period_from is None or period_to is None:
        return None
    lo, hi = sorted((period_from, period_to))
    lo_y, lo_m = divmod(lo, 100)
    hi_y, hi_m = divmod(hi, 100)
    return (hi_y * 12 + hi_m) - (lo_y * 12 + lo_m) + 1


def overlaps_range(
    meta: dict, period_from: int | None, period_to: int | None
) -> bool:
    """True when a chunk's own period overlaps the requested range.

    Undated chunks are False here, which is the opposite of the SQL predicate -
    deliberately. The SQL asks "may this be retrieved", where timeless
    documents always qualify. This asks "did the requested months actually
    match anything", where a timeless document is no evidence either way.
    """
    start, end = meta.get("period_start_ym"), meta.get("period_end_ym")
    if start is None or end is None:
        return False
    lo = period_from if period_from is not None else 1
    hi = period_to if period_to is not None else 999912
    return start <= hi and end >= lo


def k_for_range(period_from: int | None, period_to: int | None) -> int:
    """How many chunks to pull for a range of this width."""
    span = month_span(period_from, period_to)
    if span is None:
        return K_NO_RANGE
    return K_SHORT_RANGE if span <= SHORT_RANGE_MONTHS else K_LONG_RANGE


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


llm = with_retry(get_llm())


def describe_document(doc: Document) -> str:
    """One line naming the document a chunk came from, for the grader.

    doc_type, issuer and the period are metadata-only - they are never embedded
    - so this is how they reach a model at query time.
    """
    meta = doc.metadata or {}
    parts = [
        meta.get("issuer") or "",
        doc_type_label(meta.get("doc_type") or ""),
        period_label(meta.get("period_start_ym"), meta.get("period_end_ym")),
    ]
    return " · ".join(part for part in parts if part) or "Unknown document"

# --- Nodes ---

REPHRASE_SYSTEM = """You turn a user's message into a search query over the
financial documents they have uploaded.

They can upload anything financial, and the collection is wider than it looks:
bank, brokerage and credit card statements, invoices, receipts, pay stubs and
tax forms - but also credit card terms and conditions, account agreements, KYC
and onboarding paperwork, policies, disclosures, prospectuses, plan documents
and long financial reports. Numbers and prose both.

Keep everything in the message that one of those documents could contain. That
covers their own figures - payments, balances, holdings, fees, income, spending
- and equally the text they signed up to: rates, penalties, arbitration,
cancellation, coverage, eligibility, definitions stated BY their document.

Keep all of it. If they asked about three things, all three belong in the
query. Never pick one and discard the rest.

  "my rent payments and my brokerage fees last quarter"
  -> "rent payments, brokerage fees last quarter"

  "what's the late fee on my card and can I cancel without penalty"
  -> "late fee, cancellation penalty"

Drop only what no document of theirs could hold, because it lives in today's
world rather than in a file: live prices, market news, and general knowledge
asked in the abstract. Those words pull the search away from the words that
would match:

  "tell me about my bank payments last month and what AAPL is trading at"
  -> "bank payments last month"

  "how much did I spend on groceries in April, and should I buy more TSLA?"
  -> "groceries spending April"

Two things that look droppable but are not. A ticker: "what is AAPL trading at"
is the market, but "how many AAPL shares do I hold" is their statement - keep
it. A definition: "what is an APR" in the abstract is general knowledge, but
"what APR does my card charge" is in their terms - keep it.

Do drop the wrapper they speak in - "tell me about", "can you show me", "I was
wondering" - none of that appears in a document.

Do NOT judge whether the answer is really there. They may ask about a document
they never uploaded, and it still gets searched for. Cutting what could not be
in any financial document is your only job.

When unsure, KEEP the words. A useless word costs one weak match; a dropped one
cannot be searched for at all.

Resolve whatever the message leaves implicit against the chat history, so the
query stands on its own: pronouns, "that account", "the same month".

Keep their own wording, dates, amounts and names. Add nothing they did not say.
Do not answer the question.

If nothing in the message could be in a document, return it unchanged.

Return the query alone in `search_query`, with no quotes, label or explanation.

## The date range

Also report the months the question is about, as `period_from` and
`period_to`, each the integer YYYYMM. Today is {today}.

Return null for BOTH unless the question actually asks about a time. These are
the only four cases:

1. NO TIME MENTIONED - "what is my rent?", "what is my card's APR?" - null and
   null. This is the common case. Do not invent a range: a filter they did not
   ask for can only hide documents from them.

2. A SPECIFIC TIME - use it. "March 2025" is 202503 and 202503. "last quarter"
   and "the first three months of 2025" are 202501 and 202503. "last year" is
   the twelve months of the previous calendar year. "since June" runs from
   202506 to this month. A single named month has the same value for both.

3. VAGUE RECENCY - "recently", "lately", "these days", "over time", "how am I
   trending" - the last {vague_months} months ending this month.

4. EVERYTHING - "all time", "ever", "since I opened the account", "across all my
   statements" - null and null. They asked for no limit, so apply none.

A question can name a subject and no time at all. That is case 1, not case 3.
"How are my investments doing" is not "recently" - it has no time in it."""


class RewrittenQuery(BaseModel):
    """One call does both jobs: narrow the query and date-scope it."""

    search_query: str = Field(
        description="The part of the message an uploaded document could answer."
    )
    period_from: int | None = Field(
        default=None, description="First month asked about, YYYYMM, or null."
    )
    period_to: int | None = Field(
        default=None, description="Last month asked about, YYYYMM, or null."
    )


# Built once, like `llm`. Structured output needs the chat model itself, which
# the retry wrapper does not expose, so the wrap goes on the outside.
rephrase_chain = with_retry(get_llm().with_structured_output(RewrittenQuery))


def rephrase_query(state: GraphState):
    """Narrow the message to the part an uploaded document could answer.

    Runs on every turn, not just when there is history. A first-turn message is
    exactly where a mixed "my documents + live market" question arrives whole,
    and the market half is noise against a store of the user's own files.

    Only `search_query` is set. `question` stays verbatim so `generate` still
    answers what was actually asked.
    """
    question = state["question"]
    history = state.get("history", "")
    today = date.today()

    system = REPHRASE_SYSTEM.format(
        today=today.isoformat(), vague_months=VAGUE_RECENT_MONTHS
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Chat history:\n{history}\n\nMessage: {question}")
    ])
    try:
        result = rephrase_chain.invoke(
            prompt.format_messages(
                history=history or "(none)", question=question
            )
        )
        search_query = (result.search_query or "").strip()
        period_from, period_to = result.period_from, result.period_to
    except Exception as e:
        # Retries are already spent. Searching the raw message undated is worse
        # than a narrowed one, and far better than failing the turn.
        print(f"DEBUG [RAG]: Rephrase failed ({e}); raw message, no date filter.")
        search_query, period_from, period_to = "", None, None

    # A half-range would silently become an open-ended one. Either both bounds
    # survive or neither does.
    if (period_from is None) != (period_to is None):
        period_from = period_to = None
    if period_from is not None and period_to is not None and period_from > period_to:
        period_from, period_to = period_to, period_from

    search_query = search_query or question
    span = month_span(period_from, period_to)
    print(
        f"DEBUG [RAG]: Search query '{question}' -> '{search_query}' "
        f"period={period_from}..{period_to} span={span}"
    )

    return {
        "search_query": search_query,
        "period_from": period_from,
        "period_to": period_to,
    }


def retrieve(state: GraphState):
    """
    Retrieve documents based on the question.
    """
    question = state["question"]
    search_query = state.get("search_query") or question
    user_id = state.get("user_id")

    # --- BROAD QUERY DETECTION ---
    # Reads the original message, not the narrowed query: the rephraser strips
    # "summarize"/"tell me about my" as instructions to the assistant, which is
    # right for search and would silently disable this check.
    is_broad = any(
        word in question.lower()
        for word in ["summarize", "analyze", "overview", "everything", "my document"]
    )

    # If broad, use a VERY LOW threshold to ensure we get context
    THRESHOLD = 0.15 if is_broad else 0.35

    period_from, period_to = state.get("period_from"), state.get("period_to")
    k = 15 if is_broad else k_for_range(period_from, period_to)

    # --- AGGRESSIVE RETRIEVAL FOR BROAD QUERIES ---
    documents = []

    # New implementation: Use direct RPC wrapper 'perform_similarity_search'

    from .ingestion import count_chunks_in_range, perform_similarity_search

    eligible, total = count_chunks_in_range(user_id, period_from, period_to)

    # Run Search
    print(
        f"DEBUG [RAG]: Retrieving for user_id: {user_id}, query: {search_query}, "
        f"k={k}, period={period_from}..{period_to}, eligible={eligible}/{total}"
    )
    results = perform_similarity_search(
        query=search_query,
        user_id=user_id,
        k=k,
        threshold=THRESHOLD,
        period_from=period_from,
        period_to=period_to,
    )

    # A date filter must never be the reason we answer badly. Testing for an
    # EMPTY result set is not enough: undated documents are always eligible, so
    # a range matching no statement still comes back full of terms and
    # disclosures, and the answer is drawn from whatever those happen to say.
    # The real question is whether anything DATED landed in the range.
    filter_dropped = False
    if (period_from is not None or period_to is not None) and not any(
        overlaps_range(doc.metadata, period_from, period_to)
        for doc, _score in results
    ):
        print("DEBUG [RAG]: Nothing dated in range; retrying unfiltered.")
        filter_dropped = True
        results = perform_similarity_search(
            query=search_query,
            user_id=user_id,
            k=K_NO_RANGE,
            threshold=THRESHOLD,
        )
        eligible, total = count_chunks_in_range(user_id)

    coverage = {
        "period_from": None if filter_dropped else period_from,
        "period_to": None if filter_dropped else period_to,
        "requested_from": period_from,
        "requested_to": period_to,
        "filter_dropped": filter_dropped,
        "span_months": month_span(period_from, period_to),
        "k": k,
        "eligible": eligible,
        "total": total,
    }

    # Process Results
    print(f"DEBUG [RAG]: Found {len(results)} raw results.")
    for doc, score in results:
        # Avoid duplicates based on content
        if not any(d.page_content == doc.page_content for d in documents):
            documents.append(doc)
            print(f"DEBUG [RAG]: Retrieved Doc from {doc.metadata.get('source')} (Score: {score:.4f})")

    # --- [NEW] Verified Holdings Injection ---
    try:
        from ManagerAgent.holdings_db import get_holdings
        verified_holdings = get_holdings(user_id, status="verified")
        
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

    coverage["searched"] = len(documents)
    return {
        "documents": documents,
        "question": question,
        "user_id": user_id,
        "coverage": coverage,
    }


async def grade_documents(state: GraphState):
    """
    Determines if the retrieved documents are relevant to the question.

    Grades every document concurrently. One call per document is kept
    deliberately: batching them into a single prompt would make the model judge
    documents relative to each other rather than against the question, and
    position bias would grade the middle of the list less carefully. Retries
    handle the flakiness; concurrency handles the latency.
    """
    question = state["question"]
    search_query = state.get("search_query") or question
    documents = state["documents"]

    # --- SUMMARIZATION/BROAD OVERRIDE ---
    # Skipping the grader is only safe when the user genuinely wants the whole
    # document, where per-chunk grading would gut a summary. The marker has to
    # be the ASK, never the way they opened their sentence: "tell me about my"
    # and "analyze" prefix narrow questions constantly ("tell me about my
    # investment holdings"), and each one that slipped through let every
    # retrieved chunk reach the answer ungraded.
    # On the original message, for the same reason as is_broad in retrieve().
    if any(
        word in question.lower()
        for word in [
            "summarize",
            "summarise",
            "overview",
            "everything",
            "what is in my",
        ]
    ):
        print("DEBUG [RAG]: Whole-document request; keeping all chunks ungraded.")
        return {"documents": documents}

    # Simple grader prompt
    system = """You are a grader assessing relevance of a retrieved chunk to a user question.
    If the chunk contains keyword(s) or semantic meaning related to the user question, grade it as relevant.
    Give a binary score 'yes' or 'no' score to indicate whether the chunk is relevant to the question.
    Return only 'yes' or 'no'.

    Grade the CHUNK, not the source document. The source line is context for
    disambiguation only - if the question asks about a specific month and the
    source covers a different one, grade it 'no'."""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            (
                "human",
                "Source document: {source}\n\n"
                "Retrieved chunk:\n\n{document}\n\n"
                "User question: {question}",
            ),
        ]
    )
    grader_chain = prompt | llm | StrOutputParser()

    print(f"DEBUG [RAG]: Grading {len(documents)} documents...")
    scores = await asyncio.gather(
        *(
            grader_chain.ainvoke(
                {
                    "question": search_query,
                    "document": doc.page_content,
                    "source": describe_document(doc),
                }
            )
            for doc in documents
        ),
        return_exceptions=True,
    )

    filtered_docs = []
    has_relevant = False

    for doc, score in zip(documents, scores):
        if isinstance(score, BaseException):
            # Retries are already exhausted by this point. Keep the document
            # rather than drop it - a grading outage should not look to the
            # user like their statement is missing.
            print(f"DEBUG [RAG]: Grading failed for {doc.metadata.get('source')}: {score}")
            filtered_docs.append(doc)
            has_relevant = True
            continue
        print(f"DEBUG [RAG]: Doc from {doc.metadata.get('source')} Grade: {score}")
        if "yes" in score.lower():
            filtered_docs.append(doc)
            has_relevant = True

    if not has_relevant:
        print("DEBUG [RAG]: No relevant documents found after grading.")
        return {"documents": []}

    print(f"DEBUG [RAG]: {len(filtered_docs)} documents passed grading.")
    return {"documents": filtered_docs}


NO_RESULTS_MESSAGE = (
    "I searched your uploaded documents and could not find anything that answers "
    "this.\n\n"
    "Two things worth checking:\n\n"
    "- **Is the document uploaded?** If the statement, form or agreement you have "
    "in mind is not in your documents yet, there is nothing here for me to read.\n"
    "- **Can you be more specific?** Naming the institution, the account or the "
    "month usually finds it when a general phrasing does not - for example "
    '"Meridian checking, April 2025" rather than "my bank stuff".'
)


def coverage_footer(coverage: dict[str, Any] | None, documents: list) -> str:
    """What was actually searched, stated by the reply itself.

    Computed here rather than asked of the model for two reasons: a model
    writing its own coverage line will drift or invent one, and on multi-intent
    turns the synthesiser rewrites branch output - we have already watched it
    drop a notice it was told to keep. A fact appended in code survives.
    """
    if not documents:
        # Nothing was answered from, so there is no coverage to claim. The miss
        # path says its own piece.
        return ""

    coverage = coverage or {}
    parts = []

    sources = sorted(
        {
            os.path.basename(str(d.metadata.get("source", "")))
            for d in documents
            if d.metadata.get("source")
        }
    )
    if sources:
        parts.append("Sources: " + ", ".join(sources))

    label = period_label(coverage.get("period_from"), coverage.get("period_to"))
    parts.append(label if label else "all dates")

    searched, eligible = coverage.get("searched"), coverage.get("eligible")
    if searched is not None and eligible:
        parts.append(f"searched {searched} of {eligible} chunks")

    if not parts:
        return ""

    footer = "\n\n*" + " · ".join(parts) + "*"

    notes = []
    if coverage.get("filter_dropped"):
        asked = period_label(
            coverage.get("requested_from"), coverage.get("requested_to")
        )
        notes.append(
            f"Nothing in your documents falls in {asked}, so I searched all "
            "dates instead."
        )
    span = coverage.get("span_months")
    if span and span > SHORT_RANGE_MONTHS:
        notes.append(
            f"This question spans {span} months. I read the closest matches "
            "rather than every document in that range, so treat it as "
            "indicative rather than complete."
        )
    if notes:
        footer += "\n\n> " + "\n> ".join(notes)

    return footer


def reported_no_results(text: str) -> bool:
    """True when a RAG answer is the miss notice rather than an answer.

    Callers use this to keep the turn going: a miss is something to tell the
    user about and then work around, not a reason to stop.
    """
    return (text or "").strip() == NO_RESULTS_MESSAGE


def no_results(state: GraphState):
    """Nothing was retrieved, or nothing survived grading.

    A fixed message rather than a model call. The one thing this path must never
    do is produce an answer, and a model asked to explain a miss will happily
    fill the gap with something plausible. It also cannot fail or stall.

    This replaced a Tavily fallback. Answering a question about the user's own
    statement out of a web search - and citing it as "Web Search" next to their
    real filenames - reads as if their document had been found and read.
    """
    print("DEBUG [RAG]: No documents to answer from; reporting the miss.")

    coverage = state.get("coverage") or {}
    asked = period_label(
        coverage.get("requested_from"), coverage.get("requested_to")
    )
    if asked and coverage.get("total"):
        # "Upload it or be more specific" is the wrong advice when the real
        # problem is that they own nothing from the month they asked about.
        message = (
            f"I searched your uploaded documents for {asked} and found nothing "
            "that answers this.\n\n"
            "Either nothing from that period is uploaded yet, or the answer is "
            "in a document covering a different time. Try naming a different "
            "month, or ask without a date and I will search everything."
        )
        return {"generation": message, "documents": []}

    return {"generation": NO_RESULTS_MESSAGE, "documents": []}


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
- QUOTE FIGURES, DO NOT DERIVE THEM. If the document states a value - a total, a
  balance, an ending value, a subtotal - report that stated value exactly as
  written. Never add up rows to produce a number the document already gives you.
  A statement's own total accounts for cash, fees and adjustments that the line
  items above it do not, so a computed total is confidently wrong rather than
  approximately right.
- Only calculate when the question asks for something no line in the document
  states, and say plainly that you calculated it.
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

    return {
        "generation": generation,
        "documents": documents,
        "coverage": state.get("coverage") or {},
    }


# --- Conditional Logic ---
def decide_to_generate(state: GraphState):
    """
    Determines whether to answer from documents, or report that none matched.
    """
    documents = state["documents"]

    if not documents:
        # Nothing retrieved, or nothing survived grading -> say so
        return "no_results"
    else:
        # We have relevant documents, so generate answer
        return "generate"


# --- Graph Construction ---
workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("rephrase", rephrase_query)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("no_results", no_results)
workflow.add_node("generate", generate)

# Build graph
workflow.set_entry_point("rephrase")
workflow.add_edge("rephrase", "retrieve")
workflow.add_edge("retrieve", "grade_documents")

workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "no_results": "no_results",
        "generate": "generate",
    },
)
workflow.add_edge("no_results", END)
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
