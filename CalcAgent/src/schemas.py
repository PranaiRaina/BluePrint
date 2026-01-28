"""Pydantic schemas for structured agent outputs."""

from pydantic import BaseModel, Field
from typing import Optional


class CalculationResult(BaseModel):
    """Structured result from any financial calculation."""
    
    answer: str = Field(
        description="The calculated answer with units (e.g., '$19,671.51' or '6.5%')"
    )
    explanation: str = Field(
        description="Brief explanation of what was calculated and what it means"
    )
    formula_used: Optional[str] = Field(
        default=None,
        description="The formula or method used (e.g., 'FV = PV * (1 + r)^n')"
    )
    wolfram_query: str = Field(
        description="The exact query sent to Wolfram Alpha for verification"
    )


class ClarifyingQuestion(BaseModel):
    """When the agent needs more information from the user."""
    
    question: str = Field(
        description="The clarifying question to ask the user"
    )
    missing_params: list[str] = Field(
        description="List of parameters that are missing (e.g., ['interest_rate', 'years'])"
    )
    context: Optional[str] = Field(
        default=None,
        description="What the agent understood so far from the query"
    )
