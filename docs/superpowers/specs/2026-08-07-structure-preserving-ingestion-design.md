# Markdown Ingestion and Document Metadata

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

`pymupdf4llm` is the only one that produces markdown a header splitter can use.

## Goals

1. Chunks split on real document structure rather than character offsets.
2. Each chunk's embedded prefix varies by chunk.
3. Documents carry queryable metadata: type, issuer, statement period, summary.
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
  This is a known, accepted limitation rather than a regression. Recorded because
  it is recoverable later: direction equals the sign of the running-balance
  delta, which reconstructed all 16 specimen rows correctly from the merged
  output. That derivation must happen at ingestion — at query time the previous
  row's balance may sit in a different chunk.

- **A fallback extractor.** Sending PDFs to `gemini-2.5-flash` converts the
  specimen perfectly but measured **22.2s and 4,635 output tokens for one page**,
  against 20ms for local extraction. Rejected on cost and latency, and on the
  truncation risk for long statements.

- **Query-side date extraction and filtering.** The metadata stored here makes it
  possible; wiring it into `match_documents` is separate work.

- **Changes to holdings extraction** (`extract_holdings_from_text`) or to PII
  redaction, beyond the ordering noted in Step 2.

## Design

### Step 0 — Evaluation harness (built first)

Every change below is a retrieval-quality claim and there is currently no way to
test one. The harness comes first so each subsequent step is measured.

`RAG_PIPELINE/eval/questions.json` — a list of cases:

```json
[
  {
    "question": "How much did I pay for rent in May?",
    "expect_source": "specimen_bank_statement_may2025.pdf",
    "expect_contains": ["1,650.00"]
  }
]
```

`RAG_PIPELINE/eval/run.py` calls `perform_similarity_search` directly (retrieval
only, no generation) and reports per case: whether the expected source appeared
in the top *k*, at what rank, and with what score. It prints a summary table and
a pass rate.

Retrieval-only keeps the signal clean — a generation failure and a retrieval
failure have different fixes, and mixing them hides which one moved.

Run as `uv run python -m RAG_PIPELINE.eval.run`. Not part of the default pytest
suite: it needs live embeddings and real ingested data. **Record a baseline
against the current pipeline before touching anything.**

### Step 1 — Convert PDFs to markdown

Replace the loader in `process_pdf_scoped` (`ingestion.py:397`):

```python
full_text = pymupdf4llm.to_markdown(tmp_path)
```

Delete `process_pdf` (`ingestion.py:302`). It is dead — `api.py:631` and
`reingest.py:67` both call `process_pdf_scoped` — and it is a near-duplicate that
would otherwise need every edit in this spec applied twice.

Dependencies: add `pymupdf4llm` and `tiktoken`, drop `pypdf`. `tiktoken`
currently resolves only as a transitive dependency of `litellm`; Step 3 uses it
directly.

### Step 2 — Document metadata in one LLM call

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
    issuer: str                # "Meridian Trust Bank"; "" if unclear
    period_start: str | None   # ISO "YYYY-MM-DD"
    period_end: str | None
    summary: str               # 3-5 sentences
```

ISO date strings compare correctly under lexicographic ordering, so a later
date-range filter works against jsonb with no type migration.

`doc_type` is constrained rather than free text so it can be filtered on without
normalising a long tail of synonyms.

This replaces `generate_summary` (`ingestion.py:240`), which becomes one field of
this call rather than its own request. Net LLM calls per document: unchanged.

The call runs **after** PII redaction, preserving current ordering — the model
never sees unredacted text. Dates and organisation names are not in
`PII_ENTITIES`, so period and issuer extraction are unaffected.

### Step 3 — Chunking

1. `MarkdownHeaderTextSplitter` on `#`, `##`, `###`. Each chunk arrives with its
   heading path already in metadata — this is what Step 1 buys.
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

750 is the starting size, not a settled one. Chunk size trades recall against
precision and the tradeoff is empirical, so **run the eval at 500 and 1000 as
well** once the rest of the pipeline is in place, and keep whichever wins. This
is exactly the kind of question Step 0 exists to answer.

### Step 4 — A per-chunk prefix that varies

Replace the constant prefix at `ingestion.py:437`:

```python
prefix = f"[{issuer} · {doc_type_label} · {period_label} · {header_path}]"
embedded_text = f"{prefix}\n\n{chunk}"
```

`doc_type_label` is the enum humanised — `bank_statement` renders as
`Bank Statement`. `period_label` derives from the ISO dates: `May 2025` when both
fall in one month, `May-Jul 2025` when they span several, omitted when both are
`None`. Stored fields stay ISO; only the display form is condensed.

Producing:

```
[Meridian Trust Bank · Bank Statement · May 2025 · Transactions]
```

**The descriptor comes from dates in the chunk, not the heading path.** Measured
on all three fixtures, `pymupdf4llm` emits exactly two headings —
`# MERIDIAN TRUST BANK` and `## STATEMENT OF ACCOUNT` — and
`MarkdownHeaderTextSplitter` returns 2 sections whose heading path is **identical
for all content**. A heading-based descriptor would therefore give every chunk of
a statement the same prefix, reproducing Problem 1 exactly.

Dates vary per chunk and are also what date-scoped questions need:

```
[Meridian Trust Bank · Bank Statement · May 2025 · 05/01-05/16]
[Meridian Trust Bank · Bank Statement · May 2025 · 05/19-06/01]
```

Descriptor precedence: date range from the chunk's own text, else `header_path`
(which serves document types that do have real headings), else `p.N`.

At roughly 80 characters the prefix is also about a third of the current one's
length.

Note that with statements measuring 1288–1500 tokens, a document yields only 2
chunks at 750. Within-document ranking is therefore nearly moot on this corpus —
the load is carried by the document-level fields, particularly the period, which
is the only thing separating three months whose rent is 1,650.00 in all of them.

### Step 5 — Summary moves to metadata, plus one summary chunk

The summary leaves the embedded text entirely and lives in metadata, where the
grader and generator read it. It is the longest and most invariant part of the
current prefix, and therefore the largest single contributor to Problem 1.

Removing it costs the broad-query case: "summarize my finances" currently matches
summary text present in every chunk, and so works by accident. To replace that
deliberately, emit **one additional chunk per document** whose content *is* the
rendered metadata plus summary, flagged `is_summary_chunk: true`.

That chunk carries no Step 4 prefix — its body already states issuer, type, and
period in full. Its `header_path` is empty and its `chunk_index` is `-1`.

This gives document-level questions a real retrieval target instead of an
artifact, and may make the `is_broad` threshold-drop in `graph.py` redundant.
Verify with the eval; remove it only if the numbers support that.

### Step 6 — Metadata reaches the grader and the generator

`perform_similarity_search` already returns `metadata` on every `Document`, and
nothing downstream reads it. Render it into what the model sees:

- **`grade_documents`** receives the document's type, issuer, and period
  alongside the chunk, so it can reject a chunk that is topically plausible but
  from the wrong statement period. The prompt must state explicitly that it is
  grading *the chunk*, with metadata only for disambiguation — otherwise a
  relevant-sounding document summary will start passing irrelevant chunks.
- **`generate`** receives the same, rendered **once per source document** rather
  than once per chunk, so six chunks from one statement no longer repeat the same
  summary six times.

### Step 7 — Migration

Existing chunks have the summary baked into their embedded text. A mixed corpus
scores inconsistently, so a full re-ingest is required rather than optional.
`RAG_PIPELINE/src/reingest.py` already re-processes every file in the
`rag-documents` bucket and needs no structural change.

After re-ingesting, re-run the eval and retune the thresholds in `retrieve`.
Scores are expected to *spread* — good matches higher, poor matches lower — so
the current 0.15/0.35 constants will be wrong in a way that is not a constant
offset.

### Metadata field reference

| Field | Source | New |
|---|---|---|
| `file_hash`, `source`, `user_id`, `chunk_index` | existing | |
| `doc_type` | Step 2 | ✓ |
| `issuer` | Step 2 | ✓ |
| `period_start`, `period_end` | Step 2 | ✓ |
| `summary` | Step 2 | moved out of embedded text |
| `header_path` | Step 3 | ✓ |
| `page` | Step 3 | ✓ |
| `is_summary_chunk` | Step 5 | ✓ |

## Testing

The specimen statement becomes a committed fixture at
`tests/fixtures/specimen_bank_statement_may2025.pdf`. It is synthetic, contains
no real data, and makes conversion testable with no network access.

Offline unit tests, in the default suite:

1. `to_markdown` on the fixture yields at least one `#` heading.
2. `MarkdownHeaderTextSplitter` produces more than one section from it, each
   carrying a non-empty heading path.
3. Two chunks from different sections receive different prefixes.
4. A document with no headings still gets per-chunk-varying prefixes via the
   page-number fallback.
5. Splitting a table over the token budget repeats the header row and `|---|`
   delimiter on each piece.
6. `DocumentMetadata` rejects a `doc_type` outside the allowed set.
7. The summary chunk is emitted once per document, with `chunk_index == -1` and
   no prefix.
8. No chunk's embedded text contains the document summary.

`tests/test_ingestion_unit.py` currently patches
`RAG_PIPELINE.src.ingestion.PyPDFLoader` at lines 71 and 106; both move to the
new conversion function.

Retrieval quality is measured by the Step 0 harness, not by pytest — baseline
before Step 1, re-run after Step 5, and again per chunk size in Step 3.

## Sequencing

Step 0 first and alone; record the baseline. Steps 1–3 land together, since
markdown conversion without markdown-aware chunking gains nothing. Steps 4 and 5
land together and must precede Step 7, because a partial re-ingest produces
exactly the mixed corpus it exists to prevent. Step 6 is independent and can land
any time after Step 2.
