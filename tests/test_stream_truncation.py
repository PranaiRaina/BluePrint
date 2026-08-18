"""A synthesis that dies mid-response must not be presented as a finished answer.

Measured from this machine: roughly one STREAMING call in three has its SSE
connection killed part-way through. Going direct to Google with httpx shows the
truth - a ReadError - but litellm swallows it and ends the iterator reporting
finish_reason "stop". A reply cut off mid-word was therefore indistinguishable
from a complete one, and retrying could not help because nothing below reported
a failure.

So synthesis no longer streams from the model. It requests the whole answer,
which fails loudly when the connection drops, and replays it to the client in
chunks. These tests pin that: nothing reaches the user until the text is known
to be complete, failures retry, and a total failure still returns the findings
rather than losing them.
"""

from types import SimpleNamespace

import pytest

import ManagerAgent.orchestrator as orch


def response(content):
    """Shape litellm returns for a non-streaming completion."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def install(monkeypatch, *attempts):
    """Queue one outcome per acompletion() call; an Exception instance raises."""
    calls = {"n": 0}

    async def fake_acompletion(*a, **k):
        assert not k.get("stream"), "synthesis must not stream from the model"
        i = calls["n"]
        calls["n"] += 1
        outcome = attempts[min(i, len(attempts) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(orch, "acompletion", fake_acompletion)
    return calls


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(orch, "SYNTHESIS_BACKOFF_SECONDS", 0)


async def collect(gen):
    return [c async for c in gen]


DROPPED = ConnectionResetError("[Errno 54] Connection reset by peer")


@pytest.mark.asyncio
async def test_a_complete_answer_is_replayed_in_full(monkeypatch):
    calls = install(monkeypatch, response("Hello world."))

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 1, "a healthy call must not be retried"
    assert "".join(e["content"] for e in events if e["type"] == "token") == (
        "Hello world."
    )
    assert not any(e["type"] in ("reset", "error") for e in events)


@pytest.mark.asyncio
async def test_a_long_answer_arrives_in_several_chunks(monkeypatch):
    """Chunked so the client paints progressively rather than in one block."""
    text = "x" * (orch.REPLAY_CHUNK_CHARS * 4)
    install(monkeypatch, response(text))

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    tokens = [e for e in events if e["type"] == "token"]
    assert len(tokens) == 4
    assert "".join(t["content"] for t in tokens) == text


@pytest.mark.asyncio
async def test_a_dropped_connection_is_retried(monkeypatch):
    calls = install(monkeypatch, DROPPED, response("Hello world."))

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 2
    assert "".join(e["content"] for e in events if e["type"] == "token") == (
        "Hello world."
    )


@pytest.mark.asyncio
async def test_nothing_is_emitted_before_the_answer_is_known_complete(monkeypatch):
    """No half answer ever reaches the screen, so no 'reset' is ever needed."""
    install(monkeypatch, DROPPED, response("Hello world."))

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert not any(e["type"] == "reset" for e in events)


@pytest.mark.asyncio
async def test_an_empty_response_counts_as_a_failure(monkeypatch):
    calls = install(monkeypatch, response(""), response("Recovered."))

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 2
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Recovered."


@pytest.mark.asyncio
async def test_total_failure_falls_back_to_the_raw_findings(monkeypatch):
    """The branches already did their work; losing it to an error is worse."""
    calls = install(monkeypatch, DROPPED)

    events = await collect(
        orch.synthesize_response_stream(
            "q", {"rag": "Your April rent was 1,650.00.", "stock": "AAPL 271.40"}
        )
    )

    assert calls["n"] == orch.MAX_STREAM_ATTEMPTS
    body = "".join(e["content"] for e in events if e["type"] == "token")
    assert "1,650.00" in body
    assert "AAPL 271.40" in body
    assert not any(e["type"] == "error" for e in events)


@pytest.mark.asyncio
async def test_total_failure_with_no_findings_is_an_error_not_a_blank(monkeypatch):
    install(monkeypatch, DROPPED)

    events = await collect(orch.synthesize_response_stream("q", {}))

    assert events[-1]["type"] == "error"
    # Never a token: a token becomes the answer body and is saved to history.
    assert not any(e["type"] == "token" for e in events)
