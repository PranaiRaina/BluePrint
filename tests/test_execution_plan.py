"""ExecutionPlan.response_mode: how broad an answer the synthesizer writes."""

import pytest
from pydantic import ValidationError

from StockAgents.services.agent_engine import ExecutionPlan

MINIMAL_PLAN = {
    "reasoning": "user asked for a price",
    "steps": [
        {"tool": "get_stock_data", "args": {"ticker": "NVDA"}, "description": "quote"}
    ],
}


def test_response_mode_defaults_to_comprehensive():
    # A planner that omits the field must degrade to today's behavior, not to a
    # terse answer.
    plan = ExecutionPlan(**MINIMAL_PLAN)
    assert plan.response_mode == "comprehensive"


def test_response_mode_accepts_direct():
    plan = ExecutionPlan(**MINIMAL_PLAN, response_mode="direct")
    assert plan.response_mode == "direct"


def test_response_mode_rejects_anything_else():
    with pytest.raises(ValidationError):
        ExecutionPlan(**MINIMAL_PLAN, response_mode="verbose")


def test_planner_prompt_documents_response_mode():
    from StockAgents.core.prompts import PLANNER_SYSTEM_PROMPT

    assert "response_mode" in PLANNER_SYSTEM_PROMPT
    assert '"direct"' in PLANNER_SYSTEM_PROMPT
    assert '"comprehensive"' in PLANNER_SYSTEM_PROMPT


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,expected",
    [
        ("what is NVDA trading at", "direct"),
        ("analyze NVDA", "comprehensive"),
    ],
)
async def test_planner_picks_the_right_mode(query, expected):
    from StockAgents.services.agent_engine import agent_engine

    plan = await agent_engine.planner.create_plan(query, user_context={})
    assert plan.response_mode == expected
