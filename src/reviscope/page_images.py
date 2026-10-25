"""Rendered images of every PDF page, so review stages can read tables and figures as printed.

Extracted text keeps quotation anchoring; it can misplace table cells, join numbers and lose
signs, stars or bold type. Each PDF page is rendered once per run with PDFium: a whole-page view
and four overlapping magnified quarters, plus upright copies of pages with sideways text. A
manifest records the source hash, page, render configuration and each image's SHA-256, and stages
that use the images key their cache on that fingerprint.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

from .schemas import PageImage, PageImageSet, SourceDocument

# Whole-page view: the long edge in pixels. Quarters are rendered at QUARTER_DPI; each covers a
# little over half the page in both directions so that a row or cell cut by one quarter is whole
# in its neighbour.
PAGE_LONG_EDGE = 1600
QUARTER_DPI = 240
QUARTER_SPAN = 0.56
# A page whose non-space characters are at least this share, and number, sideways also gets
# upright copies, rendered turned by the angle that makes its sideways text read left to right.
SIDEWAYS_SHARE, SIDEWAYS_MIN = 0.25, 20
QUARTERS = ("upper-left", "upper-right", "lower-left", "lower-right")


def render_config() -> dict[str, object]:
    import pypdfium2.version as version

    return {"renderer": "pypdfium2", "pypdfium2": str(version.PYPDFIUM_INFO), "pdfium": str(version.PDFIUM_INFO),
            "page_long_edge": PAGE_LONG_EDGE, "quarter_dpi": QUARTER_DPI, "quarter_span": QUARTER_SPAN,
            "sideways": [SIDEWAYS_SHARE, SIDEWAYS_MIN], "format": "png-zlib6; page rgb8, quarters grey8", "annotations": True}


def _config_hash(config: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def _png(bitmap, box: tuple[int, int, int, int] | None = None) -> bytes:
    """An 8-bit RGB or greyscale PNG of a PDFium bitmap region (left, top, right, bottom) in pixels."""
    left, top, right, bottom = box or (0, 0, bitmap.width, bitmap.height)
    data, stride, channels = bytes(bitmap.buffer), bitmap.stride, bitmap.n_channels
    rows = b"".join(b"\0" + data[y * stride + left * channels: y * stride + right * channels] for y in range(top, bottom))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", right - left, bottom - top, 8, {1: 0, 3: 2}[channels], 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b"")


def _sideways_turn(page) -> int:
    """Clockwise turn (90 or 270) that sets most sideways text upright; 0 when the page has little."""
    import pypdfium2.raw as raw

    textpage = page.get_textpage()
    try:
        counts = {0: 0, 90: 0, 180: 0, 270: 0}
        for index in range(textpage.count_chars()):
            if chr(raw.FPDFText_GetUnicode(textpage.raw, index)).isspace():
                continue
            angle = raw.FPDFText_GetCharAngle(textpage.raw, index)
            if angle >= 0:
                counts[round(math.degrees(angle) / 90) * 90 % 360] += 1
    finally:
        textpage.close()
    angle = max((90, 270), key=counts.__getitem__)
    total = sum(counts.values())
    if counts[angle] < SIDEWAYS_MIN or counts[angle] < SIDEWAYS_SHARE * total:
        return 0
    # Text that PDFium reports at 270 degrees reads upright after a clockwise quarter turn.
    return 270 if angle == 90 else 90


def _views(page, turn: int) -> list[tuple[str, bytes, int, int]]:
    """(view, png, width, height) for the whole page in colour and its greyscale quarters, turned
    clockwise by `turn`."""
    width, height = page.get_size()
    if turn in (90, 270):
        width, height = height, width
    whole = page.render(scale=PAGE_LONG_EDGE / max(width, height), rotation=turn, rev_byteorder=True, may_draw_forms=True)
    views = [("turned" if turn else "page", _png(whole), whole.width, whole.height)]
    whole.close()
    big = page.render(scale=QUARTER_DPI / 72, rotation=turn, grayscale=True, may_draw_forms=True)
    span_x, span_y = round(big.width * QUARTER_SPAN), round(big.height * QUARTER_SPAN)
    for index, name in enumerate(QUARTERS):
        left = 0 if index % 2 == 0 else big.width - span_x
        top = 0 if index < 2 else big.height - span_y
        box = (left, top, left + span_x, top + span_y)
        views.append(((f"turned-{name}" if turn else name), _png(big, box), span_x, span_y))
    big.close()
    return views


def _file(source_id: str, number: int, view: str) -> str:
    suffix = {"page": "", "turned": "-turned"}.get(view)
    if suffix is None:
        turned = view.startswith("turned-")
        suffix = ("-turned" if turned else "") + f"-{QUARTERS.index(view.removeprefix('turned-')) + 1}"
    return f"{source_id}/p{number:03d}{suffix}.png"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cached(manifest: Path, source: SourceDocument, config: dict[str, object]) -> PageImageSet | None:
    """A previous rendering whose source, configuration and every image hash still match."""
    try:
        value = PageImageSet.model_validate_json(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    root = manifest.parent.parent
    if (value.source_sha256 != source.sha256 or value.source_id != source.id or value.config != config or value.error
            or not all((root / image.file).is_file() and _sha(root / image.file) == image.sha256 for image in value.images)):
        return None
    return value.model_copy(update={"directory": str(root)})


def render_source(source: SourceDocument, out: Path) -> PageImageSet | None:
    """Render every page of a PDF source into out/page-images/<config hash>/<source id>/, reusing a
    verified earlier rendering. None for non-PDF sources; a set with `error` when rendering fails."""
    if not source.path.lower().endswith(".pdf"):
        return None
    config = render_config()
    root = out / "page-images" / _config_hash(config)
    manifest = root / source.id / "manifest.json"
    if (reused := _cached(manifest, source, config)) is not None:
        return reused
    import pypdfium2 as pdfium

    images: list[PageImage] = []
    try:
        if hashlib.sha256(Path(source.path).read_bytes()).hexdigest() != source.sha256:
            raise ValueError("the PDF changed after its text was extracted")
        document = pdfium.PdfDocument(source.path)
        try:
            (root / source.id).mkdir(parents=True, exist_ok=True)
            for number in range(1, len(document) + 1):
                page = document[number - 1]
                try:
                    turns = [0] + [turn for turn in [_sideways_turn(page)] if turn]
                    for turn in turns:
                        for view, png, width, height in _views(page, turn):
                            name = _file(source.id, number, view)
                            _write(root / name, png)
                            images.append(PageImage(page=number, view=view, file=name, rotation=turn,
                                                    sha256=hashlib.sha256(png).hexdigest(), width=width, height=height))
                finally:
                    page.close()
            pages = len(document)
        finally:
            document.close()
    except Exception as exc:
        return PageImageSet(source_id=source.id, source_sha256=source.sha256, pages=0, config=config,
                            config_hash=_config_hash(config), directory=str(root),
                            error=f"page rendering failed: {type(exc).__name__}: {exc}")
    value = PageImageSet(source_id=source.id, source_sha256=source.sha256, pages=pages, config=config,
                         config_hash=_config_hash(config), directory=str(root), images=images)
    _write(manifest, value.model_dump_json(indent=2).encode())
    return value


def _write(path: Path, data: bytes) -> None:
    """Atomic write; concurrent runs sharing a directory each write a whole file."""
    import os
    import tempfile

    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint(sets: list[PageImageSet]) -> str:
    """Identity of the rendered images: configuration plus every file name and content hash."""
    return hashlib.sha256(json.dumps([[s.source_id, s.source_sha256, s.config_hash, s.error,
                                       [[i.file, i.sha256] for i in s.images]] for s in sets]).encode()).hexdigest()


def files(sets: list[PageImageSet]) -> dict[str, Path]:
    """Every rendered image, by its staged name."""
    return {image.file: Path(s.directory) / image.file for s in sets for image in s.images}


def page_files(sets: list[PageImageSet], source_id: str, page: int, quarters: bool = True) -> list[str]:
    """Staged names of one page's whole view and, optionally, its quarters (upright copies included)."""
    return [image.file for s in sets if s.source_id == source_id for image in s.images
            if image.page == page and (quarters or image.view in {"page", "turned"})]


def manifest_text(sets: list[PageImageSet]) -> str:
    """Prompt section naming the staged images; empty when no PDF source exists."""
    if not sets:
        return ""
    lines = ["PAGE IMAGES",
             "Every page of each PDF source is rendered as PNG images in the page-images directory of your working "
             "directory. The extracted text can misplace table cells, join neighbouring numbers or cells, drop "
             "minus signs and lose significance stars, bold type and column grouping; the images show each page "
             "as printed. Open the images with your file or image viewing tool whenever a point depends on a "
             "table, figure or typographic detail, including a table continued from or onto a neighbouring page."]
    for s in sets:
        if s.error:
            lines.append(f"- {s.source_id}: no page images ({s.error}). Points that depend on its tables cannot be checked against the printed page.")
            continue
        turned = sorted({i.page for i in s.images if i.rotation})
        lines.append(f"- {s.source_id}: pages 1-{s.pages}. page-images/{s.source_id}/p001.png ... p{s.pages:03d}.png show "
                     "each whole page; p005-1.png ... p005-4.png (for page 5) are magnified, overlapping quarters "
                     "(upper left, upper right, lower left, lower right) for small print.")
        if turned:
            lines.append(f"  Pages {', '.join(map(str, turned))} have sideways text and also upright copies, "
                         "for example p{0:03d}-turned.png and p{0:03d}-turned-1.png ... -4.png.".format(turned[0]))
    return "\n".join(lines)
