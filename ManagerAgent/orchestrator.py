"""
Multi-Intent Orchestrator

Executes multiple intents in sequence, passing context between them,
and synthesizes a final coherent response.
"""

from typing import List, Dict, Any
from litellm import acompletion
from ManagerAgent.router_intelligence import IntentType
from ManagerAgent.tools import perform_rag_search, ask_stock_analyst
from CalcAgent.src.agent import financial_agent
from CalcAgent.src.utils import run_with_retry
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


async def synthesize_response(query: str, results: Dict[str, str]) -> str:
    """Use LLM to combine multiple agent results into one coherent, well-formatted response."""
    
    if len(results) == 1:
        return list(results.values())[0]
    
    results_text = "\n\n".join([
        f"--- {intent.upper()} RESULT ---\n{result}"
        for intent, result in results.items()
        if result
    ])
    
    prompt = f"""You are a helpful financial assistant. Combine these results into ONE well-formatted response.

User's Question: {query}

Results:
{results_text}

CRITICAL RULES:
1. Do NOT say "I am unable to provide advice" - you ARE providing analysis based on data
2. Include ALL details from the results - do not summarize or remove information
3. Reference the user's specific holdings when giving recommendations

SPACING REQUIREMENTS (VERY IMPORTANT):
- Add a BLANK LINE before each numbered section (1., 2., 3.)
- Add a BLANK LINE before "Data Sources:" 
- Add a BLANK LINE before the disclaimer
- Each major section should be separated by a blank line

Use **bold** for key metrics (prices, percentages, scores).
Keep the disclaimer in italics at the very end.
"""
    
    try:
        response = await acompletion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"{results_text}\n\n(Synthesis failed: {str(e)})"


async def orchestrate(query: str, intents: List[IntentType]) -> str:
    """
    Execute multiple intents in order, passing context between them,
    and synthesize a final response.
    """
    context = {"query": query, "results": {}}
    
    # Skip RAG if no documents uploaded
    if IntentType.RAG in intents and not has_uploaded_documents():
        print("  → Skipping RAG (no documents uploaded)")
        intents = [i for i in intents if i != IntentType.RAG]
        if not intents:
            return "I'd like to analyze your portfolio, but you haven't uploaded any documents yet. Please upload your financial statements first."
    
    print(f"Orchestrator: Executing {len(intents)} intents: {[i.value for i in intents]}")
    
    for intent in intents:
        print(f"  → Executing: {intent.value}")
        
        if intent == IntentType.RAG:
            result = await perform_rag_search(query)
            context["results"]["rag"] = result
            print(f"    RAG Result: {result[:100]}..." if len(result) > 100 else f"    RAG Result: {result}")
        
        elif intent == IntentType.STOCK:
            enriched_query = enrich_query_with_context(query, context)
            result = await ask_stock_analyst(enriched_query)
            context["results"]["stock"] = result
            print(f"    Stock Result: {result[:100]}..." if len(result) > 100 else f"    Stock Result: {result}")
        
        elif intent == IntentType.CALCULATOR:
            result = await run_calculator(query, context)
            context["results"]["calculator"] = result
            print(f"    Calculator Result: {result[:100]}..." if len(result) > 100 else f"    Calculator Result: {result}")
        
        elif intent == IntentType.GENERAL:
            context["results"]["general"] = "I'm here to help with your financial questions."
    
    print("  → Synthesizing final response...")
    final_response = await synthesize_response(query, context["results"])
    
    return final_response
