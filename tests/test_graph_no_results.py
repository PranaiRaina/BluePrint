"""An empty document set reports the miss; it never answers anyway."""

import pytest

import RAG_PIPELINE.src.graph as graph
from RAG_PIPELINE.src.graph import (
    NO_RESULTS_MESSAGE,
    decide_to_generate,
    no_results,
)


def test_empty_documents_route_to_no_results():
    assert decide_to_generate({"documents": []}) == "no_results"


def test_documents_still_route_to_generate():
    assert decide_to_generate({"documents": ["a chunk"]}) == "generate"


def test_no_results_sets_the_message_as_the_generation():
    out = no_results({"question": "what were my March fees?"})
    assert out["generation"] == NO_RESULTS_MESSAGE
    assert out["documents"] == []


def test_message_says_it_searched_and_asks_the_two_things():
    lowered = NO_RESULTS_MESSAGE.lower()
    assert "searched" in lowered
    assert "upload" in lowered           # check the document is there
    assert "specific" in lowered         # or narrow the question


def test_no_results_never_calls_a_model(monkeypatch):
    """The miss path must not be able to invent an answer."""

    def explode(*_args, **_kwargs):
        raise AssertionError("no_results called the model")

    monkeypatch.setattr(graph, "llm", property(explode))

    assert no_results({"question": "anything"})["generation"] == NO_RESULTS_MESSAGE


def test_the_graph_has_no_web_search_fallback():
    """A miss is reported, not papered over with a web answer."""
    assert not hasattr(graph, "web_search")
    assert "no_results" in graph.workflow.nodes
    assert "web_search" not in graph.workflow.nodes


@pytest.mark.asyncio
async def test_grade_documents_routes_to_no_results_when_all_fail(monkeypatch):
    """Retrieval hit, grading rejected everything - still a miss."""
    from langchain_core.documents import Document
    from langchain_core.runnables import RunnableLambda

    monkeypatch.setattr(graph, "llm", RunnableLambda(lambda _: "no"))

    out = await graph.grade_documents(
        {
            "question": "what were my March fees?",
            "search_query": "March fees",
            "documents": [Document(page_content="April rent 1,650.00", metadata={})],
        }
    )

    assert out["documents"] == []
    assert decide_to_generate(out) == "no_results"
