# Structure-Preserving Ingestion and Document Metadata

**Date:** 2026-08-07
**Status:** Approved design, not yet implemented

## Problem

Two independent defects, both in ingestion. The first is a correctness bug that
silently produces wrong answers. The second degrades retrieval ranking.

### 1. Column position is discarded, so credit and debit are indistinguishable

`process_pdf_scoped` (`ingestion.py:397`) loads PDFs with `PyPDFLoader`, which
emits text in reading order and drops horizontal position. Empty table cells
leave no text, so a row with a blank column silently shifts left.

Measured on a specimen bank statement with columns
`Date | Description | Credit | Debit | Balance`:

```
05/01/2025
Salary Credit - Northwind Analytics
3,200.00                              <- Credit column
7,450.00

05/02/2025
Payment - Rent
1,650.00                              <- Debit column
5,800.00
```

Both rows reduce to *date, description, number, number*. Nothing distinguishes
money in from money out. The model can only infer direction from vocabulary in
the description, which fails on near-identical wording:

```
Account Transfer In - Savings     1,000.00
Account Transfer Out - Brokerage  2,000.00
```

The information is not merely hard to read — it is absent from the text.

Alternative extractors were measured on the same file:

| Extractor | Headings | Credit/Debit preserved |
|---|---|---|
| `pypdf` (current) | no | **no** |
| `pymupdf4llm` | yes (`# MERIDIAN TRUST BANK`) | no — merges Credit and Debit into one column |
| `pymupdf.find_tables()` | n/a | n/a — finds 0 tables (no ruling lines) |
| `pdfplumber` word positions | via font size | **yes** |

`pdfplumber` exposes each word's bounding box. The three numeric columns have
distinct right edges — Credit 318.8, Debit 438.8, Balance 562.8 — and every row
in the specimen classified correctly by right edge, including both transfers.

It also exposes font size and name per word, which recovers heading structure
that no PDF format field provides:

```
 8.5pt          x172 words   <- body
13.0pt bold     x3
14.0pt bold     x3           <- "STATEMENT OF ACCOUNT"
20.0pt bold     x1           <- "MERIDIAN TRUST BANK"
88-113pt bold   x25          <- diagonal SPECIMEN watermark
```

### 2. Every chunk carries an identical prefix, which flattens retrieval

`ingestion.py:437` prepends the same two lines to every chunk of a document
before embedding:

```python
augmented_text = (
    f"Document: {filename}\nGlobal Summary: {summary}\n\nContent: {chunk}"
)
```

The summary is document-global, so this prefix is byte-identical across all
chunks of a file. Shared text pulls the embeddings toward a common direction:
similarity between the query and *every* chunk of a document converges, so
retrieval finds the right document but ranks the wrong chunk within it.

This is contextual retrieval applied backwards. The technique works when the
prepended context is *per-chunk and distinct*; a constant blob is pure dilution.

Corroborating evidence: `retrieve` in `graph.py` runs thresholds of 0.15 (broad)
and 0.35 (narrow) rather than a conventional 0.5, and carries an `is_broad`
keyword list that drops the threshold further for summary-style questions. Both
are compensation for compressed score ranges.

The planned move to 500-token chunks makes this worse, not better — a fixed
~60-token prefix is ~12% of a 500-token chunk versus ~6% of a 1000-token one.

### 3. PDF is the only accepted format

`api.py:609` rejects anything not ending in `.pdf`, and `documents` listing
(`api.py:682`, `api.py:691`) filters the same way.

## Goals

1. Table columns survive extraction, including empty cells.
2. Each chunk's embedded prefix varies by chunk.
3. Documents carry queryable metadata: type, issuer, statement period, summary.
4. Word, spreadsheet, HTML, CSV, and plain-text files are accepted.
5. Retrieval changes are measured, not assumed.

## Non-goals

- **A dedicated OCR stage.** Not needed: a page yielding near-zero words routes
  to the Gemini fallback in Step 1b, which reads the rendered page directly.
- **Query-side date extraction and filtering.** The metadata this design stores
  makes it possible; wiring it into `match_documents` is separate work the user
  plans to take on next.
- **Changes to holdings extraction** (`extract_holdings_from_text`). Untouched.
- **Re-tagging chunks by content type** (table vs prose) for differential
  retrieval. Speculative until something needs it.
- **Replacing the PII redaction stage.** It stays where it is, with one ordering
  change noted below.

## Design

### Step 0 — Evaluation harness (built first)

Every change below is a retrieval-quality claim, and there is currently no way
to test one. The harness comes first so each subsequent step is measured.

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
suite: it needs live embeddings and real ingested data. Record a baseline before
touching anything.

### Step 1 — PDF to Markdown, preserving columns and headings

New module `RAG_PIPELINE/src/pdf_markdown.py`, replacing `PyPDFLoader`.

Per page:

1. **Extract words with attributes.** `page.extract_words(extra_attrs=["size", "fontname"])`.
2. **Drop watermarks.** Discard words with `size > 3 * body_size`, where
   `body_size` is the median word size on the page. On the specimen this removes
   the 88–113pt diagonal text that otherwise interleaves stray characters into
   table cells.
3. **Group into visual lines.** Sort by `top`, start a new line when the vertical
   delta exceeds `0.6 * size`.
4. **Emit headings.** A line whose first word is bold and larger than
   `1.25 * body_size` becomes a heading — `#` above `2 * body_size`, else `##`.
5. **Emit everything else as positioned cells.** Split a line into cells wherever
   the horizontal gap between consecutive words exceeds 8pt.
6. **Snap cells to columns.** Within each run of consecutive multi-column lines,
   cluster cell right edges (`x1`) within a tolerance; each cluster is a column.
   Place every cell at its column index, emitting an empty string for columns
   with no content on that row.

   Cluster **per block, not per page.** A page carries several unrelated tables
   with different geometry — on the specimen, the summary box's rightmost column
   sits at `x1=568.8` while the transaction table's Balance column sits at
   `562.8`. Page-wide clustering would merge two columns that are six points and
   one table apart.

   **Cluster both edges, not just one.** Columns do not share an alignment:
   numeric columns are right-aligned and text columns are left-aligned. On the
   specimen's 16 transaction rows, Description holds `x0=121.2` every time while
   its `x1` ranges from 180.2 to 248.8; Credit is the mirror image, with `x1`
   pinned at 318.8 and `x0` scattered. Clustering `x1` alone finds the money
   columns and misses Description entirely.

   So cluster `x0` and `x1` separately and keep the tight, frequently-hit
   clusters from each. A cluster on `x0` is a left-anchored column, one on `x1`
   is right-anchored, and a cell joins the column whose anchor its corresponding
   edge matches.

   Right-anchored columns also let a column be *named* rather than merely
   counted: the header word shares the data's right edge — `Credit` ends at
   318.8, `Debit` at 438.8, `Balance` at 562.8.

   **Snap cells, never words.** Sub-step 5 must run first. `Salary Credit -
   Northwind Analytics` happens to end at exactly 318.8, the Credit anchor; as a
   word it would snap into Credit, but as a cell it matches Description on its
   left edge and lands correctly.
7. **Render.** Lines occupying a single column emit as plain text. Lines
   occupying several emit as a markdown table row. A run of consecutive
   multi-column lines becomes one table, with the first row as its header and a
   `|---|` delimiter inserted beneath it.
8. **Record the page number** on every line produced, carried through chunking
   into chunk metadata. It backs the `header_path` fallback in Step 5 and gives
   citations a location.

Step 6 is what fixes the correctness bug, and it is the step my first prototype
omitted — gap-splitting alone reproduces `pypdf`'s failure with nicer formatting.

There is deliberately **no table detection**. Nothing asks "is this region a
table". Prose occupies one column and passes through as prose; tabular content
occupies several and renders as a table. The structure falls out of the geometry.

Expected output on the specimen:

```markdown
# MERIDIAN TRUST BANK
## STATEMENT OF ACCOUNT

| Account Number: | XXXX-XXXX-0000 (sample) | Opening Balance: | 4,250.00 |
...

## Transactions

| Date | Description | Credit | Debit | Balance |
|---|---|---|---|---|
| 05/01/2025 | Salary Credit - Northwind Analytics | 3,200.00 |  | 7,450.00 |
| 05/02/2025 | Payment - Rent |  | 1,650.00 | 5,800.00 |
```

**Assumptions, both detectable if violated:** column x-positions hold across
pages of a document, and text is embedded rather than scanned.

The two ratios (1.25x heading, 3x watermark) and the 8pt gap are starting values.
They are tunable constants, and the eval harness is how they get tuned.

### Step 1b — Verify the extraction, escalate only when it fails

A transaction moves money one direction: exactly one of the credit/debit pair is
populated, and the running balance moves by that amount. Header names vary
(Deposits/Withdrawals, Money In/Money Out, Payments/Charges) but the invariant
holds across statement formats.

That makes extraction *checkable* without a model. For each row, assert:

```
balance[n] - balance[n-1] == +credit  or  -debit
```

On the specimen all 16 rows reconcile and the final balance lands exactly on the
stated closing figure of 6,244.86. A geometry bug that misfiles a debit as a
credit inverts a delta and fails immediately.

**Escalation ladder:**

1. `pdfplumber` geometry (Step 1) — 20ms measured on the specimen.
2. If a document has a balance column and reconciliation fails, or if the page
   yields near-zero words (a scanned/image-only PDF), send the PDF to
   `gemini-2.5-flash` for markdown conversion.
3. Reconcile the model's output the same way. If it also fails, ingest the
   document but flag it, and surface that to the user.

Gemini converted the specimen correctly — every row, both near-identical
transfers, empty cells preserved — so it is a sound fallback. It is not the
primary path because it is **1000x slower**: 22.2s versus 20ms, and
output-bound at 4,635 output tokens for a single page. A ten-page statement
scales that linearly into minutes, and risks silent truncation mid-table if it
reaches the output ceiling — which reconciliation would then catch.

Because near-zero extracted words routes straight to the model, scanned PDFs are
handled without a separate OCR stage.

**Documents the check cannot reach:** statements with no running balance (common
on credit cards) and non-transactional documents (invoices, pay stubs, tax
forms). Those rely on the extractor being right. The documents where a wrong
number is most costly are the ones the check does cover.

### Step 2 — Other formats via markitdown

Add `markitdown` for `.docx`, `.xlsx`, `.pptx`, `.html`, `.csv`, `.txt`, `.md`.
These formats carry explicit structure, so no positional reconstruction is
needed. PDFs bypass markitdown entirely and use Step 1.

A single `to_markdown(filename, content) -> str` dispatches on extension and is
the only entry point the rest of the pipeline sees.

Update the extension checks at `api.py:609`, `api.py:682`, and `api.py:691`.

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
    period_start: str | None   # ISO "YYYY-MM-DD"
    period_end: str | None
    summary: str           # 3-5 sentences
```

ISO date strings compare correctly under lexicographic ordering, so the later
date-range filter works against jsonb without a type migration.

`doc_type` is constrained rather than free text so it can be filtered on later
without normalising a long tail of synonyms.

This replaces `generate_summary` (`ingestion.py:240`), which becomes one field of
this call rather than its own request. Net LLM calls per document: unchanged.

The call runs **after** PII redaction, preserving current ordering — the model
never sees unredacted text. Dates and organisation names are not in
`PII_ENTITIES`, so period and issuer extraction are unaffected.

### Step 4 — Chunking

1. `MarkdownHeaderTextSplitter` on `#`, `##`, `###`. Each chunk arrives with its
   heading path already in metadata — this is why Step 1 bothers to recover
   headings.
2. Within each section, split table blocks from prose. A table block is a run of
   consecutive lines beginning with `|`.
3. **Prose** splits with
   `RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=500, chunk_overlap=50)`.
4. **Tables** split by row groups sized to the same 500-token budget, with the
   header row and `|---|` delimiter **repeated at the top of each group**.

Sub-step 4 exists because a character-based split of a long table leaves the
second piece as unlabelled numbers:

```
| 05/18 | AMZN MKTP | -$34.99 | $1,875.45 |
```

Without the header row, whether `-$34.99` is an amount or a balance is a guess —
which would reintroduce, at chunk level, the same class of bug Step 1 fixes at
extraction level.

Add `tiktoken` to `pyproject.toml` explicitly. It resolves today only as a
transitive dependency of `litellm`.

### Step 5 — A per-chunk prefix that varies

Replace the constant prefix at `ingestion.py:437`:

```python
prefix = f"[{issuer} · {doc_type_label} · {period_label} · {header_path}]"
embedded_text = f"{prefix}\n\n{chunk}"
```

`doc_type_label` is the `doc_type` enum humanised — `bank_statement` renders as
`Bank Statement`. `period_label` is derived from the ISO dates: `May 2025` when
both fall in one month, `May-Jul 2025` when they span several, and omitted
entirely when both are `None`. The stored fields stay ISO; only the display form
is condensed.

Producing:

```
[Meridian Trust Bank · Bank Statement · May 2025 · Transactions]
```

Issuer, type, and period are constant within a document; `header_path` varies per
chunk. That variation is the point — it restores within-document ranking while
still giving isolated numeric rows a semantic anchor.

At roughly 80 characters it is also about a third of the current prefix's length.

When a document has no headings, `header_path` is empty and the prefix falls back
to document-level fields plus page number (`· p.3`), which still varies per chunk.

### Step 6 — Summary moves to metadata, plus one summary chunk

The summary leaves the embedded text entirely and lives in metadata, where the
grader and generator read it. It is the longest and most invariant part of the
current prefix, so it is the largest single contributor to Problem 2.

Removing it costs the broad-query case: "summarize my finances" currently matches
summary text present in every chunk, and therefore works by accident. To replace
that deliberately, emit **one additional chunk per document** whose content *is*
the rendered metadata plus summary, flagged `is_summary_chunk: true`.

This chunk carries no Step 5 prefix — its body already states the issuer, type,
and period in full, so a prefix would only duplicate them. Its `header_path` is
empty and its `chunk_index` is `-1`.

This gives document-level questions a real retrieval target instead of an
artifact, and may make the `is_broad` threshold-drop in `graph.py` redundant.
Verify with the eval harness; remove it only if the numbers support that.

### Step 7 — Metadata reaches the grader and the generator

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

### Step 8 — Migration

Existing chunks have the summary baked into their embedded text. A mixed corpus
scores inconsistently, so a full re-ingest is required rather than optional.
`RAG_PIPELINE/src/reingest.py` already re-processes every file in the
`rag-documents` bucket and needs no structural change.

After re-ingesting, re-run the eval harness and retune the thresholds in
`retrieve`. Scores are expected to *spread*, not shift uniformly — good matches
higher, poor matches lower — so the current 0.15/0.35 constants will be wrong in
a way that is not a constant offset.

### Metadata field reference

| Field | Source | New |
|---|---|---|
| `file_hash`, `source`, `user_id`, `chunk_index` | existing | |
| `doc_type` | Step 3 | ✓ |
| `issuer` | Step 3 | ✓ |
| `period_start`, `period_end` | Step 3 | ✓ |
| `summary` | Step 3 | moved out of embedded text |
| `header_path` | Step 4 | ✓ |
| `page` | Step 1 | ✓ |
| `is_summary_chunk` | Step 6 | ✓ |

## Testing

The specimen statement becomes a committed fixture at
`tests/fixtures/specimen_bank_statement_may2025.pdf`. It is synthetic, contains
no real data, and makes the converter testable with no network access.

Unit tests, all offline and in the default suite:

1. `Payment - Rent` yields `1,650.00` in the **Debit** column and an empty Credit
   cell. This is the regression test for the primary bug.
2. `Account Transfer In - Savings` yields a Credit; `Account Transfer Out -
   Brokerage` yields a Debit. Near-identical wording, opposite columns.
3. `MERIDIAN TRUST BANK` emits as `#`; body text does not emit as a heading.
4. No word from the 88–113pt watermark appears in the output.
5. Every emitted table row has the same cell count as its header row.
6. Splitting a table over the token budget repeats the header row and `|---|`
   delimiter on each piece.
7. Two chunks from the same document with different heading paths receive
   different prefixes.
8. A document with no headings still receives per-chunk-varying prefixes via the
   page-number fallback.
9. `DocumentMetadata` rejects a `doc_type` outside the allowed set.
10. The Description column is detected despite its right edge varying by row —
    the regression test for left-anchored columns.
11. `Salary Credit - Northwind Analytics`, whose text ends exactly on the Credit
    column's anchor, still lands in Description.
12. Reconciliation passes on the specimen: all 16 rows, closing balance 6,244.86.
13. Reconciliation *fails* when a credit and debit are deliberately swapped in a
    fixture row — the check has to be able to fail, or it proves nothing.
14. A document with no balance column skips reconciliation rather than erroring.

Retrieval quality is measured by the Step 0 harness, not by pytest — baseline
recorded before Step 1, re-run after Step 6 and after threshold retuning.

## Sequencing

Step 0 first and alone; record the baseline. Steps 1–2 are independent of 3–7 and
can land separately. Step 8 must follow Steps 5 and 6 together, since a partial
re-ingest produces exactly the mixed corpus it exists to prevent.
