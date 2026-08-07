# Markdown Ingestion with Per-Chunk Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest PDFs as markdown, prefix every chunk with its own ≤20-word summary, and store document type, issuer, and period as filterable metadata so cross-month statement queries retrieve the right document.

**Architecture:** `pymupdf4llm` replaces `PyPDFLoader`. One structured LLM call per document extracts type, issuer, and `period_ym`. Chunking splits markdown sections and keeps table headers on every piece. A second batched call writes one ≤20-word summary per chunk; that summary is the only thing prepended to chunk text before embedding. Everything else stays in metadata for the grader and for future SQL filtering.

**Tech Stack:** Python 3.12, `pymupdf4llm`, `langchain-text-splitters`, `tiktoken`, `langchain-google-genai`, Supabase pgvector, pytest.

## Global Constraints

- Chunk size **750 tokens**, overlap **100**, counted with `tiktoken` `cl100k_base`.
- Document limit **50,000 tokens**. Reject, never truncate.
- Chunk summaries **20 words maximum**, generated in batches of **25 chunks per call**.
- **Every chunk summary must state the document's period.** `period_ym` is not embedded, so the summary is the only path by which the period reaches the vector. This is the mechanism that separates March rent from April rent.
- Only the chunk summary is prepended to embedded text. `doc_type`, `issuer`, and `period_ym` are metadata-only.
- Upload stays **PDF-only**. `api.py:609` is not modified.
- Metadata and summary calls run **after** PII redaction. The model never sees unredacted text.
- All new unit tests run **offline**. The eval harness is the only network-dependent piece and is excluded from the default pytest run.
- Fixtures: `tests/fixtures/specimen_bank_statement_{mar,apr,may}2025.pdf`.

---

## Measured Facts This Plan Depends On

Verified against the three fixtures. Do not re-derive; do not assume otherwise.

| Fact | Value |
|---|---|
| `pymupdf4llm` output size | 1500 / 1288 / 1310 tokens (mar / apr / may) |
| Chunks per statement at 750 tokens | 2 |
| Headings produced | only `# **MERIDIAN TRUST BANK**`, `## **STATEMENT OF ACCOUNT**` |
| `MarkdownHeaderTextSplitter` sections | 2, heading path **identical for all content** |
| PII redaction throughput | ~10k tokens/sec (0.37s @ 14.5k chars, 3.56s @ 146k) |
| Rent amount | **1,650.00 in all three months** — the discriminator test |
| Car loan | 389.60 in all three months |
| Salary | 3,226.11 (mar) / 3,230.04 (apr) / 3,200.00 (may) |
| Unique per month | gym membership 39.79 (mar), interest credit 7.11 (apr), cheque deposit 480.00 (may) |

---

## File Structure

| File | Responsibility |
|---|---|
| `RAG_PIPELINE/src/convert.py` (new) | PDF → markdown. Dependency boundary and test patch point. |
| `RAG_PIPELINE/src/doc_metadata.py` (new) | `DocumentMetadata` model, extraction call, label helpers. |
| `RAG_PIPELINE/src/chunking.py` (new) | Markdown splitting, table-aware splitting, token counting. |
| `RAG_PIPELINE/src/chunk_summary.py` (new) | Batched per-chunk summary generation. |
| `RAG_PIPELINE/src/ingestion.py` (modify) | Orchestration. Loses the loader, inline splitter, `generate_summary`, dead `process_pdf`. |
| `RAG_PIPELINE/src/graph.py` (modify) | Renders metadata for the grader. |
| `RAG_PIPELINE/eval/` (new) | Retrieval-only eval harness and cases. |

`ingestion.py` is 478 lines mixing PII, vector store access, extraction, and
chunking. These four modules pull out the parts this work touches; the PII and
vector-store halves stay put.

---

### Task 1: Eval harness and baseline

**Files:**
- Create: `RAG_PIPELINE/eval/__init__.py`, `RAG_PIPELINE/eval/questions.json`, `RAG_PIPELINE/eval/run.py`

**Interfaces:**
- Consumes: `RAG_PIPELINE.src.ingestion.perform_similarity_search(query, user_id, k, threshold)` returning `list[tuple[Document, float]]`
- Produces: `run_eval(user_id: str, k: int = 10, threshold: float = 0.0) -> dict` with keys `cases` and `pass_rate`

- [ ] **Step 1: Create the eval cases**

Create `RAG_PIPELINE/eval/questions.json`:

```json
[
  {
    "question": "How much was my rent payment in April 2025?",
    "expect_source": "specimen_bank_statement_apr2025.pdf",
    "expect_contains": ["1,650.00"]
  },
  {
    "question": "How much was my rent payment in March 2025?",
    "expect_source": "specimen_bank_statement_mar2025.pdf",
    "expect_contains": ["1,650.00"]
  },
  {
    "question": "What was my credit card payment in March?",
    "expect_source": "specimen_bank_statement_mar2025.pdf",
    "expect_contains": ["556.72"]
  },
  {
    "question": "Did I pay for a gym membership?",
    "expect_source": "specimen_bank_statement_mar2025.pdf",
    "expect_contains": ["39.79"]
  },
  {
    "question": "What was my closing balance at the end of April?",
    "expect_source": "specimen_bank_statement_apr2025.pdf",
    "expect_contains": ["4,250.00"]
  },
  {
    "question": "How much interest did I earn in April?",
    "expect_source": "specimen_bank_statement_apr2025.pdf",
    "expect_contains": ["7.11"]
  },
  {
    "question": "How much was my cheque deposit in May?",
    "expect_source": "specimen_bank_statement_may2025.pdf",
    "expect_contains": ["480.00"]
  },
  {
    "question": "How much did I withdraw from the ATM in April?",
    "expect_source": "specimen_bank_statement_apr2025.pdf",
    "expect_contains": ["109.20"]
  },
  {
    "question": "How much did I transfer to my brokerage account in May?",
    "expect_source": "specimen_bank_statement_may2025.pdf",
    "expect_contains": ["2,000.00"]
  },
  {
    "question": "What was my salary deposit in May 2025?",
    "expect_source": "specimen_bank_statement_may2025.pdf",
    "expect_contains": ["3,200.00"]
  }
]
```

The first two cases are the point: identical amount, identical description,
different month. Only the document can distinguish them.

- [ ] **Step 2: Write the harness**

Create `RAG_PIPELINE/eval/__init__.py` as an empty file.

Create `RAG_PIPELINE/eval/run.py`:

```python
"""Retrieval-only eval. Run against a user who has the three fixture statements ingested.

    uv run python -m RAG_PIPELINE.eval.run <user_id>
"""

import json
import os
import sys

from RAG_PIPELINE.src.ingestion import perform_similarity_search

CASES_PATH = os.path.join(os.path.dirname(__file__), "questions.json")


def _rank_of(results, expect_source):
    """1-based rank of the first result whose source matches, or None."""
    for i, (doc, _score) in enumerate(results, start=1):
        if doc.metadata.get("source") == expect_source:
            return i
    return None


def run_eval(user_id: str, k: int = 10, threshold: float = 0.0) -> dict:
    with open(CASES_PATH) as f:
        cases = json.load(f)

    rows = []
    for case in cases:
        results = perform_similarity_search(
            query=case["question"], user_id=user_id, k=k, threshold=threshold
        )
        rank = _rank_of(results, case["expect_source"])
        top_text = results[0][0].page_content if results else ""
        found = [s for s in case["expect_contains"] if s in top_text]
        rows.append(
            {
                "question": case["question"],
                "expect_source": case["expect_source"],
                "rank": rank,
                "top_score": round(results[0][1], 4) if results else None,
                "value_in_top_chunk": len(found) == len(case["expect_contains"]),
                "passed": rank == 1,
            }
        )

    passed = sum(1 for r in rows if r["passed"])
    return {"cases": rows, "pass_rate": passed / len(rows) if rows else 0.0}


def main():
    if len(sys.argv) < 2:
        print("usage: python -m RAG_PIPELINE.eval.run <user_id>")
        raise SystemExit(1)

    report = run_eval(sys.argv[1])
    print(f"{'rank':>4}  {'score':>7}  {'val':>3}  question")
    print("-" * 78)
    for r in report["cases"]:
        rank = r["rank"] if r["rank"] is not None else "-"
        score = f"{r['top_score']:.4f}" if r["top_score"] is not None else "-"
        val = "y" if r["value_in_top_chunk"] else "n"
        print(f"{rank:>4}  {score:>7}  {val:>3}  {r['question']}")
    print("-" * 78)
    print(f"rank-1 pass rate: {report['pass_rate']:.0%}")


if __name__ == "__main__":
    main()
```

`threshold=0.0` is deliberate: the harness measures *ranking*, and a threshold
would hide near-misses behind an empty result. Threshold tuning happens in Task 8
using these scores.

- [ ] **Step 3: Ingest the three fixtures and record the baseline**

Upload all three fixture PDFs through the running app, then:

```bash
uv run python -m RAG_PIPELINE.eval.run <your-user-id> | tee docs/superpowers/plans/eval-baseline.txt
```

Expected: 10 rows. The March/April rent pair is expected to fail or rank poorly —
that is the baseline this work has to beat. Record the output verbatim; every
later claim is measured against it.

- [ ] **Step 4: Commit**

```bash
git add RAG_PIPELINE/eval/ docs/superpowers/plans/eval-baseline.txt
git commit -m "test: add retrieval eval harness over three specimen statements

Ten cases across March, April and May statements. The first two ask for
rent in different months, which is 1,650.00 in both - the only signal
that can separate them is the document, so it is the case this work has
to fix. Baseline recorded before any pipeline change."
```

---

### Task 2: PDF to markdown conversion

**Files:**
- Create: `RAG_PIPELINE/src/convert.py`
- Test: `tests/test_convert.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `to_markdown(path: str) -> str`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, inside `[project].dependencies`, add:

```
    "pymupdf4llm>=0.0.17",
    "tiktoken>=0.7.0",
```

and delete the line `    "pypdf",`. Then:

```bash
uv sync
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_convert.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_convert.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.convert'`

- [ ] **Step 4: Write the implementation**

Create `RAG_PIPELINE/src/convert.py`:

```python
"""PDF to markdown conversion.

Isolated behind one function so the extractor can be swapped without touching
ingestion, and so tests have a single patch point.
"""

import pymupdf4llm


def to_markdown(path: str) -> str:
    """Convert a PDF to markdown, headings and tables preserved."""
    return pymupdf4llm.to_markdown(path)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_convert.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock RAG_PIPELINE/src/convert.py tests/test_convert.py
git commit -m "feat(rag): convert PDFs to markdown with pymupdf4llm

PyPDFLoader emits one table cell per line with no headings, so there is
no structure for a chunker to split on. pymupdf4llm produces real
headings and coherent markdown tables on all three specimen statements.
Measured against markitdown, which interleaved watermark characters
into the text and mangled the tables."
```

---

### Task 3: Document metadata

**Files:**
- Create: `RAG_PIPELINE/src/doc_metadata.py`
- Test: `tests/test_doc_metadata.py`

**Interfaces:**
- Produces:
  - `class DocumentMetadata(BaseModel)` with `doc_type: str`, `issuer: str`, `period_ym: int | None`
  - `async def extract_document_metadata(text: str) -> DocumentMetadata`
  - `def doc_type_label(doc_type: str) -> str`
  - `def period_label(period_ym: int | None) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_doc_metadata.py`:

```python
import pytest
from pydantic import ValidationError

from RAG_PIPELINE.src.doc_metadata import (
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


def test_period_may_be_absent():
    meta = DocumentMetadata(doc_type="receipt", issuer="", period_ym=None)
    assert meta.period_ym is None


def test_rejects_non_integer_period():
    with pytest.raises(ValidationError):
        DocumentMetadata(doc_type="receipt", issuer="", period_ym="May 2025")


def test_doc_type_label_humanises():
    assert doc_type_label("bank_statement") == "Bank Statement"
    assert doc_type_label("other") == "Other"


def test_period_label_formats():
    assert period_label(202505) == "May 2025"
    assert period_label(202412) == "December 2024"


def test_period_label_absent():
    assert period_label(None) == ""


def test_period_label_rejects_garbage_month():
    assert period_label(202599) == ""


def test_period_ym_is_sortable_and_range_queryable():
    months = [202503, 202504, 202505]
    assert sorted(months) == months
    assert [m for m in months if 202501 <= m <= 202504] == [202503, 202504]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_doc_metadata.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.doc_metadata'`

- [ ] **Step 3: Write the implementation**

Create `RAG_PIPELINE/src/doc_metadata.py`:

```python
"""Document-level metadata, extracted once per file at ingestion.

None of these fields are embedded. They live in chunk metadata for the grader
and for SQL filtering; only the per-chunk summary reaches the vector.
"""

from typing import Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from .config import settings

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
        "of the following month. Null if the document covers no period.",
    )


PROMPT = """Extract metadata from this financial document.

Report the period as one integer YYYYMM naming the month the document is FOR.
A statement covering 05/01/2025 to 06/01/2025 is 202505, not 202506. Use null
if the document has no period.

Document:
{text}"""


async def extract_document_metadata(text: str) -> DocumentMetadata:
    """One LLM call per document. Falls back to an empty record on failure."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
        )
        structured = llm.with_structured_output(DocumentMetadata)
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
```

`Literal[DOC_TYPES]` works because `DOC_TYPES` is a tuple of string literals —
Pydantic expands it into an enum in the JSON schema, so the constraint reaches
the model through structured output rather than being checked after the fact.

The fallback matters: a metadata failure must not abort an ingest that would
otherwise succeed.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_doc_metadata.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add RAG_PIPELINE/src/doc_metadata.py tests/test_doc_metadata.py
git commit -m "feat(rag): extract document type, issuer and period as metadata

One structured LLM call per document, replacing generate_summary rather
than adding to it. period_ym is a single YYYYMM integer so range
queries need no parsing: BETWEEN 202501 AND 202503 selects Q1. doc_type
is a Literal, which Pydantic renders as an enum in the structured
output schema, so invalid values are rejected at the model boundary."
```

---

### Task 4: Structure-aware chunking

**Files:**
- Create: `RAG_PIPELINE/src/chunking.py`
- Test: `tests/test_chunking.py`

**Interfaces:**
- Produces:
  - `MAX_DOCUMENT_TOKENS = 50_000`
  - `count_tokens(text: str) -> int`
  - `split_markdown(md: str, chunk_size: int = 750, chunk_overlap: int = 100) -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chunking.py`:

```python
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
    chunks = split_markdown(to_markdown(MAY))
    assert len(chunks) > 1


def test_real_statement_chunks_are_non_empty():
    for chunk in split_markdown(to_markdown(MAY)):
        assert chunk.strip()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.chunking'`

- [ ] **Step 3: Write the implementation**

Create `RAG_PIPELINE/src/chunking.py`:

```python
"""Markdown-aware chunking."""

import re

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

MAX_DOCUMENT_TOKENS = 50_000

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]
DELIMITER_RE = re.compile(r"^\|[\s:|-]+\|$")

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _blocks(text: str):
    """Yield (block_text, is_table) for each run of same-kind lines."""
    lines = text.split("\n")
    if not lines:
        return

    current: list[str] = []
    current_is_table = _is_table_line(lines[0])

    for line in lines:
        is_table = _is_table_line(line)
        # Blank lines never break a run; they belong to whatever surrounds them.
        if line.strip() and is_table != current_is_table:
            yield "\n".join(current), current_is_table
            current, current_is_table = [], is_table
        current.append(line)

    if current:
        yield "\n".join(current), current_is_table


def _split_table(block: str, chunk_size: int) -> list[str]:
    """Split a markdown table into row groups, repeating the header on each."""
    lines = [line for line in block.split("\n") if line.strip()]
    if len(lines) < 2:
        return [block]

    header = lines[:2] if DELIMITER_RE.match(lines[1].strip()) else lines[:1]
    rows = lines[len(header):]
    if not rows:
        return [block]

    pieces: list[str] = []
    current: list[str] = []
    for row in rows:
        candidate = "\n".join(header + current + [row])
        if current and count_tokens(candidate) > chunk_size:
            pieces.append("\n".join(header + current))
            current = []
        current.append(row)

    if current:
        pieces.append("\n".join(header + current))
    return pieces


def split_markdown(
    md: str, chunk_size: int = 750, chunk_overlap: int = 100
) -> list[str]:
    """Split markdown into chunks, keeping table headers on every piece."""
    sections = MarkdownHeaderTextSplitter(
        HEADERS_TO_SPLIT_ON, strip_headers=False
    ).split_text(md)

    prose_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    chunks: list[str] = []
    for section in sections:
        for block, is_table in _blocks(section.page_content):
            if not block.strip():
                continue
            pieces = (
                _split_table(block, chunk_size)
                if is_table
                else prose_splitter.split_text(block)
            )
            chunks.extend(piece for piece in pieces if piece.strip())
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add RAG_PIPELINE/src/chunking.py tests/test_chunking.py
git commit -m "feat(rag): chunk on markdown structure, keeping table headers

Splits sections, then splits tables by row group repeating the header
row and delimiter on every piece. A character split of a long
transaction table otherwise leaves the second piece as unlabelled
numbers, where whether a value is an amount or a balance is a guess."
```

---

### Task 5: Per-chunk summaries

**Files:**
- Create: `RAG_PIPELINE/src/chunk_summary.py`
- Test: `tests/test_chunk_summary.py`

**Interfaces:**
- Consumes: `DocumentMetadata`, `doc_type_label`, `period_label` from `RAG_PIPELINE.src.doc_metadata`
- Produces:
  - `MAX_SUMMARY_WORDS = 20`, `SUMMARY_BATCH_SIZE = 25`
  - `truncate_words(text: str, limit: int = MAX_SUMMARY_WORDS) -> str`
  - `fallback_summary(meta: DocumentMetadata) -> str`
  - `build_batch_prompt(chunks: list[str], meta: DocumentMetadata) -> str`
  - `async def summarize_chunks(chunks: list[str], meta: DocumentMetadata) -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chunk_summary.py`:

```python
from RAG_PIPELINE.src.chunk_summary import (
    MAX_SUMMARY_WORDS,
    SUMMARY_BATCH_SIZE,
    build_batch_prompt,
    fallback_summary,
    truncate_words,
)
from RAG_PIPELINE.src.doc_metadata import DocumentMetadata

META = DocumentMetadata(
    doc_type="bank_statement", issuer="Meridian Trust Bank", period_ym=202504
)


def test_limits_are_as_specified():
    assert MAX_SUMMARY_WORDS == 20
    assert SUMMARY_BATCH_SIZE == 25


def test_truncate_words_cuts_at_the_limit():
    assert len(truncate_words(" ".join(["word"] * 50)).split()) == 20


def test_truncate_words_leaves_short_text_alone():
    assert truncate_words("April 2025 rent payment") == "April 2025 rent payment"


def test_fallback_summary_states_the_period():
    # The period reaching the vector is the whole mechanism; the fallback
    # must not drop it when the LLM call fails.
    assert "April 2025" in fallback_summary(META)


def test_fallback_summary_survives_empty_metadata():
    bare = DocumentMetadata(doc_type="other", issuer="", period_ym=None)
    assert isinstance(fallback_summary(bare), str)


def test_fallback_summary_respects_the_word_limit():
    assert len(fallback_summary(META).split()) <= MAX_SUMMARY_WORDS


def test_batch_prompt_numbers_every_chunk():
    prompt = build_batch_prompt(["chunk one", "chunk two", "chunk three"], META)
    assert "[1]" in prompt and "[2]" in prompt and "[3]" in prompt


def test_batch_prompt_states_the_period_requirement():
    prompt = build_batch_prompt(["chunk one"], META)
    assert "April 2025" in prompt
    assert "20 words" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_chunk_summary.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.chunk_summary'`

- [ ] **Step 3: Write the implementation**

Create `RAG_PIPELINE/src/chunk_summary.py`:

```python
"""Per-chunk summaries. The only text prepended to a chunk before embedding."""

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
- {max_words} words maximum.
- MUST state the period "{period}". Search cannot find the right month without it.
- Name what is actually in that chunk: the kinds of transactions, the accounts,
  the figures. Be specific, not generic.

Chunks:
{chunks}"""


def truncate_words(text: str, limit: int = MAX_SUMMARY_WORDS) -> str:
    return " ".join(text.split()[:limit])


def fallback_summary(meta: DocumentMetadata) -> str:
    """Used when the summary call fails. Must still carry the period."""
    parts = [
        period_label(meta.period_ym),
        meta.issuer,
        doc_type_label(meta.doc_type) if meta.doc_type else "",
    ]
    return truncate_words(" ".join(part for part in parts if part) or "Document")


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


async def _summarize_batch(
    chunks: list[str], meta: DocumentMetadata
) -> list[str]:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
    )
    structured = llm.with_structured_output(ChunkSummaries)
    result = await structured.ainvoke(build_batch_prompt(chunks, meta))

    if len(result.summaries) != len(chunks):
        # A count mismatch means the summaries no longer line up with the
        # chunks. A misaligned summary is worse than none - it describes the
        # wrong content and is embedded permanently.
        raise ValueError(
            f"expected {len(chunks)} summaries, got {len(result.summaries)}"
        )

    return [truncate_words(s) for s in result.summaries]


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
```

Batching bounds the alignment risk: a single call returning 67 summaries can
drift and attach summary 40 to chunk 41. The length check turns that drift into
an exception rather than a permanently mislabelled chunk, and the fallback keeps
the period in the vector even when the call fails entirely.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_chunk_summary.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add RAG_PIPELINE/src/chunk_summary.py tests/test_chunk_summary.py
git commit -m "feat(rag): generate one summary per chunk, capped at 20 words

The summary is the only text prepended before embedding, so it is the
only path by which the document's period reaches the vector - doc_type,
issuer and period_ym are metadata-only. The prompt requires the period
for that reason, and the fallback carries it too.

Batched at 25 chunks per call with a length check, because a single
call returning 67 summaries can drift and attach a summary to the wrong
chunk, which would then be embedded permanently."
```

---

### Task 6: Wire the pipeline together

**Files:**
- Modify: `RAG_PIPELINE/src/ingestion.py`
- Modify: `tests/test_ingestion_unit.py:1-148`

**Interfaces:**
- Consumes: `to_markdown` (Task 2); `extract_document_metadata`, `DocumentMetadata` (Task 3); `split_markdown`, `count_tokens`, `MAX_DOCUMENT_TOKENS` (Task 4); `summarize_chunks` (Task 5)
- Produces: `process_pdf_scoped(filename, file_content, user_id) -> str` — unchanged signature

- [ ] **Step 1: Update the existing test mocks**

In `tests/test_ingestion_unit.py`, change line 2 to:

```python
from unittest.mock import AsyncMock, MagicMock, patch
```

and extend the import at line 9:

```python
from RAG_PIPELINE.src.ingestion import remove_pii, process_pdf_scoped
from RAG_PIPELINE.src.doc_metadata import DocumentMetadata
```

Replace the decorator stack on both test methods (currently lines 69-73 and
104-108) with:

```python
    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    @patch("RAG_PIPELINE.src.ingestion.extract_document_metadata", new_callable=AsyncMock)
    @patch("RAG_PIPELINE.src.ingestion.summarize_chunks", new_callable=AsyncMock)
```

and change both method signatures to:

```python
    async def test_process_pdf_scoped_duplicate(
        self, mock_summaries, mock_metadata, mock_embeddings,
        mock_to_markdown, mock_get_vs, mock_get_client,
    ):
```

```python
    async def test_process_pdf_scoped_success(
        self, mock_summaries, mock_metadata, mock_embeddings,
        mock_to_markdown, mock_get_vs, mock_get_client,
    ):
```

Decorators apply bottom-up, so the parameter order above is correct.

In `test_process_pdf_scoped_success`, replace line 118:

```python
        mock_summary.return_value = "A summary."
```

with:

```python
        mock_metadata.return_value = DocumentMetadata(
            doc_type="bank_statement",
            issuer="Meridian Trust Bank",
            period_ym=202505,
        )
        mock_summaries.return_value = ["May 2025 Meridian checking rent payment."]
```

and replace the PDF-loading block at lines 130-135:

```python
        # Mock PDF Loading
        mock_doc = MagicMock()
        mock_doc.page_content = "This is the document content."
        mock_loader_instance = MagicMock()
        mock_loader.return_value = mock_loader_instance
        mock_loader_instance.load.return_value = [mock_doc]
```

with:

```python
        mock_to_markdown.return_value = (
            "# Statement\n\n| Date | Description | Amount |\n|---|---|---|\n"
            "| 05/02/2025 | Payment - Rent | 1,650.00 |\n"
        )
```

Add a new test at the end of the class, before `if __name__`:

```python
    @patch("RAG_PIPELINE.src.ingestion.get_supabase_client")
    @patch("RAG_PIPELINE.src.ingestion.get_vectorstore")
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
    @patch("RAG_PIPELINE.src.ingestion.GoogleGenerativeAIEmbeddings")
    async def test_process_pdf_scoped_rejects_oversized_document(
        self, mock_embeddings, mock_to_markdown, mock_get_vs, mock_get_client
    ):
        """Oversized documents are rejected, never silently truncated."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_execute_empty = MagicMock()
        mock_execute_empty.data = []
        mock_client.table.return_value.select.return_value \
            .contains.return_value.limit.return_value \
            .execute.return_value = mock_execute_empty

        mock_to_markdown.return_value = "word " * 200_000

        result = await process_pdf_scoped("huge.pdf", b"huge", "user123")

        self.assertIn("too large", result.lower())
        mock_get_vs.return_value.add_texts.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ingestion_unit.py -v
```

Expected: FAIL — `AttributeError: <module 'RAG_PIPELINE.src.ingestion'> does not have the attribute 'to_markdown'`

- [ ] **Step 3: Rewrite the ingestion body**

In `RAG_PIPELINE/src/ingestion.py`, replace the imports at lines 3-4:

```python
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

with:

```python
from .chunk_summary import summarize_chunks
from .chunking import MAX_DOCUMENT_TOKENS, count_tokens, split_markdown
from .convert import to_markdown
from .doc_metadata import extract_document_metadata
```

Delete `generate_summary` entirely (lines 240-258) and `process_pdf` entirely
(lines 302-369). Nothing calls `process_pdf`: `api.py:631` and `reingest.py:67`
both use `process_pdf_scoped`.

Then replace the body of `process_pdf_scoped` from the PDF-loading block through
the `add_texts` call with:

```python
        # 1. Convert to markdown
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            full_text = to_markdown(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 2. Size limit. Reject rather than truncate - half a statement in the
        # index with nothing marking the rest missing is worse than no ingest.
        token_count = count_tokens(full_text)
        if token_count > MAX_DOCUMENT_TOKENS:
            return (
                f"Document too large: {token_count:,} tokens "
                f"(limit {MAX_DOCUMENT_TOKENS:,}). Please split it and re-upload."
            )

        # 3. PII Cleaning
        clean_text = remove_pii(full_text)

        # 4. Extraction Hook (Human-in-the-Loop)
        try:
            extracted_holdings = await extract_holdings_from_text(clean_text)
            if extracted_holdings:
                print(f"Extraction Hook Found {len(extracted_holdings)} items")
                from ManagerAgent.holdings_db import upsert_holding

                for item in extracted_holdings:
                    item["source_doc"] = filename
                    item["status"] = "pending"
                    upsert_holding(user_id, item)
        except Exception as e:
            print(f"Extraction Hook Failed: {e}")

        # 5. Document metadata (one call; replaces generate_summary)
        meta = await extract_document_metadata(clean_text)

        # 6. Chunk on structure
        chunks = split_markdown(clean_text)
        if not chunks:
            return "No text found in PDF."

        # 7. One summary per chunk - the only text that gets embedded with it
        summaries = await summarize_chunks(chunks, meta)

        base_metadata = {
            "file_hash": file_hash,
            "source": filename,
            "user_id": user_id,
            "doc_type": meta.doc_type,
            "issuer": meta.issuer,
            "period_ym": meta.period_ym,
        }

        texts = [
            f"{summary}\n\n{chunk}" for summary, chunk in zip(summaries, chunks)
        ]
        metadatas = [
            {**base_metadata, "chunk_index": i, "chunk_summary": summary}
            for i, summary in enumerate(summaries)
        ]

        # 8. Embed & Store
        vectorstore.add_texts(texts=texts, metadatas=metadatas)

        return f"Successfully processed {len(texts)} chunks for {filename}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ingestion_unit.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run the whole suite and check for leftovers**

```bash
uv run pytest -q
grep -rn --include="*.py" "PyPDFLoader\|generate_summary\|process_pdf\b" . | grep -v "\.venv"
```

Expected: suite green, `grep` returns nothing.

- [ ] **Step 6: Commit**

```bash
git add RAG_PIPELINE/src/ingestion.py tests/test_ingestion_unit.py
git commit -m "feat(rag): ingest markdown with per-chunk summaries and metadata

Each chunk is embedded as its own 20-word summary followed by its text.
Document type, issuer and period stay in metadata for the grader and
for filtering, and are never embedded.

Adds a 50,000 token document limit, rejected rather than truncated.
Deletes generate_summary, absorbed into the metadata call, and dead
process_pdf, which nothing called and which duplicated every line of
process_pdf_scoped."
```

---

### Task 7: Show metadata to the grader

**Files:**
- Modify: `RAG_PIPELINE/src/graph.py:140-195` (`grade_documents`)
- Test: `tests/test_graph_context.py`

**Interfaces:**
- Consumes: chunk metadata written in Task 6; `doc_type_label`, `period_label` from Task 3
- Produces: `describe_document(doc) -> str` in `RAG_PIPELINE.src.graph`

- [ ] **Step 1: Write the failing test**

Create `tests/test_graph_context.py`:

```python
from langchain_core.documents import Document

from RAG_PIPELINE.src.graph import describe_document

APR = Document(
    page_content="April 2025 rent payment.\n\n| 04/02/2025 | Rent | 1,650.00 |",
    metadata={
        "source": "specimen_bank_statement_apr2025.pdf",
        "doc_type": "bank_statement",
        "issuer": "Meridian Trust Bank",
        "period_ym": 202504,
    },
)


def test_describe_document_names_issuer_type_and_period():
    described = describe_document(APR)
    assert "Meridian Trust Bank" in described
    assert "Bank Statement" in described
    assert "April 2025" in described


def test_describe_document_survives_missing_metadata():
    assert isinstance(describe_document(Document(page_content="x", metadata={})), str)


def test_describe_document_omits_absent_period():
    doc = Document(
        page_content="x",
        metadata={"doc_type": "receipt", "issuer": "Acme", "period_ym": None},
    )
    assert describe_document(doc).strip().endswith("Receipt")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_graph_context.py -v
```

Expected: FAIL — `ImportError: cannot import name 'describe_document'`

- [ ] **Step 3: Add the helper**

In `RAG_PIPELINE/src/graph.py`, add this import near the top:

```python
from .doc_metadata import doc_type_label, period_label
```

and add after the `get_llm()` block (around line 35):

```python
def describe_document(doc: Document) -> str:
    """One line naming the document a chunk came from, for the grader."""
    meta = doc.metadata or {}
    parts = [
        meta.get("issuer") or "",
        doc_type_label(meta.get("doc_type") or ""),
        period_label(meta.get("period_ym")),
    ]
    return " · ".join(part for part in parts if part) or "Unknown document"
```

- [ ] **Step 4: Use it in the grader**

In `grade_documents`, replace the human message at lines 169-172:

```python
            (
                "human",
                "Retrieved document: \n\n {document} \n\n User question: {question}",
            ),
```

with:

```python
            (
                "human",
                "Source document: {source}\n\n"
                "Retrieved chunk:\n\n{document}\n\n"
                "User question: {question}",
            ),
```

replace the grader invocation at lines 182-184:

```python
        score = grader_chain.invoke(
            {"question": question, "document": doc.page_content}
        )
```

with:

```python
        score = grader_chain.invoke(
            {
                "question": question,
                "document": doc.page_content,
                "source": describe_document(doc),
            }
        )
```

and extend the grader system prompt at lines 161-164 by appending:

```python
    Grade the CHUNK, not the source document. The source line is context for
    disambiguation only - if the question asks about a specific month and the
    source covers a different one, grade it 'no'."""
```

That instruction is required. Without it a relevant-looking document description
will start passing chunks that are themselves irrelevant.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_graph_context.py -v && uv run pytest -q
```

Expected: 3 passed in the new file, whole suite green.

- [ ] **Step 6: Commit**

```bash
git add RAG_PIPELINE/src/graph.py tests/test_graph_context.py
git commit -m "feat(rag): show document metadata to the grader

perform_similarity_search already returned metadata and nothing read
it. The grader now sees issuer, type and period, so it can reject an
April chunk answering a March question - the second line of defence
behind the chunk summary, which is what makes the right chunk
retrievable in the first place."
```

---

### Task 8: Re-ingest, measure, and tune

**Files:**
- Modify: `RAG_PIPELINE/src/graph.py:88` (thresholds)
- Create: `docs/superpowers/plans/eval-after.txt`

- [ ] **Step 1: Delete the old vectors and re-ingest**

Old chunks carry the global summary inside their embedded text, so a mixed
corpus scores inconsistently. Delete the three fixture documents through the
app's delete endpoint, then re-upload all three.

```bash
uv run python -m RAG_PIPELINE.eval.run <your-user-id> | tee docs/superpowers/plans/eval-after.txt
```

- [ ] **Step 2: Compare against the baseline**

```bash
diff docs/superpowers/plans/eval-baseline.txt docs/superpowers/plans/eval-after.txt
```

Expected: the March and April rent cases both rank 1. If they do not, stop and
investigate rather than proceeding — the chunk summary carrying the period is the
mechanism that should fix them, and tuning would mask the failure. Check first
that the generated summaries actually contain the month.

- [ ] **Step 3: Compare chunk sizes**

750 is a starting value, not a measured one. Re-ingest at 500 and at 1000 by
passing `chunk_size` through `split_markdown` in `ingestion.py`, running the eval
after each, and keeping whichever wins on rank-1 pass rate. Record all three
numbers in `eval-after.txt`. If they tie, keep 750.

- [ ] **Step 4: Retune the retrieval thresholds**

Read the `score` column. Scores are expected to spread relative to baseline, so
the existing constants will be wrong in a way that is not a constant offset.

In `graph.py:88`, replace:

```python
    THRESHOLD = 0.15 if is_broad else 0.35
```

with a value set just below the lowest top-1 score of a passing eval case.

- [ ] **Step 5: Check whether the broad-query hack is still needed**

Per-chunk summaries may make the `is_broad` threshold drop redundant. Run the
eval with `is_broad` forced to `False`. If the pass rate is unchanged, delete the
`is_broad` branch at `graph.py:82-88` and the duplicate keyword list in
`grade_documents` at `graph.py:148-158`. If the rate drops, keep them and note
why in the commit.

- [ ] **Step 6: Commit**

```bash
git add RAG_PIPELINE/src/graph.py docs/superpowers/plans/eval-after.txt
git commit -m "perf(rag): retune retrieval thresholds against the eval

Re-ingested the three specimen statements through the per-chunk-summary
pipeline and re-ran the eval. Threshold set from measured top-1 scores
rather than the previous hand-tuned 0.15/0.35, which existed to
compensate for the score compression caused by prefixing every chunk
with the same document summary."
```

---

## Verification

After Task 8:

```bash
uv run pytest -q                 # whole suite green
uv run ruff check .              # no new lint errors
grep -rn --include="*.py" "PyPDFLoader\|generate_summary" . | grep -v "\.venv"
```

The `grep` must return nothing.

Eval: the March and April rent cases must both rank 1. That pair is why this work
exists — same amount, same description, different month — and if they do not
separate, the summaries are not carrying the period regardless of what the other
eight cases show.
