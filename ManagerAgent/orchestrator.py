"""
Multi-Intent Orchestrator

Executes multiple intents in sequence, passing context between them,
and synthesizes a final coherent response.
"""

from typing import List, Dict, Any
from litellm import acompletion
from ManagerAgent.router_intelligence import IntentType
from ManagerAgent.tools import perform_rag_search, ask_stock_analyst
from RAG_PIPELINE.src.graph import reported_no_results
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


# One retry on top of litellm's own num_retries=3, and unlike the streaming
# version these actually fire: a dropped non-streaming request raises instead of
# being reported as a clean finish.
MAX_STREAM_ATTEMPTS = 2
SYNTHESIS_BACKOFF_SECONDS = 0.5

# The answer is generated whole, then handed over in pieces so the client paints
# progressively instead of in one block. Small enough to look continuous, large
# enough not to make thousands of SSE events out of a long reply.
REPLAY_CHUNK_CHARS = 24

BRANCH_LABELS = {
    "rag": "FROM THE USER'S OWN UPLOADED DOCUMENTS",
    "stock": "FROM LIVE MARKET DATA",
    "calculator": "FROM THE CALCULATION ENGINE",
    "general": "FROM GENERAL ANALYSIS",
}


def _continue_without_documents(rag_result: str, intents: List[IntentType]) -> None:
    """A document search that found nothing must not end the turn.

    Only fires when RAG was the whole turn. That is the case that would
    otherwise stop at "I couldn't find it" having answered nothing, so the
    general agent is added to answer from general knowledge and the web
    instead. When other branches are queued the turn already continues without
    documents, and bolting GENERAL on would just add a second voice restating
    what STOCK or CALCULATOR is about to say properly.

    Appends to `intents` while the caller is iterating it, which Python's list
    iteration picks up. GENERAL is last in ORDER_PRIORITY, so appending also
    puts it in the right place.
    """
    if not reported_no_results(rag_result):
        return
    if intents != [IntentType.RAG]:
        return

    print("[Orchestrator] Documents matched nothing; continuing without them.")
    intents.append(IntentType.GENERAL)


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

    # The miss notice has already been streamed to the user verbatim. Without
    # this the next branch opens by saying the same thing again in its own
    # words, so the user reads "I couldn't find it" twice before any answer.
    already_told = ""
    if reported_no_results(results.get("rag", "")):
        already_told = (
            "\nSTOP: the document-search notice above is ALREADY being delivered "
            "to the user as part of this same answer - it is handled, and it is "
            "not your job. Do NOT repeat it, reword it, apologise for it, or open "
            "by saying you lack access to their statements. Your FIRST sentence "
            "must already be answering the rest of their question. Say nothing "
            "about the documents at all.\n"
        )

    return (
        f"{chr(10).join(parts)}\n\n"
        f"User's Question: {query}\n"
        f"{already_told}\n"
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
- **A DOCUMENT SEARCH THAT FOUND NOTHING IS A FINDING, NOT A DISCLAIMER**: if the
  document agent reports that it searched and matched nothing, say so and keep its
  suggestions (check the file is uploaded, ask more specifically). That is the
  honest answer for the part of the question it covers. The rule above about
  dropping "cannot access" disclaimers does NOT apply to it - that rule is for an
  agent wrongly claiming it has no access, not for a search that genuinely missed.
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
            num_retries=3,
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
    """Synthesis, generated whole and then replayed to the client in pieces.

    We do NOT stream from the model. Measured from here, roughly one streaming
    call in three has its SSE connection killed mid-response - httpx raises
    ReadError - and litellm swallows that and ends the iterator with
    finish_reason "stop". A reply cut off mid-word is therefore indistinguishable
    from a finished one, and no amount of retrying helps because nothing below us
    reports a failure.

    A single request/response does not hide anything: a dropped connection
    raises, so litellm's own num_retries and the loop below both work. The text
    is then chunked out so the client still renders progressively. The cost is
    latency to first token - the whole answer has to exist first - which the
    status events before this cover.
    """

    prompt = _build_synthesis_prompt(query, results, history, user_directives)

    for attempt in range(MAX_STREAM_ATTEMPTS):
        try:
            response = await acompletion(
                num_retries=3,
                model="gemini/gemini-2.5-flash",
                messages=[{"role": "user", "content": prompt}],
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("model returned an empty response")

            # Nothing reached the client until now, so a failed attempt above
            # needs no "reset" - there is never half an answer on screen.
            for i in range(0, len(text), REPLAY_CHUNK_CHARS):
                yield {"type": "token", "content": text[i : i + REPLAY_CHUNK_CHARS]}
                await asyncio.sleep(0)  # Force buffer flush
            return

        except Exception as e:
            reason = f"{type(e).__name__}: {e}"

        print(f"[Synthesis] attempt {attempt + 1} failed - {reason}")

        if attempt + 1 < MAX_STREAM_ATTEMPTS:
            await asyncio.sleep(SYNTHESIS_BACKOFF_SECONDS * (2**attempt))
            continue

        # Every attempt failed, but the branch findings are still in hand -
        # returning them unpolished beats losing the work to an error banner.
        salvaged = "\n\n".join(text for text in results.values() if text)
        if salvaged:
            yield {"type": "token", "content": salvaged}
            return

        yield {
            "type": "error",
            "content": (
                "The response was cut off before it finished. This is usually a "
                "dropped connection to the model - please try again."
            ),
        }


async def orchestrate(
    query: str,
    intents: List[IntentType],
    user_id: str = "fallback-user-id",
    history: str = "",
    session_id: str = "default",
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
            result, rag_footer = await perform_rag_search(
                query,
                user_id=user_id,
                session_id=session_id,
                history=history,
                return_footer=True,
            )
            context["results"]["rag"] = result
            context["footer"] = rag_footer
            _continue_without_documents(result, intents)

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

    # Mirrors should_direct_stream in orchestrate_stream: a lone branch already
    # produced a chat-ready answer, so synthesising it only costs a model call
    # and a rewording. A RAG miss lands here with two results, not one.
    if len(context["results"]) == 1:
        return next(iter(context["results"].values())) + context.get("footer", "")

    final_response = await synthesize_response(
        query, context["results"], history=history, user_directives=""  # Non-stream path - directives not fetched
    )
    # After synthesis, never before: the synthesiser rewrites what it is given
    # and drops a coverage line every time.
    return final_response + context.get("footer", "")


async def orchestrate_stream(
    query: str,
    intents: List[IntentType],
    user_id: str = "fallback-user-id",
    history: str = "",
    session_id: str = "default",
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
                async for chunk in perform_rag_search_stream(
                    query, user_id=user_id, session_id=session_id, history=history
                ):
                    if chunk["type"] == "status":
                        yield chunk
                    elif chunk["type"] == "error":
                        # A failed branch ends the turn. Continuing would let a
                        # half-finished search be synthesised into a confident answer.
                        yield chunk
                        return
                    elif chunk["type"] == "footer":
                        # Held back, not streamed with the body. On a
                        # synthesised turn it must land after the synthesiser
                        # has finished, or it gets rewritten away.
                        context["footer"] = chunk["content"]
                    elif chunk["type"] == "token":
                        full_rag_response.append(chunk["content"])
                        if should_direct_stream:  # RAG is answering directly
                            yield chunk

                rag_text = "".join(full_rag_response)
                context["results"]["rag"] = rag_text
                _continue_without_documents(rag_text, intents)

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
                    elif chunk["type"] == "error":
                        yield chunk
                        return
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
                    elif chunk["type"] == "error":
                        yield chunk
                        return
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
                    elif chunk["type"] == "error":
                        yield chunk
                        return
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

        # Last, on both paths: what the document search actually covered. It is
        # a fact about the search, not prose for a model to reword.
        if context.get("footer"):
            yield {"type": "token", "content": context["footer"]}

    except GeneratorExit:
        # Handle disconnection/cancellation
        print("Orchestrator stream cancelled by client.")
        raise
    except Exception as e:
        yield {"type": "error", "content": f"Orchestration failed: {e}"}
