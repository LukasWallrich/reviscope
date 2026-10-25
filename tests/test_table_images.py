"""Page images for review stages, and the separate cell reading that table-based claims need."""
import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from reviscope import page_images
from reviscope.backend import Backend, ClaudeBackend, CodexBackend, StagedImages, _stage, parse_claude_events
from reviscope.discovery import TOPICS, requested_checks
from reviscope.pipeline import BLIND_READING, ReviewPipeline
from reviscope.render import unconfirmed_concerns
from reviscope.schemas import CellReading, Finding, Profile, StudyMap, TableCheck, TableReading
from reviscope.verification import apply_table_checks, compare_reading

from pdf_fixtures import TABLE, at, cells, write_pdf

CAPTION = "Table 1. Results"
PROFILE = Profile(id="test", title="Test", modules=["consistency"],
                  module_prompts={"consistency": "Check that reported numbers agree."})


def reading(**changes):
    values = {"source_id": "s", "page": 2, "table": "Table 1", "row": ["Treatment"], "column": ["Mean"], "value": "1.25",
              "marks": "", "emphasis": None, "unit": ""}
    return TableReading(**{**values, **changes})


def blind(**changes):
    values = {"request_id": "cell-0", "located": True, "legible": True, "value": "1.25", "marks": "", "emphasis": "none",
              "unit": "", "note": ""}
    return CellReading(**{**values, **changes})


@pytest.mark.parametrize("claimed,read,outcome", [
    (reading(), blind(), "matched"),
    (reading(value="−0.24"), blind(value="-0.24"), "matched"),       # one minus sign
    (reading(value=".05"), blind(value="0.05"), "matched"),
    (reading(value="3.281"), blind(value="3.28"), "mismatched"),          # cells joined in extracted text
    (reading(value="24"), blind(value="−24"), "mismatched"),         # lost minus sign
    (reading(value="10³"), blind(value="103"), "mismatched"),       # compatibility normalization must preserve exponents
    (reading(value="10³"), blind(value="10³"), "matched"),
    (reading(value="N/A"), blind(value=""), "mismatched"),           # a missing-value label is not an empty read
    (reading(unit="ms"), blind(unit="s"), "mismatched"),
    (reading(unit="m²"), blind(unit="m2"), "mismatched"),
    (reading(unit="%"), blind(unit=""), "mismatched"),
    (reading(unit=""), blind(unit="%"), "mismatched"),
    (reading(unit=" kg / m² "), blind(unit="kg/m²"), "matched"),
    (reading(marks="***"), blind(marks=""), "mismatched"),
    (reading(marks="*"), blind(marks="∗"), "matched"),
    (reading(emphasis="bold"), blind(emphasis="none"), "mismatched"),
    (reading(), blind(emphasis="bold"), "matched"),                       # typeface not asserted
    (reading(), blind(located=False, note="no such row"), "not_located"),
    (reading(), blind(legible=False), "illegible"),
    (reading(), None, "not_read"),
])
def test_cell_comparison(claimed, read, outcome):
    assert compare_reading(claimed, read)[0] == outcome


def test_table_gate_holds_supported_claims_without_confirmed_cells():
    base = Finding(id="f", module="m", claim="c", rationale="r", remedy="x", status="llm_supported")
    matched = TableCheck(reading=reading(), origin="discovery", outcome="matched", reason="same")
    wrong = TableCheck(reading=reading(value="3.281"), origin="verifier", outcome="mismatched", reason="differs")
    assert apply_table_checks(base, [matched], True).status == "llm_supported"
    held = apply_table_checks(base, [matched, wrong], True)
    assert held.status == "unresolved" and "differs" in held.verification
    # The verifier says the claim rests on table cells but no reading was recorded.
    assert apply_table_checks(base, [], True).status == "unresolved"
    assert apply_table_checks(base, [], False).status == "llm_supported"
    assert apply_table_checks(base.model_copy(update={"status": "contradicted"}), [wrong], True).status == "contradicted"


def test_unconfirmed_table_cells_in_a_supplement_remain_visible(tmp_path):
    from reviscope.schemas import Evidence, ReviewRun, RunMetadata, SourceDocument

    finding = Finding(id="f", module="m", claim="c", rationale="r", remedy="x", status="llm_supported",
                      verifier_status="supported", evidence=[Evidence(source_id="supp", quote=CAPTION, location="page 2")])
    held = apply_table_checks(finding, [], True)
    run = ReviewRun(metadata=RunMetadata(run_id="r", backend="fixture", profile="test", profile_hash="p",
                                        input_hash="i", output_dir=str(tmp_path)),
                    sources=[SourceDocument(id="supp", path="supp.pdf", kind="supplement", sha256="s", text=CAPTION)],
                    findings=[held])
    assert unconfirmed_concerns(run) == [held]


class TableBackend(Backend):
    """Stub reviewer: one finding resting on a table cell; records what each call received."""
    name, model, effort, tools = "codex", "gpt-6-luna", "high", True

    def __init__(self, claimed="1.25", printed="1.25", dependence=True, discovery_reading=True, verifier_reading=False):
        self.calls = []
        self.claimed, self.printed, self.dependence = claimed, printed, dependence
        self.discovery_reading, self.verifier_reading = discovery_reading, verifier_reading

    def generate(self, instruction, evidence, response_model, images=None):
        kind = response_model.__name__
        self.calls.append((kind, instruction, evidence, images))
        if images is not None:
            assert all(Path(path).is_file() for path in images.files.values())
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="d", contribution_summary="c", strengths=[])
        if kind == "DiscoveryResponse":
            sid = re.search(r"SOURCE_ID: (\S+)", evidence).group(1)
            findings = []
            if requested_checks(instruction) == TOPICS["consistency"]:
                cell = [reading(source_id=sid, value=self.claimed).model_dump()] if self.discovery_reading else []
                findings = [{"id": "mean", "module": "x", "claim": "The treatment mean conflicts with the text.",
                             "rationale": "Table 1 prints the treatment mean.", "remedy": "Correct it.",
                             "evidence": [{"source_id": sid, "quote": CAPTION}], "table_readings": cell}]
            checks = [{"check": c, "status": "not_applicable", "rationale": "Stub."} for c in requested_checks(instruction)]
            return response_model.model_validate({"concerns": findings, "checks": checks, "search_incomplete": False})
        if kind == "VerificationResponse":
            rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
            sid = rows[0]["quoted_evidence"][0]["source_id"]
            extra = [reading(source_id=sid, value=self.claimed).model_dump()] if self.verifier_reading else []
            return response_model.model_validate({"decisions": [{
                "finding_id": row["finding_id"], "status": "supported", "rationale": "Checked.",
                "evidence": row["quoted_evidence"], "remedy_status": "supported", "remedy_rationale": "Fine.",
                "table_dependence": self.dependence, "table_readings": extra} for row in rows]})
        if kind == "CellReadingResponse":
            requests = json.loads(evidence)
            return response_model.model_validate({"readings": [blind(request_id=r["request_id"], value=self.printed).model_dump()
                                                               for r in requests]})
        if kind == "EditorialResponse":
            rows = json.loads(instruction.split("FINDINGS\n")[1])
            return response_model.model_validate({"decisions": [{"finding_id": row["id"], "disposition": "keep", "reason": "ok",
                                                                 "target_id": None, "severity": "major"} for row in rows],
                                                  "reconciled_overview": {"design_summary": "d", "contribution_summary": "c", "strengths": []}})
        raise AssertionError(kind)


def _run(tmp_path, backend, name="run"):
    pdf = tmp_path / "table.pdf"
    if not pdf.exists():  # a page of prose (enough material for a review), then the table
        prose = [(50, 760 - 14 * j, f"Line {j}: participants completed the measures in a randomised order.") for j in range(30)]
        write_pdf(pdf, [cells(prose, 10), cells([(50, 740, CAPTION)] + at(50, 700, TABLE))])
    return ReviewPipeline(backend, PROFILE, run_metacheck=False, parallel=1).run(pdf, output_dir=tmp_path / name)


def test_matching_separate_reading_publishes_and_routes_images_to_review_stages(tmp_path):
    backend = TableBackend()
    run = _run(tmp_path, backend)
    finding = run.findings[0]
    assert finding.status == "llm_supported" and finding.editorial_disposition == "publish"
    assert [c.outcome for c in finding.table_checks] == ["matched"] and finding.table_dependence
    sid = run.sources[0].id
    assert finding.table_checks[0].images[0].startswith(f"{sid}/p002.png ")
    received = {kind: images for kind, _, _, images in backend.calls}
    # Study map, editorial: no images. Discovery: every page available, none attached.
    assert received["StudyMap"] is None and received["EditorialResponse"] is None
    discovery = [images for kind, _, _, images in backend.calls if kind == "DiscoveryResponse"]
    assert len(discovery) == 2 and all(len(i.files) == 10 and not i.attach for i in discovery)
    # Verification and the reader get the cited page and its quarters attached.
    assert received["VerificationResponse"].attach == tuple(page_images.page_files(run.page_images, sid, 2))
    assert received["CellReadingResponse"].attach[:5] == tuple(page_images.page_files(run.page_images, sid, 2))
    assert f"{sid}/p001.png" in received["CellReadingResponse"].attach  # neighbouring page for continuation
    # The reader sees the cell's location, never the claimed value or the claim.
    kind, instruction, evidence, _ = next(call for call in backend.calls if call[0] == "CellReadingResponse")
    assert instruction == BLIND_READING
    assert json.loads(evidence) == [{"request_id": "cell-0", "source_id": sid, "page": 2, "table": "Table 1",
                                     "row": ["Treatment"], "column": ["Mean"]}]
    assert "PAGE IMAGES" in next(i for k, i, _, _ in backend.calls if k == "DiscoveryResponse")
    report = (tmp_path / "run" / "review.md").read_text()
    assert "Read from the page image, not a text quotation" in report and "separate reading: **matched**" in report
    assert f"page-images/{run.page_images[0].config_hash}/{sid}/p002.png" in report
    assert "<a href='page-images/" in (tmp_path / "run" / "review.html").read_text()


def test_significance_marks_survive_html_rendering():
    from reviscope.render import _cell, _inline

    html = _inline("Read: " + _cell(reading(value="11", marks="***")) + " and **bold**")
    assert "<code>&#42;&#42;&#42;</code>" in html and "<strong>11</strong>" in html and "<strong>bold</strong>" in html


@pytest.mark.parametrize("backend,reason", [
    (TableBackend(claimed="3.281", printed="3.28"), "value claimed “3.281”, read “3.28”"),
    (TableBackend(discovery_reading=False), "no cell reading from the page images was recorded"),
    (TableBackend(discovery_reading=False, verifier_reading=True, claimed="2.50"), "value claimed “2.50”, read “1.25”"),
])
def test_unconfirmed_cells_hold_a_claim_whose_caption_quotation_anchors(tmp_path, backend, reason):
    run = _run(tmp_path, backend)
    finding = run.findings[0]
    assert finding.evidence and finding.evidence[0].quote == CAPTION  # the caption anchors
    assert finding.verifier_status == "supported" and finding.status == "unresolved"
    assert finding.editorial_disposition == "needs_review" and reason in finding.verification
    assert unconfirmed_concerns(run) == [finding]
    assert "**Held because:**" in (tmp_path / "run" / "review.md").read_text()


def test_missing_page_images_leave_table_claims_unresolved(tmp_path, monkeypatch):
    def broken(source, out):
        return page_images.PageImageSet(source_id=source.id, source_sha256=source.sha256, pages=0, config={}, config_hash="x",
                                        directory=str(out), error="page rendering failed: test")
    monkeypatch.setattr(page_images, "render_source", broken)
    backend = TableBackend()
    run = _run(tmp_path, backend)
    assert run.partial and any("page rendering failed" in item for item in run.coverage)
    assert run.findings[0].status == "unresolved"
    assert [c.outcome for c in run.findings[0].table_checks] == ["image_unavailable"]
    assert all(images is None for _, _, _, images in backend.calls)


def test_readings_with_different_units_are_checked_separately(tmp_path):
    class UnitsBackend(TableBackend):
        def generate(self, instruction, evidence, response_model, images=None):
            result = super().generate(instruction, evidence, response_model, images)
            if response_model.__name__ == "DiscoveryResponse":
                for finding in result.concerns:
                    for cell in finding.table_readings:
                        cell.unit = "ms"
            elif response_model.__name__ == "VerificationResponse":
                for decision in result.decisions:
                    for cell in decision.table_readings:
                        cell.unit = "s"
            elif response_model.__name__ == "CellReadingResponse":
                for cell in result.readings:
                    cell.unit = "ms"
            return result

    run = _run(tmp_path, UnitsBackend(verifier_reading=True))
    finding = run.findings[0]
    assert finding.status == "unresolved"
    assert [c.reading.unit for c in finding.table_checks] == ["ms", "s"]
    assert [c.outcome for c in finding.table_checks] == ["matched", "mismatched"]
    assert "unit claimed “s”, read “ms”" in finding.verification


def test_failed_reading_call_is_a_coverage_failure(tmp_path):
    class Failing(TableBackend):
        def generate(self, instruction, evidence, response_model, images=None):
            if response_model.__name__ == "CellReadingResponse":
                raise RuntimeError("no image access")
            return super().generate(instruction, evidence, response_model, images)

    run = _run(tmp_path, Failing())
    assert run.partial and run.findings[0].status == "unresolved"
    assert run.findings[0].table_checks[0].outcome == "not_read"
    assert any(s.name.endswith("-tables") and s.status == "failed" for s in run.stages)


def test_image_changes_invalidate_image_stages_only(tmp_path, monkeypatch):
    first = _run(tmp_path, TableBackend())
    cached = _run(tmp_path, TableBackend())
    assert all(s.status == "cached" for s in cached.stages if s.cache_key)
    monkeypatch.setattr(page_images, "QUARTER_DPI", 200)
    changed = _run(tmp_path, TableBackend())
    status = {s.name: s.status for s in changed.stages}
    assert status["study_map"] == "cached"
    assert status["review-consistency"] == status["verification-consistency-1"] == "completed"
    assert first.metadata.input_hash == changed.metadata.input_hash


def test_text_sources_get_no_images_and_drop_table_readings(tmp_path):
    class TextBackend(TableBackend):
        def generate(self, instruction, evidence, response_model):  # an offline backend without the images argument
            return super().generate(instruction, evidence.replace("CAPTION", CAPTION), response_model)

    paper = tmp_path / "paper.md"
    paper.write_text(f"{CAPTION}\nGroup | Mean\nTreatment | 1.25\n" + "Context. " * 200)
    backend = TextBackend()
    run = ReviewPipeline(backend, PROFILE, run_metacheck=False).run(paper, output_dir=tmp_path / "run")
    assert not run.page_images and not run.findings[0].table_readings and not run.findings[0].table_checks
    assert run.findings[0].status == "llm_supported"  # text tables are anchored as text, as before
    assert all(images is None for _, _, _, images in backend.calls)
    assert all("PAGE IMAGES" not in instruction for _, instruction, _, _ in backend.calls)


def test_staging_copies_read_only_files_inside_the_call_directory(tmp_path):
    rendered = tmp_path / "rendered.png"
    rendered.write_bytes(b"png")
    call = tmp_path / "call"
    call.mkdir()
    attached = _stage(call, StagedImages(files={"src/p001.png": rendered}, attach=("src/p001.png",)))
    assert attached == [call / "page-images/src/p001.png"]
    assert attached[0].read_bytes() == b"png" and not attached[0].is_symlink()
    assert not os.access(attached[0], os.W_OK)
    with pytest.raises(ValueError, match="leaves the image directory"):
        _stage(call, StagedImages(files={"../escape.png": rendered}))
    with pytest.raises(ValueError, match="not staged"):
        _stage(call, StagedImages(files={}, attach=("src/p002.png",)))


def test_backend_commands_and_attachments(tmp_path):
    claude = ClaudeBackend("claude-opus-5-5", effort="low")
    command = claude.command(tmp_path)
    assert command[command.index("--tools") + 1] == "Bash,WebSearch,WebFetch,Read"
    assert "Read" not in command[command.index("--allowedTools") + 1].split(",")  # restricted mode confines Read
    assert command[command.index("--input-format") + 1] == "stream-json" and "--restricted" in command
    assert "Read(~/**)" in json.loads(command[command.index("--settings") + 1])["permissions"]["deny"]
    image = tmp_path / "p001.png"
    image.write_bytes(b"\x89PNG")
    message = json.loads(claude._stdin("PROMPT", [image]))["message"]["content"]
    assert message[0] == {"type": "text", "text": "PROMPT"}
    assert message[1] == {"type": "text", "text": "Attached page image: p001.png"}
    assert base64.b64decode(message[2]["source"]["data"]) == b"\x89PNG"
    judge = ClaudeBackend("claude-opus-5-5", tools=False)
    assert judge.command(tmp_path)[judge.command(tmp_path).index("--tools") + 1] == "" and "--input-format" not in judge.command(tmp_path)
    assert judge._stdin("PROMPT", []) == "PROMPT"
    for tool_free in (judge, CodexBackend("gpt-6-luna", tools=False)):
        with pytest.raises(ValueError, match="tool-free"):
            tool_free._run("PROMPT", StudyMap, StagedImages(files={"p.png": image}))
    codex = CodexBackend("gpt-6-luna").command(tmp_path)
    CodexBackend("gpt-6-luna")._attach(codex, [image])
    assert codex[1:4] == ["exec", "--image", str(image)] and codex[-1] == "-"


def test_claude_file_views_are_recorded_relative_to_the_call(tmp_path):
    events = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/tmp/reviscope-x/page-images/s/p005.png"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r1", "content": [{"type": "image", "source": {"data": "AAAA"}}]}]}},
    ]
    [call], _ = parse_claude_events("\n".join(json.dumps(e) for e in events), datetime.now(timezone.utc))
    assert call.kind == "view" and call.output == "[image]" and not call.error
    from reviscope.backend import _relative

    assert _relative([call], Path("/tmp/reviscope-x"))[0].path == "page-images/s/p005.png"


@pytest.mark.parametrize("backend_type", [ClaudeBackend, CodexBackend])
def test_attached_pages_keep_their_source_labels_at_the_cli_boundary(tmp_path, monkeypatch, backend_type):
    from pydantic import BaseModel
    import reviscope.backend as backend_module

    class Answer(BaseModel):
        value: int

    image = tmp_path / "rendered.png"
    image.write_bytes(b"\x89PNG")
    names = ("source-a/p001.png", "source-b/p001.png")
    backend = backend_type(effort="low")
    monkeypatch.setattr(backend_module, "check_managed_policy", lambda _: None)
    monkeypatch.setattr(backend_module, "codex_executable", lambda: "/usr/bin/codex")

    def execute(command, prompt, cwd, env, timeout):
        if backend.name == "claude":
            blocks = json.loads(prompt)["message"]["content"]
            text = blocks[0]["text"]
            assert [b["text"] for b in blocks[1:] if b["type"] == "text"] == [
                f"Attached page image: page-images/{name}" for name in names]
            assert sum(b["type"] == "image" for b in blocks) == 2
        else:
            text = prompt
            attached = [command[i + 1] for i, arg in enumerate(command) if arg == "--image"]
            assert attached == [str(Path(cwd) / "page-images" / name) for name in names]
        assert "1. page-images/source-a/p001.png\n2. page-images/source-b/p001.png" in text
        (Path(cwd) / "last-message.json").write_text('{"value": 1}')
        return 0, "", ""

    monkeypatch.setattr(backend_module, "_execute", execute)
    assert backend.generate("Read the cells.", "", Answer,
                            images=StagedImages(files=dict.fromkeys(names, image), attach=names)).value == 1


def test_table_mismatch_example_needs_the_printed_page(tmp_path):
    """The example's table contradicts its text only as printed: the extracted text loses which
    mean belongs to which condition, so the finding requires the page image."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("build", Path(__file__).parents[1] / "examples/table_mismatch/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    from reviscope.ingest import ingest

    source = ingest(build.build(tmp_path / "example.pdf"))
    assert source.text == ingest(Path(__file__).parents[1] / "examples/table_mismatch/table_mismatch.pdf").text
    assert "higher life satisfaction than the control condition" in " ".join(source.text.split())
    table = source.pages[1].text
    assert "4.61" in table and "5.42" in table
    assert not re.search(r"Gratitude \(n = 60\)\s+4\.61|Control \(n = 60\)\s+5\.42", table)


def test_reviewers_verifier_and_reader_share_one_unit_definition():
    """Units are compared strictly, so every party must mean the same thing by one: a symbol
    printed with the cell or its headers, not a scale range or note (which readers otherwise disagree on)."""
    from reviscope.discovery import TABLE_READING_GUIDANCE
    from reviscope.pipeline import TABLE_VERIFICATION

    definition = "not a scale range, score description or table note; empty when none"
    for prompt in (TABLE_READING_GUIDANCE, TABLE_VERIFICATION, BLIND_READING):
        assert definition in " ".join(prompt.split())
