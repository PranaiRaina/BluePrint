import os

from RAG_PIPELINE.src.chunking import (
    MAX_DOCUMENT_TOKENS,
    count_tokens,
    split_markdown,
)
from RAG_PIPELINE.src.convert import to_markdown

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MAY = os.path.join(FIXTURES, "specimen_bank_statement_may2025.pdf")

TABLE_MD = """## Transactions

| Date | Description | Amount | Balance |
|---|---|---|---|
""" + "\n".join(
    f"| 05/{day:02d}/2025 | Purchase number {day} | {day}.00 | {1000 - day}.00 |"
    for day in range(1, 61)
)


def test_count_tokens_is_not_character_count():
    assert count_tokens("hello world") < len("hello world")


def test_document_limit_is_fifty_thousand():
    assert MAX_DOCUMENT_TOKENS == 50_000


def test_table_split_repeats_header_on_every_piece():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert "| Date | Description | Amount | Balance |" in chunk
        assert "|---|---|---|---|" in chunk


def test_table_split_loses_no_rows():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    for day in range(1, 61):
        needle = f"Purchase number {day} |"
        assert any(needle in chunk for chunk in chunks), f"lost row {day}"


def test_chunks_respect_the_token_budget():
    # One table row can never be split further, so allow a single-row overshoot.
    for chunk in split_markdown(TABLE_MD, chunk_size=200):
        assert count_tokens(chunk) <= 200 + 60


def test_real_statement_produces_multiple_chunks():
    assert len(split_markdown(to_markdown(MAY))) > 1


def test_real_statement_chunks_are_non_empty():
    for chunk in split_markdown(to_markdown(MAY)):
        assert chunk.strip()


def test_real_statement_keeps_the_rent_row_intact():
    chunks = split_markdown(to_markdown(MAY))
    assert any("1,650.00" in chunk for chunk in chunks)


def test_prose_without_tables_still_chunks():
    prose = "This is a sentence about index funds. " * 400
    chunks = split_markdown(prose, chunk_size=200)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_a_bare_heading_does_not_become_its_own_chunk():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    assert "## Transactions" not in [chunk.strip() for chunk in chunks]


def test_a_heading_is_attached_to_the_content_it_introduces():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    assert chunks[0].startswith("## Transactions")
    assert "| Date | Description | Amount | Balance |" in chunks[0]
