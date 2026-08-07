"""
Multi-Intent Orchestrator

Executes multiple intents in sequence, passing context between them,
and synthesizes a final coherent response.
"""

from typing import List, Dict, Any
from litellm import acompletion
from ManagerAgent.router_intelligence import IntentType
from ManagerAgent.tools import perform_rag_search, ask_stock_analyst
from ManagerAgent.profile_engine import get_profile_directives
from ManagerAgent.database import get_db
from CalcAgent.src.agent import financial_agent, general_agent
from CalcAgent.src.utils import run_with_retry
import os
import asyncio


def has_uploaded_documents() -> bool:
    """Check if user has any uploaded documents."""
    upload_dir = "ManagerAgent/uploads"
    if not os.path.exists(upload_dir):
        return False
    files = [f for f in os.listdir(upload_dir) if f.endswith(".pdf")]
    return len(files) > 0


async def run_calculator(query: str, context: Dict[str, Any] = None) -> str:
    """Run the financial calculator agent with optional context."""
    try:
        if context and context.get("results"):
            context_str = "\n".join(
                [f"{k.upper()}: {v}" for k, v in context["results"].items() if v]
            )
            enriched_query = (
                f"Context from previous analysis:\n{context_str}\n\nUser Query: {query}"
            )
        else:
            enriched_query = query

        result = await run_with_retry(financial_agent, enriched_query)
        return result.final_output
    except Exception as e:
        return f"Calculator error: {str(e)}"


BRANCH_LABELS = {
    "rag": "FROM THE USER'S OWN UPLOADED DOCUMENTS",
    "stock": "FROM LIVE MARKET DATA",
    "calculator": "FROM THE CALCULATION ENGINE",
    "general": "FROM GENERAL ANALYSIS",
}


def enrich_query_with_context(query: str, context: Dict[str, Any]) -> str:
    """Prefix the query with what earlier branches already found.

    EVERY branch that runs after another needs this, not just STOCK. A branch
    that answers blind will tell the user it has no access to their financial
    data - and suggest uploading a statement - even when a previous branch just
    read the answer out of that very statement.
    """
    results = context.get("results") or {}

    # dict order is execution order: RAG -> STOCK -> CALCULATOR -> GENERAL
    parts = [
        f"--- {BRANCH_LABELS.get(name, name.upper())} ---\n{text}"
        for name, text in results.items()
        if text and text.strip()
    ]
    if not parts:
        return query

    return (
        f"{chr(10).join(parts)}\n\n"
        f"User's Question: {query}\n\n"
        "IMPORTANT: The findings above were already retrieved for this specific "
        "user. Treat them as data you have access to and answer from them. Do NOT "
        "tell the user you have no access to their financial data, and do NOT ask "
        "them to upload a document that already appears above."
    )


ORCHESTRATOR_SYNTHESIS_PROMPT = """You are a Master Financial Orchestrator.
Your goal is to synthesize the following agent findings into a cohesive, professional, and helpful response for the user.
{persona_section}
CHAT HISTORY (for context):
{history}

USER QUERY: {query}

AGENT FINDINGS:
{results_text}

INSTRUCTIONS:
- Integrate the findings logically.
- **DOCUMENT DATA IS AUTHORITATIVE**: findings drawn from the user's own uploaded
  documents are the source of truth. These agents genuinely can read the user's
  files.
- **RESOLVE CONFLICTS IN FAVOUR OF DATA**: if one agent supplies a fact and
  another says it cannot access the user's financial data, use the fact and DROP
  the disclaimer completely. Do not mention that any agent lacked access, and do
  not hedge the fact you were given.
- Never ask the user to upload a document that already appears in the findings.
- **CITATIONS**: cite sources inline as plain markdown links, written exactly like
  this with no backticks: [marketbeat.com](https://www.marketbeat.com/stocks/NASDAQ/NVDA)
  Never wrap a markdown link in backticks - it renders as code and stops working.
  Only cite real http:// or https:// URLs that appear in the findings; for a
  document, name the file in prose instead of linking it.
- Apply the user profile directives to adjust your tone.
- Maintain a helpful, analytical tone.
- Do not repeat yourself.
- Ensure the final output is formatted in clean Markdown.
"""


def _build_synthesis_prompt(
    query: str, results: Dict[str, str], history: str, user_directives: str
) -> str:
    """Shared by the streaming and non-streaming synthesizers."""
    results_text = "\n\n".join(
        [
            f"--- {intent.upper()} RESULT ---\n{result}"
            for intent, result in results.items()
            if result
        ]
    )

    persona_section = ""
    if user_directives:
        persona_section = f"""\n\nUSER PROFILE DIRECTIVES (Apply these to your response style and recommendations):
{user_directives}
"""

    return ORCHESTRATOR_SYNTHESIS_PROMPT.format(
        persona_section=persona_section,
        history=history,
        query=query,
        results_text=results_text,
    )


async def synthesize_response(
    query: str, results: Dict[str, str], history: str = "", user_directives: str = ""
) -> str:
    """Use LLM to combine multiple agent results into one coherent response with chat history context."""

    if len(results) == 1 and not history and not user_directives:
        return list(results.values())[0]

    prompt = _build_synthesis_prompt(query, results, history, user_directives)

    try:
        response = await acompletion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        # Fall back to the raw findings rather than losing them entirely.
        joined = "\n\n".join(text for text in results.values() if text)
        return f"{joined}\n\n(Synthesis failed: {str(e)})"


async def synthesize_response_stream(
    query: str, results: Dict[str, str], history: str = "", user_directives: str = ""
):
    """Streamed synthesis. Shares ORCHESTRATOR_SYNTHESIS_PROMPT with synthesize_response."""

    prompt = _build_synthesis_prompt(query, results, history, user_directives)

    try:
        stream = await acompletion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield {"type": "token", "content": chunk.choices[0].delta.content}
                await asyncio.sleep(0)  # Force buffer flush
    except Exception as e:
        yield {"type": "token", "content": f"\n\n(Synthesis Error: {e})"}


async def orchestrate(
    query: str,
    intents: List[IntentType],
    user_id: str = "fallback-user-id",
    history: str = "",
) -> str:
    """
    Execute multiple intents in order, passing context between them,
    and synthesize a final response. Scoped by user_id and aware of chat history.
    """
    # ... (Keep existing implementation of sync orchestrate for backward compatibility if used)
    # Re-implementing strictly to avoid breaking changes if this function is called elsewhere.
    # Ideally we'd wrap orchestrate_stream but for now I'll leave the existing sync body as provided in file view
    # or just copy-paste the original implementation if I am replacing the whole file content?
    # I am using replace_file_content on a Range.
    # The range start is 106. The range end is 290.
    # 'orchestrate' is at 160. So I am replacing 'orchestrate' as well.
    # I will just keep the original 'orchestrate' code in the replacement chunks.

    context = {"query": query, "results": {}}

    # Execution Order: RAG -> STOCK -> CALCULATOR -> GENERAL
    ORDER_PRIORITY = {
        IntentType.RAG: 0,
        IntentType.STOCK: 1,
        IntentType.CALCULATOR: 2,
        IntentType.GENERAL: 3,
    }
    intents.sort(key=lambda x: ORDER_PRIORITY.get(x, 99))

    for intent in intents:
        if intent == IntentType.RAG:
            result = await perform_rag_search(query, user_id=user_id, history=history)
            context["results"]["rag"] = result

        elif intent == IntentType.STOCK:
            enriched_query = enrich_query_with_context(query, context)
            if history:
                enriched_query = f"Conversation History:\n{history}\n\n{enriched_query}"
            result = await ask_stock_analyst(enriched_query)
            context["results"]["stock"] = result

        elif intent == IntentType.CALCULATOR:
            enriched_query = enrich_query_with_context(query, context)
            if history:
                enriched_query = f"History context: {history}\n\n{enriched_query}"
            result = await asyncio.wait_for(
                run_with_retry(financial_agent, enriched_query), timeout=90.0
            )
            context["results"]["calculator"] = result.final_output

        elif intent == IntentType.GENERAL:
            enriched_query = enrich_query_with_context(query, context)
            if history:
                enriched_query = f"Chat History:\n{history}\n\n{enriched_query}"
            result = await run_with_retry(general_agent, enriched_query)
            context["results"]["general"] = result.final_output

    final_response = await synthesize_response(
        query, context["results"], history=history, user_directives=""  # Non-stream path - directives not fetched
    )
    return final_response


async def orchestrate_stream(
    query: str,
    intents: List[IntentType],
    user_id: str = "fallback-user-id",
    history: str = "",
):
    """
    Streamed version of orchestrate with 'Status for Agents, Tokens for Synthesis'.
    Supports DIRECT STREAMING for single-intent queries to minimize latency.
    Now with Dynamic Profile Directives injection.
    """
    context = {"query": query, "results": {}}
    
    # Fetch user profile directives for personalized responses
    user_directives = ""
    try:
        with get_db() as conn:
            user_directives = get_profile_directives(user_id, conn)
    except Exception as e:
        print(f"[Orchestrator] Could not fetch profile directives: {e}")

    # Execution Order: RAG -> STOCK -> CALCULATOR -> GENERAL
    ORDER_PRIORITY = {
        IntentType.RAG: 0,
        IntentType.STOCK: 1,
        IntentType.CALCULATOR: 2,
        IntentType.GENERAL: 3,
    }
    intents.sort(key=lambda x: ORDER_PRIORITY.get(x, 99))

    # Check if we can direct stream (skip synthesis buffering)
    # RAG, CALCULATOR, GENERAL, and STOCK all produce chat-ready responses.
    is_single_intent = len(intents) == 1
    should_direct_stream = is_single_intent

    try:
        for intent in intents:
            if intent == IntentType.RAG:
                yield {"type": "status", "content": "Searching documents (RAG)..."}

                from ManagerAgent.tools import perform_rag_search_stream

                full_rag_response = []
                async for chunk in perform_rag_search_stream(query, user_id=user_id, history=history):
                    if chunk["type"] == "status":
                        yield chunk
                    elif chunk["type"] == "token":
                        full_rag_response.append(chunk["content"])
                        if should_direct_stream:  # RAG is answering directly
                            yield chunk

                context["results"]["rag"] = "".join(full_rag_response)

            elif intent == IntentType.STOCK:
                yield {"type": "status", "content": "Running stock analysis..."}

                enriched_query = enrich_query_with_context(query, context)
                if history:
                    enriched_query = (
                        f"Conversation History:\n{history}\n\n{enriched_query}"
                    )

                from ManagerAgent.tools import ask_stock_analyst_stream

                full_stock_response = []
                async for chunk in ask_stock_analyst_stream(enriched_query):
                    if chunk["type"] == "status":
                        yield chunk
                    elif chunk["type"] == "data":
                        # Push chart data to frontend immediately
                        yield chunk 
                    elif chunk["type"] == "token":
                        full_stock_response.append(chunk["content"])
                        if should_direct_stream:
                            yield chunk

                context["results"]["stock"] = "".join(full_stock_response)

            elif intent == IntentType.CALCULATOR:
                yield {"type": "status", "content": "Calculating..."}

                enriched_query = enrich_query_with_context(query, context)
                if history:
                    enriched_query = f"History context: {history}\n\n{enriched_query}"

                # Use new true streaming function
                from CalcAgent.src.utils import run_with_retry_stream
                from CalcAgent.src.agent import financial_agent

                full_calc_response = []
                # Add timeout to the stream iteration if needed, or rely on internal timeouts
                async for chunk in run_with_retry_stream(
                    financial_agent, enriched_query
                ):
                    if chunk["type"] == "status":
                        yield chunk
                    elif chunk["type"] == "token":
                        full_calc_response.append(chunk["content"])
                        if should_direct_stream:
                            yield chunk

                context["results"]["calculator"] = "".join(full_calc_response)

            elif intent == IntentType.GENERAL:
                yield {"type": "status", "content": "Thinking (General Agent)..."}

                enriched_query = enrich_query_with_context(query, context)
                if history:
                    enriched_query = f"Chat History:\n{history}\n\n{enriched_query}"

                from CalcAgent.src.utils import run_with_retry_stream
                from CalcAgent.src.agent import general_agent

                full_gen_response = []
                async for chunk in run_with_retry_stream(general_agent, enriched_query):
                    if chunk["type"] == "status":
                        yield chunk
                    elif chunk["type"] == "token":
                        full_gen_response.append(chunk["content"])
                        if should_direct_stream:
                            yield chunk

                context["results"]["general"] = "".join(full_gen_response)

        # Final Synthesis
        # Only synthesize if we buffered (didn't direct stream)
        if not should_direct_stream:
            yield {"type": "status", "content": "Synthesizing final response..."}
            async for chunk in synthesize_response_stream(
                query, context["results"], history=history, user_directives=user_directives
            ):
                yield chunk

    except GeneratorExit:
        # Handle disconnection/cancellation
        print("Orchestrator stream cancelled by client.")
        raise
    except Exception as e:
        yield {"type": "token", "content": f"\n\n(Orchestrator Error: {e})"}
