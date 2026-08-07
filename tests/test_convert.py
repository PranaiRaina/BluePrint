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


def test_emphasis_is_stripped():
    """Bold markers break spaCy's tokeniser, so PII survives redaction.

    "**Jane Sample**" tokenises as "**Jane" / "Sample**", which NER does not
    recognise as a person. Stripping emphasis is what lets redaction see it.
    """
    md = to_markdown(os.path.join(FIXTURES, "specimen_bank_statement_mar2025.pdf"))
    assert "**" not in md
    assert "Jane Sample" in md, "name should be bare, ready for redaction"


def test_headings_and_tables_survive_emphasis_stripping():
    md = to_markdown(MAY)
    assert any(line.startswith("#") for line in md.splitlines())
    assert any(line.lstrip().startswith("|") for line in md.splitlines())


def test_br_markers_are_stripped():
    md = to_markdown(MAY)
    assert "<br>" not in md
