from pathlib import Path
import re

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject

from reviscope.backend import FixtureBackend
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Evidence, Finding, PageText, Profile
from reviscope.verification import verify_findings, verify_quote


def _font():
    return DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})


def _cells(cells, size=12):
    return "\n".join(f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET" for x, y, text in cells)


def _write_pdf(path, contents, xobjects=None):
    """Write one page per raw content stream; xobjects maps a page index to a form XObject stream."""
    writer = PdfWriter()
    for i, content in enumerate(contents):
        page = writer.add_blank_page(width=600, height=800)
        resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font()})})
        if xobjects and i in xobjects:
            form = DecodedStreamObject()
            form.set_data(xobjects[i].encode())
            form.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                         NameObject("/BBox"): ArrayObject([FloatObject(v) for v in (0, 0, 600, 800)]),
                         NameObject("/Resources"): DictionaryObject({
                             NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font()})})})
            resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm1"): writer._add_object(form)})
        page[NameObject("/Resources")] = resources
        stream = DecodedStreamObject()
        stream.set_data(content.encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)
    return path


TABLE = [(0, 0, "Group"), (0, -20, "Treatment"), (0, -40, "Control"),
         (200, 0, "Mean"), (200, -20, "1.25"), (200, -40, "2.50")]


def _at(x, y, cells):
    return [(x + dx, y + dy, text) for dx, dy, text in cells]


@pytest.fixture
def table_pdf(tmp_path):
    """A real PDF whose table is painted column by column, unlike its reading order."""
    return _write_pdf(tmp_path / "table.pdf", [
        _cells([(50, 740, "See Table 1 for the results.")]),
        _cells([(50, 740, "Table 1. Results")] + _at(50, 700, TABLE)),
    ])


def test_layout_preserves_columns_and_normal_quote_offsets(table_pdf):
    source = ingest(table_pdf)
    normal = [page.extract_text() for page in PdfReader(table_pdf).pages]
    assert [page.text for page in source.pages] == normal
    assert source.text == "\n\n".join(f"[Page {i}]\n{text}" for i, text in enumerate(normal, 1))
    assert source.pages[0].table_layout is None
    layout = source.pages[1].table_layout
    assert re.search(r"^Treatment +1\.25$", layout, re.MULTILINE)
    assert re.search(r"^Control +2\.50$", layout, re.MULTILINE)
    assert not source.extraction_warnings

    evidence = ReviewPipeline._evidence([source])
    assert evidence.count("[Page 2, table layout]") == 1
    assert "[Page 1, table layout]" not in evidence
    assert source.text in evidence and layout in evidence
    assert evidence.index(source.text) < evidence.index("[Page 2, table layout]")

    finding = Finding(id="table", module="statistics", claim="Check table", rationale="Check", remedy="Check",
                      evidence=[Evidence(source_id=source.id, quote="Treatment\nControl")])
    anchored = verify_findings([finding], [source])[0].evidence[0]
    assert anchored.page == 2
    assert source.text[anchored.source_char_start:anchored.source_char_end] == "Treatment\nControl"
    # A row assembled by layout mode is a reading aid, not a new quote anchor.
    assert verify_quote("Treatment 1.25", [source.model_dump()], source.id).status == "unanchored"
    finding.evidence = [Evidence(source_id=source.id, quote="Treatment 1.25")]
    assert not verify_findings([finding], [source], {"table": {"status": "supported"}})[0].evidence


class _Page:
    """A pypdf page stand-in whose layout mode returns `layout` (by default, the normal text respaced)."""

    def __init__(self, text, layout=None, calls=None):
        self.text, self.layout, self.calls, self.turns = text, layout, calls if calls is not None else [], []

    def extract_text(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs:
            return self.text
        layout = "     ".join(self.text.split()) if self.layout is None else self.layout
        if isinstance(layout, Exception):
            raise layout
        return layout(kwargs, self.turns) if callable(layout) else layout

    def add_transformation(self, transformation):
        self.turns.append(transformation.ctm)


def _mock_pdf(monkeypatch, tmp_path, pages):
    reader = type("Reader", (), {"pages": pages})()
    for i, page in enumerate(pages):
        page.pdf, page.page_number = reader, i
    monkeypatch.setattr("pypdf.PdfReader", lambda _: reader)
    monkeypatch.setattr("pypdf.PdfWriter", lambda clone_from: clone_from)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"placeholder")
    return pdf


@pytest.mark.parametrize("text,selected", [
    ("Table 1\nResults", True),
    ("  TABLE 12. Results", True),
    ("Header\n\tTable 2: Results", True),
    ("Table\n3\nResults", True),
    ("Table S1. Supplementary results", True),
    ("Table A2 (continued)", True),
    ("Table 2 Means and standard deviations", True),
    ("Table 1a. Subgroup results", True),
    ("103 Table 3. Descriptives", True),  # manuscript line number
    ("103\tTable 3", True),
    ("See Table 1 for the results.", False),
    ("Results (Table 1).", False),
    ("Insert Table 1 about here", False),
    ("<Table 1 here>", False),
    ("Tables 1 and 2 show the results.", False),
    ("Table of contents", False),
    ("Figure 1. Results", False),
    ("were stronger than reported in\nTable 4 of the supplement.", False),  # wrapped references
    ("as summarised in\nTable 4, the effects", False),
    ("(see\nTable 1). A large percentage", False),
    ("left column prose Table 8. Results", False),  # not line-leading: a known miss for row-wise text
    ("", False),
])
def test_only_caption_pages_request_layout(monkeypatch, tmp_path, text, selected):
    calls = []
    pdf = _mock_pdf(monkeypatch, tmp_path, [_Page(text, calls=calls), _Page(text, calls=calls)])
    if not text:
        with pytest.raises(ValueError, match="OCR is required"):
            ingest(pdf)
    else:
        source = ingest(pdf)
        layout = "     ".join(text.split())
        assert [page.table_layout for page in source.pages] == [layout if selected else None] * 2
        assert not source.extraction_warnings
    assert calls == ([{}, {"extraction_mode": "layout"}] if selected else [{}]) * 2


@pytest.mark.parametrize("layout", ["", " \n", "Table 1. Results", ValueError("bad layout")])
def test_unavailable_or_incomplete_layout_retains_normal_text_with_warning(monkeypatch, tmp_path, layout):
    page = _Page("Table 1. Results\nGroup\nMean", layout)
    source = ingest(_mock_pdf(monkeypatch, tmp_path, [page]))
    assert source.text == "[Page 1]\nTable 1. Results\nGroup\nMean"
    assert source.pages[0].table_layout is None
    assert len(source.extraction_warnings) == 1
    assert "PDF page 1" in source.extraction_warnings[0]
    assert "normal text is retained" in source.extraction_warnings[0]
    assert "table layout]" not in ReviewPipeline._evidence([source])
    if not isinstance(layout, Exception):  # Incomplete upright text is retried with the page turned both ways.
        assert len(page.turns) == 2
        assert "did not reproduce the normal text" in source.extraction_warnings[0]


@pytest.mark.parametrize("layout,kept", [
    ("Table 1. Results\nMean   3.281", False),     # 3.28 joined to a neighbouring 1
    ("Table 1. Results\nMean   3.28   1", True),
    ("Table 1. Results\nMean   3. 28 1", False),   # a number split that normal text keeps whole
    ("Table 1. Results\n1   Mean3.28", True),      # digits joined to words keep their value
])
def test_layout_that_regroups_digits_is_skipped(monkeypatch, tmp_path, layout, kept):
    calls = []
    source = ingest(_mock_pdf(monkeypatch, tmp_path, [_Page("Table 1. Results\nMean 3.28\n1", layout, calls)]))
    assert source.pages[0].table_layout == (layout if kept else None)
    weights = [call.get("layout_mode_scale_weight") for call in calls[1:]]
    assert weights == ([None] if kept else [None, 2.5, 5.0])
    if not kept:
        changed = "layout 3.281; normal 1, 3.28" if "3.281" in layout else "layout 3, 28; normal 3.28"
        assert source.extraction_warnings == [
            "Table layout copy skipped on PDF page 1: layout mode writes numbers differently from the normal text "
            f"({changed}); normal text is retained."]


@pytest.mark.parametrize("normal,layout,kept", [
    ("A -0.5\nB 0.3", "A 0.5     B -0.3", False),        # same characters, signs moved between numbers
    ("A \u22120.5\nB 0.3", "A 0.5     B \u22120.3", False),
    ("A \u22121 \u22121 1 x", "A \u22121 1     1 \u2212x", False),  # one -1 fewer: multiplicities count
    ("p .05", "p 05.", False),                              # leading decimal point moved
    ("p 1e-3", "p 1e3-", False),                            # exponent sign moved
    ("A 50%\nB 30", "A 50     B 30%", False),
    ("A 10\u207b\u00b3\nB 10\u00b2", "A 10\u00b3     B 10\u207b\u00b2", False),
    ("A \u22120.5", "A \u2212     0.5", False),          # a sign set apart from its number
    ("A .05 .01", "A .05.01", False),                      # neighbouring cells joined
    ("A 0.5 \u22120.3", "A 0.5\u22120.3", False),
    ("A \u22120.5\nB 0.3", "B 0.3     A \u22120.5", True),  # rearranged, every number intact
    ("A \u2212 0.5 [\u2212.73, .35]", "A \u2212     0.5     [\u2212.73,     .35]", True),
    ("COVID-19, 1-3 items (n = 19).2", "COVID-19,    1-3    items    (n = 19).2", True),
])
def test_layout_that_changes_numbers_is_skipped(monkeypatch, tmp_path, normal, layout, kept):
    """Moving a sign, decimal point, exponent or percent sign, or joining cells, changes a number."""
    normal, layout = f"Table 1. Results\n{normal}", f"Table 1. Results\n{layout}"
    source = ingest(_mock_pdf(monkeypatch, tmp_path, [_Page(normal, layout)]))
    assert source.pages[0].table_layout == (layout if kept else None)
    assert source.pages[0].text == normal
    assert len(source.extraction_warnings) == (not kept)
    assert all("writes numbers differently" in warning for warning in source.extraction_warnings)


def test_sign_drawn_after_its_number_is_skipped(tmp_path):
    """Normal text follows drawing order and puts the sign last; the copy is skipped though layout mode is right."""
    cells = [(50, 740, "Table 2. Effects"), (50, 700, "Slope"), (254, 700, "0.35")]
    pdf = _write_pdf(tmp_path / "sign.pdf", [_cells(cells) + "\n" + _cells([(250, 700, "-")])])
    assert "Slope" in PdfReader(pdf).pages[0].extract_text(extraction_mode="layout").split("-0.35")[0]
    source = ingest(pdf)
    assert source.pages[0].text.endswith("0.35-")
    assert source.pages[0].table_layout is None
    assert source.extraction_warnings == [
        "Table layout copy skipped on PDF page 1: layout mode writes numbers differently from the normal text "
        "(layout -0.35; normal 0.35); normal text is retained."]


def test_rescaled_layout_separates_small_font_cells(tmp_path):
    prose = [(50, 760 - 13 * j, "Participants completed the measures in a randomised order and the analysis "
              "followed the preregistered plan with robust standard errors") for j in range(30)]
    rows = [["Model", "chi2", "df", "CFI"]] + [[f"M{i}", f"{1234.567 + i:.3f}", f"{100 + i}", f"0.95{i}"]
                                                 for i in range(3)]
    table = "\n".join(f"BT /F1 6.5 Tf 1 0 0 1 {50 + 30 * c} {345 - 9 * r} Tm ({cell}) Tj ET"
                      for r, row in enumerate(rows) for c, cell in enumerate(row))
    pdf = _write_pdf(tmp_path / "small.pdf", [_cells(prose, 11) + "\n" + _cells([(50, 360, "Table 7. Fit")], 11)
                                              + "\n" + table])
    assert "1234.567100" in PdfReader(pdf).pages[0].extract_text(extraction_mode="layout")
    source = ingest(pdf)
    assert re.search(r"^M0 +1234\.567 +100 +0\.950$", source.pages[0].table_layout, re.MULTILINE)
    assert not source.extraction_warnings


def test_rotated_table_is_laid_out_upright(tmp_path):
    sideways = "q 0 1 -1 0 560 100 cm\n" + _cells([(0, 0, "Table 5. Rotated results")] + _at(0, -30, TABLE)) + "\nQ"
    pdf = _write_pdf(tmp_path / "rotated.pdf", [_cells([(50, 760, "Running head")]) + "\n" + sideways])
    upright = PdfReader(pdf).pages[0].extract_text(extraction_mode="layout")
    assert "Treatment" not in upright  # pypdf omits rotated text from layout mode
    source = ingest(pdf)
    assert [page.text for page in source.pages] == [page.extract_text() for page in PdfReader(pdf).pages]
    layout = source.pages[0].table_layout
    assert layout.index("Running head") < layout.index("[Rotated text on this page, turned upright]")
    assert re.search(r"^Treatment +1\.25$", layout, re.MULTILINE)
    assert not source.extraction_warnings


def test_table_in_form_xobject_is_skipped_with_warning(tmp_path):
    form = _cells([(50, 740, "Table 6. Results")] + _at(50, 700, TABLE))
    pdf = _write_pdf(tmp_path / "xobject.pdf", [_cells([(300, 40, "24")]) + "\nq /Fm1 Do Q"], {0: form})
    source = ingest(pdf)
    assert "Treatment" in source.text
    assert source.pages[0].table_layout is None
    assert source.extraction_warnings == [
        "Table layout copy skipped on PDF page 1: layout mode did not reproduce the normal text "
        "(for example, form XObject or obliquely rotated content); normal text is retained."]


def test_line_numbered_and_two_column_captions(tmp_path):
    numbered = [(30, 740, "101"), (72, 740, "Participants completed the measures."),
                (30, 726, "102"), (72, 726, "Table 3. Descriptives")] + _at(72, 700, TABLE)
    prose = [(320, 740 - 12 * j, f"Right column prose line {j} about the sample") for j in range(8)]
    pdf = _write_pdf(tmp_path / "columns.pdf", [_cells(numbered, 10), _cells(_at(50, 0, [(0, 740, "Table 1. Means")])
                                                + _at(50, 720, TABLE) + prose, 10)])
    source = ingest(pdf)
    assert re.search(r"^102 +Table 3\. Descriptives$", source.pages[0].table_layout, re.MULTILINE)
    # Prose from the other column shares lines with table cells in a full-page copy.
    assert re.search(r"^ *Treatment +1\.25 +Right column prose", source.pages[1].table_layout, re.MULTILINE)
    assert "Full-page layout copies" in ReviewPipeline._evidence([source])
    assert not source.extraction_warnings


def test_layout_only_change_invalidates_cached_study_map(monkeypatch, tmp_path, table_pdf):
    profile = Profile(id="test", title="Test", modules=[], module_prompts={})
    pipeline = ReviewPipeline(FixtureBackend(), profile, run_metacheck=False)
    first = pipeline.run(table_pdf, output_dir=tmp_path / "run")
    cached = pipeline.run(table_pdf, output_dir=tmp_path / "run")
    assert cached.stages[0].status == "cached"
    source = first.sources[0].model_copy(deep=True)
    source.pages[1].table_layout += "\nAdditional table detail"
    monkeypatch.setattr("reviscope.pipeline.ingest", lambda *args, **kwargs: source)
    changed = pipeline.run(table_pdf, output_dir=tmp_path / "run")
    assert changed.sources[0].sha256 == first.sources[0].sha256
    assert changed.sources[0].text == first.sources[0].text
    assert changed.metadata.input_hash != first.metadata.input_hash
    assert changed.stages[0].status == "completed"


def test_older_page_records_and_non_pdf_evidence_remain_valid(tmp_path):
    assert PageText.model_validate({"page": 1, "text": "Normal text"}).table_layout is None
    path = tmp_path / "paper.md"
    path.write_text("Table 1. A Markdown table\nGroup | Mean\nTreatment | 1.25")
    source = ingest(path)
    assert not source.pages
    assert ReviewPipeline._evidence([source]) == (
        f"SOURCE_ID: {source.id}\nTYPE: manuscript\nCONTENT BEGIN\n{source.text}\nCONTENT END")


CORPUS = Path(__file__).resolve().parents[1] / "eval/corpus/cache/open-review-curation-20261002"


@pytest.mark.parametrize("name,table_pages,row", [
    ("mackinnon", [21, 22, 23, 24], "Robust CFI 0.953 0.952 0.950 0.946"),
    ("ziano", [7, 9, 12, 14, 17], "Morality .70 .40 .99"),
    ("satrevik", [29, 31], "Operationalization Statistical test Results"),
    ("heyman", [28], "Week 1 General introduction"),
])
def test_cached_corpus_pdf_table_pages(name, table_pages, row):
    pdf = CORPUS / name / "manuscript/original.pdf"
    if not pdf.is_file():
        pytest.skip("requires the local, untracked manuscript corpus cache")
    source = ingest(pdf)
    normal = [page.extract_text() or "" for page in PdfReader(pdf).pages]
    assert [page.text for page in source.pages] == normal
    assert source.text == "\n\n".join(f"[Page {i}]\n{text}" for i, text in enumerate(normal, 1))
    kept = {page.page for page in source.pages if page.table_layout}
    skipped = {int(match.group(1)) for warning in source.extraction_warnings
               if (match := re.match(r"Table layout copy skipped on PDF page (\d+):", warning))}
    # pypdf versions differ: a caption page must have a checked copy or an explicit fallback.
    assert kept | skipped == set(table_pages)
    assert not kept & skipped
    assert len(source.extraction_warnings) == len(skipped)
    if layout := source.pages[table_pages[0] - 1].table_layout:
        assert row in [" ".join(line.split()) for line in layout.splitlines()]
    evidence = ReviewPipeline._evidence([source])
    assert evidence.count(", table layout]") == len(kept)
