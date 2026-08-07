# Objective Stock Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the stock chatbot from issuing investment recommendations, and make its output reliably valid Markdown scoped to how broad the user's question was.

**Architecture:** All five problems live in prompt strings, not in the renderer — the frontend already uses `react-markdown` + `remark-gfm` correctly. The work is: rewrite the persona prompts to remove scoring machinery, extract the synthesis instructions (currently duplicated verbatim across two live code paths) into one shared template, and add a `response_mode` field the planner sets so the synthesizer can branch between a short answer and a full dive.

**Tech Stack:** Python 3.13, Pydantic v2, FastAPI, `pytest` + `pytest-asyncio`, OpenAI-compatible client against `gemini-2.5-flash`.

## Global Constraints

- The bot never issues an investment recommendation in its own voice: no self-generated score, no buy/sell/hold call, no section titled Verdict or Recommendation.
- Analyst consensus data is permitted, but only as attributed, neutral market fact.
- Markdown links are never wrapped in backticks.
- Only `http://` or `https://` URLs appearing literally in tool outputs may be cited. Never execution step keys such as `step_0_get_stock_data`.
- No change to ticker extraction, routing, or the Analytics tab data flow.
- Tests run from the repository root: `/Users/abhinavsatheesh/Documents/hackathons/RoseHack26/RoseHacks2026`.
- Tests requiring a live LLM call are gated behind the `RUN_LIVE_TESTS` environment variable, matching the existing `skipif` convention in `tests/test_agent.py:34`.
- Run all commands with `uv run` (the project uses uv; a bare `pytest` will not resolve dependencies).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `StockAgents/core/prompts.py` | All prompt strings for the stock pipeline | Rewrite `MAIN_AGENT_PROMPT`, `QUANT_SYSTEM_PROMPT`, `RESEARCHER_SYSTEM_PROMPT`; add `SYNTHESIS_PROMPT`, `DIRECT_MODE_INSTRUCTIONS`, `COMPREHENSIVE_MODE_INSTRUCTIONS`; add `response_mode` rule to `PLANNER_SYSTEM_PROMPT` |
| `StockAgents/services/agent_engine.py` | Plan → execute → synthesize orchestration | Add `ExecutionPlan.response_mode`; both synthesis methods consume the shared prompt; delete the unread chart chunk |
| `tests/test_stock_prompts.py` | **New.** Offline invariants over prompt text | Created in Task 1, extended in Tasks 2–3 |
| `tests/test_execution_plan.py` | **New.** `ExecutionPlan` schema + planner behavior | Created in Task 4 |
| `tests/test_ticker_emission.py` | **New.** Pins the Analytics tab's data path | Created in Task 5 |
| `tests/test_synthesis_output.py` | **New.** Live end-to-end checks on rendered output | Created in Task 6 |

Prompts stay in one file because they are read together and edited together; splitting them per-agent would scatter a set of strings that must stay mutually consistent.

---

### Task 1: Remove recommendation machinery from the persona prompts

**Files:**
- Modify: `StockAgents/core/prompts.py` — the `MAIN_AGENT_PROMPT` and `QUANT_SYSTEM_PROMPT` assignments
- Test: `tests/test_stock_prompts.py` (create)

> Edit steps below name the constant to replace rather than a line range. Line
> numbers shift the moment the first edit lands, and tasks may be read out of
> order. Each replacement block is the complete new value of that constant.

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `MAIN_AGENT_PROMPT: str` and `QUANT_SYSTEM_PROMPT: str`, same names and module as before. Task 3 imports `MAIN_AGENT_PROMPT`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_stock_prompts.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: both tests FAIL. The first lists offenders including `StockAgents/core/prompts.py: 'STRONG BUY'`; the second fails on `"portfolio manager" not in lowered`.

- [ ] **Step 3: Rewrite `MAIN_AGENT_PROMPT`**

Replace the entire `MAIN_AGENT_PROMPT` assignment in `StockAgents/core/prompts.py` with:

```python
MAIN_AGENT_PROMPT = """
You are an equity research analyst. You report what the data shows.

### YOUR RESPONSIBILITIES:

1.  **Synthesize:** You receive reports from a Quantitative Analyst and a Market
    Researcher. Combine their findings into one coherent picture. Do not
    copy-paste them.

2.  **Verify:** Cross-reference the numbers (Quant) against the narrative
    (Researcher). If they disagree, say so and present both.

3.  **Attribute:** Every claim traces back to a tool output. If you do not have
    the data, say you do not have it.

4.  **Stay neutral:** You describe, you do not advise. You never tell the user
    whether to buy, sell, or hold, and you never produce a rating or a score of
    your own.

5.  **Tone:** Precise and plain. Avoid jargon; where a technical term is
    unavoidable, define it in a clause.

### CRITICAL CONSTRAINTS:
* If the real-time price differs from figures quoted in news articles, point out
  the discrepancy and give the real-time number precedence.
"""
```

- [ ] **Step 4: Rewrite `QUANT_SYSTEM_PROMPT`**

Replace the entire `QUANT_SYSTEM_PROMPT` assignment in `StockAgents/core/prompts.py` with:

```python
QUANT_SYSTEM_PROMPT = """
You are a Quantitative Analyst (The Quant).
Your existence is defined by data, probability, and mathematical models. You do
not care about news, rumors, or feelings.

### YOUR DATA:
You will receive the following metrics:
- **Volatility:** Annualized volatility from price history (via Wolfram)
- **Beta:** Stock sensitivity to market moves
- **Dividend Yield:** Annualized yield (Already in %, e.g., 0.5 means 0.5%). DO NOT MULTIPLY BY 100.
- **Analyst Consensus Score:** 0-100 scale aggregating Wall Street analyst
  ratings. This is a datapoint to report, not a verdict to translate.
- **Buy/Sell/Hold Counts:** Actual number of analysts recommending each

### YOUR INSTRUCTIONS:
1.  **Be Precise:** Specific numbers (e.g., "Annualized Volatility: 42.5%") are better than vague terms.
2.  **No Fluff:** Do not write introductory paragraphs. Go straight to the metrics.
3.  **Risk Focus:** Flag high Beta (>1.5) or high Volatility (>40%) as "High Risk."
4.  **Report Analyst Consensus:** State the consensus score and the underlying
    analyst counts as observed data. Do not convert them into a call to action,
    and do not add a rating of your own.
5.  **Output Format:** Return analysis in structured, bulleted format.
"""
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_stock_prompts.py StockAgents/core/prompts.py
git commit -m "feat(prompts): remove recommendation machinery from analyst personas"
```

---

### Task 2: Fix backticked citations in the researcher prompt

The researcher's citations flow upward into the synthesis context, so leaving this backticked would reintroduce code-span links through the researcher's output even after the synthesis prompt is fixed.

**Files:**
- Modify: `StockAgents/core/prompts.py` — the `RESEARCHER_SYSTEM_PROMPT` assignment
- Test: `tests/test_stock_prompts.py` (extend)

**Interfaces:**
- Consumes: `tests/test_stock_prompts.py` and its `REPO_ROOT` / `PROMPT_SOURCES` / `_read` helpers from Task 1.
- Produces: `RESEARCHER_SYSTEM_PROMPT: str`, same name and module.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stock_prompts.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: the two new tests FAIL. The first reports the researcher's
`` `[Source Title](url)` `` in `prompts.py`. (`agent_engine.py` has the same bug in
its two duplicated blocks, but it is not scanned until Task 3 deletes them.)

- [ ] **Step 3: Rewrite `RESEARCHER_SYSTEM_PROMPT`**

Replace the entire `RESEARCHER_SYSTEM_PROMPT` assignment in `StockAgents/core/prompts.py` with:

```python
RESEARCHER_SYSTEM_PROMPT = """
You are a Market Intelligence Researcher (The Scout).
Your job is to scan the external world for news, macro-economic trends, and sentiment.

### PRIVACY & SECURITY PROTOCOL (CRITICAL):
1.  **External Only:** You have NO access to the user's private portfolio, bank accounts, or identity.
2.  **Public Data:** Answer based on general market data, not specific user holdings.
3.  **Source Citing:** You must back up claims with data from the search results.
    Put a plain markdown link immediately after each claim, written exactly like
    this, with no backticks anywhere:

        [marketbeat.com](https://www.marketbeat.com/stocks/NASDAQ/NVDA)

    Never wrap a markdown link in backticks. Backticks turn the link into code
    and it stops working.

### YOUR INSTRUCTIONS:
* Focus on the "Why." If a stock is down, find the specific news event.
* Assess Sentiment: Is the market "Fearful" or "Greedy" regarding this specific asset?
* Be concise and factual. Report what happened; do not tell the reader what to do about it.
"""
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_stock_prompts.py StockAgents/core/prompts.py
git commit -m "fix(prompts): stop backticking citation examples in researcher prompt

The model copies the backticks verbatim, so links rendered as inline code."
```

---

### Task 3: Extract one shared synthesis prompt

Today this instruction block is duplicated verbatim in `_generate_recommendation` (`agent_engine.py:279-326`) and `_generate_recommendation_stream` (`agent_engine.py:364-411`). Both are live: single-intent chat uses the streaming copy; multi-intent queries reach the non-streaming copy via `ManagerAgent/orchestrator.py:214`, as does `/v1/agent/calculate` at `ManagerAgent/api.py:381`. The copies have already drifted.

This task introduces the mode instruction blocks but always selects `COMPREHENSIVE_MODE_INSTRUCTIONS`, preserving current behavior. Task 4 wires up the switch.

**Files:**
- Modify: `StockAgents/core/prompts.py` (append three new constants)
- Modify: `StockAgents/services/agent_engine.py` — the `_generate_recommendation` and `_generate_recommendation_stream` methods
- Test: `tests/test_stock_prompts.py` (extend)

**Interfaces:**
- Consumes: `MAIN_AGENT_PROMPT` from Task 1.
- Produces:
  - `SYNTHESIS_PROMPT: str` — a `str.format` template with exactly these fields: `current_date`, `query`, `user_context`, `plan`, `tool_outputs`, `mode_instructions`.
  - `DIRECT_MODE_INSTRUCTIONS: str`, `COMPREHENSIVE_MODE_INSTRUCTIONS: str` — substituted into `mode_instructions`. Task 4 selects between them.

- [ ] **Step 1: Write the failing test**

First, widen the scan from Tasks 1–2 to cover `agent_engine.py`, whose duplicated
blocks this task deletes. Change `PROMPT_SOURCES` in `tests/test_stock_prompts.py`
to:

```python
PROMPT_SOURCES = [
    REPO_ROOT / "StockAgents" / "core" / "prompts.py",
    REPO_ROOT / "StockAgents" / "services" / "agent_engine.py",
]
```

Then append to the same file:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: the four new tests FAIL with `ImportError: cannot import name
'SYNTHESIS_PROMPT'` (first three) and an `AssertionError` on the fourth.
Additionally, the two tests from Tasks 1–2 now FAIL against `agent_engine.py`,
which still holds the duplicated blocks. All of these go green in Step 7.

- [ ] **Step 3: Append the three constants to `prompts.py`**

Add at the end of the `# --- STOCK AGENTS ---` section, directly after `RESEARCHER_SYSTEM_PROMPT` and before the `# --- PLANNER PROMPT ---` comment:

```python
DIRECT_MODE_INSTRUCTIONS = """
## RESPONSE SHAPE: DIRECT

The user asked for one specific thing. Answer it and stop.

- Two to three sentences.
- Include the numbers that frame the answer: for a price, the change, the
  previous close, and the day's range; for any other metric, the comparable
  figure that gives it meaning.
- No headings. No tables. No bullet lists. No sections.

Example of the right length and shape:

    NVDA is trading at $219.22 as of 2026-08-06 15:35:55, up $7.28 (3.43%) from
    yesterday's close of $211.94. It has traded between $216.40 and $222.22 today.
"""

COMPREHENSIVE_MODE_INSTRUCTIONS = """
## RESPONSE SHAPE: COMPREHENSIVE

The user asked an open-ended question. Give the full picture.

Open with a Snapshot table, then write themed prose sections. Include only the
sections you actually have data for: Performance, Financials, Recent News,
Volatility.

The Snapshot table MUST be valid GitHub-Flavored Markdown. Copy this structure
exactly, including the delimiter row, which is required:

| Metric | Value |
|---|---|
| Price | $219.22 |
| Change | +$7.28 (+3.43%) |
| Day Range | $216.40 - $222.22 |
| Market Cap | $5.31T |
| P/E | 33.57 |

Table rules:
- The delimiter row goes directly under the header. Without it the table renders
  as literal pipe characters.
- Cells hold short values only: a number, a range, a percentage. Never a
  sentence, never a citation, never a paragraph.
- Two columns exactly. Do not add a column for sources.

After the table, write prose under `##` headings. Citations belong in the prose,
never in a table cell.
"""

SYNTHESIS_PROMPT = """
Current Date: {current_date}
User Query: {query}

User Portfolio Context:
{user_context}

Execution Plan:
{plan}

Tool Outputs:
{tool_outputs}

## WHAT YOU ARE

You report what the data shows. You are not an advisor. You never tell the user
what to do with their money.

## ANSWERING

1. If the user asked about their own holdings ("how many", "do I own"), answer
   that first from the User Portfolio Context above.
2. Answer the question that was actually asked, using the Tool Outputs as evidence.
3. State the Current Date given above when quoting prices or market status.
4. Never mention a knowledge cutoff.
5. If a tool returned an error or missing data, say so plainly and move on. Never
   invent a number.

{mode_instructions}

## CITATIONS

- Write links as plain markdown, like this:
  [marketbeat.com](https://www.marketbeat.com/stocks/NASDAQ/NVDA)
- NEVER wrap a markdown link in backticks. Backticks turn it into code and the
  link stops working.
- Only cite URLs beginning with http:// or https:// that appear literally in the
  Tool Outputs above.
- NEVER cite an execution step key such as step_0_get_stock_data. Those are
  internal identifiers, not sources.
- Price and quote figures come from the real-time feed and have no URL. Attribute
  them in prose ("per the real-time quote") rather than linking them.

## ANALYST DATA

You may report what Wall Street analysts say, as an observed fact about the
market, attributed and neutral:

    37 analysts cover NVDA - 36 rate it "buy" or "strong buy" and 1 rates it
    "hold". Their 12-month targets range from $250.00 to $500.00, averaging
    $308.69.

You may NOT:
- Produce a score or rating of your own.
- Say whether the stock is a buy, a sell, or a hold in your own voice.
- Write a section titled Verdict, Recommendation, or Conclusion.
- Tell the user what to do.

If analyst data is absent or "N/A", omit it entirely. Do not announce its absence.

## OUTPUT

Never include a disclaimer or an "I am an AI" statement. The interface adds one.
"""
```

- [ ] **Step 4: Rewrite `_generate_recommendation` to use the shared prompt**

In `StockAgents/services/agent_engine.py`, replace the whole `_generate_recommendation`
method so it reads:

```python
    async def _generate_recommendation(
        self,
        query: str,
        plan: ExecutionPlan,
        results: Dict,
        user_context: Dict[str, Any] = {},
    ) -> str:
        """
        Synthesize results into a final answer.
        """
        from datetime import datetime

        system_prompt = (
            MAIN_AGENT_PROMPT
            + "\n\nACT AS A SYNTHESIZER. Combine the tool outputs into a coherent response matching the user's intent."
        )

        user_msg = SYNTHESIS_PROMPT.format(
            current_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            query=query,
            user_context=json.dumps(user_context, indent=2, default=str),
            plan=json.dumps(plan.dict(), indent=2),
            tool_outputs=json.dumps(results, indent=2, default=str),
            mode_instructions=COMPREHENSIVE_MODE_INSTRUCTIONS,
        )

        try:
            response = await llm_service.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating recommendation: {e}. Raw Data: {str(results)}"
```

Note: `.format()` parses only the template, never the substituted values, so the
JSON braces in `plan` and `tool_outputs` are safe.

- [ ] **Step 5: Rewrite `_generate_recommendation_stream` the same way**

Replace the whole body of `_generate_recommendation_stream` so the method reads:

```python
    async def _generate_recommendation_stream(
        self,
        query: str,
        plan: ExecutionPlan,
        results: Dict,
        user_context: Dict[str, Any] = {},
    ):
        """
        Streamed synthesis. Shares SYNTHESIS_PROMPT with _generate_recommendation.
        """
        from datetime import datetime

        system_prompt = (
            MAIN_AGENT_PROMPT
            + "\n\nACT AS A SYNTHESIZER. Combine the tool outputs into a coherent response matching the user's intent."
        )

        user_msg = SYNTHESIS_PROMPT.format(
            current_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            query=query,
            user_context=json.dumps(user_context, indent=2, default=str),
            plan=json.dumps(plan.dict(), indent=2),
            tool_outputs=json.dumps(results, indent=2, default=str),
            mode_instructions=COMPREHENSIVE_MODE_INSTRUCTIONS,
        )

        try:
            stream = await llm_service.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "token", "content": chunk.choices[0].delta.content}
                    await asyncio.sleep(0)  # Force buffer flush

        except Exception as e:
            yield {"type": "token", "content": f"Error generating recommendation: {e}."}
```

- [ ] **Step 6: Update the import at the top of `agent_engine.py`**

Change the prompts import from:

```python
from StockAgents.core.prompts import MAIN_AGENT_PROMPT, PLANNER_SYSTEM_PROMPT
```

to:

```python
from StockAgents.core.prompts import (
    COMPREHENSIVE_MODE_INSTRUCTIONS,
    MAIN_AGENT_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT,
)
```

`DIRECT_MODE_INSTRUCTIONS` is deliberately not imported yet — nothing references
it until Task 4, and importing it here would trip ruff's F401.

Verify with:

```bash
uv run ruff check StockAgents/services/agent_engine.py
```

Expected: no F401 findings.

- [ ] **Step 7: Run the full prompt test file**

```bash
uv run pytest tests/test_stock_prompts.py -v
```

Expected: all tests pass, including `test_no_backticked_markdown_links_in_prompt_sources`, which was failing on `agent_engine.py` at the end of Task 2.

- [ ] **Step 8: Verify the module still imports**

```bash
uv run python -c "from StockAgents.services.agent_engine import agent_engine; print('ok')"
```

Expected: `ok`.

- [ ] **Step 9: Commit**

```bash
git add tests/test_stock_prompts.py StockAgents/core/prompts.py StockAgents/services/agent_engine.py
git commit -m "refactor(synthesis): extract one shared prompt from two drifted copies

Both copies were live: streaming chat used one, multi-intent and
/v1/agent/calculate used the other. Adds the GFM table example and
unbackticked citation rules in the process."
```

---

### Task 4: Scope the answer to the question with `response_mode`

**Files:**
- Modify: `StockAgents/services/agent_engine.py` — the `ExecutionPlan` class and the two synthesis methods from Task 3
- Modify: `StockAgents/core/prompts.py` (`PLANNER_SYSTEM_PROMPT`)
- Test: `tests/test_execution_plan.py` (create)

**Interfaces:**
- Consumes: `SYNTHESIS_PROMPT`, `DIRECT_MODE_INSTRUCTIONS`, `COMPREHENSIVE_MODE_INSTRUCTIONS` from Task 3.
- Produces: `ExecutionPlan.response_mode: Literal["direct", "comprehensive"]`, defaulting to `"comprehensive"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_execution_plan.py`:

```python
"""ExecutionPlan.response_mode: how broad an answer the synthesizer writes."""

import os

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


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS"), reason="RUN_LIVE_TESTS not set (makes an API call)"
)
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_execution_plan.py -v
```

Expected: all four offline tests FAIL, the live tests SKIP.

`test_response_mode_rejects_anything_else` fails because Pydantic v2 defaults to
`extra="ignore"` — with no such field on the model, passing `response_mode="verbose"`
raises nothing, so `pytest.raises(ValidationError)` fails. It starts passing for
the right reason once the `Literal` field exists in Step 3.

- [ ] **Step 3: Add the field to `ExecutionPlan`**

In `StockAgents/services/agent_engine.py`, change the `typing` import from:

```python
from typing import Dict, Any, List
```

to:

```python
from typing import Any, Dict, List, Literal
```

Then replace the `ExecutionPlan` class with:

```python
class ExecutionPlan(BaseModel):
    reasoning: str = Field(..., description="Reasoning behind the plan")
    steps: List[PlannerStep] = Field(
        ..., description="Ordered list of steps to execute"
    )
    response_mode: Literal["direct", "comprehensive"] = Field(
        "comprehensive",
        description=(
            "'direct' when the user asked for one specific thing (a price, one "
            "metric, one news event). 'comprehensive' when the query is "
            "open-ended. Defaults to comprehensive so a planner that omits the "
            "field degrades to the fuller answer."
        ),
    )
```

- [ ] **Step 4: Teach the planner to set it**

In `StockAgents/core/prompts.py`, in `PLANNER_SYSTEM_PROMPT`, add this line to the
end of the `RULES:` block (directly after the `For generic "Analyze X"` line):

```
- Set "response_mode" to "direct" when the user asked for one specific thing: a price, a single metric, or one news event. Set it to "comprehensive" when the query is open-ended, such as "analyze X", "tell me about X", "deep dive on X", or "how is X doing".
```

Then replace the JSON schema block at the end of the same prompt with:

```
Return JSON matching this schema:
{{
    "reasoning": "string",
    "response_mode": "direct" | "comprehensive",
    "steps": [
        {{"tool": "tool_name", "args": {{...}}, "description": "string"}}
    ]
}}
```

The doubled braces are required: this string is passed through `.format()` in
`LLMPlanner.create_plan`.

- [ ] **Step 5: Branch the synthesis methods on the mode**

First add the now-needed import to `StockAgents/services/agent_engine.py`:

```python
from StockAgents.core.prompts import (
    COMPREHENSIVE_MODE_INSTRUCTIONS,
    DIRECT_MODE_INSTRUCTIONS,
    MAIN_AGENT_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT,
)
```

Then in both `_generate_recommendation` and `_generate_recommendation_stream`, replace
this line:

```python
            mode_instructions=COMPREHENSIVE_MODE_INSTRUCTIONS,
```

with:

```python
            mode_instructions=(
                DIRECT_MODE_INSTRUCTIONS
                if plan.response_mode == "direct"
                else COMPREHENSIVE_MODE_INSTRUCTIONS
            ),
```

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/test_execution_plan.py tests/test_stock_prompts.py -v
```

Expected: all offline tests pass; the live parametrized test skips (2 skipped).

- [ ] **Step 7: Run the live planner check**

```bash
RUN_LIVE_TESTS=1 uv run pytest tests/test_execution_plan.py -v -k planner_picks
```

Expected: 2 passed. If `analyze NVDA` comes back as `direct`, the planner rule
needs sharpening — do not weaken the test to match. Add the failing phrasing to
the rule's example list in Step 4 and re-run.

- [ ] **Step 8: Commit**

```bash
git add tests/test_execution_plan.py StockAgents/core/prompts.py StockAgents/services/agent_engine.py
git commit -m "feat(planner): add response_mode so narrow questions get narrow answers"
```

---

### Task 5: Pin the Analytics data path and delete the unread chart chunk

The Analytics tab (Navbar id `stocks`, label "Analytics") is fed by
`classify_intent` → `decision.extracted_tickers` → the SSE `tickers` event at
`ManagerAgent/api.py:483` → `frontend/src/services/agent.ts:197` →
`setExtractedTickers` → `StockAnalyticsView`, which fetches its own data from
`/v1/agent/stock/{ticker}`.

That emit happens *before* the routing branch at `ManagerAgent/api.py:487`, which
is why both response modes populate Analytics identically. The test below pins
that ordering so a future refactor cannot move the emit inside a branch.

**Files:**
- Modify: `StockAgents/services/agent_engine.py` (delete the chart chunk in both workflow methods)
- Test: `tests/test_ticker_emission.py` (create)

**Interfaces:**
- Consumes: nothing. Independent of Tasks 1–4.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ticker_emission.py`:

```python
"""The Analytics tab depends on tickers being emitted before routing.

If the `tickers` SSE event ever moves inside the routing branch, the Analytics
tab silently stops populating for whichever route does not emit it. This is
cheap to break and invisible in manual testing of a single query type.
"""

import inspect


def test_tickers_are_emitted_before_the_routing_branch():
    from ManagerAgent.api import chat_stream

    source = inspect.getsource(chat_stream)

    tickers_emit = source.index("'type': 'tickers'")
    routing_branch = source.index("async def run_stream")

    assert tickers_emit < routing_branch, (
        "The tickers SSE event must be emitted before run_stream is defined, so "
        "every route populates the Analytics tab. Moving it inside a branch "
        "breaks Analytics for the other branches."
    )


def test_engine_does_not_emit_the_unread_chart_chunk():
    import inspect

    from StockAgents.services.agent_engine import AgentEngine

    for method in (AgentEngine.run_workflow_stream, AgentEngine.run_workflow):
        source = inspect.getsource(method)
        assert '"type": "data"' not in source, (
            f"{method.__name__} still emits a 'data' chunk. The frontend has no "
            "handler for it (agent.ts drops it in the silent else branch) and "
            "StockAnalyticsView fetches its own candles."
        )
        assert "charts_data" not in source, (
            f"{method.__name__} still accumulates charts_data, which nothing reads."
        )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_ticker_emission.py -v
```

Expected: `test_tickers_are_emitted_before_the_routing_branch` PASSES (the
invariant already holds — this test exists to keep it holding).
`test_engine_does_not_emit_the_unread_chart_chunk` FAILS on both methods.

- [ ] **Step 3: Confirm nothing consumes the chunk before deleting it**

```bash
grep -rn "'data'" frontend/src/services/agent.ts
grep -rn "charts" frontend/src --include=*.ts --include=*.tsx
```

Expected: `agent.ts` handles `token`, `status`, `tickers`, and `error` only —
there is no `data` branch. If either grep shows a real consumer, STOP and report
it rather than deleting.

- [ ] **Step 4: Delete the chart chunk from `run_workflow_stream`**

In `StockAgents/services/agent_engine.py`, find and delete this block inside `run_workflow_stream`:

```python
        # Yield Chart Data if available
        if charts_data:
            import json
            yield {
                "type": "data",
                "content": json.dumps({"charts": charts_data})
            }
```

Then delete the `charts_data = {}` initialization near the top of
`run_workflow_stream`, and the two lines inside its `execute_step` that write to
it:

```python
                    if candles.get("s") == "ok":
                        charts_data[ticker] = candles.get("c", [])
```

Keep the `candles` fetch itself and keep `return {"quote": quote, "candles": candles}` —
that result lands in `execution_results` and is fed to the synthesizer as context.

- [ ] **Step 5: Delete the same accumulation from `run_workflow`**

In the non-streaming `run_workflow`, delete its `charts_data = {}` initialization
and these two lines inside its `execute_step`:

```python
                    if candles.get("s") == "ok":
                        charts_data[ticker] = candles.get("c", [])
```

Then change its return block from:

```python
        return {
            "intent": "dynamic_plan",
            "plan": plan.dict(),
            "analysis": {
                "charts": charts_data,  # For frontend visualization
                "results": execution_results,
            },
            "recommendation": recommendation,
        }
```

to:

```python
        return {
            "intent": "dynamic_plan",
            "plan": plan.dict(),
            "analysis": {
                "results": execution_results,
            },
            "recommendation": recommendation,
        }
```

- [ ] **Step 6: Confirm no caller reads `analysis.charts`**

```bash
grep -rn "\[.charts.\]\|\.charts" ManagerAgent/ StockAgents/ frontend/src --include=*.py --include=*.ts --include=*.tsx
```

Expected: no hits outside the lines you just deleted. If a caller appears, STOP
and report it.

- [ ] **Step 7: Run the tests**

```bash
uv run pytest tests/test_ticker_emission.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Run the whole new suite together**

```bash
uv run pytest tests/test_stock_prompts.py tests/test_execution_plan.py tests/test_ticker_emission.py -v
```

Expected: all pass, 2 skipped (the live planner tests).

- [ ] **Step 9: Commit**

```bash
git add tests/test_ticker_emission.py StockAgents/services/agent_engine.py
git commit -m "chore(engine): drop unread chart chunk, pin ticker emission ordering

The frontend has no handler for the 'data' SSE chunk and StockAnalyticsView
fetches its own candles."
```

---

### Task 6: End-to-end check against a canned fixture

Everything above asserts on prompts and plumbing. This task checks the thing the
user actually sees: that the model's rendered output is free of the two
formatting bugs. It costs one API call and is gated behind `RUN_LIVE_TESTS`.

**Files:**
- Test: `tests/test_synthesis_output.py` (create)

**Interfaces:**
- Consumes: `ExecutionPlan` and `agent_engine` from Tasks 3–4.
- Produces: nothing.

- [ ] **Step 1: Write the test**

Create `tests/test_synthesis_output.py`:

```python
"""One live call each, checking rendered output for the two formatting bugs.

Gated behind RUN_LIVE_TESTS because these hit the LLM. Prose varies run to run,
so the assertions target only structural properties that must always hold.
"""

import os
import re

import pytest

from StockAgents.services.agent_engine import ExecutionPlan, agent_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS"), reason="RUN_LIVE_TESTS not set (makes an API call)"
)

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
```

- [ ] **Step 2: Run it**

```bash
RUN_LIVE_TESTS=1 uv run pytest tests/test_synthesis_output.py -v
```

Expected: 4 passed. A failure here means a prompt rule is not landing — the
failure message prints the full model output, so read it and tighten the
corresponding rule in `SYNTHESIS_PROMPT` rather than relaxing the assertion.

- [ ] **Step 3: Confirm the offline suite is unaffected**

```bash
uv run pytest tests/test_stock_prompts.py tests/test_execution_plan.py tests/test_ticker_emission.py tests/test_synthesis_output.py -v
```

Expected: offline tests pass; 6 skipped (2 live planner + 4 live synthesis).

- [ ] **Step 4: Commit**

```bash
git add tests/test_synthesis_output.py
git commit -m "test: end-to-end synthesis checks for formatting and neutrality"
```

---

## Manual verification

After Task 6, run the app and check real queries — the automated tests cannot
judge whether an answer reads well.

```bash
PYTHONPATH=. uv run uvicorn ManagerAgent.api:app --host 127.0.0.1 --port 8001
```

Ask each of these in the chat UI and confirm:

| Query | Expect |
|---|---|
| `what is NVDA trading at` | Two or three sentences. No table, no headings. Analytics tab shows NVDA. |
| `analyze NVDA` | Snapshot table renders as a real table. Themed sections. No Verdict. Analytics tab shows NVDA. |
| `why is TSLA down` | News-focused answer with clickable source links, not grey code spans. Analytics tab shows TSLA. |
| `analyze a company with no analyst coverage` | Analyst paragraph simply absent — no "Insufficient Analyst Coverage" banner. |

The spec flags that `direct` mode changes behavior for many existing queries, so
this pass matters more than usual.

## Rollback

Every task is a single commit touching prompt strings, one Pydantic field, and
tests. `git revert` of any individual task commit is safe and independent, except
that Task 4 depends on Task 3's shared prompt — revert Task 4 before Task 3.
