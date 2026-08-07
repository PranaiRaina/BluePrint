"""psycopg is blocking. A DB-backed endpoint declared `async def` runs that
blocking call directly on the single event loop, stalling every other request
(including in-flight SSE chat streams) for a full network round trip or more.

Declaring them `def` makes FastAPI run them in its threadpool instead.
"""

import inspect

import pytest

from ManagerAgent.api import app

# Endpoints whose handler body talks to Postgres and does no awaiting.
DB_ROUTES = [
    ("/v1/agent/history", "GET"),
    ("/v1/agent/sessions", "GET"),
    ("/v1/agent/sessions", "POST"),
    ("/v1/agent/sessions/{session_id}", "PATCH"),
    ("/v1/agent/sessions/{session_id}", "DELETE"),
    ("/v1/portfolio/pending", "GET"),
    ("/v1/portfolio/holdings", "GET"),
    ("/v1/portfolio/holdings", "POST"),
    ("/v1/user/profile", "GET"),
    ("/v1/user/profile", "POST"),
]


@pytest.mark.parametrize("path,method", DB_ROUTES)
def test_db_endpoint_is_sync(path, method):
    endpoint = next(
        r.endpoint
        for r in app.routes
        if getattr(r, "path", None) == path and method in getattr(r, "methods", ())
    )
    assert not inspect.iscoroutinefunction(endpoint), (
        f"{method} {path} is `async def` but blocks on psycopg - it will freeze "
        f"the event loop. Declare it `def`, or await it via asyncio.to_thread."
    )
