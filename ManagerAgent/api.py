from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from agents import Runner
import asyncio
import time
from datetime import datetime, timedelta

# Import ManagerAgent instead of CalcAgent
# Import ManagerAgent instead of CalcAgent
from ManagerAgent.router import manager_agent
from fastapi import Depends
from Auth.dependencies import get_current_user

app = FastAPI(title="Financial Calculation Agent API")

# --- Security & Precautions ---

# 1. CORS: Allow access from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate Limiting (Simple In-Memory)
# Map IP -> [timestamp1, timestamp2, ...]
RATE_LIMIT_STORE = {}
RATE_LIMIT_WINDOW = 60 # seconds
MAX_REQUESTS_PER_WINDOW = 10 

def check_rate_limit(client_ip: str):
    now = datetime.now()
    if client_ip not in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = []
    
    # Filter out old requests
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    RATE_LIMIT_STORE[client_ip] = [t for t in RATE_LIMIT_STORE[client_ip] if t > window_start]
    
    if len(RATE_LIMIT_STORE[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    
    RATE_LIMIT_STORE[client_ip].append(now)

import sqlite3
import json

# --- Database Setup ---
DB_PATH = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB immediately
init_db()

def get_chat_history(session_id: str, limit: int = 10) -> str:
    """Retrieve recent chat history for a session formatted as text."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM chat_history 
        WHERE session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse to chronological order
    history = rows[::-1]
    formatted_history = "\n".join([f"{role}: {content}" for role, content in history])
    return formatted_history

def save_chat_entry(session_id: str, role: str, content: str):
    """Save a single chat entry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)", 
                   (session_id, role, content))
    conn.commit()
    conn.close()

# --- Data Models ---

class AgentRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"  # Default session if none provided
    
class AgentResponse(BaseModel):
    final_output: str
    status: str = "success"

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ManagerAgent"}

@app.post("/v1/agent/calculate", response_model=AgentResponse)
async def calculate(request: Request, body: AgentRequest, user: dict = Depends(get_current_user)):
    """
    Run the Manager Agent on a user query.
    Protected by rate limiting, timeouts, and Authentication.
    """
    # 0. Authenticate User (Dependency Injection)
    # The 'user' variable now holds the decoded JWT payload
    # user_id = user.get("sub") 
    
    # 1. Check Rate Limit
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)
    
    # 2. Input Sanity Check
    if len(body.query) > 1000:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 chars)")

    try:
        # 3. Retrieve History
        history = get_chat_history(body.session_id)
        
        # --- HARD BYPASS FOR STOCK QUERIES ---
        # User requested absolutely NO manager interference for stock data.
        # We detect intent manually and call the tool directly.
        lower_query = body.query.lower()
        stock_keywords = ["stock", "price", "buy", "sell", "compare", "analyze", "market", "nvda", "aapl", "tsla", "amd", "meta", "googl", "amzn", "msft"]
        
        if any(kw in lower_query for kw in stock_keywords) and len(lower_query.split()) < 20:
             print(f"Bypassing Manager Agent for stock query: {body.query}")
             from ManagerAgent.tools import ask_stock_analyst
             # Call tool directly
             final_output = await ask_stock_analyst(body.query)
        else:
            # 4. Construct Contextual Query
            # We assume the Agent isn't natively stateful here, so we inject history.
            if history:
                full_query = f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
            else:
                full_query = body.query

            # 5. Execution with Timeout (30s)
            # Prevent runaway agent loops
            result = await asyncio.wait_for(
                Runner.run(manager_agent, full_query),
                timeout=30.0
            )
            final_output = result.final_output
        
        # 6. Save Interaction to History
        save_chat_entry(body.session_id, "User", body.query)
        save_chat_entry(body.session_id, "Agent", final_output)
        
        return AgentResponse(
            final_output=final_output,
            status="success"
        )
    except asyncio.TimeoutError:
        print(f"Timeout executing query: {body.query}")
        raise HTTPException(status_code=504, detail="Agent execution timed out (complexity limit)")
    except Exception as e:
        print(f"Error executing agent: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

from fastapi import UploadFile, File
import shutil
import os

@app.post("/v1/agent/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """
    Upload and ingest a PDF document into the RAG system.
    """
    # 1. Validate File Type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")

    # 2. Save to Temp
    upload_dir = "ManagerAgent/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Process with Ingestion Pipeline
        from RAG_PIPELINE.src.ingestion import process_pdf
        
        result = await process_pdf(file_path)
        
        # 4. Clean up (Optional - maybe keep for debug?)
        # os.remove(file_path) 
        
        return {"status": "success", "message": result, "filename": file.filename}
        
    except Exception as e:
        print(f"Upload failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.get("/v1/agent/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    """
    List all uploaded documents.
    """
    upload_dir = "ManagerAgent/uploads"
    try:
        if not os.path.exists(upload_dir):
            return {"documents": []}
            
        files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
        # Sort by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(upload_dir, x)), reverse=True)
        return {"documents": files}
    except Exception as e:
        print(f"Error listing documents: {e}")
        return {"documents": []}

@app.get("/v1/agent/stock/{ticker}")
async def get_stock_data(ticker: str, user: dict = Depends(get_current_user)):
    """
    Get real-time stock quote and price history for a ticker.
    Returns data formatted for frontend charting.
    """
    try:
        # Import FinnhubClient
        from StockAgents.backend.services.finnhub_client import finnhub_client
        
        # Fetch quote and candles in parallel
        quote = await finnhub_client.get_quote(ticker.upper())
        candles = await finnhub_client.get_candles(ticker.upper())
        
        # Format candles for recharts
        chart_data = []
        if candles.get("s") == "ok" and candles.get("c") and candles.get("t"):
            for i, (price, timestamp) in enumerate(zip(candles["c"], candles["t"])):
                # Convert timestamp to readable time
                from datetime import datetime
                time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")
                chart_data.append({
                    "time": time_str,
                    "value": round(price, 2)
                })
        
        return {
            "ticker": ticker.upper(),
            "currentPrice": quote.get("c", 0),
            "change": quote.get("d", 0),
            "changePercent": quote.get("dp", 0),
            "high": quote.get("h", 0),
            "low": quote.get("l", 0),
            "open": quote.get("o", 0),
            "previousClose": quote.get("pc", 0),
            "candles": chart_data
        }
    except Exception as e:
        print(f"Error fetching stock data for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch stock data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
