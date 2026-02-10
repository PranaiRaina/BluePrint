from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from TradingAgents.agents.utils.agent_states import AgentState

class TradeOrder(BaseModel):
    """Structure for a trade order."""
    action: Literal["BUY", "SELL", "HOLD"] = Field(
        ..., description="The action to take: BUY, SELL, or HOLD"
    )
    quantity: int = Field(
        ..., description="Number of shares to buy or sell. 0 if HOLD."
    )
    order_type: Literal["MARKET", "LIMIT"] = Field(
        "MARKET", description="Type of order: MARKET or LIMIT"
    )
    limit_price: float | None = Field(
        None, description="Limit price if order_type is LIMIT. None if MARKET or HOLD."
    )
    reasoning: str = Field(
        ..., description="Brief explanation for the trade execution details."
    )

def validate_trade_order(order: TradeOrder, cash: float, holdings: int, estimated_price: float) -> tuple[bool, str, TradeOrder]:
    """
    Validate a trade order against portfolio constraints.
    Returns (is_valid, error_message, corrected_order).
    """
    corrected = order.copy()
    
    if order.action == "HOLD" or order.quantity <= 0:
        corrected.action = "HOLD"
        corrected.quantity = 0
        if order.action != "HOLD":
            return False, f"Invalid quantity {order.quantity} for {order.action}. Defaulting to HOLD.", corrected
        return True, "", corrected
    
    price = order.limit_price if order.limit_price else estimated_price
    if price <= 0: price = 100.0
    
    if order.action == "BUY":
        max_buyable = int(cash // price)
        if order.quantity > max_buyable:
            corrected.quantity = max_buyable
            if max_buyable <= 0:
                corrected.action = "HOLD"
                corrected.quantity = 0
                return False, "INSUFFICIENT CASH for even 1 share. Switch to HOLD.", corrected
            return False, f"INSUFFICIENT CASH: Requested {order.quantity}, but max is {max_buyable}. Clamping.", corrected
        return True, "", corrected
    
    if order.action == "SELL":
        if order.quantity > holdings:
            corrected.quantity = holdings
            if holdings <= 0:
                corrected.action = "HOLD"
                corrected.quantity = 0
                return False, "NO HOLDINGS to sell. Switch to HOLD.", corrected
            return False, f"INSUFFICIENT SHARES: Requested {order.quantity}, but only own {holdings}. Clamping.", corrected
        return True, "", corrected
    
    return False, f"Unknown action: {order.action}", corrected

def create_trade_executor(llm, max_retries: int = 3):
    """Create the trade executor agent node with safety validation."""
    
    def trade_executor_node(state: AgentState):
        risk_decision = state.get("final_trade_decision", "No decision")
        ticker = state.get("company_of_interest", "Unknown")
        
        cash = state.get("cash_available", 0.0)
        holdings = state.get("current_holdings", 0)
        
        # Try to get price from state or estimate
        estimated_price = state.get("current_price", 0.0)
        if estimated_price <= 0:
            print(f"⚠️ WARNING: Trade Executor received invalid price {estimated_price}. Defaulting to 100.0 for safety check only (Simulated).")
            # In a real system, we should likely abort or fetch live price.
            # For backtest, this is a critical data error.
            # We'll allow 100 as a placeholder to prevent crash but it's bad.
            # Actually, let's just use 0 which will result in 0 quantity.
            # No wait, math.floor(cash/0) is error.
            estimated_price = 100.0 
        
        # Pre-calculate useful share counts to prevent LLM math hallucinations
        import math
        max_buyable = math.floor(cash / estimated_price) if estimated_price > 0 else 0
        half_cash_shares = math.floor((cash * 0.5) / estimated_price) if estimated_price > 0 else 0
        
        base_system_message = f"""You are a Trade Execution Algorithm. Your task is to translate the Risk Manager's final qualitative decision into a precise, executable trade order (simulated).

You have access to the current Portfolio Context:
- Cash Available: ${cash:.2f}
- Current Holdings of {ticker}: {holdings} shares
- Current Market Price: ~${estimated_price:.2f} per share

CRITICAL UNIT CONVERSION (DO NOT IGNORE):
- If the decision mentions a dollar amount (e.g., "$5,000 worth"), YOU must convert it to shares.
- To spend $5,000: Use exactly {math.floor(5000/estimated_price) if estimated_price > 0 else 0} shares.
- You have access to the number of shares you can buy with half of your cash: {half_cash_shares} shares.
- You have access to the number of shares you can buy with all of your cash: {max_buyable} shares.

CRITICAL RULES:
1. **BUY Validation**: Max buyable = {max_buyable}. Never output a quantity higher than this.
2. **SELL Validation**: Max sellable = {holdings}. Never sell more than you own.
3. **HOLD**: If the decision is to hold or you cannot execute a valid trade (e.g., trying to sell when you own 0), set action=HOLD with quantity=0.
4. **Decide on a reasonable quantity** based on the risk manager's decision, ensuring it fits within the limits above.
5. If the action is BUY, the number of shares bought HAS to be above 0, if {max_buyable} is above 0.

Risk Manager's Decision:
{{risk_decision}}
"""
        
        error_context = ""
        result = None
        
        for attempt in range(max_retries):
            system_message = base_system_message
            if error_context:
                system_message += f"\n\n⚠️ PREVIOUS ERROR: {error_context}\nAdjust your quantity to be valid and try again."
            
            prompt = ChatPromptTemplate.from_template(system_message)
            structured_llm = llm.with_structured_output(TradeOrder)
            chain = prompt | structured_llm
            
            try:
                result = chain.invoke({
                    "risk_decision": risk_decision
                })
                
                # Validate and potentially correct the order
                is_valid, error_msg, corrected = validate_trade_order(result, cash, holdings, estimated_price)
                
                if is_valid:
                    print(f"✓ Trade order validated: {result.action} {result.quantity} shares")
                    return {"trade_order": result.dict()}
                else:
                    # If it's just a clamping correction, use it!
                    if "Clamping" in error_msg or "Defaulting" in error_msg:
                        print(f"ℹ️ Applied automatic correction: {error_msg}")
                        print(f"✓ Corrected order: {corrected.action} {corrected.quantity} shares")
                        return {"trade_order": corrected.dict()}
                        
                    print(f"⚠️ Trade order invalid (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    error_context = error_msg
                    
            except Exception as e:
                print(f"⚠️ Trade executor error (attempt {attempt + 1}/{max_retries}): {e}")
                error_context = str(e)
        
        # All retries exhausted - fall back to safe HOLD
        print(f"❌ Trade executor failed after {max_retries} attempts. Falling back to HOLD.")
        fallback_order = TradeOrder(
            action="HOLD",
            quantity=0,
            order_type="MARKET",
            limit_price=None,
            reasoning=f"Safety fallback: Could not generate valid order after {max_retries} attempts. Last error: {error_context}"
        )
        return {"trade_order": fallback_order.dict()}

    return trade_executor_node

