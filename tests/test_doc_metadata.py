import pytest
from pydantic import ValidationError

from RAG_PIPELINE.src.doc_metadata import (
    PROMPT,
    DocumentMetadata,
    doc_type_label,
    period_label,
)


def test_rejects_unknown_doc_type():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            doc_type="mortgage_application", issuer="Meridian", period_ym=202505
        )


def test_accepts_known_doc_type():
    meta = DocumentMetadata(
        doc_type="bank_statement", issuer="Meridian Trust Bank", period_ym=202505
    )
    assert meta.doc_type == "bank_statement"
    assert meta.period_ym == 202505


def test_period_defaults_to_none():
    """A document with no determinable period must carry None, not a guess."""
    meta = DocumentMetadata(doc_type="other", issuer="")
    assert meta.period_ym is None


def test_period_may_be_explicitly_none():
    meta = DocumentMetadata(doc_type="receipt", issuer="", period_ym=None)
    assert meta.period_ym is None


def test_rejects_non_integer_period():
    with pytest.raises(ValidationError):
        DocumentMetadata(doc_type="receipt", issuer="", period_ym="May 2025")


def test_prompt_instructs_null_for_undated_documents():
    """Prose documents have no period; the prompt must say so explicitly."""
    assert "null" in PROMPT.lower()
    assert "no period" in PROMPT.lower() or "not a statement" in PROMPT.lower()


def test_doc_type_label_humanises():
    assert doc_type_label("bank_statement") == "Bank Statement"
    assert doc_type_label("other") == "Other"


def test_doc_type_label_handles_empty():
    assert doc_type_label("") == ""


def test_period_label_formats():
    assert period_label(202505) == "May 2025"
    assert period_label(202412) == "December 2024"


def test_period_label_absent():
    assert period_label(None) == ""


def test_period_label_rejects_garbage_month():
    assert period_label(202599) == ""
    assert period_label(202500) == ""


def test_period_ym_is_sortable_and_range_queryable():
    months = [202503, 202504, 202505]
    assert sorted(months) == months
    assert [m for m in months if 202501 <= m <= 202504] == [202503, 202504]
