from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from Auth.dependencies import get_current_user
from PaperTrader.service import paper_trading_service

router = APIRouter(prefix="/paper-trader", tags=["Paper Trader"])

class CreatePortfolioRequest(BaseModel):
    name: str
    initial_cash: float = 100000.00

class TradeRequest(BaseModel):
    portfolio_id: str
    ticker: str
    action: str  # BUY or SELL
    quantity: int

@router.get("/portfolios")
def list_portfolios(user=Depends(get_current_user)):
    user_id = user["sub"]
    return paper_trading_service.get_portfolios(user_id)

@router.post("/portfolios")
def create_portfolio(req: CreatePortfolioRequest, user=Depends(get_current_user)):
    user_id = user["sub"]
    return paper_trading_service.create_portfolio(user_id, req.name, req.initial_cash)

@router.get("/portfolios/{portfolio_id}")
def get_portfolio_details(portfolio_id: str, user=Depends(get_current_user)):
    user_id = user["sub"]
    return paper_trading_service.get_portfolio_details(user_id, portfolio_id)

@router.post("/trade")
def execute_trade(req: TradeRequest, user=Depends(get_current_user)):
    user_id = user["sub"]
    return paper_trading_service.execute_trade(
        user_id, 
        req.portfolio_id, 
        req.ticker, 
        req.action, 
        req.quantity
    )
