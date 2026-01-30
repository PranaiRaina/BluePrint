"""
Multi-Intent Orchestrator

Executes multiple intents in sequence, passing context between them,
and synthesizes a final coherent response.
"""

from typing import List, Dict, Any
from litellm import acompletion
from ManagerAgent.router_intelligence import IntentType
from ManagerAgent.tools import perform_rag_search, ask_stock_analyst
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


def enrich_query_with_context(query: str, context: Dict[str, Any]) -> str:
    """Enrich the query with results from previous intent executions."""
    if not context.get("results"):
        return query

    context_parts = []

    if "rag" in context["results"]:
        context_parts.append(f"USER'S CURRENT HOLDINGS:\n{context['results']['rag']}")

    if "stock" in context["results"]:
        context_parts.append(f"Stock Analysis: {context['results']['stock']}")

    if not context_parts:
        return query

    return f"{chr(10).join(context_parts)}\n\nUser's Question: {query}\n\nIMPORTANT: Consider the user's current holdings when making recommendations."


async def synthesize_response(
    query: str, results: Dict[str, str], history: str = ""
) -> str:
    """Use LLM to combine multiple agent results into one coherent response with chat history context."""

    if len(results) == 1 and not history:
        return list(results.values())[0]

    results_text = "\n\n".join(
        [
            f"--- {intent.upper()} RESULT ---\n{result}"
            for intent, result in results.items()
            if result
        ]
    )

    prompt = f"""You are a Master Financial Orchestrator. 
Your goal is to synthesize the following agent findings into a cohesive, professional, and helpful response for the user.

CHAT HISTORY (for context):
{history}

USER QUERY: {query}

AGENT FINDINGS:
{results_text}

INSTRUCTIONS:
- Integrate the findings logically.
- If RAG documents (User's Portfolio) were searched, prioritize that data for "do I own" questions.
- Maintain a helpful, analytical tone.
- Do not repeat yourself.
- Ensure the final output is formatted in clean Markdown.
"""

    try:
        response = await acompletion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"{results_text}\n\n(Synthesis failed: {str(e)})"


async def synthesize_response_stream(
    query: str, results: Dict[str, str], history: str = ""
):
    """Streamed synthesis."""

    results_text = "\n\n".join(
        [
            f"--- {intent.upper()} RESULT ---\n{result}"
            for intent, result in results.items()
            if result
        ]
    )

    prompt = f"""You are a Master Financial Orchestrator. 
Your goal is to synthesize the following agent findings into a cohesive, professional, and helpful response for the user.

CHAT HISTORY (for context):
{history}

USER QUERY: {query}

AGENT FINDINGS:
{results_text}

INSTRUCTIONS:
- Integrate the findings logically.
- If RAG documents (User's Portfolio) were searched, prioritize that data for "do I own" questions.
- Maintain a helpful, analytical tone.
- Do not repeat yourself.
- Ensure the final output is formatted in clean Markdown.
"""
    try:
        stream = await acompletion(
            model="gemini/gemini-2.0-flash",
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
            result = await perform_rag_search(query, user_id=user_id)
            context["results"]["rag"] = result

        elif intent == IntentType.STOCK:
            enriched_query = enrich_query_with_context(query, context)
            if history:
                enriched_query = f"Conversation History:\n{history}\n\n{enriched_query}"
            result = await ask_stock_analyst(enriched_query)
            context["results"]["stock"] = result

        elif intent == IntentType.CALCULATOR:
            enriched_query = f"History context: {history}\n\nUser Query: {query}"
            result = await asyncio.wait_for(
                run_with_retry(financial_agent, enriched_query), timeout=90.0
            )
            context["results"]["calculator"] = result.final_output

        elif intent == IntentType.GENERAL:
            enriched_query = f"Chat History:\n{history}\n\nUser Query: {query}"
            result = await run_with_retry(general_agent, enriched_query)
            context["results"]["general"] = result.final_output

    final_response = await synthesize_response(
        query, context["results"], history=history
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
    """
    context = {"query": query, "results": {}}

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
                async for chunk in perform_rag_search_stream(query, user_id=user_id):
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
                    elif chunk["type"] == "token":
                        full_stock_response.append(chunk["content"])
                        if should_direct_stream:
                            yield chunk

                context["results"]["stock"] = "".join(full_stock_response)

            elif intent == IntentType.CALCULATOR:
                yield {"type": "status", "content": "Calculating..."}

                enriched_query = f"History context: {history}\n\nUser Query: {query}"

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

                enriched_query = f"Chat History:\n{history}\n\nUser Query: {query}"

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
                query, context["results"], history=history
            ):
                yield chunk

    except GeneratorExit:
        # Handle disconnection/cancellation
        print("Orchestrator stream cancelled by client.")
        raise
    except Exception as e:
        yield {"type": "token", "content": f"\n\n(Orchestrator Error: {e})"}
