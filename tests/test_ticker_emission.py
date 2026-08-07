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
