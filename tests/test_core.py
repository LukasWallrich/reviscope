from pathlib import Path

from coarse_socpsy.backend import FixtureBackend
from coarse_socpsy.ingest import ingest
from coarse_socpsy.pipeline import ReviewPipeline
from coarse_socpsy.schemas import Profile
from coarse_socpsy.pipeline import FindingsResponse
from coarse_socpsy.render import to_html, to_markdown
from pydantic import ValidationError
import pytest


def profile() -> Profile:
    return Profile(id="test", title="Test", modules=["study_design"], module_prompts={"study_design": "Review sampling."})


def test_ingest_and_pipeline_resume(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("Participants were recruited from the university pool.")
    source = ingest(manuscript)
    assert source.sha256 and source.kind == "manuscript"
    pipeline = ReviewPipeline(FixtureBackend(), profile())
    first = pipeline.run(manuscript, output_dir=tmp_path / "run")
    second = pipeline.run(manuscript, output_dir=tmp_path / "run")
    assert any(s.status == "cached" for s in second.stages)
    assert (tmp_path / "run" / "review.json").is_file()
    assert first.findings


def test_partial_failure_still_renders(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("Some manuscript content")
    broken = Profile(id="broken", title="Broken", modules=["missing"])
    run = ReviewPipeline(FixtureBackend(), broken).run(manuscript, output_dir=tmp_path / "run")
    assert run.partial
    assert (tmp_path / "run" / "review.html").is_file()


def test_model_response_requires_explicit_abstention():
    with pytest.raises(ValidationError):
        FindingsResponse.model_validate({})
    assert FindingsResponse.model_validate({"findings": []}).findings == []


def test_fixture_export_is_unmistakable_and_html_escaped(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("Participants were recruited from the university pool. <script>alert(1)</script>")
    run = ReviewPipeline(FixtureBackend(), profile()).run(manuscript, output_dir=tmp_path / "run")
    markdown = to_markdown(run)
    rendered = to_html(markdown)
    assert markdown.startswith("# DEMONSTRATION — NOT AN AI REVIEW")
    assert "<script>" not in rendered


def test_input_change_invalidates_stage_cache(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("First content")
    pipeline = ReviewPipeline(FixtureBackend(), profile())
    pipeline.run(manuscript, output_dir=tmp_path / "run")
    manuscript.write_text("Changed content")
    changed = pipeline.run(manuscript, output_dir=tmp_path / "run")
    assert changed.stages[0].status == "completed"


def test_all_scanned_pdf_is_rejected(monkeypatch, tmp_path: Path):
    class BlankPage:
        def extract_text(self):
            return ""

    class BlankReader:
        def __init__(self, _path):
            self.pages = [BlankPage(), BlankPage()]

    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", BlankReader)
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"scanned-placeholder")
    with pytest.raises(ValueError, match="OCR is required"):
        ingest(pdf)
