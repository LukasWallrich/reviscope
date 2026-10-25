from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf._page import PageObject

import reviscope
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Evidence, Finding, PageText
from reviscope.verification import verify_findings, verify_quote

from pdf_fixtures import table_pdf


def test_pdf_text_is_plain_pypdf_extraction_and_quotes_anchor_in_it(tmp_path):
    pdf = table_pdf(tmp_path / "table.pdf")
    source = ingest(pdf)
    normal = [page.extract_text() for page in PdfReader(pdf).pages]
    assert [page.text for page in source.pages] == normal
    assert source.text == "\n\n".join(f"[Page {i}]\n{text}" for i, text in enumerate(normal, 1))
    assert not source.extraction_warnings
    assert ReviewPipeline._evidence([source]) == f"SOURCE_ID: {source.id}\nTYPE: manuscript\nCONTENT BEGIN\n{source.text}\nCONTENT END"

    finding = Finding(id="table", module="statistics", claim="Check table", rationale="Check", remedy="Check",
                      evidence=[Evidence(source_id=source.id, quote="Treatment\nControl")])
    anchored = verify_findings([finding], [source])[0].evidence[0]
    assert anchored.page == 2
    assert source.text[anchored.source_char_start:anchored.source_char_end] == "Treatment\nControl"
    # A row as printed is not in the extracted text, so it cannot be a quotation.
    assert verify_quote("Treatment 1.25", [source.model_dump()], source.id).status == "unanchored"


def test_ingest_requests_only_plain_extraction(monkeypatch, tmp_path):
    calls = []
    original = PageObject.extract_text

    def record(self, *args, **kwargs):
        calls.append(kwargs)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", record)
    ingest(table_pdf(tmp_path / "table.pdf"))
    assert calls == [{}, {}]


def test_layout_copies_are_gone_and_older_page_records_still_load():
    assert set(PageText.model_fields) == {"page", "text"}
    assert PageText.model_validate({"page": 1, "text": "Normal text", "table_layout": "old copy"}).text == "Normal text"
    package = Path(reviscope.__file__).parent
    code = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
    for remnant in ("extraction_mode", "table_layout", "layout_mode_scale_weight", "_TABLE_CAPTION", "TABLE LAYOUT COPIES"):
        assert remnant not in code


def test_markdown_evidence_is_unchanged(tmp_path):
    path = tmp_path / "paper.md"
    path.write_text("Table 1. A Markdown table\nGroup | Mean\nTreatment | 1.25")
    source = ingest(path)
    assert not source.pages
    assert ReviewPipeline._evidence([source]) == (
        f"SOURCE_ID: {source.id}\nTYPE: manuscript\nCONTENT BEGIN\n{source.text}\nCONTENT END")


CORPUS = Path(__file__).resolve().parents[1] / "eval/corpus/cache/open-review-curation-20261002"


@pytest.mark.parametrize("name", ["mackinnon", "ziano", "satrevik", "heyman"])
def test_cached_corpus_pdfs_keep_plain_text(name):
    pdf = CORPUS / name / "manuscript/original.pdf"
    if not pdf.is_file():
        pytest.skip("requires the local, untracked manuscript corpus cache")
    source = ingest(pdf)
    normal = [page.extract_text() or "" for page in PdfReader(pdf).pages]
    assert [page.text for page in source.pages] == normal
    assert source.text == "\n\n".join(f"[Page {i}]\n{text}" for i, text in enumerate(normal, 1))
    assert not source.extraction_warnings
