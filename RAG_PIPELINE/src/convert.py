"""PDF to markdown conversion.

Isolated behind one function so the extractor can be swapped without touching
ingestion, and so tests have a single patch point.
"""

import re

import pymupdf4llm

# pymupdf4llm packs multi-line cells with literal <br>, which reaches the
# embedder as noise and inflates every chunk's token count.
_BR_RE = re.compile(r"\s*<br\s*/?>\s*")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def to_markdown(path: str) -> str:
    """Convert a PDF to markdown, headings and tables preserved."""
    md = pymupdf4llm.to_markdown(path)
    md = _BR_RE.sub(" ", md)
    return _BLANK_RUN_RE.sub("\n\n", md).strip()
