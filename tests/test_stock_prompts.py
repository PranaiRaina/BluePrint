"""Invariants over the stock pipeline's prompt text.

These assertions are case-sensitive on purpose. The uppercase tokens below are
the recommendation-threshold machinery we deleted; lowercase rating labels
("36 rate it 'buy'") are legitimate reported analyst data and must stay legal.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROMPT_SOURCES = [
    REPO_ROOT / "StockAgents" / "core" / "prompts.py",
    REPO_ROOT / "StockAgents" / "services" / "agent_engine.py",
]

# Exact strings from the deleted scoring/threshold machinery.
FORBIDDEN = [
    "STRONG BUY",
    "STRONG SELL",
    "MODERATE BUY",
    "WEAK SELL",
    "RECOMMENDATION THRESHOLDS",
    "Score: X/100",
    "Insufficient Analyst Coverage",
    "Base your recommendation",
    "SCORING RULES",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_recommendation_machinery_in_prompt_sources():
    offenders = []
    for path in PROMPT_SOURCES:
        text = _read(path)
        for phrase in FORBIDDEN:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase!r}")
    assert not offenders, (
        "Recommendation machinery is back in the prompts:\n  "
        + "\n  ".join(offenders)
    )


def test_main_agent_prompt_forbids_advising():
    from StockAgents.core.prompts import MAIN_AGENT_PROMPT

    lowered = MAIN_AGENT_PROMPT.lower()
    assert "you do not advise" in lowered or "do not advise" in lowered
    assert "portfolio manager" not in lowered


# A markdown link wrapped in backticks: `[label](url)
BACKTICKED_LINK = re.compile(r"`\[[^\]]*\]\(")


def test_no_backticked_markdown_links_in_prompt_sources():
    offenders = []
    for path in PROMPT_SOURCES:
        for match in BACKTICKED_LINK.finditer(_read(path)):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)!r}")
    assert not offenders, (
        "A markdown link is wrapped in backticks. The model copies the backticks "
        "verbatim and the link renders as inline code:\n  " + "\n  ".join(offenders)
    )


def test_researcher_prompt_warns_against_backticks():
    from StockAgents.core.prompts import RESEARCHER_SYSTEM_PROMPT

    assert "backtick" in RESEARCHER_SYSTEM_PROMPT.lower()


SYNTHESIS_FIELDS = {
    "current_date",
    "query",
    "user_context",
    "plan",
    "tool_outputs",
    "mode_instructions",
}


def test_synthesis_prompt_has_exactly_the_expected_format_fields():
    import string

    from StockAgents.core.prompts import SYNTHESIS_PROMPT

    found = {
        field
        for _, field, _, _ in string.Formatter().parse(SYNTHESIS_PROMPT)
        if field
    }
    assert found == SYNTHESIS_FIELDS


def test_comprehensive_mode_shows_a_valid_gfm_table():
    from StockAgents.core.prompts import COMPREHENSIVE_MODE_INSTRUCTIONS

    # GFM requires a delimiter row directly under the header, or the whole
    # table renders as literal pipe characters.
    assert "|---|---|" in COMPREHENSIVE_MODE_INSTRUCTIONS
    assert "Source" not in COMPREHENSIVE_MODE_INSTRUCTIONS


def test_direct_mode_forbids_structure():
    from StockAgents.core.prompts import DIRECT_MODE_INSTRUCTIONS

    lowered = DIRECT_MODE_INSTRUCTIONS.lower()
    assert "no headings" in lowered
    assert "no tables" in lowered


def test_both_synthesis_methods_use_the_shared_prompt():
    import inspect

    from StockAgents.services.agent_engine import AgentEngine

    for method in (
        AgentEngine._generate_recommendation,
        AgentEngine._generate_recommendation_stream,
    ):
        source = inspect.getsource(method)
        assert "SYNTHESIS_PROMPT.format(" in source, (
            f"{method.__name__} does not use the shared prompt - the duplication is back"
        )
