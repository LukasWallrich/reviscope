from __future__ import annotations

import hashlib
from pathlib import Path

from .schemas import PageText, SourceDocument


SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt"}


def _pdf(path: Path) -> tuple[str, list[PageText]]:
    from pypdf import PdfReader

    pages = [PageText(page=i, text=(p.extract_text() or "")) for i, p in enumerate(PdfReader(path).pages, 1)]
    return "\n\n".join(f"[Page {p.page}]\n{p.text}" for p in pages), pages


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_SKIP = {_W + "del", _W + "moveFrom", _W + "instrText", _W + "delText", _MC + "Fallback"}
_NOTES = (("footnotes", "footnote", "Footnote"), ("endnotes", "endnote", "Endnote"))


class _DocxText:
    """Plain text from WordprocessingML in document order.

    Walks the XML directly because python-docx's ``cell.text`` and ``paragraph.text``
    omit nested tables, Office math, text boxes and note references.
    """

    def __init__(self) -> None:
        self.note_numbers: dict[tuple[str, str], int] = {}

    def blocks(self, container) -> list[str]:
        out: list[str] = []
        for child in container:
            if child.tag == _W + "p":
                out.extend(self.paragraph(child))
            elif child.tag == _W + "tbl":
                out.extend(self.table(child))
            elif child.tag in {_W + "sdt", _W + "sdtContent", _W + "customXml"}:
                out.extend(self.blocks(child))
        return out

    def paragraph(self, p) -> list[str]:
        parts: list[str] = []
        boxes: list[str] = []
        self._inline(p, parts, boxes)
        return ["".join(parts), *boxes]

    def _inline(self, el, parts: list[str], boxes: list[str]) -> None:
        for child in el:
            tag = child.tag
            if not isinstance(tag, str) or tag in _SKIP:
                continue
            if tag in {_W + "t", _M + "t"}:
                parts.append(child.text or "")
            elif tag == _W + "tab":
                parts.append("\t")
            elif tag in {_W + "br", _W + "cr"}:
                parts.append("\n")
            elif tag == _W + "noBreakHyphen":
                parts.append("-")
            elif tag in {_W + "footnoteReference", _W + "endnoteReference"}:
                kind = "footnote" if tag == _W + "footnoteReference" else "endnote"
                key = (kind, child.get(_W + "id"))
                number = self.note_numbers.setdefault(key, sum(k[0] == kind for k in self.note_numbers) + 1)
                parts.append(f"[{kind} {number}]")
            elif tag == _W + "txbxContent":
                boxes.extend(self.blocks(child))
            else:
                self._inline(child, parts, boxes)

    def table(self, tbl) -> list[str]:
        out: list[str] = []
        # Nested rows and cells belong to their own table; each <w:tc> is visited once, so
        # merged cells are not repeated as python-docx's row.cells would.
        for tr in (tr for tr in tbl.iter(_W + "tr") if _nearest(tr, "tbl") is tbl):
            cells = [tc for tc in tr.iter(_W + "tc") if _nearest(tc, "tr") is tr]
            contents = [self.blocks(tc) for tc in cells]
            if any(tc.find(_W + "tbl") is not None for tc in cells):
                # Layout cells (e.g. a caption wrapped round its data table) cannot be a single row.
                out.extend(line for blocks in contents for line in blocks if line.strip())
            else:
                out.append(" | ".join(" ".join(line for line in blocks if line.strip()) for blocks in contents))
        return out

    def notes(self, part, element: str, label: str) -> list[str]:
        from docx.oxml import parse_xml

        out: list[str] = []
        for note in parse_xml(part.blob).iter(_W + element):
            if note.get(_W + "type") in {"separator", "continuationSeparator", "continuationNotice"}:
                continue
            number = self.note_numbers.get((element, note.get(_W + "id")))
            text = " ".join(line.strip() for line in self.blocks(note) if line.strip())
            if text:
                out.append(f"[{label} {number}] {text}" if number else f"[{label}] {text}")
        return out


def _nearest(el, name: str):
    parent = el.getparent()
    while parent is not None and parent.tag != _W + name:
        parent = parent.getparent()
    return parent


def _docx(path: Path) -> str:
    from docx import Document

    doc = Document(path)
    reader = _DocxText()
    blocks = reader.blocks(doc.element.body)
    for kind, element, label in _NOTES:
        part = next((rel.target_part for rel in doc.part.rels.values() if not rel.is_external and rel.reltype.endswith("/" + kind)), None)
        if part is not None:
            notes = reader.notes(part, element, label)
            if notes:
                blocks.extend(["", f"{label}s", *notes])
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
