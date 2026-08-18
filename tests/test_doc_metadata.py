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
            doc_type="mortgage_application",
            issuer="Meridian",
            period_start_ym=202505,
            period_end_ym=202505,
        )


def test_accepts_known_doc_type():
    meta = DocumentMetadata(
        doc_type="bank_statement",
        issuer="Meridian Trust Bank",
        period_start_ym=202505,
        period_end_ym=202505,
    )
    assert meta.doc_type == "bank_statement"
    assert meta.period_start_ym == 202505
    assert meta.period_end_ym == 202505


def test_period_defaults_to_none():
    """A document with no determinable period must carry None, not a guess."""
    meta = DocumentMetadata(doc_type="other", issuer="")
    assert meta.period_start_ym is None
    assert meta.period_end_ym is None


def test_period_may_be_explicitly_none():
    meta = DocumentMetadata(
        doc_type="receipt", issuer="", period_start_ym=None, period_end_ym=None
    )
    assert meta.period_start_ym is None


def test_rejects_non_integer_period():
    with pytest.raises(ValidationError):
        DocumentMetadata(doc_type="receipt", issuer="", period_start_ym="May 2025")


def test_a_quarter_spans_three_months():
    meta = DocumentMetadata(
        doc_type="brokerage_statement",
        issuer="Vantage Point Securities",
        period_start_ym=202501,
        period_end_ym=202503,
    )
    assert meta.period_start_ym == 202501
    assert meta.period_end_ym == 202503


def test_prompt_instructs_null_for_undated_documents():
    """Prose documents have no period; the prompt must say so explicitly."""
    assert "null" in PROMPT.lower()
    assert "no period" in PROMPT.lower() or "not a statement" in PROMPT.lower()


def test_prompt_keeps_the_first_of_the_month_rule():
    """A statement ending 06/01 is not a June statement - this bit us before."""
    assert "06/01/2025" in PROMPT
    assert "202506" in PROMPT


def test_prompt_gives_a_multi_month_example():
    assert "202503" in PROMPT


def test_doc_type_label_humanises():
    assert doc_type_label("bank_statement") == "Bank Statement"
    assert doc_type_label("other") == "Other"


def test_doc_type_label_handles_empty():
    assert doc_type_label("") == ""


def test_period_label_single_month():
    assert period_label(202505, 202505) == "May 2025"
    assert period_label(202412, 202412) == "December 2024"


def test_period_label_spans_a_quarter_within_one_year():
    assert period_label(202501, 202503) == "January-March 2025"


def test_period_label_spans_a_year_boundary():
    assert period_label(202411, 202502) == "November 2024-February 2025"


def test_period_label_spans_a_full_year():
    assert period_label(202401, 202412) == "January-December 2024"


def test_period_label_absent():
    assert period_label(None, None) == ""
    assert period_label(None) == ""


def test_period_label_tolerates_a_missing_end():
    """What a backfilled row looks like before it is re-ingested."""
    assert period_label(202505, None) == "May 2025"


def test_period_label_rejects_garbage_month():
    assert period_label(202599, 202599) == ""
    assert period_label(202500, 202500) == ""


def test_period_range_is_containment_queryable():
    """The point of two columns: one predicate answers 'does this cover March'."""
    docs = [
        ("april statement", 202504, 202504),
        ("q1 statement", 202501, 202503),
        ("card terms", None, None),
    ]
    march = [
        name
        for name, start, end in docs
        if start is not None and start <= 202503 <= end
    ]
    assert march == ["q1 statement"]

    april = [
        name
        for name, start, end in docs
        if start is not None and start <= 202504 <= end
    ]
    assert april == ["april statement"]
