"""Configuration for CalcAgent - Groq + Wolfram Alpha setup."""

import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

# Load environment variables
load_dotenv()

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")

# Wolfram Alpha LLM API endpoint
WOLFRAM_API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Configure Gemini client (OpenAI Compatible)
# Docs: https://ai.google.dev/gemini-api/docs/openai
groq_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=GOOGLE_API_KEY,
)

# Disable tracing (we don't have an OpenAI API key)
set_tracing_disabled(True)

# Model configuration
# We use OpenAIChatCompletionsModel to pass the specific Gemini model name cleanly
MODEL = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=groq_client,
)