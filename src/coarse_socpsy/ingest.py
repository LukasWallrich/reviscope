from __future__ import annotations

import hashlib
from pathlib import Path

from .schemas import PageText, SourceDocument


SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt"}


def _pdf(path: Path) -> tuple[str, list[PageText]]:
    from pypdf import PdfReader

    pages = [PageText(page=i, text=(p.extract_text() or "")) for i, p in enumerate(PdfReader(path).pages, 1)]
    return "\n\n".join(f"[Page {p.page}]\n{p.text}" for p in pages), pages


def _docx(path: Path) -> str:
    from docx import Document

    doc = Document(path)
    blocks: list[str] = []
    for item in doc.iter_inner_content():
        if hasattr(item, "rows"):
            blocks.extend(" | ".join(cell.text for cell in row.cells) for row in item.rows)
        else:
            blocks.append(item.text)
    return "\n".join(blocks)


def ingest(path: str | Path, kind: str = "manuscript") -> SourceDocument:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    if p.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported document type: {p.suffix}")
    raw = p.read_bytes()
    pages: list[PageText] = []
    warnings: list[str] = []
    if p.suffix.lower() == ".pdf":
        text, pages = _pdf(p)
        blank = [page.page for page in pages if not page.text.strip()]
        if pages and len(blank) == len(pages):
            raise ValueError(f"No text could be extracted from scanned PDF {p}; OCR is required")
        if blank:
            warnings.append(f"No extractable text on PDF page(s): {', '.join(map(str, blank))}; coverage is incomplete.")
    elif p.suffix.lower() == ".docx":
        text = _docx(p)
    else:
        text = raw.decode("utf-8")
    if not text.strip():
        raise ValueError(f"No text could be extracted from {p}")
    digest = hashlib.sha256(raw).hexdigest()
    return SourceDocument(id=f"{kind}-{digest[:12]}", path=str(p), kind=kind, sha256=digest, text=text, pages=pages, extraction_warnings=warnings)
