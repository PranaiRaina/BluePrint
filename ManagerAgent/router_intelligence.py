from enum import Enum
from pydantic import BaseModel, Field
from litellm import completion
from dotenv import load_dotenv
from typing import List
from ManagerAgent.prompts import ROUTER_SYSTEM_PROMPT

load_dotenv()


# Intent Categories
class IntentType(str, Enum):
    STOCK = "stock"
    RAG = "rag"
    CALCULATOR = "calculator"
    GENERAL = "general"


class RouterDecision(BaseModel):
    intents: List[IntentType] = Field(
        ..., description="List of applicable intents in execution order."
    )
    primary_intent: IntentType = Field(
        ..., description="The main intent if only one agent is needed."
    )
    extracted_tickers: List[str] = Field(
        default=[],
        description="List of stock tickers (e.g., AAPL, TSLA) explicitly mentioned or inferred from company names. Empty if none.",
    )
    reasoning: str = Field(
        ..., description="Brief explanation of why these intents were chosen."
    )


async def classify_intent(query: str) -> RouterDecision:
    """
    Uses a fast LLM to semantically classify the user's intent(s).
    Returns a list of intents in execution order.
    """
    try:
        response = completion(
            model="gemini/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            response_format=RouterDecision,
        )

        # Parse the structured output
        content = response.choices[0].message.content
        decision = RouterDecision.model_validate_json(content)
        return decision

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Router Error: {e}. Defaulting to GENERAL.")
        return RouterDecision(
            intents=[IntentType.GENERAL],
            primary_intent=IntentType.GENERAL,
            reasoning="Error in classification",
        )
