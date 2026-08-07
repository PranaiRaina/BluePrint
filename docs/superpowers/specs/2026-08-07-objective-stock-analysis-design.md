# Objective Stock Analysis Pipeline

**Date:** 2026-08-07
**Status:** Approved design, not yet implemented

## Problem

The stock analysis chatbot produces badly formatted output and issues investment
recommendations. Both come from the prompts, not the renderer — the frontend uses
`react-markdown` with `remark-gfm` correctly in the streaming path
(`LiveMessage.tsx:50`) and the final path (`ChatView.tsx:304`).

Observed failures and their causes:

| Symptom | Cause |
|---|---|
| Citations render as inline code, not links | `prompts.py:75` and `agent_engine.py:386` give the citation format *inside backticks*: ``Format: `[🔗](url)` ``. The model copies the backticks. |
| Citations point at `step_0_get_stock_data` | The prompt says to cite "links provided in the Tool Outputs", but tool outputs are keyed by step name and carry no URL for price data. The model cites the key. |
| Tables render as raw pipe characters | GFM requires a `\|---\|---\|` delimiter row. No table example appears in the prompt, and it asks for a `Source` column that holds a paragraph of prose. |
| Verdict says "Insufficient Analyst Coverage — No Recommendation" | The `MISSING DATA RULE` in `MAIN_AGENT_PROMPT` firing — the scoring machinery leaking through its own failure mode. |
| Every query gets a full report | The synthesis prompt mandates `Executive Summary (Table) → Deep Dive → Verdict` unconditionally, ignoring how narrow the question was. |

The synthesis instruction block is **duplicated verbatim** in
`_generate_recommendation` (`agent_engine.py:279`) and
`_generate_recommendation_stream` (`agent_engine.py:364`). Both copies are live:
single-intent chat uses the streaming one, while multi-intent queries route through
`orchestrator.py:214` and `/v1/agent/calculate` (`api.py:381`) to the non-streaming
one. The two copies have already drifted, and both carry garbled numbering (two
`3.`s, two `7.`s, and `agent_engine.py:300`–`301` are byte-identical duplicates).

## Goals

1. The bot never issues an investment recommendation in its own voice.
2. Output formatting is reliably valid GFM.
3. Narrow questions get narrow answers; broad questions get the full dive.
4. One source of truth for the synthesis prompt.

## Non-goals

- Structured/JSON output with frontend-rendered sections. Rejected: it costs
  token-by-token streaming, which is a real UX regression in live chat.
- Engine-rendered metrics components. Rejected for now as more surface area than
  the prompt fix needs. Revisit only if tables still break after this lands.
- Any change to ticker extraction, routing, or the Analytics tab's data flow.

## Design

### 1. One synthesis prompt

Extract the duplicated instruction block from `_generate_recommendation` and
`_generate_recommendation_stream` into a single `SYNTHESIS_PROMPT` in
`StockAgents/core/prompts.py`, with format slots for date, query, user context,
plan, tool results, and response mode. Both methods format the same template.

This also fixes the garbled numbering, since there is now one copy to renumber.

### 2. Persona is an analyst, not an advisor

`MAIN_AGENT_PROMPT` changes from "Senior Portfolio Manager … provide holistic,
actionable … advice" to an objective equity research analyst that reports what the
data shows and never advises.

Delete from `MAIN_AGENT_PROMPT`:
- `SCORING RULES` (the ±10 adjustment machinery)
- `RECOMMENDATION THRESHOLDS` (STRONG SELL / WEAK SELL / HOLD / MODERATE BUY / STRONG BUY)
- `MISSING DATA RULE` ("Insufficient Analyst Coverage")
- `Output format: "Score: X/100 — RECOMMENDATION"`

In `QUANT_SYSTEM_PROMPT`, "Base your recommendation heavily on the
analystConsensusScore" becomes "report the consensus as a datapoint". The
buy/sell band legend in its `YOUR DATA` section is removed.

### 3. Two response modes

`ExecutionPlan` gains a field:

```python
response_mode: Literal["direct", "comprehensive"] = "comprehensive"
```

One rule in `PLANNER_SYSTEM_PROMPT` sets it: `direct` when the user asked for one
specific thing (a price, a single metric, one news event), `comprehensive` when the
query is open-ended ("analyze X", "tell me about X", "deep dive"). The default is
`comprehensive` so a planner that omits the field degrades to today's behavior.

`SYNTHESIS_PROMPT` selects one of two instruction blocks on that value:

**direct** — Answer the question, plus the numbers that frame it. Two to three
sentences. No headers, no table, no sections.

> NVDA is trading at $219.22 as of 2026-08-06 15:35:55, up $7.28 (3.43%) from
> yesterday's close of $211.94. It has traded between $216.40 and $222.22 today.

**comprehensive** — A `Snapshot` table of key metrics, then themed prose sections:
Performance, Financials, Recent News, Volatility. No verdict section.

### 4. Formatting rules the model can follow

In `SYNTHESIS_PROMPT`:

- Include one literal, correctly formed GFM table, delimiter row included, cells
  holding only short values:

  ```
  | Metric | Value |
  |---|---|
  | Price | $219.22 |
  | Change | +3.43% |
  ```

- **Delete the `Source` column.** A column holding a paragraph of prose is what
  broke the table. Citations belong in the prose.
- Show citations plainly as `[domain](url)`, never inside backticks, with an
  explicit instruction: never wrap markdown links in backticks.
- Hard rule: cite only `http`/`https` URLs that literally appear in the tool
  outputs. Never cite step keys. Price and quote data is attributed in prose
  ("per the real-time quote"), not linked.

The same backtick fix applies to `RESEARCHER_SYSTEM_PROMPT` (`prompts.py:75`),
which has the identical ``ALWAYS format citations as `[🔗](url)` `` bug. Its
citations flow upward into the synthesis context, so leaving it backticked would
reintroduce code-span links through the researcher's output.

### 5. Analyst data survives as attributed fact

Permitted, because it is an observed market datapoint rather than the bot's own
view:

> 37 analysts cover NVDA — 36 rate it Buy or Strong Buy and 1 rates it Hold.
> 12-month price targets range from $250.00 to $500.00, averaging $308.69.
> ([google.com](https://www.google.com/finance/quote/NVDA:NASDAQ))

Forbidden: any score in the bot's own voice, buy/sell language as the bot's own
conclusion, any section titled Verdict or Recommendation.

When `analystConsensusScore` is `N/A` or missing, the analyst paragraph is omitted
silently. No "Insufficient Analyst Coverage" banner.

### 6. Analytics tab is unaffected, and pinned by a test

The Analytics tab (Navbar id `stocks`, label "Analytics") is fed by a path that
does not touch the synthesis text:

```
classify_intent  →  decision.extracted_tickers
                 →  SSE {"type": "tickers"}   (api.py:483)
                 →  agent.ts:197  →  onTickers  →  setExtractedTickers
                 →  StockAnalyticsView  →  GET /v1/agent/stock/{ticker}
```

The emit at `api.py:483` happens **before** the routing branch at `api.py:487` that
selects the stock pipeline, so both response modes populate Analytics identically.
`response_mode` lives inside the StockAgents planner, below that branch.

Add a regression test asserting the tickers event is emitted before routing, so a
future refactor cannot move it inside a branch.

### 7. Delete the dead chart chunk

`agent_engine.py:167-173` builds `charts_data` and streams a `{"type": "data"}`
chunk. The frontend has no handler for `data` — it falls into the silent `else` at
`agent.ts:202`. `StockAnalyticsView` fetches its own candles from
`/v1/agent/stock/{ticker}`.

Delete the `{"type": "data"}` yield and the `charts_data` accumulation in both
`run_workflow_stream` and `run_workflow`. **Keep** the `candles` fetch inside
`get_stock_data` — its result is returned in the step dict and lands in
`execution_results`, which is fed to the synthesizer as context. Only the unread
chart chunk goes.

## Files touched

| File | Change |
|---|---|
| `StockAgents/core/prompts.py` | Rewrite `MAIN_AGENT_PROMPT`, `QUANT_SYSTEM_PROMPT`, `RESEARCHER_SYSTEM_PROMPT` citation rule; add `SYNTHESIS_PROMPT`; add `response_mode` rule to `PLANNER_SYSTEM_PROMPT` |
| `StockAgents/services/agent_engine.py` | `ExecutionPlan.response_mode`; both synthesis methods use the shared prompt; delete the dead chart chunk |
| `tests/` | New tests per below |

## Testing

Output is LLM prose, so assertions target the prompts and the plumbing, not
generated text.

**Prompt invariants** (offline, no API calls) — import the prompt modules and assert:
- No `STRONG BUY`, `STRONG SELL`, `MODERATE BUY`, `WEAK SELL`, `RECOMMENDATION
  THRESHOLDS`, or `Score: X/100` in any prompt string.
- The citation example is not wrapped in backticks.
- The table example contains a `|---|` delimiter row.
- `SYNTHESIS_PROMPT` is referenced by both `_generate_recommendation` and
  `_generate_recommendation_stream`, so the duplication cannot silently return.

**Plan shape** (offline) — `ExecutionPlan` validates `response_mode`, rejects
values outside the two allowed, and defaults to `comprehensive` when absent.

**Planner behavior** (one live call each, marked `@pytest.mark.live`) —
"what is NVDA trading at" yields `direct`; "analyze NVDA" yields `comprehensive`.

**Ticker emission ordering** (offline) — assert the `tickers` yield precedes the
routing branch in `chat_stream`, so Analytics populates in both modes.

**Synthesis output smoke test** (one live call, marked `@pytest.mark.live`, manual)
— run the synthesizer against a canned tool-output fixture and assert the text
contains no `` `[ `` code-span link and no `step_N_` reference.

## Risks

- `direct` mode changes behavior for many existing queries. Eyeball a handful of
  real questions after it lands before assuming the planner classifies well.
- The planner is `gemini-2.5-flash` at `temperature=0.0`, so mode selection should
  be stable, but it is still a model judgment. The `comprehensive` default means
  misclassification degrades toward today's behavior rather than toward an
  unhelpfully terse answer.
- Prompt-only formatting enforcement leaves residual risk of a malformed table.
  If that persists, the fallback is engine-rendered metrics (non-goal above).
