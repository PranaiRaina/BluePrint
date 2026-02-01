@app.patch("/api/portfolios/{portfolio_id}/toggle")
async def toggle_agent_status(portfolio_id: str, request: dict):
    """
    Toggle the autonomous agent on/off.
    Body: {"is_active": true/false}
    """
    try:
        user_id = "00000000-0000-0000-0000-000000000000" # TODO: Get from auth
        from PaperTrader.service import paper_trading_service
        is_active = request.get("is_active", False)
        
        result = paper_trading_service.toggle_agent(user_id, portfolio_id, is_active)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
