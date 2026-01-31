import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from CalcAgent.src.utils import run_with_retry
import asyncio
from datetime import datetime, timedelta

# Import GeneralAgent for fallback
from CalcAgent.src.agent import financial_agent, general_agent
from fastapi import Depends
from Auth.dependencies import get_current_user
from ManagerAgent.router_intelligence import classify_intent, IntentType
from ManagerAgent.tools import ask_stock_analyst, perform_rag_search
from ManagerAgent.orchestrator import orchestrate, orchestrate_stream
from supabase import create_client, Client
from fastapi.responses import StreamingResponse
import json
import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from fastapi import UploadFile, File

app = FastAPI(title="Financial Calculation Agent API")

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
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# Initialize Connection Pool
pool = None
if SUPABASE_DB_URL:
    print("Initializing Supabase Postgres Connection Pool...")
    pool = ConnectionPool(
        conninfo=SUPABASE_DB_URL,
        max_size=20,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
    )
else:
    print("WARNING: SUPABASE_DB_URL not found in .env. Database operations will fail.")


def get_db():
    """Context manager for getting a connection from the pool."""
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized.")
    return pool.connection()


# Initialize Supabase client for storage (Bucket logic)
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_JWT_SECRET")
)


def init_db():
    """No-op for migration to Supabase (Schema assumed created via SQL Editor)."""
    pass


init_db()


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
            # 1. Retrieve History
            history = get_chat_history(user_id, body.session_id)

            # 2. Analyze Intent
            yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing intent...'})}\n\n"
            decision = await classify_intent(body.query)

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
                        body.query, user_id, body.session_id
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

            async for chunk in run_stream():
                # Yield to client (SSE format) IMMEDIATELY
                yield f"data: {json.dumps(chunk)}\n\n"
                # Force return to event loop to allow write to socket
                await asyncio.sleep(0)

                # Buffer tokens for history
                if chunk["type"] == "token":
                    content = chunk["content"]
                    full_response_buffer.append(content)

            # 4. Save History (After stream completes - Atomic Pair)
            final_text = "".join(full_response_buffer)
            save_chat_pair(user_id, body.session_id, body.query, final_text)

            # End of stream
            yield f"data: {json.dumps({'type': 'end', 'content': ''})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

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
    List all uploaded documents from Supabase Storage.
    """
    user_id = user["sub"]
    try:
        # List files in the user's specific folder in the bucket
        res = supabase.storage.from_("rag-documents").list(path=user_id)

        # Supabase returns a list of file info objects
        files = [f["name"] for f in res if f["name"].endswith(".pdf")]

        return {"documents": files}
    except Exception as e:
        print(f"Error listing documents: {e}")
        return {"documents": []}


@app.get("/v1/agent/history")
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    """
    Get chat history for a specific session.
    """
    user_id = user["sub"]
    return get_chat_history_json(user_id, session_id)


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
    ticker: str, time_range: str = "3m", user: dict = Depends(get_current_user)
):
    """
    Get real-time stock quote and price history for a ticker.
    Returns data formatted for frontend charting.
    """
    try:
        # Import FinnhubClient
        from StockAgents.services.finnhub_client import finnhub_client

        # Fetch quote and candles in parallel
        quote = await finnhub_client.get_quote(ticker.upper())
        candles = await finnhub_client.get_candles(
            ticker.upper(), time_range=time_range
        )

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
                    # Daily: Show Date (UTC midnight)
                    time_str = datetime.fromtimestamp(
                        timestamp, tz=timezone.utc
                    ).strftime("%b %d")

                chart_data.append(
                    {
                        "time": time_str,
                        "value": round(price, 2),
                        "open": round(o[i], 2),
                        "high": round(h[i], 2),
                        "low": round(lows[i], 2),
                    }
                )

        return {
            "ticker": ticker.upper(),
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


# Auto-update session timestamp on activity
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
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
