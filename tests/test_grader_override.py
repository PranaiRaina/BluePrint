"""The grader is only skipped for genuine whole-document requests.

Skipping it lets every retrieved chunk through ungraded, so the trigger must be
what the user asked for, not how they phrased the opening of the sentence.
"""

import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

import RAG_PIPELINE.src.graph as graph

IRRELEVANT = [
    Document(
        page_content="April 2025 rent and groceries.\n\n| Rent | 1,650.00 |",
        metadata={"source": "specimen_bank_statement_apr2025.pdf"},
    )
]


async def grade(question, search_query, monkeypatch, verdict="no"):
    monkeypatch.setattr(graph, "llm", RunnableLambda(lambda _: verdict))
    return await graph.grade_documents(
        {
            "question": question,
            "search_query": search_query,
            "documents": list(IRRELEVANT),
        }
    )


@pytest.mark.asyncio
async def test_a_conversational_opener_does_not_skip_the_grader(monkeypatch):
    """The reported bug: bank statements reached an answer about stock holdings."""
    out = await grade(
        "tell me about my investment stock holdings, how they can improve and "
        "current trading price of NVDA",
        "investment stock holdings",
        monkeypatch,
    )
    assert out["documents"] == []


@pytest.mark.asyncio
async def test_analyze_does_not_skip_the_grader(monkeypatch):
    out = await grade(
        "analyze my NVDA position", "NVDA position", monkeypatch
    )
    assert out["documents"] == []


@pytest.mark.asyncio
async def test_summarize_still_skips_the_grader(monkeypatch):
    """A real whole-document request keeps every chunk."""
    out = await grade(
        "summarize my documents", "summarize my documents", monkeypatch
    )
    assert len(out["documents"]) == len(IRRELEVANT)


@pytest.mark.asyncio
async def test_what_is_in_my_still_skips_the_grader(monkeypatch):
    out = await grade(
        "what is in my April statement?", "April statement", monkeypatch
    )
    assert len(out["documents"]) == len(IRRELEVANT)


@pytest.mark.asyncio
async def test_relevant_chunks_survive_grading(monkeypatch):
    out = await grade(
        "what was my April rent?", "April rent", monkeypatch, verdict="yes"
    )
    assert len(out["documents"]) == len(IRRELEVANT)
