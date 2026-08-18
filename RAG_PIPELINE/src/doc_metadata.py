"""Document-level metadata, extracted once per file at ingestion.

None of these fields are embedded. They live in chunk metadata for the grader
and for SQL filtering; only the per-chunk summary reaches the vector.
"""

from typing import Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from .config import settings
from .llm_retry import with_retry

DOC_TYPES = (
    "bank_statement",
    "brokerage_statement",
    "credit_card_statement",
    "invoice",
    "receipt",
    "pay_stub",
    "tax_document",
    "insurance",
    "other",
)

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


class DocumentMetadata(BaseModel):
    """Structured output of the one metadata call per document."""

    doc_type: Literal[DOC_TYPES] = Field(
        description="The kind of financial document this is."
    )
    issuer: str = Field(
        description="Institution that issued it, e.g. 'Meridian Trust Bank'. "
        "Empty string if unclear."
    )
    period_start_ym: int | None = Field(
        default=None,
        description="First month this document covers, as the integer YYYYMM. "
        "A May 2025 statement is 202505; a Jan-Mar quarterly statement is "
        "202501. Null when the document covers no period.",
    )
    period_end_ym: int | None = Field(
        default=None,
        description="Last month this document covers, as the integer YYYYMM. "
        "Equal to period_start_ym for a single-month document; 202503 for a "
        "Jan-Mar quarterly statement. Null when the document covers no period.",
    )


PROMPT = """Extract metadata from this financial document.

Report the period it covers as two integers of the form YYYYMM: the first month
and the last month.

A single-month document has the same value for both. A May 2025 statement is
202505 and 202505. A quarterly statement covering 01/01/2025 to 03/31/2025 is
202501 and 202503. A 2024 tax year document is 202401 and 202412.

Coverage ending on the FIRST day of a month does not make that month covered. A
statement covering 05/01/2025 to 06/01/2025 is 202505 and 202505, not 202506 -
it holds one day of June, which is not a June statement.

Return null for BOTH when the document has no period. Prose documents -
articles, letters, contracts, terms and conditions, agreements, KYC paperwork,
disclosures, guides, research papers - have no period. A date printed on such a
document is when it was written, not a period it covers, so it is still null.
Only return a period for documents that cover a span of time, such as
statements and pay stubs. Never guess.

Document:
{text}"""


async def extract_document_metadata(text: str) -> DocumentMetadata:
    """One LLM call per document. Falls back to an empty record on failure."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
        )
        structured = with_retry(llm.with_structured_output(DocumentMetadata))
        return await structured.ainvoke(PROMPT.format(text=text[:8000]))
    except Exception as e:
        print(f"Metadata Extraction Warning: {e}")
        return DocumentMetadata(doc_type="other", issuer="")


def doc_type_label(doc_type: str) -> str:
    """'bank_statement' -> 'Bank Statement'."""
    return " ".join(word.capitalize() for word in doc_type.split("_"))


def _month_label(period_ym: int | None) -> str:
    """202505 -> 'May 2025'. Empty string for None or a malformed value."""
    if not period_ym:
        return ""
    year, month = divmod(int(period_ym), 100)
    if not 1 <= month <= 12:
        return ""
    return f"{MONTH_NAMES[month - 1]} {year}"


def period_label(start_ym: int | None, end_ym: int | None = None) -> str:
    """The span in words: 'April 2025', 'January-March 2025', or ''.

    A quarterly statement labelled with only its first month is a false
    statement, and this label is embedded in every chunk summary - so the span
    has to survive into the text, not just into the filter columns.

    Tolerates one end being absent, which is what a backfilled row looks like
    before it has been re-ingested.
    """
    start, end = _month_label(start_ym), _month_label(end_ym)
    if not start:
        return end
    if not end or start == end:
        return start

    start_year, _ = divmod(int(start_ym), 100)
    end_year, _ = divmod(int(end_ym), 100)
    if start_year == end_year:
        # "January-March 2025" reads better than repeating the year.
        return f"{start.rsplit(' ', 1)[0]}-{end}"
    return f"{start}-{end}"
