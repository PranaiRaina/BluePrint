"""A stream that dies mid-response must not be presented as a finished answer.

Observed live: the Gemini connection resets roughly 1 call in 3 from this
machine. When it happens mid-stream, `async for chunk in stream` simply ends -
no exception, no finish_reason. Without a check, a reply cut off at 105
characters is indistinguishable from one that completed, so it was streamed to
the user mid-sentence and then saved to history that way.
"""

from types import SimpleNamespace

import pytest

import ManagerAgent.orchestrator as orch


def chunk(content=None, finish_reason=None):
    """Shape litellm/Gemini yields: chunk.choices[0].delta.content / .finish_reason."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content), finish_reason=finish_reason
            )
        ]
    )


def fake_stream(chunks):
    async def _stream():
        for c in chunks:
            yield c

    return _stream()


def install(monkeypatch, *attempts):
    """Queue one fake stream per acompletion() call."""
    calls = {"n": 0}

    async def fake_acompletion(*a, **k):
        i = calls["n"]
        calls["n"] += 1
        return fake_stream(attempts[i])

    monkeypatch.setattr(orch, "acompletion", fake_acompletion)
    return calls


async def collect(gen):
    out = []
    async for c in gen:
        out.append(c)
    return out


COMPLETE = [chunk("Hello "), chunk("world."), chunk(finish_reason="stop")]
TRUNCATED = [chunk("Hello ")]  # dies mid-stream: no finish_reason, no exception


@pytest.mark.asyncio
async def test_complete_stream_is_passed_through_untouched(monkeypatch):
    calls = install(monkeypatch, COMPLETE)

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 1, "a healthy stream must not be retried"
    assert [e["content"] for e in events if e["type"] == "token"] == ["Hello ", "world."]
    assert not any(e["type"] in ("reset", "error") for e in events)


@pytest.mark.asyncio
async def test_truncated_stream_is_retried(monkeypatch):
    calls = install(monkeypatch, TRUNCATED, COMPLETE)

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 2, "a stream ending without finish_reason must be retried"
    # The partial text was already on screen, so the client is told to clear it
    # before the retry replays from the top - otherwise the user sees it twice.
    types = [e["type"] for e in events]
    assert "reset" in types
    assert types.index("reset") < len(types) - 1
    assert "".join(e["content"] for e in events if e["type"] == "token").endswith(
        "Hello world."
    )


@pytest.mark.asyncio
async def test_both_attempts_truncated_yields_an_error_not_a_half_answer(monkeypatch):
    calls = install(monkeypatch, TRUNCATED, TRUNCATED)

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert calls["n"] == 2, "retry exactly once, not forever"
    assert events[-1]["type"] == "error", (
        "after the retry also dies the user must get an error, not a sentence "
        "that stops mid-word"
    )


@pytest.mark.asyncio
async def test_exception_mid_stream_is_reported_as_an_error_event(monkeypatch):
    async def boom(*a, **k):
        raise ConnectionResetError("[Errno 54] Connection reset by peer")

    monkeypatch.setattr(orch, "acompletion", boom)

    events = await collect(orch.synthesize_response_stream("q", {"rag": "r"}))

    assert events[-1]["type"] == "error"
    # Never emitted as a token - a token becomes the answer body and gets saved.
    assert not any(e["type"] == "token" for e in events)
