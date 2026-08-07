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

# Emphasis markers must go before PII redaction runs. Presidio tokenises with
# spaCy, and "**Jane Sample**" tokenises as "**Jane" and "Sample**", which its
# NER does not recognise as a person - so a bolded account-holder name survives
# redaction and reaches the embedder. Bold carries no meaning we need here.
_EMPHASIS_RE = re.compile(r"\*{1,3}(?=\S)|(?<=\S)\*{1,3}")


def to_markdown(path: str) -> str:
    """Convert a PDF to markdown, headings and tables preserved.

    Emphasis is stripped; see _EMPHASIS_RE. Headings and table pipes are kept,
    since chunking splits on them.
    """
    md = pymupdf4llm.to_markdown(path)
    md = _BR_RE.sub(" ", md)
    md = _EMPHASIS_RE.sub("", md)
    return _BLANK_RUN_RE.sub("\n\n", md).strip()
