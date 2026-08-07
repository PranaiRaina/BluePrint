"""Markdown-aware chunking."""

import os
import re

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

MAX_DOCUMENT_TOKENS = 50_000

# Overridable so the eval can compare sizes without editing code.
DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "750"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))

# A block shorter than this is not worth its own embedding - a bare "##
# Transactions" heading answers nothing and occupies a retrieval slot. Such
# blocks are carried forward onto whatever follows them instead.
MIN_STANDALONE_TOKENS = 30

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]
DELIMITER_RE = re.compile(r"^\|[\s:|-]+\|$")

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _column_count(line: str) -> int:
    return line.count("|")


def _blocks(text: str):
    """Yield (block_text, is_table) for each run of same-kind lines.

    A run of table lines ends when a *different* table starts. Documents like
    brokerage statements stack several tables in a row, and merging them means
    the second table's rows inherit the first table's header - so a date reads
    as a Symbol. A confidently mislabelled column is worse than none.
    """
    lines = text.split("\n")
    if not lines:
        return

    current: list[str] = []
    current_is_table = _is_table_line(lines[0])
    current_columns = _column_count(lines[0]) if current_is_table else 0
    rows_since_header = 0

    for line in lines:
        is_table = _is_table_line(line)
        starts_new_block = False
        # A delimiter row means the line *above* it is the new table's header,
        # so the break belongs one line earlier than where we noticed it.
        carry_header = False

        if line.strip():
            if is_table != current_is_table:
                starts_new_block = True
            elif is_table and current:
                if _column_count(line) != current_columns:
                    starts_new_block = True
                elif DELIMITER_RE.match(line.strip()) and rows_since_header > 1:
                    starts_new_block = True
                    carry_header = True

        if starts_new_block:
            carried: list[str] = []
            if carry_header:
                while current and not current[-1].strip():
                    current.pop()
                if current:
                    carried = [current.pop()]
            yield "\n".join(current), current_is_table
            current, current_is_table = carried, is_table
            current_columns = (
                _column_count(carried[0]) if carried else
                (_column_count(line) if is_table else 0)
            )
            rows_since_header = len(carried)

        current.append(line)
        if line.strip() and is_table:
            rows_since_header += 1

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
    md: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split markdown into chunks, keeping table headers on every piece."""
    chunk_size = DEFAULT_CHUNK_SIZE if chunk_size is None else chunk_size
    chunk_overlap = DEFAULT_CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap
    sections = MarkdownHeaderTextSplitter(
        HEADERS_TO_SPLIT_ON, strip_headers=False
    ).split_text(md)

    prose_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    chunks: list[str] = []
    pending = ""
    for section in sections:
        for block, is_table in _blocks(section.page_content):
            if not block.strip():
                continue

            if not is_table and count_tokens(block) < MIN_STANDALONE_TOKENS:
                pending = f"{pending}\n{block}".strip()
                continue

            pieces = [
                piece
                for piece in (
                    _split_table(block, chunk_size)
                    if is_table
                    else prose_splitter.split_text(block)
                )
                if piece.strip()
            ]
            if pending and pieces:
                # Attach the heading to the content it introduces, once. Later
                # pieces of a split table carry the repeated table header, which
                # is what they actually need.
                pieces[0] = f"{pending}\n\n{pieces[0]}"
                pending = ""
            chunks.extend(pieces)

    if pending:
        # Nothing followed it anywhere in the document; keep it rather than
        # lose the text. Carried across sections, not per-section, because a
        # stray line before the first heading is its own section.
        chunks.append(pending)
    return chunks
