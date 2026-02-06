"""
Profile Engine - Dynamic Agent Profile System

Transforms user settings (Risk, Objective, Net Worth) into active
AI persona directives that alter the agent's tone and recommendations.
"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class InvestmentObjective(str, Enum):
    GROWTH = "growth"
    INCOME = "income"
    PRESERVATION = "preservation"
    SPECULATION = "speculation"


class TaxStatus(str, Enum):
    TAXABLE = "taxable"
    TAX_ADVANTAGED = "tax_advantaged"
    MIXED = "mixed"


class UserProfile(BaseModel):
    """User's investment profile settings."""
    user_id: str
    risk_level: int = 50  # 0-100 scale
    objective: InvestmentObjective = InvestmentObjective.GROWTH
    net_worth: Optional[float] = None
    tax_status: TaxStatus = TaxStatus.MIXED
    strategy_notes: Optional[str] = None
    version: int = 1  # Optimistic locking / Reactivity


def get_risk_persona(risk_level: int) -> str:
    """Convert risk level to persona description."""
    if risk_level <= 25:
        return "You are advising a CONSERVATIVE investor who prioritizes capital preservation above all. Emphasize stability, warn strongly about volatility and downside risks. Recommend only established, low-volatility assets. Be protective and cautious in your tone."
    elif risk_level <= 50:
        return "You are advising a MODERATE investor who seeks balanced growth with controlled risk. Acknowledge both opportunities and risks fairly. Recommend a diversified approach with some growth potential."
    elif risk_level <= 75:
        return "You are advising a GROWTH-ORIENTED investor comfortable with higher volatility for better returns. Be optimistic about opportunities while still noting key risks. Support calculated risk-taking."
    else:
        return "You are advising an AGGRESSIVE investor with high risk tolerance seeking maximum growth. Be enthusiastic about high-growth opportunities. The investor understands and accepts significant volatility. Focus on upside potential while briefly noting risks."


def get_objective_directive(objective: InvestmentObjective) -> str:
    """Convert objective to directive."""
    directives = {
        InvestmentObjective.GROWTH: "Primary goal: CAPITAL GROWTH. Prioritize recommendations that maximize long-term appreciation. Reinvesting dividends and compounding are key themes.",
        InvestmentObjective.INCOME: "Primary goal: INCOME GENERATION. Prioritize dividend-paying stocks, bonds, and income-producing assets. Yield and cash flow are paramount.",
        InvestmentObjective.PRESERVATION: "Primary goal: CAPITAL PRESERVATION. The investor is protecting existing wealth. Prioritize stability, low volatility, and inflation protection over growth.",
        InvestmentObjective.SPECULATION: "Primary goal: SPECULATIVE GAINS. The investor is comfortable with high-risk/high-reward bets. Options, crypto, and emerging sectors are acceptable topics."
    }
    return directives.get(objective, "")


def get_wealth_context(net_worth: Optional[float]) -> str:
    """Provide context based on net worth tier."""
    if net_worth is None:
        return ""
    
    if net_worth < 50000:
        return "This investor has limited capital. Focus on building an emergency fund first, low-cost index funds, and avoiding excessive fees."
    elif net_worth < 250000:
        return "This investor has moderate savings. Focus on tax-efficient investing, diversification, and systematic contributions."
    elif net_worth < 1000000:
        return "This investor has substantial assets. Consider tax optimization, asset allocation across accounts, and some alternative investments."
    else:
        return "This investor has significant wealth. Consider estate planning implications, alternative investments, tax-loss harvesting, and wealth preservation strategies."


def get_tax_context(tax_status: TaxStatus) -> str:
    """Provide tax-aware advice context."""
    contexts = {
        TaxStatus.TAXABLE: "The investor primarily uses taxable accounts. Consider tax-efficient investments, municipal bonds, and long-term holding periods to minimize tax drag.",
        TaxStatus.TAX_ADVANTAGED: "The investor primarily uses tax-advantaged accounts (401k, IRA). Tax efficiency is less critical - focus on total return optimization.",
        TaxStatus.MIXED: "The investor has both taxable and tax-advantaged accounts. Consider asset location strategies - place tax-inefficient assets in tax-advantaged accounts."
    }
    return contexts.get(tax_status, "")


def distill_profile(profile: UserProfile) -> str:
    """
    Convert a UserProfile into natural language directives for the AI.
    These directives are injected into the system prompt to alter behavior.
    """
    parts = []
    
    # Risk persona (most impactful)
    parts.append(get_risk_persona(profile.risk_level))
    
    # Investment objective
    parts.append(get_objective_directive(profile.objective))
    
    # Wealth context (if provided)
    wealth_ctx = get_wealth_context(profile.net_worth)
    if wealth_ctx:
        parts.append(wealth_ctx)
    
    # Tax context
    parts.append(get_tax_context(profile.tax_status))

    # Custom Strategy Notes (High Priority)
    if profile.strategy_notes:
        parts.append(f"ADDITIONAL USER-DEFINED STRATEGY:\n{profile.strategy_notes}")
    
    return "\n\n".join(parts)


def get_profile_directives(user_id: str, conn) -> str:
    """
    Fetch user profile from database and return distilled directives.
    Returns empty string if no profile exists (use default behavior).
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT risk_level, objective, net_worth, tax_status, strategy_notes
                FROM user_profiles
                WHERE user_id = %s
                """,
                (user_id,)
            )
            row = cur.fetchone()
            
            if not row:
                return ""
            
            profile = UserProfile(
                user_id=user_id,
                risk_level=row.get("risk_level", 50),
                objective=InvestmentObjective(row.get("objective", "growth")),
                net_worth=row.get("net_worth"),
                tax_status=TaxStatus(row.get("tax_status", "mixed")),
                strategy_notes=row.get("strategy_notes")
            )
            
            return distill_profile(profile)
    except Exception as e:
        print(f"Error fetching profile directives: {e}")
        return ""
