"""The rewriter narrows the query and date-scopes it, in one call."""

import os

import pytest
from langchain_core.runnables import RunnableLambda

import RAG_PIPELINE.src.graph as graph
from RAG_PIPELINE.src.graph import RewrittenQuery

MIXED = "tell me about my bank payments last month and what AAPL is trading at"


def fake_rewriter(monkeypatch, reply, seen=None):
    """Replace the structured rewriter chain with a canned response."""

    def respond(messages):
        if seen is not None:
            seen.append(str(messages))
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(graph, "rephrase_chain", RunnableLambda(respond))


def test_narrows_the_search_query_and_leaves_the_question_alone(monkeypatch):
    fake_rewriter(monkeypatch, RewrittenQuery(search_query="bank payments last month"))

    out = graph.rephrase_query({"question": MIXED, "history": ""})

    assert out["search_query"] == "bank payments last month"
    # generate() answers state["question"], so the market half must survive.
    assert "question" not in out


def test_runs_without_history(monkeypatch):
    """The regression this exists for: it used to return early on turn one."""
    called = []
    fake_rewriter(
        monkeypatch, RewrittenQuery(search_query="bank payments"), seen=called
    )

    graph.rephrase_query({"question": MIXED, "history": ""})

    assert called, "rewriter skipped the model on a first-turn message"


def test_history_reaches_the_prompt(monkeypatch):
    seen = []
    fake_rewriter(
        monkeypatch, RewrittenQuery(search_query="Meridian April"), seen=seen
    )

    graph.rephrase_query(
        {"question": "what about the same month?", "history": "User asked about April"}
    )

    assert "User asked about April" in seen[0]


def test_todays_date_reaches_the_prompt(monkeypatch):
    """"last month" is unresolvable without it."""
    seen = []
    fake_rewriter(monkeypatch, RewrittenQuery(search_query="x"), seen=seen)

    graph.rephrase_query({"question": "what did I spend last month?", "history": ""})

    from datetime import date

    assert date.today().isoformat() in seen[0]


def test_falls_back_to_the_raw_message_when_the_model_returns_nothing(monkeypatch):
    fake_rewriter(monkeypatch, RewrittenQuery(search_query="   "))

    out = graph.rephrase_query({"question": MIXED, "history": ""})

    assert out["search_query"] == MIXED


def test_falls_back_to_the_raw_message_when_the_model_errors(monkeypatch):
    fake_rewriter(
        monkeypatch, ConnectionResetError(54, "Connection reset by peer")
    )

    out = graph.rephrase_query({"question": MIXED, "history": ""})

    assert out["search_query"] == MIXED
    # An unparsed query must not carry a date filter it never established.
    assert out["period_from"] is None
    assert out["period_to"] is None


# --- date scoping -----------------------------------------------------------


def test_a_specific_month_becomes_a_range(monkeypatch):
    fake_rewriter(
        monkeypatch,
        RewrittenQuery(
            search_query="rent", period_from=202503, period_to=202503
        ),
    )

    out = graph.rephrase_query({"question": "my rent in March 2025?", "history": ""})

    assert (out["period_from"], out["period_to"]) == (202503, 202503)


def test_no_date_mentioned_means_no_filter(monkeypatch):
    """The common case. A filter they did not ask for can only lose documents."""
    fake_rewriter(monkeypatch, RewrittenQuery(search_query="rent"))

    out = graph.rephrase_query({"question": "what is my rent?", "history": ""})

    assert out["period_from"] is None
    assert out["period_to"] is None


def test_a_half_range_is_discarded(monkeypatch):
    """One bound alone would silently become an open-ended filter."""
    fake_rewriter(
        monkeypatch, RewrittenQuery(search_query="rent", period_from=202503)
    )

    out = graph.rephrase_query({"question": "rent since March?", "history": ""})

    assert out["period_from"] is None
    assert out["period_to"] is None


def test_a_backwards_range_is_repaired(monkeypatch):
    fake_rewriter(
        monkeypatch,
        RewrittenQuery(
            search_query="rent", period_from=202505, period_to=202503
        ),
    )

    out = graph.rephrase_query({"question": "rent March to May?", "history": ""})

    assert (out["period_from"], out["period_to"]) == (202503, 202505)


# --- live -------------------------------------------------------------------

live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1"
)


@pytest.mark.live
@live
def test_live_drops_the_market_half():
    out = graph.rephrase_query({"question": MIXED, "history": ""})
    assert "aapl" not in out["search_query"].lower()
    assert "bank payments" in out["search_query"].lower()


@pytest.mark.live
@live
def test_live_keeps_prose_documents_not_just_statements():
    out = graph.rephrase_query(
        {
            "question": "what does my KYC paperwork say about source of funds, "
            "and is the market up today?",
            "history": "",
        }
    )
    narrowed = out["search_query"].lower()
    assert "source of funds" in narrowed
    assert "market up today" not in narrowed


@pytest.mark.live
@live
def test_live_keeps_every_thing_the_user_asked_about():
    out = graph.rephrase_query(
        {
            "question": "show me my rent payments, my brokerage fees, and my "
            "paycheck deposits last quarter",
            "history": "",
        }
    )
    narrowed = out["search_query"].lower()
    assert "rent" in narrowed
    assert "brokerage fees" in narrowed
    assert "paycheck" in narrowed or "deposit" in narrowed


@pytest.mark.live
@live
def test_live_no_time_in_the_question_means_no_filter():
    out = graph.rephrase_query({"question": "what is my card's APR?", "history": ""})
    assert out["period_from"] is None
    assert out["period_to"] is None


@pytest.mark.live
@live
def test_live_an_explicit_month_is_scoped():
    out = graph.rephrase_query(
        {"question": "what was my rent in March 2025?", "history": ""}
    )
    assert (out["period_from"], out["period_to"]) == (202503, 202503)


@pytest.mark.live
@live
def test_live_all_time_means_no_filter():
    out = graph.rephrase_query(
        {"question": "summarize my bank statements across all time", "history": ""}
    )
    assert out["period_from"] is None
    assert out["period_to"] is None
