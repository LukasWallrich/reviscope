import json

from docx import Document

from reviscope import metacheck
from reviscope.cli import parser
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Profile, StudyMap
from reviscope.backend import Backend

OWN_DOI = "10.1234/own.paper"


class CaptureBackend(Backend):
    name, model, effort = "capture", "m", "low"

    def __init__(self):
        self.evidence = {}

    def generate(self, instruction, evidence, response_model):
        kind = response_model.__name__
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="d", contribution_summary="c", strengths=[])
        if kind == "FindingsResponse":
            self.evidence[instruction.split()[1]] = evidence
            return response_model.model_validate({"findings": []})
        return response_model.model_validate({"decisions": [], "reconciled_overview": {"design_summary": "d", "contribution_summary": "c", "strengths": []}})


def fake_r(calls):
    def module(name, status, light, rows, error=None):
        return {"module": name, "status": status, "traffic_light": light, "summary_text": f"{name} summary",
                "table": rows, "error": error}
    outputs = [
        module("stat_check", "ok", "red", [{"candidate_id": "x", "raw": "t(20) = 2.1, p = .20", "computed_p": 0.048, "text_id": 3}]),
        module("causal_claims", "failed", None, [], "HuggingFace classifier unreachable"),
        module("ref_pubpeer", "ok", "info", [{"doi": "10.5555/cited", "total_comments": 2}, {"doi": OWN_DOI.upper(), "total_comments": 9}]),
        module("open_practices", "ok", "green", []),
    ]

    def run_r(script, args):
        calls.append(script)
        run_dir = metacheck.Path(args[args.index("--run-dir") + 1])
        if script == "mc_import.R":
            (run_dir / "modules").mkdir(parents=True)
            (run_dir / "paper.rds").write_bytes(b"rds")
            (run_dir / "import_summary.json").write_text(json.dumps({"status": "ok", "doi": OWN_DOI, "parse_warnings": ["No method section detected"]}))
            return {"status": "ok"}, "Checking grobid-online\n"
        for row in outputs:
            (run_dir / "modules" / f"{row['module']}.json").write_text(json.dumps(row))
        (run_dir / "run_status.json").write_text(json.dumps({"status": "ok", "modules": [
            {"module": r["module"], "status": r["status"], "error": r["error"]} for r in outputs]}))
        return {"status": "ok"}, ""
    return run_r


def manuscript(tmp_path):
    document = Document()
    for _ in range(40):
        document.add_paragraph("Participants completed the task and the effect was t(20) = 2.1, p = .20.")
    path = tmp_path / "paper.docx"
    document.save(path)
    return path


def profile():
    modules = ["contribution", "design", "statistical_inference", "interpretation"]
    return Profile(id="mc", title="mc", modules=modules, module_prompts={m: f"RUN {m} module" for m in modules})


def test_metacheck_leads_are_routed_failures_marked_and_own_doi_withheld(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(metacheck, "run_r", fake_r(calls))
    monkeypatch.setattr(metacheck.shutil, "which", lambda _: "/usr/bin/Rscript")
    backend, paper = CaptureBackend(), manuscript(tmp_path)
    run = ReviewPipeline(backend, profile()).run(paper, output_dir=tmp_path / "run")
    stats = backend.evidence["statistical_inference"]
    assert "METACHECK SCREENING LEADS (UNVERIFIED)" in stats and "t(20) = 2.1, p = .20" in stats
    assert "RUBRIC stat_check_triage.md" in stats
    assert "causal_claims: could not check (failed: HuggingFace classifier unreachable)" in backend.evidence["interpretation"]
    contribution = backend.evidence["contribution"]
    assert "10.5555/cited" in contribution and OWN_DOI.upper() not in contribution
    assert "open_practices: metacheck light green" in backend.evidence["design"]
    assert run.metacheck.converter == "online server grobid-online (manuscript uploaded)"
    assert any("could not check: causal_claims" in line for line in run.coverage)
    assert any("own DOI withheld" in line for line in run.coverage)
    report = (tmp_path / "run" / "review.md").read_text()
    assert "### Metacheck screening" in report and "`stat_check` — light red, 1 row(s)" in report
    assert "`causal_claims` — could not check" in report
    from reviscope.evaluation import strip_review_metadata
    assert "Metacheck" not in strip_review_metadata(report)  # judges see findings only
    ReviewPipeline(CaptureBackend(), profile()).run(paper, output_dir=tmp_path / "run")
    assert calls.count("mc_import.R") == 1  # same input: import reused, modules rerun (mc_run.R reuses ok outputs)


def test_no_metacheck_flag_skips_stage_and_says_so(tmp_path):
    assert parser().parse_args(["review", "paper.pdf", "--no-metacheck"]).no_metacheck
    backend = CaptureBackend()
    run = ReviewPipeline(backend, profile(), run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    assert run.metacheck.status == "skipped" and "metacheck: skipped by flag" in run.coverage
    assert "metacheck: skipped by flag" in (tmp_path / "run" / "review.md").read_text()
    assert "METACHECK" not in backend.evidence["statistical_inference"]


def test_text_input_is_not_checked(tmp_path):
    record = metacheck.run_metacheck(tmp_path / "paper.txt", tmp_path)
    assert record.status == "not_checked" and record.reason == "unsupported input type (.txt)"
