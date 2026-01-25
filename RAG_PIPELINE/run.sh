#!/bin/bash

# 1. Install Dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# 2. Start (Local) Vector DB
echo "Using Local ChromaDB (in-process)..."

# 3. Start FastAPI
echo "Starting FastAPI..."
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
