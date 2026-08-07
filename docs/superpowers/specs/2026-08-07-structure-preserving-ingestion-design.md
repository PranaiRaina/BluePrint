# Markdown Ingestion, Chunk Summaries, and Document Metadata

**Date:** 2026-08-07
**Status:** Approved design, not yet implemented

## Problem

### 1. Every chunk carries an identical prefix, which flattens retrieval

`ingestion.py:437` prepends the same two lines to every chunk of a document
before embedding:

```python
augmented_text = (
    f"Document: {filename}\nGlobal Summary: {summary}\n\nContent: {chunk}"
)
```

The summary is document-global, so this prefix is byte-identical across every
chunk of a file. Shared text pulls the embeddings toward a common direction:
similarity between the query and *every* chunk of a document converges, so
retrieval finds the right document but ranks the wrong chunk within it.

This is contextual retrieval applied backwards. The technique works when the
prepended context is *per-chunk and distinct*; a constant blob is pure dilution.

Corroborating evidence: `retrieve` in `graph.py` runs thresholds of 0.15 (broad)
and 0.35 (narrow) rather than a conventional 0.5, and carries an `is_broad`
keyword list that drops the threshold further for summary-style questions. Both
are compensation for a compressed score range.

### 2. `PyPDFLoader` discards document structure

`process_pdf_scoped` (`ingestion.py:397`) loads PDFs with `PyPDFLoader`, which
emits text in reading order with no headings and no tables. Measured on a
specimen bank statement:

```
Transactions
Date
Description
Credit
Debit
Balance
05/01/2025
Salary Credit - Northwind Analytics
3,200.00
7,450.00
```

Every cell on its own line. There is no section structure for a chunker to split
on, and `RecursiveCharacterTextSplitter` therefore cuts at arbitrary character
offsets.

Three converters were measured on the same file:

| Converter | Headings | Tables |
|---|---|---|
| `pypdf` (current) | none | none — one cell per line |
| `markitdown` | none | mangled; watermark characters interleaved (`PDate`, `NClosing`) |
| `pymupdf4llm` | `# MERIDIAN TRUST BANK`, `## STATEMENT OF ACCOUNT` | coherent markdown tables |

### 3. No metadata to filter or disambiguate on

Chunks carry only `file_hash`, `source`, `user_id`, and `chunk_index`. Nothing
records what kind of document it is, who issued it, or what period it covers, so
nothing can separate three statements whose contents look nearly identical.

## Goals

1. Every chunk's embedded prefix is distinct and describes that chunk.
2. Documents carry filterable metadata: type, issuer, period.
3. Chunks split on document structure rather than character offsets.
4. Retrieval changes are measured, not assumed.

## Non-goals

- **File types beyond PDF.** Upload stays PDF-only; `api.py:609` is unchanged.
  `markitdown` was measured and produced worse output than the current loader on
  a PDF, so it earns nothing here.

- **Preserving the credit/debit distinction.** `pymupdf4llm` merges those two
  columns:

  ```
  | Payment - Rent | 1,650.00 | 5,800.00 |
  ```

  so money in and money out are textually identical, exactly as they are today.
  A known, accepted limitation rather than a regression. Recorded because it is
  recoverable: direction equals the sign of the running-balance delta, which
  reconstructed all 16 specimen rows correctly from the merged output. That
  derivation must happen at ingestion — at query time the previous row's balance
  may sit in a different chunk.

- **A fallback extractor.** Sending PDFs to `gemini-2.5-flash` converts the
  specimen perfectly but measured **22.2s and 4,635 output tokens for one page**,
  against 20ms locally. Rejected on cost and latency.

- **A document-level summary field.** Superseded by per-chunk summaries. The
  grader disambiguates on `doc_type`/`issuer`/`period_ym`, and the generator
  reads the chunk summaries already present in the text.

- **A per-document summary chunk.** It existed to give broad queries a target
  after removing the global summary from chunk text. Per-chunk summaries serve
  that role. If the eval shows broad queries regressing, add it back — do not
  add it speculatively.

- **Query-side date filtering.** `period_ym` makes it possible; wiring it into
  `match_documents` is separate work.

- **Changes to holdings extraction** (`extract_holdings_from_text`) or to PII
  redaction, beyond ordering.

## Design

### Step 0 — Evaluation harness (built first)

Every change below is a retrieval-quality claim and there is currently no way to
test one. The harness comes first so each subsequent step is measured.

`RAG_PIPELINE/eval/questions.json` holds cases over the three fixture statements;
`RAG_PIPELINE/eval/run.py` calls `perform_similarity_search` directly (retrieval
only, no generation) and reports, per case, whether the expected source appeared
in the top *k*, at what rank, and with what score.

Retrieval-only keeps the signal clean — a generation failure and a retrieval
failure have different fixes, and mixing them hides which one moved.

**Record a baseline against the current pipeline before touching anything.**

### Step 1 — Convert PDFs to markdown

Replace the loader in `process_pdf_scoped` (`ingestion.py:397`):

```python
full_text = pymupdf4llm.to_markdown(tmp_path)
```

Delete `process_pdf` (`ingestion.py:302`). It is dead — `api.py:631` and
`reingest.py:67` both call `process_pdf_scoped` — and it is a near-duplicate that
would otherwise need every edit in this spec applied twice.

Dependencies: add `pymupdf4llm` and `tiktoken`, drop `pypdf`.

### Step 2 — Document size limit

Reject documents over **50,000 tokens** at upload with a clear message. Do not
truncate: a silently truncated statement puts half the transactions in the index
with nothing indicating the rest is missing.

50k is ~35 pages at the specimen statements' density (1288–1500 tokens per page),
which covers every realistic personal-finance document — statements run 1–8
pages, tax returns 5–20, brokerage annuals up to 30.

Measured ingest cost at that ceiling, ~67 chunks:

| Stage | Time |
|---|---|
| PII redaction | ~5s (measured at ~10k tokens/sec) |
| Document metadata call | ~3s |
| Chunk summary calls | ~10s |
| Embedding | ~15s |
| **Total** | **~30s** |

PII redaction is not the bottleneck; measured at 0.37s for 14.5k chars, 1.42s for
58k, 3.56s for 146k — linear and cheap.

### Step 3 — Document metadata in one LLM call

One call per document, on the first ~8k characters of the redacted markdown,
using `with_structured_output` so parsing cannot fail the way
`extract_holdings_from_text` can (manual fence-stripping at
`ingestion.py:289-292`):

```python
class DocumentMetadata(BaseModel):
    doc_type: Literal[
        "bank_statement", "brokerage_statement", "credit_card_statement",
        "invoice", "receipt", "pay_stub", "tax_document", "insurance", "other",
    ]
    issuer: str            # "Meridian Trust Bank"; "" if unclear
    period_ym: int | None  # 202505 — the month the document is FOR
```

`period_ym` is a single `YYYYMM` integer rather than a date range. Range queries
need no parsing or casting beyond one cast:

```sql
WHERE (metadata->>'period_ym')::int BETWEEN 202501 AND 202503   -- Q1 2025
```

It sorts correctly, has no timezone or string-comparison traps, and survives
jsonb cleanly. The specimen statements nominally run 05/01→06/01, but the
document *is* the May statement — a single month is the right model.

`doc_type` is constrained rather than free text so it can be filtered on without
normalising a long tail of synonyms.

This replaces `generate_summary` (`ingestion.py:240`). Net LLM calls per document
change from 2 (summary + holdings) to 2 + one call per batch of chunk summaries.

The call runs **after** PII redaction, preserving current ordering — the model
never sees unredacted text. Dates and organisation names are not in
`PII_ENTITIES`, so period and issuer extraction are unaffected.

### Step 4 — Chunking

1. `MarkdownHeaderTextSplitter` on `#`, `##`, `###`.
2. Within each section, split table blocks from prose. A table block is a run of
   consecutive lines beginning with `|`.
3. **Prose** splits with
   `RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=750, chunk_overlap=100)`.
4. **Tables** split by row groups sized to the same 750-token budget, with the
   header row and `|---|` delimiter **repeated at the top of each group**.

Sub-step 4 exists because a character-based split of a long table leaves the
second piece as unlabelled numbers:

```
| 05/18 | AMZN MKTP | -$34.99 | $1,875.45 |
```

Without the header row, whether `-$34.99` is an amount or a balance is a guess.

750 is a starting size, not a settled one. Chunk size trades recall against
precision and the tradeoff is empirical, so **run the eval at 500 and 1000 as
well** and keep whichever wins.

Measured: the fixtures are 1288–1500 tokens each, so 2 chunks per statement at
750.

### Step 5 — Per-chunk summaries as the prefix

Each chunk is embedded as its own summary followed by its text:

```
April 2025 Meridian checking transactions: rent, internet, insurance, interest credit, ATM withdrawal, salary.

| 04/02/2025 | Payment - Rent | 1,650.00 | 5,682.69 |
...
```

**Twenty words maximum.** Long enough to name the period and the content, short
enough that the chunk's own text dominates the embedding.

**The summary must state the document's period.** This is load-bearing, not
stylistic: `doc_type`, `issuer`, and `period_ym` live in metadata and are *not*
embedded, so the chunk summary is the only place the period reaches the vector.
Without it nothing separates March rent from April rent at retrieval time, which
is the failure this design exists to fix.

Generated in batches of **25 chunks per call**, each call receiving the document
metadata and the chunk texts, returning one summary per chunk. Batching bounds
the alignment risk — a single call returning 67 summaries can drift and attach
summary 40 to chunk 41. A 50k-token document costs 3 calls.

Structured output with a list length equal to the batch size, so a
count mismatch is a validation error rather than a silent misalignment.

### Step 6 — Metadata reaches the grader

`perform_similarity_search` already returns `metadata` on every `Document`, and
nothing downstream reads it. Render it into what the grader sees:

`grade_documents` receives the document's type, issuer, and period alongside the
chunk, so it can reject a chunk that is topically plausible but from the wrong
statement period. The prompt must state explicitly that it is grading *the
chunk*, with metadata only for disambiguation — otherwise a relevant-sounding
document description will start passing irrelevant chunks.

This is the second line of defence behind the chunk summary: the summary makes
the right chunk retrievable, the metadata lets the grader reject a wrong-month
chunk that slipped through.

`generate` needs no change — the chunk summaries are already in the text it
receives.

### Step 7 — Migration

Existing chunks have the global summary baked into their embedded text. A mixed
corpus scores inconsistently, so a full re-ingest is required rather than
optional. `RAG_PIPELINE/src/reingest.py` already re-processes every file in the
`rag-documents` bucket and needs no structural change.

After re-ingesting, re-run the eval and retune the thresholds in `retrieve`.
Scores are expected to *spread* — good matches higher, poor matches lower — so
the current 0.15/0.35 constants will be wrong in a way that is not a constant
offset.

### Metadata field reference

| Field | Source | New | Embedded? |
|---|---|---|---|
| `file_hash`, `source`, `user_id`, `chunk_index` | existing | | no |
| `doc_type` | Step 3 | ✓ | no |
| `issuer` | Step 3 | ✓ | no |
| `period_ym` | Step 3 | ✓ | no |
| `chunk_summary` | Step 5 | ✓ | **yes — the prefix** |

## Testing

The three specimen statements are committed fixtures at
`tests/fixtures/specimen_bank_statement_{mar,apr,may}2025.pdf`. They are
synthetic, contain no real data, and make conversion and chunking testable with
no network access.

Offline unit tests:

1. `to_markdown` on a fixture yields at least one `#` heading and one `|` row.
2. Splitting a table over the token budget repeats the header row and `|---|`
   delimiter on every piece, and loses no rows.
3. Chunks respect the token budget.
4. `DocumentMetadata` rejects a `doc_type` outside the allowed set.
5. `period_ym` accepts `202505` and `None`, rejects a non-integer.
6. The summary prompt builder produces one entry per chunk, and a response whose
   length differs from the batch size raises rather than misaligning.
7. A summary longer than 20 words is truncated at assembly.
8. No chunk's embedded text contains `doc_type`, `issuer`, or `period_ym`
   verbatim — those are metadata-only.

`tests/test_ingestion_unit.py` currently patches
`RAG_PIPELINE.src.ingestion.PyPDFLoader` at lines 71 and 106; both move to the
new conversion function.

Retrieval quality is measured by the Step 0 harness — baseline before Step 1,
re-run after Step 5, and again per chunk size in Step 4.

## Sequencing

Step 0 first and alone; record the baseline. Steps 1, 2, and 4 land together —
markdown conversion without markdown-aware chunking gains nothing. Steps 3 and 5
land together and must precede Step 7, because a partial re-ingest produces
exactly the mixed corpus it exists to prevent. Step 6 is independent and can land
any time after Step 3.
