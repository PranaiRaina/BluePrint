import os

import pytest

from RAG_PIPELINE.src.convert import to_markdown

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MAY = os.path.join(FIXTURES, "specimen_bank_statement_may2025.pdf")


def test_to_markdown_emits_headings():
    md = to_markdown(MAY)
    assert any(line.startswith("#") for line in md.splitlines())


def test_to_markdown_emits_table_rows():
    md = to_markdown(MAY)
    assert any(line.lstrip().startswith("|") for line in md.splitlines())


def test_to_markdown_preserves_transaction_values():
    md = to_markdown(MAY)
    assert "1,650.00" in md
    assert "Payment - Rent" in md


@pytest.mark.parametrize("name", ["mar", "apr", "may"])
def test_all_fixtures_convert(name):
    md = to_markdown(os.path.join(FIXTURES, f"specimen_bank_statement_{name}2025.pdf"))
    assert len(md) > 500
