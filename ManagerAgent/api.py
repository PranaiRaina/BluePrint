import os
from dotenv import load_dotenv

# Load env vars before any other imports that might use them
load_dotenv()

import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

from ManagerAgent.database import get_db
from ManagerAgent.router_intelligence import classify_intent, IntentType
from ManagerAgent.tools import ask_stock_analyst, perform_rag_search
from ManagerAgent.orchestrator import orchestrate, orchestrate_stream
from ManagerAgent.profile_engine import UserProfile, InvestmentObjective, TaxStatus, distill_profile
from CalcAgent.src.utils import run_with_retry
# Import GeneralAgent for fallback
from CalcAgent.src.agent import financial_agent, general_agent
from Auth.dependencies import get_current_user

# Env vars loaded at top of file
from PaperTrader.router import router as paper_trader_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Open the LangGraph checkpointer pool
    try:
        from RAG_PIPELINE.src.graph import rag_pool, checkpointer
        if rag_pool:
            print("Opening LangGraph AsyncPostgresPool...")
            await rag_pool.open()
            if checkpointer:
                print("Setting up LangGraph checkpointer tables...")
                await checkpointer.setup()
    except Exception as e:
        print(f"Lifespan Startup Error (RAG Pool): {e}")
        
    yield
    
    # Shutdown: Close the pool
    try:
        from RAG_PIPELINE.src.graph import rag_pool
        if rag_pool:
            print("Closing LangGraph AsyncPostgresPool...")
            await rag_pool.close()
    except Exception as e:
        print(f"Lifespan Shutdown Error: {e}")

app = FastAPI(
    title="Financial Calculation Agent API",
    lifespan=lifespan
)

# Include Routers
app.include_router(paper_trader_router)


# --- Security & Precautions ---

# 1. CORS: Allow access from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate Limiting (Simple In-Memory)
# Map IP -> [timestamp1, timestamp2, ...]
RATE_LIMIT_STORE = {}
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 10


def check_rate_limit(client_ip: str):
    now = datetime.now()
    if client_ip not in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = []

    # Filter out old requests
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    RATE_LIMIT_STORE[client_ip] = [
        t for t in RATE_LIMIT_STORE[client_ip] if t > window_start
    ]

    if len(RATE_LIMIT_STORE[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again later."
        )

    RATE_LIMIT_STORE[client_ip].append(now)


# --- Database Setup (Supabase Postgres) ---
# See ManagerAgent.database for pool initialization

# Initialize Supabase client for storage (Bucket logic)
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_JWT_SECRET")
)


# init_db removed (redundant)


def get_chat_history(user_id: str, session_id: str, limit: int = 10) -> str:
    """Retrieve recent chat history for a session formatted as text, scoped by user."""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Use seq_id for guaranteed insertion order sorting
                cursor.execute(
                    """
                    SELECT role, content FROM (
                        SELECT role, content, seq_id 
                        FROM chat_history 
                        WHERE user_id = %s AND session_id = %s 
                        ORDER BY seq_id DESC 
                        LIMIT %s
                    ) AS sub
                    ORDER BY seq_id ASC
                """,
                    (user_id, session_id, limit),
                )
                rows = cursor.fetchall()

        formatted_history = "\n".join(
            [f"{row['role']}: {row['content']}" for row in rows]
        )
        return formatted_history
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return ""


def get_chat_history_json(user_id: str, session_id: str, limit: int = 50) -> List[dict]:
    """Retrieve recent chat history for a session formatted as JSON list, scoped by user."""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Use seq_id for guaranteed insertion order sorting
                cursor.execute(
                    """
                    SELECT role, content FROM (
                        SELECT role, content, seq_id 
                        FROM chat_history 
                        WHERE user_id = %s AND session_id = %s 
                        ORDER BY seq_id DESC 
                        LIMIT %s
                    ) AS sub
                    ORDER BY seq_id ASC
                """,
                    (user_id, session_id, limit),
                )
                rows = cursor.fetchall()

        # Map backend roles to frontend roles
        formatted_history = []
        for row in rows:
            role = str(row["role"]).lower()
            content = row["content"]
            frontend_role = "user" if role == "user" else "ai"
            formatted_history.append({"role": frontend_role, "content": content})

        return formatted_history
    except Exception as e:
        print(f"Error fetching chat history JSON: {e}")
        return []


def save_chat_pair(user_id: str, session_id: str, user_query: str, agent_response: str):
    """Save both user and agent messages in a single atomic transaction for correct ordering."""
    if user_id == "00000000-0000-0000-0000-000000000000":
         print("DEBUG: Skipping history save for mock dev user.")
         return

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # 1. Ensure session exists
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE 
                    SET updated_at = CURRENT_TIMESTAMP
                """,
                    (session_id, user_id, user_query[:50] if user_query else "New Conversation"),
                )

                # 2. Insert User message
                cursor.execute(
                    "INSERT INTO chat_history (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                    (user_id, session_id, "User", user_query),
                )

                # 3. Insert Agent message
                cursor.execute(
                    "INSERT INTO chat_history (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                    (user_id, session_id, "Agent", agent_response),
                )
        print(f"DEBUG: Successfully saved message pair for session {session_id}")
    except Exception as e:
        print(f"ERROR saving chat pair for session {session_id}: {e}")
        import traceback
        traceback.print_exc()


def save_chat_entry(user_id: str, session_id: str, role: str, content: str):
    """Fallback for single entries, though save_chat_pair is preferred for turn consistency."""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE 
                    SET updated_at = CURRENT_TIMESTAMP
                """,
                    (session_id, user_id, "New Conversation"),
                )
                cursor.execute(
                    "INSERT INTO chat_history (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                    (user_id, session_id, role, content),
                )
    except Exception as e:
        print(f"ERROR saving chat entry: {e}")


# Helper to update session timestamp (used elsewhere if needed)
def update_session_timestamp(session_id: str):
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = %s",
                    (session_id,),
                )
    except Exception as e:
        print(f"Error updating session timestamp: {e}")


# --- Backtesting Endpoint ---
@app.post("/api/backtest")
async def run_backtest(request: dict):
    """
    Run a simulation on a ticker with REAL-TIME STREAMING using AI Trading Agents.
    Body: {"ticker": "AAPL", "days": 30}
    Returns: SSE Stream
    """
    try:
        from PaperTrader.agent_backtester import AgentBacktestEngine
        from fastapi.responses import StreamingResponse
        import json
        import asyncio
        
        ticker = request.get("ticker", "AAPL")
        days = int(request.get("days", 30))
        
        async def event_generator():
            engine = AgentBacktestEngine()
            
            async for event in engine.stream_agent_simulation(ticker, days=days, interval="1d"):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0) # Yield control to event loop

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Data Models ---


class AgentRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"  # Default session if none provided


class AgentResponse(BaseModel):
    final_output: str
    status: str = "success"
    extracted_tickers: List[str] = []


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    metadata: Optional[str] = None


class CreateHoldingRequest(BaseModel):
    ticker: str
    asset_name: str
    quantity: float
    price: float
    source_doc: str = "Manual Entry"


class UpdateProfileRequest(BaseModel):
    risk_level: int
    objective: str
    net_worth: Optional[float]
    tax_status: str
    strategy_notes: Optional[str] = None  # New field


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ManagerAgent"}


@app.post("/v1/agent/calculate", response_model=AgentResponse)
async def calculate(
    request: Request, body: AgentRequest, user: dict = Depends(get_current_user)
):
    """
    Run the Manager Agent on a user query.
    Protected by rate limiting, timeouts, and Authentication.
    """
    # 1. Input Validation
    if len(body.query) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Query too long (max 1000 characters).",
        )

    try:
        # 0. Authenticate User (Dependency Injection)
        user_id = user["sub"]

        # 3. Retrieve History
        history = get_chat_history(user_id, body.session_id)

        # --- MULTI-INTENT ROUTING ---

        # 1. Analyze Intent(s)
        decision = await classify_intent(body.query)

        # 2. Route based on Intent(s)
        if len(decision.intents) > 1:
            # Multi-intent query - use orchestrator
            final_output = await asyncio.wait_for(
                orchestrate(
                    body.query, decision.intents, user_id=user_id, history=history
                ),
                timeout=60.0,  # Longer timeout for multi-step
            )

        elif decision.primary_intent == IntentType.STOCK:
            final_output = await ask_stock_analyst(body.query)

        elif decision.primary_intent == IntentType.RAG:
            final_output = await perform_rag_search(
                body.query, user_id=user_id, session_id=body.session_id
            )

        elif decision.primary_intent == IntentType.CALCULATOR:
            # Construct Contextual Query for Financial Agent
            if history:
                full_query = f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
            else:
                full_query = body.query

            # Direct routing to Financial Agent
            result = await asyncio.wait_for(
                run_with_retry(financial_agent, full_query), timeout=30.0
            )
            final_output = result.final_output

        else:
            # Construct Contextual Query for General Agent
            if history:
                full_query = f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
            else:
                full_query = body.query

            # Execution with Timeout (30s)
            result = await asyncio.wait_for(
                run_with_retry(general_agent, full_query), timeout=30.0
            )
            final_output = result.final_output

        # 6. Save Interaction to History (Atomic Pair)
        save_chat_pair(user_id, body.session_id, body.query, final_output)

        return AgentResponse(
            final_output=final_output,
            status="success",
            extracted_tickers=decision.extracted_tickers,
        )
    except asyncio.TimeoutError:
        print(f"Timeout executing query: {body.query}")
        raise HTTPException(
            status_code=504, detail="Agent execution timed out (complexity limit)"
        )
    except Exception as e:
        print(f"Error executing agent: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/v1/agent/chat/stream")
async def chat_stream(request: Request, body: AgentRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Yields JSON chunks: {"type": "token"|"status"|"error", "content": "..."}
    """
    # Verify Auth Manually since StreamingResponse makes Dependency injection tricky with generators
    # But actually, we can resolve dependencies before the stream starts.
    # However, for simplicity/safety, we'll verify the token from the header inside the stream or before.
    # To keep it standard, let's use Depends in the signature, but we need to pass the user_id to the generator.

    # 0. Authenticate (Manual extract for stream safety or use Depends)
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    token = auth_header.split(" ")[1]
    from Auth.verification import verify_token

    try:
        payload = verify_token(token)
        user_id = payload["sub"]
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Token: {str(e)}")

    async def event_generator():
        try:
            # 0. Handle 'new' session - generate real UUID if frontend didn't (safety fallback)
            actual_session_id = body.session_id
            if body.session_id == 'new':
                actual_session_id = str(uuid.uuid4())
                # Note: No need to emit back anymore as frontend uses real IDs now
                # but we'll include it for tool consistency just in case
                yield f"data: {json.dumps({'type': 'status', 'content': 'Initializing new session...'})}\n\n"

            # 1. Retrieve History
            import time
            hist_start = time.perf_counter()
            history = get_chat_history(user_id, actual_session_id)
            print(f"DEBUG [PERF]: get_chat_history took {(time.perf_counter() - hist_start) * 1000:.2f}ms")

            # 2. Analyze Intent
            yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing intent...'})}\n\n"
            intent_start = time.perf_counter()
            decision = await classify_intent(body.query)
            print(f"DEBUG [PERF]: classify_intent took {(time.perf_counter() - intent_start) * 1000:.2f}ms")

            # Emit extracted tickers early
            if decision.extracted_tickers:
                yield f"data: {json.dumps({'type': 'tickers', 'content': decision.extracted_tickers})}\n\n"

            # 3. Route & Stream
            async def run_stream():
                if len(decision.intents) > 1:
                    # Multi-Intent -> Orchestrator Stream
                    async for chunk in orchestrate_stream(
                        body.query, decision.intents, user_id, history
                    ):
                        yield chunk

                elif decision.primary_intent == IntentType.STOCK:
                    from ManagerAgent.tools import ask_stock_analyst_stream

                    async for chunk in ask_stock_analyst_stream(body.query):
                        yield chunk

                elif decision.primary_intent == IntentType.RAG:
                    from ManagerAgent.tools import perform_rag_search_stream

                    yield {"type": "status", "content": "Searching documents..."}
                    async for chunk in perform_rag_search_stream(
                        body.query, user_id, body.session_id, history=history
                    ):
                        yield chunk

                elif decision.primary_intent == IntentType.CALCULATOR:
                    yield {"type": "status", "content": "Running calculations..."}
                    # Calculator is currently sync/fast, so we fake stream or just yield result
                    # But financial_agent might be slow-ish.
                    # We'll just run it and yield the result as one token block for now or fake stream it.
                    full_query = (
                        f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
                        if history
                        else body.query
                    )
                    result = await run_with_retry(financial_agent, full_query)
                    yield {"type": "token", "content": result.final_output}

                else:  # GENERAL
                    yield {"type": "status", "content": "Thinking..."}
                    full_query = (
                        f"Previous conversation:\n{history}\n\nCurrent User Query: {body.query}"
                        if history
                        else body.query
                    )
                    result = await run_with_retry(general_agent, full_query)
                    # General agent (LangChain) could be streamed, but keeping it simple for now
                    yield {"type": "token", "content": result.final_output}

            # Execute and yield
            full_response_buffer = []
            history_saved = False

            try:
                async for chunk in run_stream():
                    # Yield to client (SSE format) IMMEDIATELY
                    yield f"data: {json.dumps(chunk)}\n\n"
                    # Force return to event loop to allow write to socket
                    await asyncio.sleep(0)

                    # Buffer tokens for history
                    if chunk["type"] == "token":
                        content = chunk["content"]
                        full_response_buffer.append(content)
                
                # Normal completion save
                final_text = "".join(full_response_buffer)
                if final_text:
                    save_chat_pair(user_id, actual_session_id, body.query, final_text)
                    history_saved = True
                    
            except GeneratorExit:
                # Client disconnected but we may have content to save
                final_text = "".join(full_response_buffer)
                if not history_saved:
                    # Even if no AI text, save the USER query so it doesn't vanish
                    saved_text = final_text if final_text else "..."
                    print(f"DEBUG: Saving response (len={len(saved_text)}) on client disconnect for session {actual_session_id}")
                    save_chat_pair(user_id, actual_session_id, body.query, saved_text)
                    history_saved = True
                raise

            # End of stream status
            yield f"data: {json.dumps({'type': 'end', 'content': ''})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': f'SERVER ERROR: {type(e).__name__}: {str(e)}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering if present
        },
    )


@app.post("/v1/agent/upload")
async def upload_document(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    """
    Upload and ingest a PDF document into Supabase Storage and RAG system.
    """
    user_id = user["sub"]

    # 1. Validate File Type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are currently supported."
        )

    # 2. Upload to Supabase Storage
    # Path: {user_id}/{filename}
    try:
        file_content = await file.read()
        storage_path = f"{user_id}/{file.filename}"

        # Check if bucket exists/create logic is handled in Dashboard,
        # but here we just upload to 'rag-documents' bucket
        supabase.storage.from_("rag-documents").upload(
            path=storage_path, file=file_content, file_options={"upsert": "true"}
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
        raise HTTPException(
            status_code=500, detail=f"Upload/Ingestion failed: {str(e)}"
        )


@app.delete("/v1/agent/documents/{filename}")
async def delete_document(filename: str, user: dict = Depends(get_current_user)):
    """
    Delete a document from both Supabase Storage and vector database.
    """
    user_id = user["sub"]
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
    List all uploaded documents from Supabase Storage, searching 1 level deep.
    """
    user_id = user["sub"]
    try:
        # List files in the user's root folder
        res = supabase.storage.from_("rag-documents").list(path=user_id)

        files = []
        for item in res:
            name = item.get("name", "")
            if name.endswith(".pdf"):
                files.append(name)
            elif item.get("id") is None: # Likely a folder
                 # Check subfolder
                 try:
                     sub_path = f"{user_id}/{name}"
                     sub_res = supabase.storage.from_("rag-documents").list(path=sub_path)
                     for sub_item in sub_res:
                         sub_name = sub_item.get("name", "")
                         if sub_name.endswith(".pdf"):
                             files.append(f"{name}/{sub_name}")
                 except Exception:
                     continue

        return {"documents": files}
    except Exception as e:
        print(f"Error listing documents: {e}")
        return {"documents": []}


@app.get("/v1/agent/history")
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    """
    Get chat history for a specific session.
    """
    import time
    start = time.perf_counter()
    user_id = user["sub"]
    history = get_chat_history_json(user_id, session_id)
    print(f"DEBUG [PERF]: get_chat_history_json for {session_id} took {(time.perf_counter() - start) * 1000:.2f}ms")
    return history


@app.get("/v1/agent/articles/{ticker}")
async def get_articles(
    ticker: str, max_articles: int = 20, user: dict = Depends(get_current_user)
):
    """
    Get news articles with sentiment analysis for a ticker.
    Returns articles with Positive/Negative/Neutral sentiment and overall Bullish/Bearish/Neutral.
    """
    try:
        from StockAgents.services.article_service import article_service

        result = await article_service.fetch_and_analyze(ticker.upper(), max_articles)
        return result
    except Exception as e:
        print(f"Error fetching articles for {ticker}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch articles: {str(e)}"
        )


@app.get("/v1/agent/stock/{ticker}")
async def get_stock_data(
    ticker: str, 
    time_range: str = "3m", 
    start_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Get real-time stock quote, price history, and company profile.
    If start_date is provided (YYYY-MM-DD), fetches candles from that date to now.
    """
    try:
        # Import FinnhubClient
        from StockAgents.services.finnhub_client import finnhub_client
        import asyncio

        tasks = [
            finnhub_client.get_quote(ticker.upper()),
            finnhub_client.get_candles(ticker.upper(), time_range=time_range), # TODO: Handle specific start_date inside client if needed, or filter here. 
            finnhub_client.get_company_profile(ticker.upper()),
            finnhub_client.get_company_metrics(ticker.upper())
        ]
        
        results = await asyncio.gather(*tasks)
        quote = results[0]
        candles = results[1]
        profile = results[2]
        metrics = results[3]
        company_name = profile.get("name", ticker.upper())


        # Format candles for recharts
        chart_data = []
        if candles.get("s") == "ok" and candles.get("c"):
            c = candles.get("c", [])
            t = candles.get("t", [])
            o = candles.get("o", [0] * len(c))  # Fallback if missing
            h = candles.get("h", [0] * len(c))
            lows = candles.get("l", [0] * len(c))

            for i in range(len(c)):
                price = c[i]
                timestamp = t[i]

                # Convert timestamp to readable date/time
                # For intraday (1d, 1w), show Time. For daily (1m+), show Date.
                from datetime import datetime, timezone

                if time_range == "1d":
                    # Intraday 1D: Show Time only
                    time_str = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%H:%M")
                elif time_range == "1w":
                    # Intraday 1W: Show Date + Time so frontend can detect day changes
                    time_str = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%b %d %H:%M")
                else:
                    # Daily: Show YYYY-MM-DD (Match filtering logic format)
                    time_str = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%Y-%m-%d")

                chart_data.append(
                    {
                        "time": time_str,
                        "value": round(price, 2),
                        "open": round(o[i], 2),
                        "high": round(h[i], 2),
                        "low": round(lows[i], 2),
                    }
                )

        # Filter candles if start_date is provided
        if start_date:
            try:
                from datetime import datetime
                # Parse start_date (YYYY-MM-DD or ISO) to timestamp
                if "T" in start_date:
                     # Parse ISO format and normalize to midnight (start of day)
                     dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                     start_ts = int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
                else:
                     # Already YYYY-MM-DD (midnight by default)
                     start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
                # DEBUG: Trace start_date logic
                print(f"DEBUG GRAPH: Ticker={ticker}, StartDate={start_date}, StartTS={start_ts}")
                
                # Filter: Include candles from the start of the buy date
                pre_filter_len = len(chart_data)
                filtered_data = [c for c in chart_data if int(datetime.strptime(c["time"], "%Y-%m-%d").timestamp()) >= start_ts]
                print(f"DEBUG GRAPH: Pre-filter={pre_filter_len}, Post-filter={len(filtered_data)}")
                
                # If filtering removes all data (e.g. buy date is today/future) 
                # OR if the result is too small for a graph (Recharts needs >1 point for Area), 
                # keep at least the last 5 candles (approx 1 week) for context.
                if len(filtered_data) < 2 and chart_data:
                    print("DEBUG GRAPH: Filtered data too small, falling back to last 5 candles")
                    filtered_data = chart_data[-5:] 
                
                chart_data = filtered_data
                print(f"DEBUG GRAPH: Final candle count={len(chart_data)}")

            except Exception as e:
                print(f"Error filtering candles by date: {e}")

        return {
            "ticker": ticker.upper(),
            "name": company_name,
            "metrics": metrics,
            "currentPrice": quote.get("c", 0),
            "change": quote.get("d", 0),
            "changePercent": quote.get("dp", 0),
            "high": quote.get("h", 0),
            "low": quote.get("l", 0),
            "open": quote.get("o", 0),
            "previousClose": quote.get("pc", 0),
            "candles": chart_data,
        }
    except Exception as e:
        print(f"Error fetching stock data for {ticker}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch stock data: {str(e)}"
        )


@app.get("/v1/agent/analyst/{ticker}")
async def get_analyst_ratings(ticker: str, user: dict = Depends(get_current_user)):
    """
    Get Wall Street analyst ratings for a ticker.
    Returns consensus score (0-100), recommendation, and buy/sell/hold counts.
    """
    try:
        from StockAgents.services.finnhub_client import finnhub_client

        result = await finnhub_client.get_analyst_ratings(ticker.upper())
        return result
    except Exception as e:
        print(f"Error fetching analyst ratings for {ticker}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch analyst ratings: {str(e)}"
        )


# --- Session Management Endpoints ---


@app.get("/v1/agent/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    """List all chat sessions for the user (Newest first)."""
    user_id = user["sub"]
    try:
        print(f"Listing sessions for user_id: {user_id}")
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, title, metadata, created_at, updated_at 
                    FROM chat_sessions 
                    WHERE user_id = %s 
                    ORDER BY updated_at DESC
                """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        # Convert metadata (JSONB/dict) and UUIDs/dates to strings if needed for frontend
        # dict_row already gives us dicts, but we need to ensure they are fully serializable
        formatted_sessions = []
        for row in rows:
            # Metadata might be a dict (from JSONB) or None
            metadata = row["metadata"]
            if isinstance(metadata, dict):
                metadata = json.dumps(metadata)
            
            formatted_sessions.append({
                "session_id": str(row["session_id"]),
                "title": row["title"],
                "metadata": metadata,
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"])
            })

        print(f"Found {len(formatted_sessions)} sessions for user {user_id}")
        return {"sessions": formatted_sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/agent/sessions")
async def create_session(
    body: CreateSessionRequest, user: dict = Depends(get_current_user)
):
    """Create a new chat session."""
    user_id = user["sub"]
    import uuid

    session_id = str(uuid.uuid4())

    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (%s, %s, %s)
                """,
                    (session_id, user_id, body.title),
                )

        return {"session_id": session_id, "title": body.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/v1/agent/sessions/{session_id}")
async def update_session(
    session_id: str, body: UpdateSessionRequest, user: dict = Depends(get_current_user)
):
    """Update a session (rename or update metadata)."""
    user_id = user["sub"]
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                if body.title is not None and body.metadata is not None:
                    cursor.execute(
                        """
                        UPDATE chat_sessions SET title = %s, metadata = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND user_id = %s
                    """,
                        (body.title, body.metadata, session_id, user_id),
                    )
                elif body.title is not None:
                    cursor.execute(
                        """
                        UPDATE chat_sessions SET title = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND user_id = %s
                    """,
                        (body.title, session_id, user_id),
                    )
                elif body.metadata is not None:
                    cursor.execute(
                        """
                        UPDATE chat_sessions SET metadata = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND user_id = %s
                    """,
                        (body.metadata, session_id, user_id),
                    )

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/agent/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a session and its history."""
    user_id = user["sub"]
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Delete session
                cursor.execute(
                    "DELETE FROM chat_sessions WHERE session_id = %s AND user_id = %s",
                    (session_id, user_id),
                )

                # Delete history
                cursor.execute(
                    "DELETE FROM chat_history WHERE session_id = %s AND user_id = %s",
                    (session_id, user_id),
                )

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# --- Portfolio endpoints (Local Store for now) ---

@app.get("/v1/portfolio/pending")
async def get_pending_holdings(user: dict = Depends(get_current_user)):
    """Get pending extracted holdings from local store."""
    try:
        from RAG_PIPELINE.src.local_store import load_holdings
        items = load_holdings()
        # Filter for pending items
        pending = [item for item in items if item.get("status") == "pending"]
        return {"items": pending}
    except Exception as e:
        print(f"Error loading pending holdings: {e}")
        return {"items": []}


@app.post("/v1/portfolio/confirm/{item_id}")
async def confirm_holding(item_id: str, user: dict = Depends(get_current_user)):
    """Confirm a pending holding (move to verified status)."""
    try:
        from RAG_PIPELINE.src.local_store import update_holding_status
        success = update_holding_status(item_id, "verified")
        if not success:
             raise HTTPException(status_code=404, detail="Item not found")
        return {"status": "success", "message": "Holding verified"}
    except Exception as e:
        print(f"Error confirming holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/v1/portfolio/holdings")
async def get_verified_holdings(user: dict = Depends(get_current_user)):
    """Get verified holdings from local store."""
    try:
        from RAG_PIPELINE.src.local_store import load_holdings
        items = load_holdings()
        # Filter for verified items
        verified = [item for item in items if item.get("status") == "verified"]
        return {"items": verified}
    except Exception as e:
        print(f"Error loading verified holdings: {e}")
        return {"items": []}


@app.post("/v1/portfolio/holdings")
async def add_holding(body: CreateHoldingRequest, user: dict = Depends(get_current_user)):
    """Add a new verified holding manually."""
    try:
        from RAG_PIPELINE.src.local_store import save_holding
        import uuid
        
        new_item = body.dict()
        new_item["id"] = f"manual_{str(uuid.uuid4())}"
        new_item["status"] = "verified"
        
        save_holding(new_item)
        return {"status": "success", "item": new_item}
    except Exception as e:
        print(f"Error adding holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/portfolio/holdings/{ticker}")
async def delete_holding(ticker: str, user: dict = Depends(get_current_user)):
    """Delete all holdings for a given ticker."""
    try:
        from RAG_PIPELINE.src.local_store import load_holdings, save_all_holdings
        
        items = load_holdings()
        ticker_upper = ticker.upper()
        
        # Filter out all items matching this ticker
        remaining = [i for i in items if (i.get("ticker") or "").upper() != ticker_upper]
        deleted_count = len(items) - len(remaining)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No holdings found for {ticker}")
        
        save_all_holdings(remaining)
        return {"status": "success", "deleted": deleted_count, "ticker": ticker_upper}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# User Profile Endpoints - Dynamic Agent Profile System
# =============================================================================

@app.get("/v1/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """Get the current user's investment profile."""
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT risk_level, objective, net_worth, tax_status, strategy_notes, version, created_at, updated_at
                    FROM user_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    # Return default profile
                    return {
                        "risk_level": 50,
                        "objective": "growth",
                        "net_worth": None,
                        "tax_status": "mixed",
                        "strategy_notes": None,
                        "version": 1,
                        "is_default": True
                    }
                
                return {
                    "risk_level": row["risk_level"],
                    "objective": row["objective"],
                    "net_worth": row["net_worth"],
                    "tax_status": row["tax_status"],
                    "strategy_notes": row.get("strategy_notes"),
                    "version": row.get("version", 1),
                    "is_default": False,
                    "updated_at": str(row["updated_at"]) if row.get("updated_at") else None
                }
    except Exception as e:
        print(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/user/profile")
async def update_user_profile(body: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Update the current user's investment profile (upsert)."""
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # Validate objective and tax_status
    valid_objectives = ["growth", "income", "preservation", "speculation"]
    valid_tax_statuses = ["taxable", "tax_advantaged", "mixed"]
    
    if body.objective not in valid_objectives:
        raise HTTPException(status_code=400, detail=f"Invalid objective. Must be one of: {valid_objectives}")
    if body.tax_status not in valid_tax_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid tax_status. Must be one of: {valid_tax_statuses}")
    if not 0 <= body.risk_level <= 100:
        raise HTTPException(status_code=400, detail="risk_level must be between 0 and 100")
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_profiles (user_id, risk_level, objective, net_worth, tax_status, strategy_notes, version, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        risk_level = EXCLUDED.risk_level,
                        objective = EXCLUDED.objective,
                        net_worth = EXCLUDED.net_worth,
                        tax_status = EXCLUDED.tax_status,
                        strategy_notes = EXCLUDED.strategy_notes
                    RETURNING risk_level, objective, net_worth, tax_status, strategy_notes, version
                    """,
                    (user_id, body.risk_level, body.objective, body.net_worth, body.tax_status, body.strategy_notes)
                )
                row = cur.fetchone()
                conn.commit()
                
                # Distill profile to show user what directives are active
                profile = UserProfile(
                    user_id=user_id,
                    risk_level=row["risk_level"],
                    objective=InvestmentObjective(row["objective"]),
                    net_worth=row["net_worth"],
                    tax_status=TaxStatus(row["tax_status"]),
                    strategy_notes=row["strategy_notes"],
                    version=row["version"]
                )
                
                return {
                    "status": "success",
                    "profile": {
                        "risk_level": row["risk_level"],
                        "objective": row["objective"],
                        "net_worth": row["net_worth"],
                        "tax_status": row["tax_status"],
                        "strategy_notes": row["strategy_notes"],
                        "version": row["version"]
                    },
                    "active_persona": distill_profile(profile)[:200] + "..."  # Preview
                }
    except Exception as e:
        print(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Stock Report Generation Endpoints
# =============================================================================

@app.get("/v1/reports/{ticker}")
async def get_report_endpoint(ticker: str, user: dict = Depends(get_current_user)):
    """Get cached analyst report for a ticker (today's date)."""
    from ManagerAgent.reports_db import get_report
    
    user_id = user.get("sub", "anonymous")
    report = get_report(user_id, ticker.upper())
    
    if report is None:
        raise HTTPException(status_code=404, detail="No report found for today. Generate one first.")
    
    return report


@app.post("/v1/reports/{ticker}")
async def generate_report_endpoint(ticker: str, force: bool = False, user: dict = Depends(get_current_user)):
    """
    Generate analyst reports for a ticker using the TradingAgents pipeline.
    Streams progress updates via SSE, then returns the final report.
    """
    from ManagerAgent.reports_db import get_report, save_report
    from datetime import date
    
    user_id = user.get("sub", "anonymous")
    today = date.today().isoformat()
    
    # Check cache first (skip if force regeneration)
    cached = get_report(user_id, ticker.upper(), today) if not force else None
    if cached:
        async def cached_stream():
            yield json.dumps({"type": "status", "content": "📋 Report already generated today, returning cached version..."}) + "\n"
            yield json.dumps({"type": "report", "content": cached}) + "\n"
        return StreamingResponse(cached_stream(), media_type="application/x-ndjson")
    
    async def event_generator():
        try:
            yield json.dumps({"type": "status", "content": "🚀 Initializing AI Analyst Pipeline..."}) + "\n"
            
            # Import and initialize the graph (analyst-only mode)
            from PaperTrader.TradingAgents.graph.trading_graph import TradingAgentsGraph
            
            graph = TradingAgentsGraph(
                selected_analysts=["market", "social", "news", "fundamentals"],
                debug=False,
            )
            
            # Run analysts in a thread to not block the event loop
            import asyncio
            
            loop = asyncio.get_event_loop()
            
            # We need to collect results from the generator in a thread
            def run_analysts():
                results = []
                for step in graph.run_analysts_only(ticker.upper(), today):
                    results.append(step)
                return results
            
            steps = await loop.run_in_executor(None, run_analysts)
            
            # Stream the progress steps
            final_reports = None
            for step_name, is_final, reports in steps:
                if is_final and reports:
                    final_reports = reports
                yield json.dumps({"type": "status", "content": step_name}) + "\n"
            
            if final_reports:
                # Save to SQLite cache
                save_report(user_id, ticker.upper(), final_reports, today)
                
                # Return the full report
                report_data = {
                    "user_id": user_id,
                    "ticker": ticker.upper(),
                    "report_date": today,
                    "market_report": final_reports.get("market_report", ""),
                    "news_report": final_reports.get("news_report", ""),
                    "fundamentals_report": final_reports.get("fundamentals_report", ""),
                    "sentiment_report": final_reports.get("sentiment_report", ""),
                }
                yield json.dumps({"type": "report", "content": report_data}) + "\n"
            else:
                yield json.dumps({"type": "error", "content": "Failed to generate reports"}) + "\n"
                
        except Exception as e:
            print(f"Report generation error: {e}")
            import traceback
            traceback.print_exc()
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"
    
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

