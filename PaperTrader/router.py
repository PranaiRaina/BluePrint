from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
from .agent_backtester import AgentBacktestEngine

router = APIRouter()

class BacktestRequest(BaseModel):
    ticker: str
    days: int = 30

@router.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    engine = AgentBacktestEngine()
    
    async def event_generator():
        try:
            async for event in engine.stream_agent_simulation(request.ticker, days=request.days):
                yield json.dumps(event) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
