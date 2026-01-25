from groq import Groq, AsyncGroq
from core.config import settings
import json

class LLMService:
    def __init__(self):
        # Initialize Groq client
        # It automatically looks for GROQ_API_KEY env var, but we can pass it explicitly if needed
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile" # High performance model

    async def analyze_context(self, query: str, context_data: dict) -> str:
        """
        Sends the user query + stock/portfolio data context to Groq for analysis.
        """
        
        # Construct a system prompt that acts as a financial analyst
        system_prompt = (
            "You are an advanced AI Financial Agent. Your goal is to provide concise, "
            "data-driven insights based on the provided market data. "
            "Format your response as a direct answer to the user. "
            "Do not provide financial advice (disclaimer), but provide technical and fundamental analysis based on the data. "
            "If the data is missing, state that clearly."
        )

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
                    {"role": "user", "content": user_message}
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
        system_prompt = (
            "You are a data extractor. Extract stock symbols and their corresponding monetary values "
            "or share counts from the user's query. "
            "Return ONLY a valid JSON object with the format: {'SYMBOL': amount}. "
            "If no currency is specified, assume USD value. "
            "If integers are small (<1000) and context suggests shares, you can treat as shares but prefer value. "
            "Example input: 'I have 5k in Apple and 2000 in Tesla' -> {'AAPL': 5000, 'TSLA': 2000}. "
            "If no data found, return empty json {}."
        )
        
        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model=self.model,
                temperature=0.0, # Deterministic for extraction
                response_format={"type": "json_object"}
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
        system_prompt = (
            "You are a Ticker Resolver. output ONLY the capital stock ticker symbols for the company mentioned. "
            "If the user mentions a company name, convert it to the most common US listing ticker. "
            "If multiple mentioned, return the first one. "
            "Example: 'Analyze Microsoft' -> 'MSFT'. "
            "Example: 'How is NVDA doing' -> 'NVDA'. "
            "Output ONLY the ticker string. No extra text."
        )
        
        try:
            completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model=self.model,
                temperature=0.0,
                max_tokens=10
            )
            content = completion.choices[0].message.content.strip()
            # Basic validation
            if content.isalpha() and len(content) <= 5:
                return content.upper()
            return None
        except Exception:
            return None

llm_service = LLMService()
