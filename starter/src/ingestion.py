"""Read and normalize source PDFs page by page, keeping source/page traceability."""
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from .models import DocumentPage

# Ligatures that pypdf often leaves in OpenStax/LaTeX PDFs.
_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace; keep line/paragraph breaks for chunking."""
    text = unicodedata.normalize("NFC", text)
    for lig, repl in _LIGATURES.items():
        text = text.replace(lig, repl)
    text = text.replace("­", "")                      # soft hyphen
    text = text.replace(" ", " ").replace("\t", " ")  # nbsp / tab
    text = re.sub(r"[​‌‍﻿]", "", text)  # zero-width chars
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)           # word broken across lines
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str,
             pages: Iterable[int] | None = None,
             metadata: dict[str, Any] | None = None,
             errors: list[dict[str, Any]] | None = None,
             min_chars: int = 200) -> list[DocumentPage]:
    """Extract selected physical pages (1-based). Empty/short/failed pages go to ``errors``.

    OCR is not performed; scanned pages are reported as empty so they can be
    excluded or replaced, as required by GUIDE.md.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(path)
    wanted = set(pages) if pages is not None else None
    if wanted:
        out_of_range = sorted(p for p in wanted if p < 1 or p > len(reader.pages))
        if out_of_range:
            raise ValueError(f"{document_id}: pages {out_of_range} outside 1..{len(reader.pages)}")
    errors = errors if errors is not None else []
    result: list[DocumentPage] = []
    for number, pdf_page in enumerate(reader.pages, start=1):
        if wanted is not None and number not in wanted:
            continue
        try:
            text = normalize_text(pdf_page.extract_text() or "")
        except Exception as exc:  # keep going, but record it
            errors.append({"document_id": document_id, "page": number, "error": repr(exc)})
            continue
        if len(text) < min_chars:
            errors.append({"document_id": document_id, "page": number,
                           "error": f"empty_or_short ({len(text)} chars < {min_chars})"})
            continue
        result.append(DocumentPage(document_id, source, number, text, dict(metadata or {})))
    return result
