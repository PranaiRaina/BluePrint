"""One retry policy for every model call.

Gemini drops connections from some networks - `[Errno 54] Connection reset by
peer` - and neither ChatGoogleGenerativeAI nor GoogleGenerativeAIEmbeddings
exposes a retry setting, so an unwrapped call fails the whole turn.

A RAG turn makes ~9 model calls (rephrase, embed, one grade per retrieved
document, generate). At a 10% per-call reset rate that is a ~60% chance the
turn dies; with three attempts each it is under 1%.
"""

import asyncio
import time

LLM_MAX_ATTEMPTS = 3
LLM_BACKOFF_SECONDS = 0.5


def with_retry(runnable):
    """Wrap a LangChain runnable so .invoke/.ainvoke/.stream retry."""
    return runnable.with_retry(
        stop_after_attempt=LLM_MAX_ATTEMPTS,
        wait_exponential_jitter=True,
    )


def retry_sync(fn, *args, **kwargs):
    """Retry a plain callable - for methods that are not runnables.

    GoogleGenerativeAIEmbeddings.embed_query is a direct method call, so
    with_retry cannot reach it.
    """
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt + 1 == LLM_MAX_ATTEMPTS:
                raise
            delay = LLM_BACKOFF_SECONDS * (2**attempt)
            print(f"[retry] {fn.__name__} failed ({e}); retrying in {delay:.1f}s")
            time.sleep(delay)


async def retry_async(fn, *args, **kwargs):
    """Async counterpart of retry_sync."""
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if attempt + 1 == LLM_MAX_ATTEMPTS:
                raise
            delay = LLM_BACKOFF_SECONDS * (2**attempt)
            print(f"[retry] {fn.__name__} failed ({e}); retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
