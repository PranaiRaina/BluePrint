import pytest

from RAG_PIPELINE.src.chunk_summary import (
    MAX_SUMMARY_WORDS,
    SUMMARY_BATCH_SIZE,
    ChunkSummaries,
    build_batch_prompt,
    fallback_summary,
    truncate_words,
)
from RAG_PIPELINE.src.doc_metadata import DocumentMetadata

META = DocumentMetadata(
    doc_type="bank_statement",
    issuer="Meridian Trust Bank",
    period_start_ym=202504,
    period_end_ym=202504,
)
UNDATED = DocumentMetadata(doc_type="other", issuer="")


def test_limits_are_as_specified():
    assert MAX_SUMMARY_WORDS == 20
    assert SUMMARY_BATCH_SIZE == 25


def test_truncate_words_cuts_at_the_limit():
    assert len(truncate_words(" ".join(["word"] * 50)).split()) == 20


def test_truncate_words_leaves_short_text_alone():
    assert truncate_words("April 2025 rent payment") == "April 2025 rent payment"


def test_truncate_words_collapses_whitespace():
    assert truncate_words("April\n\n2025   rent") == "April 2025 rent"


def test_fallback_summary_states_the_period():
    # The period reaching the vector is the whole mechanism; the fallback must
    # not drop it when the LLM call fails.
    assert "April 2025" in fallback_summary(META)


def test_fallback_summary_survives_empty_metadata():
    assert isinstance(fallback_summary(UNDATED), str)
    assert fallback_summary(UNDATED)


def test_fallback_summary_respects_the_word_limit():
    assert len(fallback_summary(META).split()) <= MAX_SUMMARY_WORDS


def test_batch_prompt_numbers_every_chunk():
    prompt = build_batch_prompt(["chunk one", "chunk two", "chunk three"], META)
    assert "[1]" in prompt and "[2]" in prompt and "[3]" in prompt


def test_batch_prompt_states_the_period_requirement():
    prompt = build_batch_prompt(["chunk one"], META)
    assert "April 2025" in prompt
    assert "20 words" in prompt


def test_batch_prompt_handles_undated_documents():
    prompt = build_batch_prompt(["chunk one"], UNDATED)
    assert isinstance(prompt, str) and "chunk one" in prompt


def test_undated_prompt_forbids_inventing_a_period():
    """Telling an undated document to state a period produced 'An unstated
    period:' on every chunk - identical text, which is the dilution the
    per-chunk prefix exists to avoid."""
    prompt = build_batch_prompt(["chunk one"], UNDATED)
    assert "unstated period" in prompt.lower()
    assert "do not mention a date" in prompt.lower()
    assert "MUST state the period" not in prompt


def test_dated_prompt_still_requires_the_period():
    prompt = build_batch_prompt(["chunk one"], META)
    assert "MUST state the period" in prompt
    assert "April 2025" in prompt


def test_undated_prompt_omits_the_covering_clause():
    assert "covering" not in build_batch_prompt(["chunk one"], UNDATED)
    assert "covering April 2025" in build_batch_prompt(["chunk one"], META)


def test_chunk_summaries_model_requires_a_list():
    assert ChunkSummaries(summaries=["a", "b"]).summaries == ["a", "b"]


@pytest.mark.asyncio
async def test_count_mismatch_falls_back_rather_than_misaligning(monkeypatch):
    """A short response must not shift summaries onto the wrong chunks."""
    import RAG_PIPELINE.src.chunk_summary as mod

    async def _bad_batch(chunks, meta):
        raise ValueError(f"expected {len(chunks)} summaries, got 1")

    monkeypatch.setattr(mod, "_summarize_batch", _bad_batch)
    result = await mod.summarize_chunks(["a", "b", "c"], META)

    assert len(result) == 3
    assert all("April 2025" in s for s in result)
