from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from .schemas import PageText, SourceDocument


SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt"}
# A caption starts a line (after an optional manuscript line number) and is followed by
# punctuation, a capitalised title or the line end; "Table 4 of the supplement" is a reference.
_TABLE_CAPTION = re.compile(r"^[^\S\r\n]*(?:\d{1,4}[^\S\r\n]+)?(?:Table|TABLE)\s+(?:[A-Z][^\S\r\n]*)?\d+[a-z]?"
                            r"(?=[^\S\r\n]*(?:$|[.:|(\u2013\u2014-]|[A-Z]))", re.MULTILINE)
# A number with what is written directly against it, with no space between: a sign (minus,
# en dash or plus-minus), a leading decimal point, an exponent and a percent sign. A dash or
# point right after a letter, digit, closing bracket or percent sign is a hyphen, range or
# full stop ("COVID-19", "1-3", "(n = 19).2"), so cells joined as "0.5-0.3" differ from
# "0.5 -0.3". Superscript digits count separately.
_STARTS = r"(?<![^\W_]|[)\]}%])"
_NUMBER = re.compile(rf"(?:{_STARTS}[-+\u2212\u2013\u00b1])?(?:{_STARTS}\.)?\d+(?:[.,]\d+)*(?:[eE][-+\u2212]?\d+)?%?"
                     r"|[\u207a\u207b]?[\u2070\u00b9\u00b2\u00b3\u2074-\u2079]+")
# pypdf places each text run at column x // char_width; when runs are narrower than the
# page average, a run can overrun the next one's column and be joined to it. Smaller
# character widths (higher scale weights) leave more room.
_LAYOUT_SCALE_WEIGHTS = (None, 2.5, 5.0)


def _glyphs(text: str) -> Counter[str]:
    return Counter(ch for ch in text if ch.isprintable() and not ch.isspace())


def _new_numbers(text: str, normal: str) -> list[str]:
    """Numbers written in `text` but not in the normal text, e.g. 3.28 and 1 joined as 3.281."""
    return list((Counter(_NUMBER.findall(text)) - Counter(_NUMBER.findall(normal))).elements())


def _layout_text(page, weight: float | None) -> str:
    kwargs = {} if weight is None else {"layout_mode_scale_weight": weight}
    try:
        return page.extract_text(extraction_mode="layout", **kwargs) or ""
    except ZeroDivisionError:  # pypdf, when an orientation has only zero-width text
        return ""


def _table_layout(page, normal: str) -> tuple[str | None, str | None]:
    """Return a full-page layout copy, or the reason it is unsafe to show.

    A copy is kept only if it contains exactly the normal text's characters, so that it
    rearranges the page without omitting or adding content, and groups no digits into
    numbers that the normal text separates (or the reverse) or moves a sign, decimal point,
    exponent or percent sign between numbers.
    """
    want, parts = _glyphs(normal), []
    for turn in (0, 90, 180):  # Cumulative turns: upright text, then text rotated either way.
        if turn:
            from pypdf import PdfWriter, Transformation
            if turn == 90:  # Turn a copy; the source page is left unchanged.
                page = PdfWriter(clone_from=page.pdf).pages[page.page_number]
            page.add_transformation(Transformation().rotate(turn))
        for weight in _LAYOUT_SCALE_WEIGHTS:
            text = _layout_text(page, weight)
            if not _new_numbers(text, normal):
                break
        parts.append(text)
        if sum(map(_glyphs, parts), Counter()) == want:
            break
    else:
        return None, "layout mode did not reproduce the normal text (for example, form XObject or obliquely rotated content)"
    upright, *turned = parts
    layout = "\n\n".join([upright] * bool(upright.strip()) + [
        f"[Rotated text on this page, turned upright]\n{part}" for part in turned if part.strip()])
    if changed := _new_numbers(layout, normal):  # With the same digits, a lost number implies a new one.
        lost = _new_numbers(normal, layout)
        return None, (f"layout mode writes numbers differently from the normal text "
                      f"(layout {', '.join(changed[:3])}; normal {', '.join(lost[:3])})")
    return layout, None


def _pdf(path: Path) -> tuple[str, list[PageText], list[str]]:
    from pypdf import PdfReader

    pages: list[PageText] = []
    warnings: list[str] = []
    for i, p in enumerate(PdfReader(path).pages, 1):
        page = PageText(page=i, text=(p.extract_text() or ""))
        if _TABLE_CAPTION.search(page.text):
            try:
                page.table_layout, problem = _table_layout(p, page.text)
            except Exception as exc:
                problem = f"layout extraction failed: {type(exc).__name__}: {exc}"
            if problem:
                warnings.append(f"Table layout copy skipped on PDF page {i}: {problem}; normal text is retained.")
        pages.append(page)
    return "\n\n".join(f"[Page {p.page}]\n{p.text}" for p in pages), pages, warnings


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
        text, pages, warnings = _pdf(p)
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
