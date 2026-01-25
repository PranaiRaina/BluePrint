"""Configuration for CalcAgent - Groq + Wolfram Alpha setup."""

import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

# Load environment variables
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")

# Wolfram Alpha LLM API endpoint
WOLFRAM_API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Configure Groq client
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# Disable tracing (we don't have an OpenAI API key)
set_tracing_disabled(True)

# Model configuration - Using OpenAIChatCompletionsModel to preserve model name
# This is required because the SDK strips prefixes like "openai/" when using string model names
MODEL = OpenAIChatCompletionsModel(
    model="openai/gpt-oss-120b",
    openai_client=groq_client,
)