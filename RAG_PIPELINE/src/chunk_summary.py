"""Per-chunk summaries. The only text prepended to a chunk before embedding.

Document type, issuer and period live in metadata and are never embedded, so
this summary is the only path by which a document's period reaches the vector.
That is why the prompt requires it and why the failure fallback carries it too.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from .config import settings
from .doc_metadata import DocumentMetadata, doc_type_label, period_label

MAX_SUMMARY_WORDS = 20
SUMMARY_BATCH_SIZE = 25


class ChunkSummaries(BaseModel):
    summaries: list[str] = Field(
        description="One summary per input chunk, in the same order."
    )


PROMPT = """You are labelling chunks of a financial document so they can be found by search.

Document: {issuer} {doc_type}, covering {period}.

Write one summary per chunk below, in the same order, {count} in total.

Rules for each summary:
- {max_words} words maximum. Every word has to earn its place.
- MUST state the period "{period}". Search cannot find the right month without it.
- Then LIST THE LINE ITEMS in that chunk by name: rent, salary, ATM withdrawal,
  insurance, groceries, car loan, and so on. These are what people search for.
- Do NOT spend words on opening balances, closing balances, or period totals
  unless the chunk contains nothing else. Nobody searches for "opening balance
  4102.65", and those words displace the ones they do search for.

Chunks:
{chunks}"""


def truncate_words(text: str, limit: int = MAX_SUMMARY_WORDS) -> str:
    """Cap at `limit` words and collapse whitespace."""
    return " ".join(text.split()[:limit])


def fallback_summary(meta: DocumentMetadata) -> str:
    """Used when the summary call fails. Must still carry the period."""
    parts = [
        period_label(meta.period_ym),
        meta.issuer,
        doc_type_label(meta.doc_type) if meta.doc_type else "",
    ]
    joined = " ".join(part for part in parts if part)
    return truncate_words(joined or "Document")


def build_batch_prompt(chunks: list[str], meta: DocumentMetadata) -> str:
    numbered = "\n\n".join(f"[{i}]\n{chunk}" for i, chunk in enumerate(chunks, 1))
    return PROMPT.format(
        issuer=meta.issuer or "Unknown institution",
        doc_type=doc_type_label(meta.doc_type),
        period=period_label(meta.period_ym) or "an unstated period",
        count=len(chunks),
        max_words=MAX_SUMMARY_WORDS,
        chunks=numbered,
    )


async def _summarize_batch(chunks: list[str], meta: DocumentMetadata) -> list[str]:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
    )
    structured = llm.with_structured_output(ChunkSummaries)
    result = await structured.ainvoke(build_batch_prompt(chunks, meta))

    if len(result.summaries) != len(chunks):
        # A count mismatch means the summaries no longer line up with the
        # chunks. A misaligned summary is worse than none: it describes the
        # wrong content and is embedded permanently.
        raise ValueError(
            f"expected {len(chunks)} summaries, got {len(result.summaries)}"
        )

    return [truncate_words(summary) for summary in result.summaries]


async def summarize_chunks(
    chunks: list[str], meta: DocumentMetadata
) -> list[str]:
    """One summary per chunk, generated in batches of SUMMARY_BATCH_SIZE."""
    summaries: list[str] = []
    for start in range(0, len(chunks), SUMMARY_BATCH_SIZE):
        batch = chunks[start : start + SUMMARY_BATCH_SIZE]
        try:
            summaries.extend(await _summarize_batch(batch, meta))
        except Exception as e:
            print(f"Chunk Summary Warning (batch at {start}): {e}")
            summaries.extend(fallback_summary(meta) for _ in batch)
    return summaries
