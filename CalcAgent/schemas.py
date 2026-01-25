"""Pydantic schemas for structured agent outputs."""

from pydantic import BaseModel, Field
from typing import Optional


class CalculationResult(BaseModel):
    """Structured result from any calculation tool."""
    
    answer: str = Field(description="The calculated answer with units")
    explanation: str = Field(description="Brief explanation of what was calculated")
    formula_used: Optional[str] = Field(default=None, description="The formula or method used")
    wolfram_query: Optional[str] = Field(default=None, description="The query sent to Wolfram Alpha")


class ClarifyingQuestion(BaseModel):
    """When the agent needs more information."""
    
    question: str = Field(description="The clarifying question to ask the user")
    missing_params: list[str] = Field(description="List of parameters that are missing")
