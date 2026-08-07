"""PDF to markdown conversion.

Isolated behind one function so the extractor can be swapped without touching
ingestion, and so tests have a single patch point.
"""

import pymupdf4llm


def to_markdown(path: str) -> str:
    """Convert a PDF to markdown, headings and tables preserved."""
    return pymupdf4llm.to_markdown(path)
