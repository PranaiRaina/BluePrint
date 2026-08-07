# Markdown Ingestion and Document Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest PDFs as markdown with document-level metadata, chunk on structure at 750 tokens, and give every chunk a distinct context prefix so cross-month statement queries retrieve the right document.

**Architecture:** `pymupdf4llm` replaces `PyPDFLoader`. One structured LLM call per document extracts type, issuer, statement period, and summary. Chunking splits markdown sections, keeps table header rows on every piece, and prefixes each chunk with issuer/type/period plus a per-chunk descriptor derived from the dates inside that chunk. The summary leaves the embedded text for metadata, and one extra summary chunk per document serves broad queries.

**Tech Stack:** Python 3.12, `pymupdf4llm`, `langchain-text-splitters`, `tiktoken`, `langchain-google-genai`, Supabase pgvector, pytest.

## Global Constraints

- Chunk size **750 tokens**, overlap **100**, counted with `tiktoken` `cl100k_base`.
- Upload stays **PDF-only**. `api.py:609` is not modified.
- The document metadata call runs **after** PII redaction. The model never sees unredacted text.
- Net LLM calls per document ingest must stay at **2** (metadata + holdings). `generate_summary` is absorbed, not added to.
- All new unit tests run **offline** — no network, no API keys. The eval harness is the only network-dependent piece and is excluded from the default pytest run.
- Existing fixtures live at `tests/fixtures/specimen_bank_statement_{mar,apr,may}2025.pdf`.

---

## Measured Facts This Plan Depends On

Verified against the three fixtures before writing this plan. Do not re-derive; do not assume otherwise.

| Fact | Value |
|---|---|
| `pymupdf4llm.to_markdown` output size | 1500 / 1288 / 1310 tokens (mar / apr / may) |
| Chunks per statement at 750 tokens | 2 |
| Headings produced | exactly `# **MERIDIAN TRUST BANK**` and `## **STATEMENT OF ACCOUNT**` |
| `MarkdownHeaderTextSplitter` sections | 2, and the heading path is **identical for all content** |
| Rent amount | **1,650.00 in all three months** — the cross-document discriminator test |
| Car loan amount | 389.60 in all three months |
| Salary | 3,226.11 (mar) / 3,230.04 (apr) / 3,200.00 (may) |
| Unique-to-one-month items | gym membership 39.79 (mar), interest credit 7.11 (apr), cheque deposit 480.00 (may) |

**Consequence:** the heading path cannot be the per-chunk descriptor — it does not vary. The descriptor is derived from dates found in the chunk, falling back to heading path, then page number.

---

## File Structure

| File | Responsibility |
|---|---|
| `RAG_PIPELINE/src/convert.py` (new) | PDF → markdown. Single dependency boundary and the patch point for tests. |
| `RAG_PIPELINE/src/doc_metadata.py` (new) | `DocumentMetadata` model, the extraction call, and label formatting. |
| `RAG_PIPELINE/src/chunking.py` (new) | Markdown splitting, table-aware splitting, chunk descriptors, prefix assembly. |
| `RAG_PIPELINE/src/ingestion.py` (modify) | Orchestrates the above. Loses the loader, the inline splitter, `generate_summary`, and dead `process_pdf`. |
| `RAG_PIPELINE/src/graph.py` (modify) | Renders metadata for the grader and generator. |
| `RAG_PIPELINE/eval/run.py` (new) | Retrieval-only eval harness. |
| `RAG_PIPELINE/eval/questions.json` (new) | Eval cases over the three fixtures. |

`ingestion.py` is 478 lines and mixes PII, vector store access, extraction, and chunking. These three new modules pull out the parts this work touches; the PII and vector-store halves stay put.

---

### Task 1: Eval harness and baseline

**Files:**
- Create: `RAG_PIPELINE/eval/__init__.py`
- Create: `RAG_PIPELINE/eval/questions.json`
- Create: `RAG_PIPELINE/eval/run.py`

**Interfaces:**
- Consumes: `RAG_PIPELINE.src.ingestion.perform_similarity_search(query, user_id, k, threshold)` returning `list[tuple[Document, float]]`
- Produces: `run_eval(user_id: str, k: int = 10, threshold: float = 0.0) -> dict` with keys `cases` (list of per-case dicts) and `pass_rate` (float)

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

The first two cases are the point of the exercise: identical amount, identical
description, different month. Only the document can distinguish them.

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
would hide near-misses behind an empty result. Threshold tuning happens in Task 7
using these scores.

- [ ] **Step 3: Ingest the three fixtures and record the baseline**

Upload all three fixture PDFs through the running app, then:

```bash
uv run python -m RAG_PIPELINE.eval.run <your-user-id> | tee docs/superpowers/plans/eval-baseline.txt
```

Expected: a table of 10 rows. The March/April rent pair is expected to fail or
rank poorly — that is the baseline this work has to beat. Record the output
verbatim; do not skip this step, because every later claim is measured against it.

- [ ] **Step 4: Commit**

```bash
git add RAG_PIPELINE/eval/ docs/superpowers/plans/eval-baseline.txt
git commit -m "test: add retrieval eval harness over three specimen statements

Ten cases across March, April and May statements. The first two ask for
rent in different months, which is 1,650.00 in both - the only signal
that can separate them is the document, so it is the case the metadata
work has to fix. Baseline recorded before any pipeline change."
```

---

### Task 2: PDF to markdown conversion

**Files:**
- Create: `RAG_PIPELINE/src/convert.py`
- Test: `tests/test_convert.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `to_markdown(path: str) -> str` — full-document markdown
- Produces: `to_markdown_pages(path: str) -> list[tuple[int, str]]` — `(page_number, markdown)`, page numbers 1-based

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, inside `[project].dependencies`, add:

```
    "pymupdf4llm>=0.0.17",
    "tiktoken>=0.7.0",
```

and delete the line `    "pypdf",`.

Then:

```bash
uv sync
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_convert.py`:

```python
import os

import pytest

from RAG_PIPELINE.src.convert import to_markdown, to_markdown_pages

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


def test_to_markdown_pages_are_numbered_from_one():
    pages = to_markdown_pages(MAY)
    assert len(pages) == 1
    assert pages[0][0] == 1
    assert "Payment - Rent" in pages[0][1]


@pytest.mark.parametrize(
    "name", ["mar", "apr", "may"]
)
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

Isolated behind two functions so the extractor can be swapped without touching
ingestion, and so tests have a single patch point.
"""

import pymupdf4llm


def to_markdown(path: str) -> str:
    """Convert a PDF to markdown, headings and tables preserved."""
    return pymupdf4llm.to_markdown(path)


def to_markdown_pages(path: str) -> list[tuple[int, str]]:
    """Convert a PDF to per-page markdown as (page_number, text), 1-based."""
    pages = pymupdf4llm.to_markdown(path, page_chunks=True)
    return [(p["metadata"]["page_number"], p["text"]) for p in pages]
```

Note the metadata key is `page_number`, not `page` — verified against the
installed version. `page_count` is also available on the same dict.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_convert.py -v
```

Expected: 7 passed.

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

### Task 3: Document metadata extraction

**Files:**
- Create: `RAG_PIPELINE/src/doc_metadata.py`
- Test: `tests/test_doc_metadata.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `class DocumentMetadata(BaseModel)` with fields `doc_type: str`, `issuer: str`, `period_start: str | None`, `period_end: str | None`, `summary: str`
  - `async def extract_document_metadata(text: str) -> DocumentMetadata`
  - `def doc_type_label(doc_type: str) -> str`
  - `def period_label(period_start: str | None, period_end: str | None) -> str`

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
            doc_type="mortgage_application",
            issuer="Meridian Trust Bank",
            period_start="2025-05-01",
            period_end="2025-05-31",
            summary="A statement.",
        )


def test_accepts_known_doc_type():
    meta = DocumentMetadata(
        doc_type="bank_statement",
        issuer="Meridian Trust Bank",
        period_start="2025-05-01",
        period_end="2025-05-31",
        summary="A statement.",
    )
    assert meta.doc_type == "bank_statement"


def test_period_may_be_absent():
    meta = DocumentMetadata(
        doc_type="receipt",
        issuer="",
        period_start=None,
        period_end=None,
        summary="A receipt.",
    )
    assert meta.period_start is None


def test_doc_type_label_humanises():
    assert doc_type_label("bank_statement") == "Bank Statement"
    assert doc_type_label("other") == "Other"


def test_period_label_single_month():
    assert period_label("2025-05-01", "2025-05-31") == "May 2025"


def test_period_label_spanning_months():
    assert period_label("2025-03-01", "2025-05-31") == "Mar-May 2025"


def test_period_label_spanning_years():
    assert period_label("2024-12-01", "2025-01-31") == "Dec 2024-Jan 2025"


def test_period_label_absent():
    assert period_label(None, None) == ""


def test_period_label_partial():
    assert period_label("2025-05-01", None) == "May 2025"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_doc_metadata.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.doc_metadata'`

- [ ] **Step 3: Write the implementation**

Create `RAG_PIPELINE/src/doc_metadata.py`:

```python
"""Document-level metadata extracted once per file at ingestion."""

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

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class DocumentMetadata(BaseModel):
    """Structured output of the one metadata call per document."""

    doc_type: Literal[DOC_TYPES] = Field(
        description="The kind of financial document this is."
    )
    issuer: str = Field(
        description="Institution that issued it, e.g. 'Meridian Trust Bank'. "
        "Empty string if unclear."
    )
    period_start: str | None = Field(
        default=None, description="First day the document covers, ISO YYYY-MM-DD."
    )
    period_end: str | None = Field(
        default=None, description="Last day the document covers, ISO YYYY-MM-DD."
    )
    summary: str = Field(
        description="Three to five sentences describing what this document contains."
    )


PROMPT = """Extract metadata from this financial document.

Return the statement period as ISO dates (YYYY-MM-DD). If the document covers no
date range, leave both period fields null. Summarise in three to five sentences,
naming the account, the period, and anything notable.

Document:
{text}"""


async def extract_document_metadata(text: str) -> DocumentMetadata:
    """One LLM call per document. Falls back to an empty 'other' record on failure."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", google_api_key=settings.GOOGLE_API_KEY
        )
        structured = llm.with_structured_output(DocumentMetadata)
        return await structured.ainvoke(PROMPT.format(text=text[:8000]))
    except Exception as e:
        print(f"Metadata Extraction Warning: {e}")
        return DocumentMetadata(
            doc_type="other",
            issuer="",
            period_start=None,
            period_end=None,
            summary="Document summary unavailable.",
        )


def doc_type_label(doc_type: str) -> str:
    """'bank_statement' -> 'Bank Statement'."""
    return " ".join(word.capitalize() for word in doc_type.split("_"))


def _month_year(iso: str) -> tuple[int, int]:
    year, month, _day = iso.split("-")
    return int(year), int(month)


def period_label(period_start: str | None, period_end: str | None) -> str:
    """Condense an ISO range for display: 'May 2025', 'Mar-May 2025', ''."""
    present = [p for p in (period_start, period_end) if p]
    if not present:
        return ""

    try:
        start_year, start_month = _month_year(present[0])
        end_year, end_month = _month_year(present[-1])
    except (ValueError, IndexError):
        return ""

    if (start_year, start_month) == (end_year, end_month):
        return f"{MONTHS[start_month - 1]} {start_year}"
    if start_year == end_year:
        return f"{MONTHS[start_month - 1]}-{MONTHS[end_month - 1]} {start_year}"
    return (
        f"{MONTHS[start_month - 1]} {start_year}-"
        f"{MONTHS[end_month - 1]} {end_year}"
    )
```

`Literal[DOC_TYPES]` works because `DOC_TYPES` is a tuple of string literals —
Pydantic expands it, and the constraint reaches the model through the structured
output schema so invalid values are rejected rather than silently stored.

The fallback matters: a metadata failure must not abort an ingest that would
otherwise succeed. The document still gets chunked and embedded, just without a
useful prefix.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_doc_metadata.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add RAG_PIPELINE/src/doc_metadata.py tests/test_doc_metadata.py
git commit -m "feat(rag): extract document type, issuer, period and summary

One structured LLM call per document, replacing generate_summary rather
than adding to it. Uses with_structured_output so parsing cannot fail
the way extract_holdings_from_text can with its manual fence stripping.
doc_type is a Literal so it can be filtered on later without
normalising synonyms, and ISO dates compare correctly under jsonb's
lexicographic ordering for the date filter that comes next."
```

---

### Task 4: Structure-aware chunking

**Files:**
- Create: `RAG_PIPELINE/src/chunking.py`
- Test: `tests/test_chunking.py`

**Interfaces:**
- Consumes: `doc_type_label`, `period_label` from `RAG_PIPELINE.src.doc_metadata`
- Produces:
  - `count_tokens(text: str) -> int`
  - `split_markdown(md: str, page: int = 1, chunk_size: int = 750, chunk_overlap: int = 100) -> list[dict]` — each dict has keys `text`, `header_path`, `page`
  - `chunk_descriptor(chunk: dict) -> str`
  - `build_prefix(issuer: str, doc_type: str, period_start: str | None, period_end: str | None, descriptor: str) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chunking.py`:

```python
import os

from RAG_PIPELINE.src.chunking import (
    build_prefix,
    chunk_descriptor,
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


def test_table_split_repeats_header_on_every_piece():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert "| Date | Description | Amount | Balance |" in chunk["text"]
        assert "|---|---|---|---|" in chunk["text"]


def test_table_split_loses_no_rows():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    for day in range(1, 61):
        needle = f"Purchase number {day} |"
        assert any(needle in chunk["text"] for chunk in chunks), f"lost row {day}"


def test_chunks_respect_the_token_budget():
    chunks = split_markdown(TABLE_MD, chunk_size=200)
    # One row can never be split further, so allow a single-row overshoot.
    for chunk in chunks:
        assert count_tokens(chunk["text"]) <= 200 + 60


def test_descriptor_uses_date_range_when_present():
    chunk = {
        "text": "| 05/02/2025 | Rent |\n| 05/19/2025 | Fuel |",
        "header_path": "Statement",
        "page": 1,
    }
    assert chunk_descriptor(chunk) == "05/02-05/19"


def test_descriptor_collapses_a_single_date():
    chunk = {"text": "| 05/02/2025 | Rent |", "header_path": "", "page": 1}
    assert chunk_descriptor(chunk) == "05/02"


def test_descriptor_falls_back_to_header_path():
    chunk = {"text": "No dates here at all.", "header_path": "Fees", "page": 3}
    assert chunk_descriptor(chunk) == "Fees"


def test_descriptor_falls_back_to_page():
    chunk = {"text": "No dates here at all.", "header_path": "", "page": 3}
    assert chunk_descriptor(chunk) == "p.3"


def test_build_prefix_full():
    assert build_prefix(
        "Meridian Trust Bank", "bank_statement", "2025-05-01", "2025-05-31", "05/02-05/19"
    ) == "[Meridian Trust Bank · Bank Statement · May 2025 · 05/02-05/19]"


def test_build_prefix_skips_empty_parts():
    assert build_prefix("", "receipt", None, None, "p.1") == "[Receipt · p.1]"


def test_real_statement_chunks_get_distinct_prefixes():
    md = to_markdown(MAY)
    chunks = split_markdown(md)
    assert len(chunks) > 1
    prefixes = [
        build_prefix(
            "Meridian Trust Bank", "bank_statement", "2025-05-01", "2025-05-31",
            chunk_descriptor(chunk),
        )
        for chunk in chunks
    ]
    assert len(set(prefixes)) == len(prefixes), f"prefixes repeat: {prefixes}"
```

The last test is the one that matters. The heading path is identical across a
statement's chunks, so a descriptor built from headings would make every prefix
the same — reproducing the exact defect this work exists to remove.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'RAG_PIPELINE.src.chunking'`

- [ ] **Step 3: Write the implementation**

Create `RAG_PIPELINE/src/chunking.py`:

```python
"""Markdown-aware chunking with per-chunk context prefixes."""

import re

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .doc_metadata import doc_type_label, period_label

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]
DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
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
    md: str, page: int = 1, chunk_size: int = 750, chunk_overlap: int = 100
) -> list[dict]:
    """Split markdown into chunks carrying their heading path and page number."""
    sections = MarkdownHeaderTextSplitter(
        HEADERS_TO_SPLIT_ON, strip_headers=False
    ).split_text(md)

    prose_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    chunks: list[dict] = []
    for section in sections:
        header_path = " › ".join(
            value.strip("* ") for value in section.metadata.values() if value
        )
        for block, is_table in _blocks(section.page_content):
            if not block.strip():
                continue
            pieces = (
                _split_table(block, chunk_size)
                if is_table
                else prose_splitter.split_text(block)
            )
            for piece in pieces:
                if piece.strip():
                    chunks.append(
                        {"text": piece, "header_path": header_path, "page": page}
                    )
    return chunks


def chunk_descriptor(chunk: dict) -> str:
    """Short label for one chunk. Dates first - they are what actually varies."""
    stamps = sorted(
        {(year, month, day) for month, day, year in DATE_RE.findall(chunk["text"])}
    )
    if stamps:
        low, high = stamps[0], stamps[-1]
        if low == high:
            return f"{low[1]}/{low[2]}"
        return f"{low[1]}/{low[2]}-{high[1]}/{high[2]}"

    if chunk.get("header_path"):
        return chunk["header_path"]
    return f"p.{chunk.get('page', 1)}"


def build_prefix(
    issuer: str,
    doc_type: str,
    period_start: str | None,
    period_end: str | None,
    descriptor: str,
) -> str:
    """'[Meridian Trust Bank · Bank Statement · May 2025 · 05/02-05/19]'"""
    parts = [
        issuer,
        doc_type_label(doc_type) if doc_type else "",
        period_label(period_start, period_end),
        descriptor,
    ]
    return "[" + " · ".join(part for part in parts if part) + "]"
```

Dates come before the heading path in `chunk_descriptor` because on the specimen
statements the heading path is constant across the document — it cannot
discriminate. Dates can, and they are also what a date-scoped question needs.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add RAG_PIPELINE/src/chunking.py tests/test_chunking.py
git commit -m "feat(rag): chunk on markdown structure with varying prefixes

Splits sections, then splits tables by row group repeating the header
row and delimiter on every piece - a character split of a long
transaction table otherwise leaves the second piece as unlabelled
numbers.

The per-chunk descriptor comes from dates in the chunk, not the heading
path. Measured on the specimen statements, pymupdf4llm emits exactly
two headings and the heading path is identical for all content, so a
heading-based descriptor would give every chunk the same prefix - the
defect this exists to remove."
```

---

### Task 5: Wire the pipeline together

**Files:**
- Modify: `RAG_PIPELINE/src/ingestion.py`
- Modify: `tests/test_ingestion_unit.py:69-148`

**Interfaces:**
- Consumes: `to_markdown` (Task 2); `extract_document_metadata`, `DocumentMetadata` (Task 3); `split_markdown`, `chunk_descriptor`, `build_prefix` (Task 4)
- Produces: `process_pdf_scoped(filename, file_content, user_id) -> str` — unchanged signature

- [ ] **Step 1: Update the existing test mocks**

In `tests/test_ingestion_unit.py`, replace the decorator at line 71 and line 106:

```python
    @patch("RAG_PIPELINE.src.ingestion.PyPDFLoader")
```

with:

```python
    @patch("RAG_PIPELINE.src.ingestion.to_markdown")
```

Rename the parameter `mock_loader` to `mock_to_markdown` in both signatures
(lines 74 and 109), and replace the decorator at lines 73 and 108:

```python
    @patch("RAG_PIPELINE.src.ingestion.generate_summary")
```

with:

```python
    @patch("RAG_PIPELINE.src.ingestion.extract_document_metadata")
```

Rename `mock_summary` to `mock_metadata` in both signatures.

In `test_process_pdf_scoped_success`, replace the PDF-loading mock block at
lines 130-135:

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
        # Mock conversion and metadata
        mock_to_markdown.return_value = (
            "# Statement\n\n| Date | Description | Amount |\n|---|---|---|\n"
            "| 05/02/2025 | Payment - Rent | 1,650.00 |\n"
        )
```

and replace line 118:

```python
        mock_summary.return_value = "A summary."
```

with:

```python
        mock_metadata.return_value = DocumentMetadata(
            doc_type="bank_statement",
            issuer="Meridian Trust Bank",
            period_start="2025-05-01",
            period_end="2025-05-31",
            summary="A summary.",
        )
```

Update the import at line 9:

```python
from RAG_PIPELINE.src.ingestion import remove_pii, process_pdf_scoped
from RAG_PIPELINE.src.doc_metadata import DocumentMetadata
```

`extract_document_metadata` is async, so its patch must be an `AsyncMock` or the
awaited call returns a `MagicMock` instead of a `DocumentMetadata`. Change line 2
to:

```python
from unittest.mock import AsyncMock, MagicMock, patch
```

and write that decorator on both test methods as:

```python
    @patch("RAG_PIPELINE.src.ingestion.extract_document_metadata", new_callable=AsyncMock)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ingestion_unit.py -v
```

Expected: FAIL — `AttributeError: <module 'RAG_PIPELINE.src.ingestion'> does not have the attribute 'to_markdown'`

- [ ] **Step 3: Rewrite the ingestion body**

In `RAG_PIPELINE/src/ingestion.py`, replace the import at line 3:

```python
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

with:

```python
from .chunking import build_prefix, chunk_descriptor, split_markdown
from .convert import to_markdown
from .doc_metadata import extract_document_metadata
```

Delete `generate_summary` entirely (lines 240-258) and delete `process_pdf`
entirely (lines 302-369). Nothing calls `process_pdf`: `api.py:631` and
`reingest.py:67` both use `process_pdf_scoped`.

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

        # 2. PII Cleaning
        clean_text = remove_pii(full_text)

        # 3. Extraction Hook (Human-in-the-Loop)
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

        # 4. Document metadata (one call; replaces generate_summary)
        meta = await extract_document_metadata(clean_text)

        # 5. Chunk on structure
        chunks = split_markdown(clean_text)

        base_metadata = {
            "file_hash": file_hash,
            "source": filename,
            "user_id": user_id,
            "doc_type": meta.doc_type,
            "issuer": meta.issuer,
            "period_start": meta.period_start,
            "period_end": meta.period_end,
            "summary": meta.summary,
        }

        texts = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            prefix = build_prefix(
                meta.issuer,
                meta.doc_type,
                meta.period_start,
                meta.period_end,
                chunk_descriptor(chunk),
            )
            texts.append(f"{prefix}\n\n{chunk['text']}")
            metadatas.append(
                {
                    **base_metadata,
                    "chunk_index": i,
                    "header_path": chunk["header_path"],
                    "page": chunk["page"],
                    "is_summary_chunk": False,
                }
            )

        # 6. One summary chunk per document, for broad queries
        if texts:
            summary_body = (
                f"{meta.issuer} — {meta.doc_type.replace('_', ' ')}\n"
                f"Period: {meta.period_start or 'n/a'} to {meta.period_end or 'n/a'}\n"
                f"Source: {filename}\n\n{meta.summary}"
            )
            texts.append(summary_body)
            metadatas.append(
                {
                    **base_metadata,
                    "chunk_index": -1,
                    "header_path": "",
                    "page": 1,
                    "is_summary_chunk": True,
                }
            )

        if not texts:
            return "No text found in PDF."

        # 7. Embed & Store
        vectorstore.add_texts(texts=texts, metadatas=metadatas)

        return f"Successfully processed {len(texts)} chunks for {filename}"
```

The summary chunk carries no prefix — its body already names issuer, type, and
period, so a prefix would only repeat them.

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ingestion_unit.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run the whole suite**

```bash
uv run pytest -q
```

Expected: all previously-passing tests still pass. No test should reference
`PyPDFLoader`, `generate_summary`, or `process_pdf` any more:

```bash
grep -rn --include="*.py" "PyPDFLoader\|generate_summary\|process_pdf\b" . | grep -v "\.venv"
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add RAG_PIPELINE/src/ingestion.py tests/test_ingestion_unit.py
git commit -m "feat(rag): ingest markdown with metadata and varying prefixes

Replaces the PyPDFLoader path with markdown conversion, structure-aware
chunking, and a per-chunk prefix. The document summary leaves the
embedded text for metadata and gains one summary chunk per document, so
broad queries have a real retrieval target instead of matching a blob
that was repeated on every chunk.

Deletes generate_summary, absorbed into the metadata call, and dead
process_pdf, which nothing called and which duplicated every line of
process_pdf_scoped."
```

---

### Task 6: Show metadata to the grader and the generator

**Files:**
- Modify: `RAG_PIPELINE/src/graph.py:140-195` (`grade_documents`), `:243-277` (`generate`)
- Test: `tests/test_graph_context.py`

**Interfaces:**
- Consumes: chunk metadata written in Task 5 (`doc_type`, `issuer`, `period_start`, `period_end`, `summary`, `source`)
- Produces: `describe_document(doc) -> str`, `format_context(documents) -> str` in `RAG_PIPELINE.src.graph`

- [ ] **Step 1: Write the failing test**

Create `tests/test_graph_context.py`:

```python
from langchain_core.documents import Document

from RAG_PIPELINE.src.graph import describe_document, format_context

APR = Document(
    page_content="| 04/02/2025 | Payment - Rent | 1,650.00 |",
    metadata={
        "source": "specimen_bank_statement_apr2025.pdf",
        "doc_type": "bank_statement",
        "issuer": "Meridian Trust Bank",
        "period_start": "2025-04-01",
        "period_end": "2025-04-30",
        "summary": "April statement.",
    },
)
APR_SECOND = Document(page_content="| 04/20/2025 | ATM |", metadata=dict(APR.metadata))


def test_describe_document_names_issuer_and_period():
    described = describe_document(APR)
    assert "Meridian Trust Bank" in described
    assert "2025-04-01" in described
    assert "2025-04-30" in described


def test_describe_document_survives_missing_metadata():
    bare = Document(page_content="text", metadata={})
    assert isinstance(describe_document(bare), str)


def test_format_context_emits_each_document_once():
    context = format_context([APR, APR_SECOND])
    assert context.count("April statement.") == 1


def test_format_context_includes_every_chunk():
    context = format_context([APR, APR_SECOND])
    assert "Payment - Rent" in context
    assert "ATM" in context
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_graph_context.py -v
```

Expected: FAIL — `ImportError: cannot import name 'describe_document'`

- [ ] **Step 3: Add the helpers**

In `RAG_PIPELINE/src/graph.py`, add after the `get_llm()` block (around line 35):

```python
def describe_document(doc: Document) -> str:
    """One line naming the document a chunk came from."""
    meta = doc.metadata or {}
    parts = [
        meta.get("issuer") or "",
        (meta.get("doc_type") or "").replace("_", " "),
        meta.get("source") or "",
    ]
    line = " · ".join(part for part in parts if part) or "Unknown document"
    start, end = meta.get("period_start"), meta.get("period_end")
    if start or end:
        line += f" (covers {start or '?'} to {end or '?'})"
    return line


def format_context(documents: list[Document]) -> str:
    """Group chunks under their source document, describing each source once."""
    grouped: dict[str, list[Document]] = {}
    for doc in documents:
        key = (doc.metadata or {}).get("source", "unknown")
        grouped.setdefault(key, []).append(doc)

    blocks = []
    for docs in grouped.values():
        header = describe_document(docs[0])
        summary = (docs[0].metadata or {}).get("summary") or ""
        block = f"--- {header} ---"
        if summary:
            block += f"\n{summary}"
        for doc in docs:
            block += f"\n\n{doc.page_content}"
        blocks.append(block)

    return "\n\n".join(blocks)
```

- [ ] **Step 4: Use them in `generate`**

In `generate`, replace line 251:

```python
    context = "\n\n".join([doc.page_content for doc in documents])
```

with:

```python
    context = format_context(documents)
```

- [ ] **Step 5: Use `describe_document` in the grader**

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

and replace the grader invocation at lines 182-184:

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

Then extend the grader system prompt at lines 161-164 by appending this line:

```python
    Grade the CHUNK, not the source document. The source line is context for
    disambiguation only - if the question asks about a specific month or period
    and the source covers a different one, grade it 'no'."""
```

That instruction is required. Without it a relevant-looking document description
will start passing chunks that are themselves irrelevant.

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_graph_context.py -v && uv run pytest -q
```

Expected: 4 passed in the new file, whole suite green.

- [ ] **Step 7: Commit**

```bash
git add RAG_PIPELINE/src/graph.py tests/test_graph_context.py
git commit -m "feat(rag): show document metadata to the grader and generator

perform_similarity_search already returned metadata and nothing read
it. The grader now sees which document and period a chunk came from, so
it can reject an April chunk answering a March question - the failure
the three specimen statements are built to expose, since rent is
1,650.00 in every one of them.

The generator groups chunks by source and prints each document's
summary once rather than repeating it per chunk."
```

---

### Task 7: Re-ingest, measure, and tune

**Files:**
- Modify: `RAG_PIPELINE/src/graph.py:88` (thresholds), `:102` (k)
- Create: `docs/superpowers/plans/eval-after.txt`

**Interfaces:**
- Consumes: `run_eval` from Task 1; the full pipeline from Tasks 2-6

- [ ] **Step 1: Delete the old vectors and re-ingest**

Old chunks carry the summary inside their embedded text, so a mixed corpus scores
inconsistently. Delete the three fixture documents through the app's delete
endpoint, then re-upload all three.

```bash
uv run python -m RAG_PIPELINE.eval.run <your-user-id> | tee docs/superpowers/plans/eval-after.txt
```

- [ ] **Step 2: Compare against the baseline**

```bash
diff docs/superpowers/plans/eval-baseline.txt docs/superpowers/plans/eval-after.txt
```

Expected: the March/April rent pair now ranks 1. If it does not, stop and
investigate rather than proceeding to tuning — the prefix is the mechanism that
should fix it, and a tuning change would mask the failure.

- [ ] **Step 3: Compare chunk sizes**

750 is a starting value, not a measured one. Re-ingest at 500 and at 1000 by
passing `chunk_size` through `split_markdown` in `ingestion.py`, running the eval
after each, and keeping whichever wins on rank-1 pass rate.

Record all three numbers in `eval-after.txt`. If they tie, keep 750.

- [ ] **Step 4: Retune the retrieval thresholds**

Read the `score` column from the eval output. Scores are expected to spread
relative to baseline — good matches higher, poor matches lower — so the existing
constants will be wrong in a way that is not a constant offset.

In `graph.py:88`, replace:

```python
    THRESHOLD = 0.15 if is_broad else 0.35
```

with a value set just below the lowest top-1 score of a passing eval case.

- [ ] **Step 5: Check whether the broad-query hack is still needed**

The summary chunk gives broad queries a real target, which may make the
`is_broad` threshold drop redundant. Test it:

```bash
uv run python -m RAG_PIPELINE.eval.run <your-user-id>
```

with `is_broad` forced to `False`. If the pass rate is unchanged, delete the
`is_broad` branch at `graph.py:82-88` and the duplicate keyword list in
`grade_documents` at `graph.py:148-158`. If the rate drops, keep them and note
why in the commit.

- [ ] **Step 6: Commit**

```bash
git add RAG_PIPELINE/src/graph.py docs/superpowers/plans/eval-after.txt
git commit -m "perf(rag): retune retrieval thresholds against the eval

Re-ingested the three specimen statements through the markdown
pipeline and re-ran the eval. Threshold set from measured top-1 scores
rather than the previous hand-tuned 0.15/0.35, which existed to
compensate for the score compression caused by prefixing every chunk
with the same document summary."
```

---

## Verification

After Task 7, all of the following must hold:

```bash
uv run pytest -q                 # whole suite green
uv run ruff check .              # no new lint errors
grep -rn --include="*.py" "PyPDFLoader\|generate_summary" . | grep -v "\.venv"
```

The `grep` must return nothing.

Eval: the March and April rent cases must both rank 1. That pair is the reason
this work exists — same amount, same description, different month — and if they
do not separate, the metadata is not doing its job regardless of what the other
eight cases show.
