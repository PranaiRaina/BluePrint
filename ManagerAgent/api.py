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
        
        # 6. Save Interaction to History
        save_chat_entry(body.session_id, "User", body.query)
        save_chat_entry(body.session_id, "Agent", result.final_output)
        
        return AgentResponse(
            final_output=result.final_output,
            status="success"
        )
    except asyncio.TimeoutError:
        print(f"Timeout executing query: {body.query}")
        raise HTTPException(status_code=504, detail="Agent execution timed out (complexity limit)")
    except Exception as e:
        print(f"Error executing agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
