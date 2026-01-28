import os
import shutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from agents import Runner
from CalcAgent.src.utils import run_with_retry
import asyncio
import time
from datetime import datetime, timedelta

# Import GeneralAgent for fallback
from CalcAgent.src.agent import financial_agent, general_agent
from fastapi import Depends
from Auth.dependencies import get_current_user
from ManagerAgent.router_intelligence import classify_intent, IntentType
from ManagerAgent.tools import ask_stock_analyst, perform_rag_search
from ManagerAgent.orchestrator import orchestrate
from supabase import create_client, Client


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

# Initialize Supabase client for storage
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_JWT_SECRET"))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user_id column exists, if not, add it (Migration)
    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if not columns:
        cursor.execute("""
            CREATE TABLE chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    elif "user_id" not in columns:
        print("  → Migrating DB: Adding user_id column")
        cursor.execute("ALTER TABLE chat_history ADD COLUMN user_id TEXT NOT NULL DEFAULT 'fallback-user-id'")
        
    conn.commit()
    conn.close()

# Initialize DB immediately
init_db()

def get_chat_history(user_id: str, session_id: str, limit: int = 10) -> str:
    """Retrieve recent chat history for a session formatted as text, scoped by user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM chat_history 
        WHERE user_id = ? AND session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (user_id, session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse to chronological order
    history = rows[::-1]
    formatted_history = "\n".join([f"{role}: {content}" for role, content in history])
    return formatted_history

def get_chat_history_json(user_id: str, session_id: str, limit: int = 50) -> List[dict]:
    """Retrieve recent chat history for a session formatted as JSON list, scoped by user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM chat_history 
        WHERE user_id = ? AND session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (user_id, session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse to chronological order (Oldest -> Newest)
    history = rows[::-1]
    
    # Map backend roles to frontend roles
    formatted_history = []
    for role, content in history:
        frontend_role = "user" if role == "User" else "ai"
        formatted_history.append({"role": frontend_role, "content": content})
        
    return formatted_history

def save_chat_entry(user_id: str, session_id: str, role: str, content: str):
    """Save a single chat entry scoped by user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_id, session_id, role, content) VALUES (?, ?, ?, ?)", 
                   (user_id, session_id, role, content))
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
    try:
        # 0. Authenticate User (Dependency Injection)
        user_id = user.get("sub", "fallback-user-id")
        
        # 3. Retrieve History
        history = get_chat_history(user_id, body.session_id)
        
        # --- MULTI-INTENT ROUTING ---
        
        # 1. Analyze Intent(s)
        decision = await classify_intent(body.query)
        print(f"Router Decision: {decision.intents} | Primary: {decision.primary_intent} | Reason: {decision.reasoning}")

        # 2. Route based on Intent(s)
        if len(decision.intents) > 1:
            # Multi-intent query - use orchestrator
            print(f"Multi-Intent Detected: {[i.value for i in decision.intents]}")
            final_output = await asyncio.wait_for(
                orchestrate(body.query, decision.intents, user_id=user_id, history=history),
                timeout=60.0  # Longer timeout for multi-step
            )
        
        elif decision.primary_intent == IntentType.STOCK:
             print(f"Routing to Stock Analyst: {body.query}")
             final_output = await ask_stock_analyst(body.query)
        
        elif decision.primary_intent == IntentType.RAG:
             print(f"Routing to RAG Search: {body.query}")
             final_output = await perform_rag_search(body.query, user_id=user_id)

        elif decision.primary_intent == IntentType.CALCULATOR:
             print(f"Routing to Financial Calculator (Direct): {body.query}")
             
             # Construct Contextual Query for Financial Agent
             if history:
                full_query = f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
             else:
                full_query = body.query

             # Direct routing to Financial Agent
             result = await asyncio.wait_for(
                 run_with_retry(financial_agent, full_query),
                 timeout=30.0
             )
             final_output = result.final_output
             
        else:
             # GENERAL -> Send to General Agent for conversation
             print(f"Routing to General Agent: {body.query}")
             
             # Construct Contextual Query for General Agent
             if history:
                full_query = f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
             else:
                full_query = body.query

             # Execution with Timeout (30s)
             result = await asyncio.wait_for(
                 run_with_retry(general_agent, full_query),
                 timeout=30.0
             )
             final_output = result.final_output
        
        # 6. Save Interaction to History
        save_chat_entry(user_id, body.session_id, "User", body.query)
        save_chat_entry(user_id, body.session_id, "Agent", final_output)
        
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
    Upload and ingest a PDF document into Supabase Storage and RAG system.
    """
    user_id = user.get("sub", "fallback-user-id")
    
    # 1. Validate File Type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")

    # 2. Upload to Supabase Storage
    # Path: {user_id}/{filename}
    try:
        file_content = await file.read()
        storage_path = f"{user_id}/{file.filename}"
        
        # Check if bucket exists/create logic is handled in Dashboard, 
        # but here we just upload to 'rag-documents' bucket
        res = supabase.storage.from_("rag-documents").upload(
            path=storage_path,
            file=file_content,
            file_options={"upsert": "true"}
        )
        
        # 3. Process with Ingestion Pipeline for RAG
        # Note: process_pdf currently expects a local path. 
        # Refactoring ingestion.py to accept user_id and content/path.
        from RAG_PIPELINE.src.ingestion import process_pdf_scoped
        
        result = await process_pdf_scoped(file.filename, file_content, user_id)
        
        return {"status": "success", "message": result, "filename": file.filename}
        
    except Exception as e:
        print(f"Upload failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload/Ingestion failed: {str(e)}")

@app.delete("/v1/agent/documents/{filename}")
async def delete_document(filename: str, user: dict = Depends(get_current_user)):
    """
    Delete a document from both Supabase Storage and vector database.
    """
    user_id = user.get("sub", "fallback-user-id")
    storage_path = f"{user_id}/{filename}"

    try:
        # 1. Delete from Vector DB
        from RAG_PIPELINE.src.ingestion import delete_document_vectors_scoped
        await delete_document_vectors_scoped(filename, user_id)

        # 2. Delete from Supabase Storage
        supabase.storage.from_("rag-documents").remove([storage_path])
                 
        return {"status": "success", "message": f"Deleted {filename}"}

    except Exception as e:
        print(f"Deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.get("/v1/agent/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    """
    List all uploaded documents from Supabase Storage.
    """
    user_id = user.get("sub", "fallback-user-id")
    try:
        # List files in the user's specific folder in the bucket
        res = supabase.storage.from_("rag-documents").list(path=user_id)
        
        # Supabase returns a list of file info objects
        files = [f['name'] for f in res if f['name'].endswith('.pdf')]
        
        return {"documents": files}
    except Exception as e:
        print(f"Error listing documents: {e}")
        return {"documents": []}

@app.get("/v1/agent/history")
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    """
    Get chat history for a specific session.
    """
    user_id = user.get("sub", "fallback-user-id")
    return get_chat_history_json(user_id, session_id)
@app.get("/v1/agent/stock/{ticker}")
async def get_stock_data(ticker: str, time_range: str = "3m", user: dict = Depends(get_current_user)):
    """
    Get real-time stock quote and price history for a ticker.
    Returns data formatted for frontend charting.
    """
    try:
        # Import FinnhubClient
        from StockAgents.services.finnhub_client import finnhub_client
        
        # Fetch quote and candles in parallel
        quote = await finnhub_client.get_quote(ticker.upper())
        candles = await finnhub_client.get_candles(ticker.upper(), time_range=time_range)
        
        # Format candles for recharts
        chart_data = []
        if candles.get("s") == "ok" and candles.get("c"):
            c = candles.get("c", [])
            t = candles.get("t", [])
            o = candles.get("o", [0] * len(c)) # Fallback if missing
            h = candles.get("h", [0] * len(c))
            l = candles.get("l", [0] * len(c))
            
            for i in range(len(c)):
                price = c[i]
                timestamp = t[i]
                
                # Convert timestamp to readable date/time
                # For intraday (1d, 1w), show Time. For daily (1m+), show Date.
                from datetime import datetime, timezone
                
                if time_range == "1d":
                     # Intraday 1D: Show Time only
                     time_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%H:%M")
                elif time_range == "1w":
                     # Intraday 1W: Show Date + Time so frontend can detect day changes
                     time_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%b %d %H:%M")
                else:
                     # Daily: Show Date (UTC midnight)
                     time_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%b %d")
                
                chart_data.append({
                    "time": time_str,
                    "value": round(price, 2),
                    "open": round(o[i], 2),
                    "high": round(h[i], 2),
                    "low": round(l[i], 2),
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
