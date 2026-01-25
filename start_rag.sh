#!/bin/bash
echo "🚀 Starting RAG Pipeline..."

# 1. Install Dependencies (Fast with uv)
echo "📦 Installing/Syncing requirements..."
uv pip install -r requirements.txt

# 2. Ensure Spacy Model (Required for PII Redaction)
# We test if it is loadable, if not we download
echo "🧠 Checking Spacy model..."
uv run python -c "import spacy; spacy.load('en_core_web_lg')" 2>/dev/null || (echo "Downloading en_core_web_lg..." && uv run python -m spacy download en_core_web_lg)

# 3. Start FastAPI Server
echo "⚡ Starting Uvicorn Server on port 8080..."
# Runs the module RAG_PIPELINE.src.main
uv run uvicorn RAG_PIPELINE.src.main:app --reload --host 0.0.0.0 --port 8080
