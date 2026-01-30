from openai import AsyncOpenAI
from StockAgents.core.config import settings
import json
from StockAgents.core.prompts import (
    LLM_ANALYSIS_PROMPT,
    DATA_EXTRACTION_PROMPT,
    TICKER_RESOLVER_PROMPT,
    TICKER_EXTRACTOR_PROMPT,
)


class LLMService:
    def __init__(self):
        # Initialize Gemini client via OpenAI SDK
        self.client = AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.GOOGLE_API_KEY,
        )
        self.model = "gemini-2.0-flash"  # High performance model

    async def analyze_context(self, query: str, context_data: dict) -> str:
        """
        Sends the user query + stock/portfolio data context to Groq for analysis.
        """

        # Construct a system prompt that acts as a financial analyst
        system_prompt = LLM_ANALYSIS_PROMPT

        # Prepare the context (limit size if needed)
        context_str = json.dumps(context_data, indent=2)
        if len(context_str) > 10000:
            context_str = context_str[:10000] + "...(truncated)"

        user_message = (
            f"User Query: {query}\n\n"
            f"Market Data Context:\n{context_str}\n\n"
            "Analyze this data and provide a recommendation/insight."
        )

        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=self.model,
                temperature=0.5,
                max_tokens=500,
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"LLM Error: {e}")
            return "I'm having trouble connecting to my analytical engine right now. Please rely on the raw data."

    async def extract_structured_data(self, query: str) -> dict:
        """
        Uses LLM to extract structured JSON data from a natural language query.
        Target: Extract stock holdings like {"AAPL": 5000, "TSLA": 2000}.
        """
        system_prompt = DATA_EXTRACTION_PROMPT

        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                model=self.model,
                temperature=0.0,  # Deterministic for extraction
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"LLM Extraction Error: {e}")
            return {}

    async def resolve_ticker(self, query: str) -> str:
        """
        Extracts the primary stock ticker from a query, resolving company names if needed.
        Example: "Analyze Apple" -> "AAPL". "Stock for Tesla" -> "TSLA".
        Returns just the ticker string, or None.
        """
        system_prompt = TICKER_RESOLVER_PROMPT

        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                model=self.model,
                temperature=0.0,
                max_tokens=10,
            )
            content = completion.choices[0].message.content.strip()
            # Basic validation
            if content.isalpha() and len(content) <= 5:
                return content.upper()
            return None
        except Exception:
            return None

    async def extract_tickers_list(self, query: str) -> list[str]:
        """
        Extracts ALL stock tickers mentioned in a query, resolving company names.
        Example: "Compare Apple, Meta and NVDA" -> ["AAPL", "META", "NVDA"]
        """
        system_prompt = TICKER_EXTRACTOR_PROMPT

        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                model=self.model,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            # Expecting {"tickers": [...]} or just a list if possible?
            # OpenAI JSON mode ensures valid JSON. Let's ask for specific key in prompt or parse list directly.
            # Actually, standard JSON object requirement means we should ask for a key.
            # Let's refine prompt above slightly in next step or just handle parsing.
            # Wait, I can't refine prompt in "ReplacementContent" easily if I don't change the execution logic.
            # I'll rely on parsing.
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # Search values for a list
                for val in data.values():
                    if isinstance(val, list):
                        return [str(x).upper() for x in val]
            return []
        except Exception as e:
            print(f"LLM Ticker Extraction Error: {e}")
            return []


llm_service = LLMService()
