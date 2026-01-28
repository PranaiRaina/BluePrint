from enum import Enum
from pydantic import BaseModel, Field
from litellm import completion
from dotenv import load_dotenv
from typing import List

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


ROUTER_SYSTEM_PROMPT = """You are a Multi-Intent Classifier for a Financial AI.
Your job is to identify ALL applicable intents in a user query and order them for execution.

## INTENT TYPES:
1. **STOCK**: Real-time market data, price checks, stock analysis, buy/sell recommendations.
   - Keywords: "price", "buy", "sell", "analyze", "NVDA", "AAPL", ticker symbols.
   - Use when user wants EXTERNAL market data or stock analysis.

2. **RAG**: Questions about the user's UPLOADED documents or personal data.
   - Keywords: "my document", "my portfolio", "how many stocks do I have", "my file".
   - Use when user references their personal/uploaded information.

3. **CALCULATOR**: Math calculations, tax computations, mortgage, projections.
   - Keywords: "calculate", "tax", "mortgage", "future value", "how much would".

4. **GENERAL**: Greetings, general questions, or unclear intent.

## RULES:
- Return ALL applicable intents in EXECUTION ORDER.
- Execution order: RAG (get user data) → STOCK (analyze) → CALCULATOR (compute)
- If only one intent applies, return a single-item list.
- Set primary_intent to the MAIN goal of the query.

## EXAMPLES:

Query: "What is the price of Apple?"
→ intents: ["stock"], primary_intent: "stock"
→ Reason: Only needs stock data.

Query: "How many Apple stocks do I have?"
→ intents: ["rag"], primary_intent: "rag"
→ Reason: Only needs user's document data.

Query: "How many Apple stocks do I have and should I buy more?"
→ intents: ["rag", "stock"], primary_intent: "stock"
→ Reason: First get holdings from documents, then analyze stock for recommendation.

Query: "What's my portfolio value and calculate 15% taxes on gains?"
→ intents: ["rag", "calculator"], primary_intent: "calculator"
→ Reason: Get portfolio from documents, then calculate taxes.

Query: "What's NVDA trading at and how much would 50 shares cost?"
→ intents: ["stock", "calculator"], primary_intent: "calculator"
→ Reason: Get stock price, then calculate total cost.

Query: "Hello"
→ intents: ["general"], primary_intent: "general"
→ Reason: Simple greeting.
"""


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
