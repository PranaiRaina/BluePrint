from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from agents import Runner
import asyncio
import time
from datetime import datetime, timedelta

# Import ManagerAgent instead of CalcAgent
from ManagerAgent.router import manager_agent

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

# --- Data Models ---

class AgentRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    
class AgentResponse(BaseModel):
    final_output: str
    status: str = "success"

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ManagerAgent"}

@app.post("/v1/agent/calculate", response_model=AgentResponse)
async def calculate(request: Request, body: AgentRequest):
    """
    Run the Manager Agent on a user query.
    Protected by rate limiting and timeouts.
    """
    # 1. Check Rate Limit
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)
    
    # 2. Input Sanity Check
    if len(body.query) > 1000:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 chars)")

    try:
        # 3. Execution with Timeout (30s)
        # Prevent runaway agent loops
        result = await asyncio.wait_for(
            Runner.run(manager_agent, body.query),
            timeout=30.0
        )
        
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
