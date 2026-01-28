# Base Image: Lightweight Python 3.12
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# - curl for healthchecks
# - build-essential for compiling some python extensions if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml requirements.txt requirements.lock ./

# Install dependencies via uv (system-wide)
RUN uv pip install --system -r requirements.lock

# Download Spacy model (for PII redaction if RAG pipeline uses this container)
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Expose ports
# 8001: CalcAgent API
EXPOSE 8001

# Environment variables
ENV PYTHONUNBUFFERED=1

# Default command: Run the CalcAgent API
# Can be overridden to run RAG pipeline
CMD ["uvicorn", "ManagerAgent.api:app", "--host", "0.0.0.0", "--port", "8001"]
