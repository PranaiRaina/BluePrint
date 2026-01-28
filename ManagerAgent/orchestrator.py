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
from ManagerAgent.prompts import ORCHESTRATOR_SYNTHESIS_PROMPT
import os


def has_uploaded_documents() -> bool:
    """Check if user has any uploaded documents."""
    upload_dir = "ManagerAgent/uploads"
    if not os.path.exists(upload_dir):
        return False
    files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
    return len(files) > 0


async def run_calculator(query: str, context: Dict[str, Any] = None) -> str:
    """Run the financial calculator agent with optional context."""
    try:
        if context and context.get("results"):
            context_str = "\n".join([
                f"{k.upper()}: {v}" 
                for k, v in context["results"].items() 
                if v
            ])
            enriched_query = f"Context from previous analysis:\n{context_str}\n\nUser Query: {query}"
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


async def synthesize_response(query: str, results: Dict[str, str], history: str = "") -> str:
    """Use LLM to combine multiple agent results into one coherent response with chat history context."""
    
    if len(results) == 1 and not history:
        return list(results.values())[0]
    
    results_text = "\n\n".join([
        f"--- {intent.upper()} RESULT ---\n{result}"
        for intent, result in results.items()
        if result
    ])
    
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
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"{results_text}\n\n(Synthesis failed: {str(e)})"


async def orchestrate(query: str, intents: List[IntentType], user_id: str = "fallback-user-id", history: str = "") -> str:
    """
    Execute multiple intents in order, passing context between them,
    and synthesize a final response. Scoped by user_id and aware of chat history.
    """
    context = {"query": query, "results": {}}
    
    # Execution Order: RAG -> STOCK -> CALCULATOR -> GENERAL
    ORDER_PRIORITY = {
        IntentType.RAG: 0,
        IntentType.STOCK: 1,
        IntentType.CALCULATOR: 2,
        IntentType.GENERAL: 3
    }
    intents.sort(key=lambda x: ORDER_PRIORITY.get(x, 99))

    print(f"Orchestrator: Executing {len(intents)} intents: {[i.value for i in intents]}")
    
    for intent in intents:
        print(f"  → Executing: {intent.value}")
        
        if intent == IntentType.RAG:
            result = await perform_rag_search(query, user_id=user_id)
            context["results"]["rag"] = result
            print(f"    RAG Result: {result[:100]}..." if len(result) > 100 else f"    RAG Result: {result}")
        
        elif intent == IntentType.STOCK:
            enriched_query = enrich_query_with_context(query, context)
            # Add history to enriched query
            if history:
                 enriched_query = f"Conversation History:\n{history}\n\n{enriched_query}"
            
            result = await ask_stock_analyst(enriched_query)
            context["results"]["stock"] = result
            print(f"    Stock Result: {result[:100]}..." if len(result) > 100 else f"    Stock Result: {result}")
        
        elif intent == IntentType.CALCULATOR:
            # Construct enriched context for calculator
            calc_context = {"results": context["results"]}
            result = await run_calculator(f"History context: {history}\n\nUser Query: {query}", calc_context)
            context["results"]["calculator"] = result
            print(f"    Calculator Result: {result[:100]}..." if len(result) > 100 else f"    Calculator Result: {result}")
        
        elif intent == IntentType.GENERAL:
            # For general conversation, we use the general agent with full history
            enriched_query = f"Chat History:\n{history}\n\nUser Query: {query}"
            res = await run_with_retry(general_agent, enriched_query)
            context["results"]["general"] = res.final_output
            print(f"    General Result: {res.final_output[:100]}...")
    
    print("  \u2192 Synthesizing final response...")
    final_response = await synthesize_response(query, context["results"], history=history)
    
    return final_response
