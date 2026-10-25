from pathlib import Path
import re

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from reviscope.backend import FixtureBackend
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Evidence, Finding, PageText, Profile
from reviscope.verification import verify_findings, verify_quote


@pytest.fixture
def table_pdf(tmp_path):
    """A real PDF whose table is painted column by column, unlike its reading order."""
    writer = PdfWriter()
    pages = [
        [(50, 740, "See Table 1 for the results.")],
        [(50, 740, "Table 1. Results"),
         (50, 700, "Group"), (50, 680, "Treatment"), (50, 660, "Control"),
         (250, 700, "Mean"), (250, 680, "1.25"), (250, 660, "2.50")],
    ]
    for cells in pages:
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data("\n".join(f"BT /F1 12 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET"
                                  for x, y, text in cells).encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    pdf = tmp_path / "table.pdf"
    writer.write(pdf)
    return pdf


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


@pytest.mark.parametrize("text,selected", [
    ("Table 1\nResults", True),
    ("  TABLE 12. Results", True),
    ("Header\n\tTable 2: Results", True),
    ("Table\n3\nResults", True),
    ("Table S1. Supplementary results", True),
    ("Table A2 (continued)", True),
    ("See Table 1 for the results.", False),
    ("Results (Table 1).", False),
    ("Insert Table 1 about here", False),
    ("<Table 1 here>", False),
    ("Tables 1 and 2 show the results.", False),
    ("Table of contents", False),
    ("Figure 1. Results", False),
    ("", False),
])
def test_only_caption_pages_request_layout(monkeypatch, tmp_path, text, selected):
    calls = []

    class Page:
        def extract_text(self, **kwargs):
            calls.append(kwargs)
            return "Group     Mean" if kwargs else text

    monkeypatch.setattr("pypdf.PdfReader", lambda _: type("Reader", (), {"pages": [Page(), Page()]})())
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"placeholder")
    if not text:
        with pytest.raises(ValueError, match="OCR is required"):
            ingest(pdf)
    else:
        source = ingest(pdf)
        assert [page.table_layout for page in source.pages] == ["Group     Mean" if selected else None] * 2
    assert calls == ([{}, {"extraction_mode": "layout"}] if selected else [{}]) * 2


@pytest.mark.parametrize("layout", [None, "", " \n", ValueError("bad layout")])
def test_unavailable_layout_retains_normal_text_with_warning(monkeypatch, tmp_path, layout):
    class Page:
        def extract_text(self, **kwargs):
            if not kwargs:
                return "Table 1. Results\nGroup\nMean"
            if isinstance(layout, Exception):
                raise layout
            return layout

    monkeypatch.setattr("pypdf.PdfReader", lambda _: type("Reader", (), {"pages": [Page()]})())
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"placeholder")
    source = ingest(pdf)
    assert source.text == "[Page 1]\nTable 1. Results\nGroup\nMean"
    assert source.pages[0].table_layout is None
    assert len(source.extraction_warnings) == 1
    assert "page 1" in source.extraction_warnings[0]
    assert "normal text is retained" in source.extraction_warnings[0]
    assert "table layout]" not in ReviewPipeline._evidence([source])


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
    assert [page.page for page in source.pages if page.table_layout] == table_pages
    assert not source.extraction_warnings
    assert row in [" ".join(line.split())
                   for line in source.pages[table_pages[0] - 1].table_layout.splitlines()]
    evidence = ReviewPipeline._evidence([source])
    assert evidence.count(", table layout]") == len(table_pages)
