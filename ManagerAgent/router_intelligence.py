from enum import Enum
from pydantic import BaseModel, Field
from litellm import completion
from dotenv import load_dotenv
from typing import List

ROUTER_SYSTEM_PROMPT = """You are a Semantic Intent Classifier for a Financial AI.
Your job is to route user queries to the correct specialized agent.

## CLASSES:
1. **STOCK**: Creating real-time market data, price checks, or ticker analysis.
   - Keywords: "price", "buy", "sell", "dividend", "market cap", "NVDA", "AAPL".
   - CRITICAL: Only use this if the user wants EXTERNAL market data.

2. **RAG**: Questions about the user's UPLOADED documents, context, or files.
   - Keywords: "my pdf", "uploaded file", "this report", "what does the doc say", "revenue in the file", "summarize my document", "analyze my doc".
   - CRITICAL: If the user mentions a specific company (e.g. "Apple") but asks about "the document" or "my file", this is RAG, NOT STOCK.
   - CRITICAL: Any request to "summarize" or "analyze" "my files" or "the document" MUST be RAG.

3. **CALCULATOR**: requests for math, tax calculations, mortgages, or projections.
   - Keywords: "calculate", "tax", "mortgage", "future value", "401k".

4. **GENERAL**: Greetings, general questions, or unclear intent.

## EXAMPLES:
- "What is the price of Apple?" -> STOCK
- "What does the uploaded PDF say about Apple's debt?" -> RAG
- "Calculate the tax on $50k" -> CALCULATOR
- "Hello" -> GENERAL
"""

load_dotenv()


# Intent Categories
class IntentType(str, Enum):
    STOCK = "stock"
    RAG = "rag"
    CALCULATOR = "calculator"
    GENERAL = "general"


class RouterDecision(BaseModel):
    intents: List[IntentType] = Field(..., description="List of applicable intents in execution order.")
    primary_intent: IntentType = Field(..., description="The main intent if only one agent is needed.")
    reasoning: str = Field(..., description="Brief explanation of why these intents were chosen.")





async def classify_intent(query: str) -> RouterDecision:
    """
    Uses a fast LLM to semantically classify the user's intent(s).
    Returns a list of intents in execution order.
    """
    try:
        response = completion(
            model="gemini/gemini-2.0-flash",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            response_format=RouterDecision
        )
        
        # Parse the structured output
        content = response.choices[0].message.content
        decision = RouterDecision.model_validate_json(content)
        return decision
        
    except Exception as e:
        print(f"Router Error: {e}. Defaulting to GENERAL.")
        return RouterDecision(
            intents=[IntentType.GENERAL],
            primary_intent=IntentType.GENERAL,
            reasoning="Error in classification"
        )
