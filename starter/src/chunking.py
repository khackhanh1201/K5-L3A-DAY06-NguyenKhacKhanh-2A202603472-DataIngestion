"""Fixed-size and structure-aware (paragraph) chunking.

Both chunkers work inside one page, so every chunk maps to exactly one
source page. Chunk IDs are deterministic, so re-ingesting the same data
overwrites instead of duplicating.
"""
import re

from .models import Chunk, DocumentPage


def _make(page: DocumentPage, chunk_id: str, text: str, extra: dict) -> Chunk:
    return Chunk(chunk_id, page.document_id, page.source, page.page, text,
                 {**page.metadata, **extra})


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Sliding character windows of ``size`` with ``overlap``; ignores structure."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    step, chunks = size - overlap, []
    for idx, start in enumerate(range(0, max(len(page.text) - overlap, 1), step)):
        piece = page.text[start:start + size].strip()
        if piece:
            chunks.append(_make(page, f"{page.document_id}:p{page.page}:fix{size}-{overlap}:{idx}",
                                piece, {"char_start": start}))
    return chunks


def _paragraphs(text: str) -> list[str]:
    """Split into paragraphs. pypdf often drops blank lines, so a line that ends
    with sentence punctuation is also treated as a paragraph end."""
    parts = re.split(r"\n\n+|(?<=[.!?:])\n", text)
    return [re.sub(r"\s*\n\s*", " ", p).strip() for p in parts if p and p.strip()]


def _split_long(paragraph: str, max_size: int) -> list[str]:
    """Split an oversized paragraph at sentence ends; hard-cut only if one sentence is too long."""
    pieces, buf = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        if buf and len(buf) + 1 + len(sentence) > max_size:
            pieces.append(buf)
            buf = sentence
        else:
            buf = f"{buf} {sentence}".strip()
    if buf:
        pieces.append(buf)
    return [p[i:i + max_size] for p in pieces for i in range(0, len(p), max_size)]


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Greedily pack whole paragraphs up to ``max_size`` characters."""
    if max_size <= 0:
        raise ValueError("max_size must be > 0")
    texts, buf = [], ""
    for paragraph in _paragraphs(page.text):
        units = _split_long(paragraph, max_size) if len(paragraph) > max_size else [paragraph]
        for unit in units:
            if buf and len(buf) + 2 + len(unit) > max_size:
                texts.append(buf)
                buf = unit
            else:
                buf = f"{buf}\n\n{unit}" if buf else unit
    if buf:
        texts.append(buf)
    return [_make(page, f"{page.document_id}:p{page.page}:par{max_size}:{i}", t, {})
            for i, t in enumerate(texts)]
