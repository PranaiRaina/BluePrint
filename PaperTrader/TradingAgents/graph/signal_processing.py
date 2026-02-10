# TradingAgents/graph/signal_processing.py

from langchain_openai import ChatOpenAI


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> dict:
        """
        Process a full trading signal to extract the core decision, quantity, and reasoning.
        """
        messages = [
            (
                "system",
                "You are an efficient assistant designed to analyze financial decisions. "
                "Extract the following from the text:\n"
                "1. Action: BUY, SELL, or HOLD\n"
                "2. Intent Amount: The number being discussed (e.g. 5000 for $5000 or 50 for 50 shares).\n"
                "3. Intent Unit: 'USD' if the amount is a dollar value, 'SHARES' if it's a specific share count.\n"
                "4. Reasoning: A concise 1-sentence explanation.\n\n"
                "Return ONLY a valid JSON object with keys 'action', 'intent_amount', 'intent_unit', 'reasoning'. "
            ),
            ("human", full_signal),
        ]

        try:
            response = self.quick_thinking_llm.invoke(messages)
            content = response.content.strip()
            
            # Robust JSON extraction: Find the first { and last }
            import re
            json_match = re.search(r"(\{.*\})", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            import json
            data = json.loads(content)
            
            # Normalize action
            if "action" in data:
                data["action"] = data["action"].upper()
                if data["action"] not in ["BUY", "SELL", "HOLD"]:
                    data["action"] = "HOLD"
            
            return data
        except Exception as e:
            print(f"Error parsing signal: {e}")
            # Try a very basic regex fallback for the action if JSON fails
            import re
            action_match = re.search(r"(BUY|SELL|HOLD)", full_signal.upper())
            action = action_match.group(1) if action_match else "HOLD"
            return {
                "action": action, 
                "intent_amount": 0,
                "intent_unit": "SHARES",
                "reasoning": f"Heuristic fallback: {action} detected in text."
            }
