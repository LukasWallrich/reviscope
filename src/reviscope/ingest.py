from __future__ import annotations

import hashlib
import re
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
_SCRIPTS = {"superscript": "^", "subscript": "_"}
_ORDINAL = {"st", "nd", "rd", "th"}


class _DocxText:
    """Plain text from WordprocessingML in document order.

    Walks the XML directly because python-docx's ``cell.text`` and ``paragraph.text``
    omit nested tables, Office math, text boxes and note references. Superscripts and
    subscripts, in Office math or as run formatting, are written as ``x^2``, ``x_{ij}``.
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
        return [_join(parts), *boxes]

    def _inline(self, el, parts: list, boxes: list[str]) -> None:
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
            elif tag == _M + "oMath":
                parts.append(_math(child))
            elif tag == _W + "r" and (mark := _run_script(child)):
                inner: list = []
                self._inline(child, inner, boxes)
                text = _join(inner)
                previous = parts[-1] if parts and isinstance(parts[-1], str) else ""
                if mark == "^" and text in _ORDINAL and previous[-1:].isdigit():
                    parts.append(text)  # Word's automatic ordinal formatting (1st, 21st)
                elif text:
                    parts.append((mark, text))
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


def _join(parts: list) -> str:
    """Join inline text; (mark, text) entries are scripts, merged across adjacent runs."""
    out: list[str] = []
    pending: tuple[str, str] | None = None
    for part in [*parts, ""]:
        if isinstance(part, tuple) and pending and pending[0] == part[0]:
            pending = (pending[0], pending[1] + part[1])
            continue
        if pending:
            out.append(pending[0] + _group(pending[1]))
            pending = None
        if isinstance(part, tuple):
            pending = part
        else:
            out.append(part)
    return "".join(out)


def _group(text: str) -> str:
    return text if len(text) == 1 else "{" + text + "}"


def _run_script(run) -> str | None:
    align = run.find(f"{_W}rPr/{_W}vertAlign")
    if align is None or run.find(f".//{_W}footnoteReference") is not None or run.find(f".//{_W}endnoteReference") is not None:
        return None
    return _SCRIPTS.get(align.get(_W + "val"))


def _math(el) -> str:
    """Linear text for an Office math (OMML) element, keeping structure that m:t text alone loses."""
    local = el.tag.removeprefix(_M) if isinstance(el.tag, str) else ""

    def part(name: str) -> str:
        child = el.find(_M + name)
        return "" if child is None else _math(child)

    def prop(name: str, default: str) -> str:
        child = el.find(f"{_M}{local}Pr/{_M}{name}")
        return default if child is None else child.get(_M + "val", default)

    def operand(text: str) -> str:
        return text if re.fullmatch(r"[\w.]+", text) else f"({text})"

    def scripts(base: str) -> str:
        sub, sup = part("sub"), part("sup")
        return base + (f"_{_group(sub)}" if sub else "") + (f"^{_group(sup)}" if sup else "")

    if local == "t":
        return el.text or ""
    if local in {"sSup", "sSub", "sSubSup"}:
        return scripts(part("e"))
    if local == "sPre":
        return scripts("") + part("e")
    if local == "f":
        return f"{operand(part('num'))}/{operand(part('den'))}"
    if local == "rad":
        degree = part("deg")
        return f"root({degree}, {part('e')})" if degree else f"sqrt({part('e')})"
    if local == "d":
        inner = prop("sepChr", "|").join(_math(e) for e in el.findall(_M + "e"))
        return prop("begChr", "(") + inner + prop("endChr", ")")
    if local == "nary":
        return scripts(prop("chr", "∫")) + " " + part("e")
    if local == "acc":
        return part("e") + prop("chr", "\u0302")
    if local == "func":
        body = part("e")
        return part("fName") + (body if body.startswith("(") else " " + body)
    if local in {"limLow", "limUpp"}:
        return part("e") + ("_" if local == "limLow" else "^") + _group(part("lim"))
    if local == "eqArr":
        return "; ".join(_math(e) for e in el.findall(_M + "e"))
    if local == "m":
        rows = (", ".join(_math(e) for e in row.findall(_M + "e")) for row in el.findall(_M + "mr"))
        return "[" + "; ".join(rows) + "]"
    if local.endswith("Pr") or el.tag in _SKIP:
        return ""
    return "".join(_math(child) for child in el)


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
