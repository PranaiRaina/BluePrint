"""Markdown-aware chunking."""

import re

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

MAX_DOCUMENT_TOKENS = 50_000

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
