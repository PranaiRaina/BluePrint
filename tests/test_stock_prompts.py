"""Invariants over the stock pipeline's prompt text.

These assertions are case-sensitive on purpose. The uppercase tokens below are
the recommendation-threshold machinery we deleted; lowercase rating labels
("36 rate it 'buy'") are legitimate reported analyst data and must stay legal.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Task 3 appends agent_engine.py here, once the duplicated synthesis blocks that
# still live in it have been deleted.
PROMPT_SOURCES = [
    REPO_ROOT / "StockAgents" / "core" / "prompts.py",
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


import re

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
