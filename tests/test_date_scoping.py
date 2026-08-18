"""Date arithmetic, retrieval width, and the coverage footer."""

from langchain_core.documents import Document

from RAG_PIPELINE.src.graph import (
    K_LONG_RANGE,
    K_NO_RANGE,
    K_SHORT_RANGE,
    coverage_footer,
    k_for_range,
    month_span,
    months_before,
    no_results,
    overlaps_range,
    ym,
)

DOCS = [
    Document(page_content="x", metadata={"source": "/tmp/mar2025.pdf"}),
    Document(page_content="y", metadata={"source": "/tmp/apr2025.pdf"}),
]


def test_months_before_within_a_year():
    assert months_before(202505, 3) == 202502


def test_months_before_crosses_the_year():
    assert months_before(202501, 3) == 202410
    assert months_before(202502, 14) == 202312


def test_months_before_zero_is_identity():
    assert months_before(202505, 0) == 202505


def test_ym_from_a_date():
    from datetime import date

    assert ym(date(2025, 3, 9)) == 202503
    assert ym(date(2024, 12, 31)) == 202412


def test_month_span_counts_inclusively():
    assert month_span(202503, 202503) == 1
    assert month_span(202501, 202503) == 3
    assert month_span(202401, 202412) == 12
    assert month_span(202411, 202502) == 4


def test_month_span_is_none_without_a_range():
    assert month_span(None, None) is None
    assert month_span(202503, None) is None


def test_overlaps_range_matches_a_quarter_from_one_month():
    q1 = {"period_start_ym": 202501, "period_end_ym": 202503}
    assert overlaps_range(q1, 202503, 202503)
    assert not overlaps_range(q1, 202504, 202504)


def test_overlaps_range_is_false_for_undated_chunks():
    """Opposite of the SQL rule, on purpose: a timeless document is not
    evidence that the requested months matched anything."""
    assert not overlaps_range({"period_start_ym": None, "period_end_ym": None}, 202503, 202503)
    assert not overlaps_range({}, 202503, 202503)


def test_k_scales_with_the_range():
    assert k_for_range(None, None) == K_NO_RANGE
    assert k_for_range(202503, 202503) == K_SHORT_RANGE
    assert k_for_range(202501, 202503) == K_SHORT_RANGE   # exactly 3 months
    assert k_for_range(202501, 202504) == K_LONG_RANGE    # 4 months
    assert k_for_range(202401, 202412) == K_LONG_RANGE


# --- coverage footer --------------------------------------------------------


def test_footer_names_sources_and_the_range():
    footer = coverage_footer(
        {"period_from": 202503, "period_to": 202505, "searched": 9, "eligible": 24},
        DOCS,
    )
    assert "mar2025.pdf" in footer
    assert "March-May 2025" in footer
    assert "searched 9 of 24 chunks" in footer


def test_footer_says_all_dates_when_unfiltered():
    footer = coverage_footer({"searched": 6, "eligible": 43}, DOCS)
    assert "all dates" in footer


def test_footer_warns_only_beyond_three_months():
    short = coverage_footer(
        {"period_from": 202503, "period_to": 202505, "span_months": 3}, DOCS
    )
    assert "indicative" not in short

    long = coverage_footer(
        {"period_from": 202501, "period_to": 202512, "span_months": 12}, DOCS
    )
    assert "12 months" in long
    assert "indicative" in long


def test_footer_reports_a_dropped_filter():
    footer = coverage_footer(
        {
            "period_from": None,
            "period_to": None,
            "requested_from": 202401,
            "requested_to": 202401,
            "filter_dropped": True,
            "searched": 6,
            "eligible": 43,
        },
        DOCS,
    )
    assert "January 2024" in footer
    assert "searched all dates instead" in footer


def test_footer_is_empty_without_documents():
    assert coverage_footer({}, []) == ""


# --- date-aware miss --------------------------------------------------------


def test_miss_names_the_period_that_was_asked_for():
    out = no_results(
        {
            "question": "what was my rent in January 2024?",
            "coverage": {
                "requested_from": 202401,
                "requested_to": 202401,
                "total": 43,
            },
        }
    )
    assert "January 2024" in out["generation"]
    assert "without a date" in out["generation"]


def test_miss_falls_back_to_the_generic_message_without_a_period():
    from RAG_PIPELINE.src.graph import NO_RESULTS_MESSAGE

    out = no_results({"question": "what is my rent?", "coverage": {"total": 43}})
    assert out["generation"] == NO_RESULTS_MESSAGE
