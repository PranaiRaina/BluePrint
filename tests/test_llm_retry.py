import pytest

from RAG_PIPELINE.src.llm_retry import (
    LLM_MAX_ATTEMPTS,
    retry_async,
    retry_sync,
)


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """Keep the tests fast; the backoff itself is not under test."""
    import RAG_PIPELINE.src.llm_retry as mod

    monkeypatch.setattr(mod, "LLM_BACKOFF_SECONDS", 0)


def test_retry_sync_returns_on_first_success():
    calls = []

    def ok():
        calls.append(1)
        return "value"

    assert retry_sync(ok) == "value"
    assert len(calls) == 1


def test_retry_sync_recovers_from_a_connection_reset():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionResetError(54, "Connection reset by peer")
        return "value"

    assert retry_sync(flaky) == "value"
    assert len(calls) == 3


def test_retry_sync_reraises_after_the_last_attempt():
    calls = []

    def always_fails():
        calls.append(1)
        raise ConnectionResetError(54, "Connection reset by peer")

    with pytest.raises(ConnectionResetError):
        retry_sync(always_fails)
    assert len(calls) == LLM_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_retry_async_recovers():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionResetError(54, "Connection reset by peer")
        return "value"

    assert await retry_async(flaky) == "value"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_retry_async_reraises_after_the_last_attempt():
    async def always_fails():
        raise ConnectionResetError(54, "Connection reset by peer")

    with pytest.raises(ConnectionResetError):
        await retry_async(always_fails)


def test_with_retry_wraps_a_runnable():
    from langchain_core.runnables import RunnableLambda

    from RAG_PIPELINE.src.llm_retry import with_retry

    calls = []

    def flaky(_):
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionResetError(54, "Connection reset by peer")
        return "value"

    assert with_retry(RunnableLambda(flaky)).invoke(None) == "value"
    assert len(calls) == 2
