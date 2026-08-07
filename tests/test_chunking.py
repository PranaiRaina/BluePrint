import os

from RAG_PIPELINE.src.chunking import (
    DELIMITER_RE,
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


TWO_TABLES = """| Symbol | Shares | Cost Basis | Market Value |
|---|---|---|---|
""" + "\n".join(
    f"| TICK{i} | {i*10} | {i*100}.00 | {i*120}.00 |" for i in range(1, 26)
) + """

| Date | Activity | Amount |
|---|---|---|
""" + "\n".join(
    f"| 05/{i:02d}/2025 | Dividend TICK{i} | {i}.50 |" for i in range(1, 21)
)


def test_adjacent_tables_do_not_share_a_header():
    """A brokerage statement stacks several different tables in a row.

    Merging them means the second table's rows get stamped with the first
    table's header, so a date reads as a Symbol. Confidently mislabelled is
    worse than unlabelled.
    """
    for chunk in split_markdown(TWO_TABLES, chunk_size=300):
        has_holdings_header = "| Symbol | Shares | Cost Basis | Market Value |" in chunk
        has_dividend_row = "| Dividend TICK" in chunk
        assert not (has_holdings_header and has_dividend_row), (
            "dividend rows carried the holdings header:\n" + chunk[:300]
        )


def test_each_table_keeps_its_own_header():
    chunks = split_markdown(TWO_TABLES, chunk_size=300)
    for chunk in chunks:
        if "| TICK1 |" in chunk or "| TICK16 |" in chunk:
            assert "| Symbol | Shares | Cost Basis | Market Value |" in chunk
        if "| Dividend TICK" in chunk:
            assert "| Date | Activity | Amount |" in chunk


def test_adjacent_tables_lose_no_rows():
    chunks = split_markdown(TWO_TABLES, chunk_size=300)
    for i in range(1, 26):
        assert any(f"| TICK{i} |" in c for c in chunks), f"lost holding {i}"
    for i in range(1, 21):
        assert any(f"Dividend TICK{i} |" in c for c in chunks), f"lost dividend {i}"


SAME_WIDTH_TABLES = """| Symbol | Shares | Value |
|---|---|---|
| AAPL | 50 | 9000.00 |
| MSFT | 20 | 8400.00 |

| Date | Activity | Amount |
|---|---|---|
| 05/04/2025 | Dividend | 4.50 |
| 05/11/2025 | Dividend | 6.25 |
"""


def test_same_width_adjacent_tables_are_separated():
    """Column count cannot tell these apart; the delimiter row is the signal."""
    chunks = split_markdown(SAME_WIDTH_TABLES, chunk_size=1000)
    for chunk in chunks:
        if "Dividend" in chunk:
            assert "| Date | Activity | Amount |" in chunk
            assert "| Symbol | Shares | Value |" not in chunk
        if "AAPL" in chunk:
            assert "| Symbol | Shares | Value |" in chunk


def test_same_width_split_leaves_no_orphan_header():
    """Breaking at the delimiter instead of the header strands rows unlabelled."""
    for chunk in split_markdown(SAME_WIDTH_TABLES, chunk_size=1000):
        stripped = chunk.strip()
        assert not stripped.startswith("|---|"), f"orphaned delimiter:\n{chunk}"
        assert not stripped.endswith("| Date | Activity | Amount |"), (
            f"header orphaned onto previous table:\n{chunk}"
        )


def test_no_chunk_of_a_real_statement_starts_with_an_orphan_delimiter():
    """Regression: a header line and its own delimiter row routinely disagree
    on pipe count, so a column-width rule split them apart and left the
    delimiter — and every data row under it — with no column labels.

    Synthetic tables did not catch this; only the real converter output did.
    """
    for name in ("mar", "apr", "may"):
        path = os.path.join(FIXTURES, f"specimen_bank_statement_{name}2025.pdf")
        for chunk in split_markdown(to_markdown(path)):
            assert not chunk.strip().startswith("|---"), (
                f"{name}: orphaned delimiter:\n{chunk[:200]}"
            )


def test_real_statement_table_chunks_carry_column_labels():
    """Every table chunk must start with a header row, not a data row."""
    for name in ("mar", "apr", "may"):
        path = os.path.join(FIXTURES, f"specimen_bank_statement_{name}2025.pdf")
        chunks = split_markdown(to_markdown(path))
        table_chunks = [c for c in chunks if c.lstrip().startswith("|")]
        for chunk in table_chunks:
            lines = [ln for ln in chunk.split("\n") if ln.strip()]
            assert any(DELIMITER_RE.match(ln.strip()) for ln in lines[:2]), (
                f"{name}: table chunk has no header+delimiter:\n{chunk[:200]}"
            )
