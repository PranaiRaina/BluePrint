"""One live call each, checking rendered output for the two formatting bugs.

Gated behind RUN_LIVE_TESTS because these hit the LLM. Prose varies run to run,
so the assertions target only structural properties that must always hold.
"""

import re

import pytest

from StockAgents.services.agent_engine import ExecutionPlan, agent_engine

# Every test here calls a real external API. See tests/conftest.py.
pytestmark = pytest.mark.live

TOOL_OUTPUTS = {
    "step_0_get_stock_data": {
        "quote": {
            "c": 219.22,
            "d": 7.28,
            "dp": 3.43,
            "pc": 211.94,
            "h": 222.22,
            "l": 216.40,
        }
    },
    "step_1_news_research": {
        "analysis": (
            "NVIDIA reported Q1 EPS of $1.87 versus consensus of $1.76 "
            "[marketbeat.com](https://www.marketbeat.com/stocks/NASDAQ/NVDA)."
        )
    },
}

BACKTICKED_LINK = re.compile(r"`\[[^\]]*\]\(")
STEP_KEY = re.compile(r"step_\d+_")


async def _synthesize(mode: str) -> str:
    plan = ExecutionPlan(
        reasoning="test fixture",
        response_mode=mode,
        steps=[
            {
                "tool": "get_stock_data",
                "args": {"ticker": "NVDA"},
                "description": "quote",
            }
        ],
    )
    return await agent_engine._generate_recommendation(
        "how is NVDA doing", plan, TOOL_OUTPUTS, user_context={}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["direct", "comprehensive"])
async def test_output_has_no_backticked_links_or_step_keys(mode):
    text = await _synthesize(mode)

    assert not BACKTICKED_LINK.search(text), f"backticked link in output:\n{text}"
    assert not STEP_KEY.search(text), f"internal step key cited in output:\n{text}"


@pytest.mark.asyncio
async def test_output_carries_no_recommendation():
    text = (await _synthesize("comprehensive")).lower()

    for banned in ("## verdict", "## recommendation", "strong buy", "we recommend"):
        assert banned not in text, f"{banned!r} appeared in output:\n{text}"


@pytest.mark.asyncio
async def test_direct_mode_stays_short():
    text = await _synthesize("direct")

    assert "\n#" not in text, f"direct mode used a heading:\n{text}"
    assert "|---" not in text, f"direct mode used a table:\n{text}"
