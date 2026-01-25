"""Configuration for CalcAgent - Groq + Wolfram Alpha setup."""

import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api, set_tracing_disabled

# Load environment variables
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID")

# Wolfram Alpha LLM API endpoint
WOLFRAM_API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Configure OpenAI Agents SDK to use Groq
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# Set as default client for all agents
set_default_openai_client(groq_client)

# Use chat completions API (Groq doesn't support Responses API)
set_default_openai_api("chat_completions")

# Disable tracing (we don't have an OpenAI API key)
set_tracing_disabled(True)

# Model to use
MODEL = "llama-3.3-70b-versatile"
