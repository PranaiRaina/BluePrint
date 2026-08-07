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
    period_ym: int | None = Field(
        default=None,
        description="The single month this document covers, as the integer "
        "YYYYMM. A May 2025 statement is 202505, even if it lists a few days "
        "of the following month. Null when the document covers no period.",
    )


PROMPT = """Extract metadata from this financial document.

Report the period as one integer YYYYMM naming the month the document is FOR.
A statement covering 05/01/2025 to 06/01/2025 is 202505, not 202506.

Return null for the period when the document has no period. Prose documents -
articles, letters, contracts, guides, research papers - have no period. A date
printed on such a document is when it was written, not a period it covers, so
it is still null. Only return a period for documents that cover a span of time,
such as statements and pay stubs. Never guess.

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
        return DocumentMetadata(doc_type="other", issuer="", period_ym=None)


def doc_type_label(doc_type: str) -> str:
    """'bank_statement' -> 'Bank Statement'."""
    return " ".join(word.capitalize() for word in doc_type.split("_"))


def period_label(period_ym: int | None) -> str:
    """202505 -> 'May 2025'. Empty string for None or a malformed value."""
    if not period_ym:
        return ""
    year, month = divmod(int(period_ym), 100)
    if not 1 <= month <= 12:
        return ""
    return f"{MONTH_NAMES[month - 1]} {year}"
