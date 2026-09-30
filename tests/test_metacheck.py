import json

from docx import Document

from reviscope import metacheck
from reviscope.backend import Backend
from reviscope.cli import parser
from reviscope.evaluation import strip_review_metadata
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Profile, StudyMap

RUN_METACHECK = metacheck.run_metacheck  # conftest replaces the stage; these tests stub only its external calls


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


def module(name, status, light, rows, error=None, warnings=()):
    return {"module": name, "status": status, "traffic_light": light, "summary_text": f"{name} summary", "table": rows,
            "error": error, "warnings": list(warnings)}


OUTPUTS = [
    module("stat_check", "ok", "red", [{"candidate_id": "p:stat_check:t3", "text": "t(20) = 2.1, p = .20", "computed_p": 0.048,
                                        "error": True, "text_id": 3, "formatted": "dropped"},
                                       {"candidate_id": "p:stat_check:t4", "text": "F(0, 9) = 0", "computed_p": 0.0, "df1": 0, "error": False}]),
    module("repo_check", "ok", "yellow", [{"candidate_id": "p:repo_check:r1", "repo_url": "https://osf.io/abc", "repo_error": "HTTP 404"}],
           warnings=["Repository could not be checked: https://osf.io/abc - HTTP 404"]),
    module("causal_claims", "failed", None, [], "classifier unreachable"),
    module("ref_pubpeer", "ok", "info", [{"candidate_id": "p:ref_pubpeer:b1", "doi": "10.5555/cited", "total_comments": 2}]),
    module("open_practices", "ok", "green", []),
]


def fake_r(calls, outputs=OUTPUTS):
    def run_r(script, args):
        calls.append(script)
        run_dir = metacheck.Path(args[args.index("--run-dir") + 1])
        if script == "mc_import.R":
            (run_dir / "modules").mkdir(parents=True)
            (run_dir / "paper.rds").write_bytes(b"rds")
            (run_dir / "import_summary.json").write_text(json.dumps({"status": "ok", "counts": {"sections": 5, "refs": 25},
                                                                    "parse_warnings": ["Empty title"]}))
            return {"status": "ok"}, "Checking TUE grobid 0.8.2\n"
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


def stub(monkeypatch, calls, outputs=OUTPUTS):
    monkeypatch.setattr(metacheck, "run_metacheck", RUN_METACHECK)
    monkeypatch.setattr(metacheck, "run_r", fake_r(calls, outputs))
    monkeypatch.setattr(metacheck.shutil, "which", lambda _: "/usr/bin/tool")
    monkeypatch.setattr(metacheck, "package_version", lambda: "0.1.0")


def test_leads_are_routed_compacted_and_failures_marked(tmp_path, monkeypatch):
    calls = []
    stub(monkeypatch, calls)
    backend, paper = CaptureBackend(), manuscript(tmp_path)
    run = ReviewPipeline(backend, profile()).run(paper, output_dir=tmp_path / "run")
    stats = backend.evidence["statistical_inference"]
    assert "METACHECK SCREENING LEADS (UNVERIFIED)" in stats and "RUBRIC stat_check_triage.md (excerpt)" in stats
    assert '"candidate_id": "p:stat_check:t3", "module": "stat_check", "text": "t(20) = 2.1, p = .20", "computed_p": 0.048' in stats
    assert "formatted" not in stats and "## Procedure" not in stats
    assert '"computed_p": 0.0, "df1": 0, "error": false' in stats  # zeroes and false are data, not empty fields
    design = backend.evidence["design"]
    assert "repo_check: metacheck light yellow; 1 candidate row(s); partly could not check: Repository could not be checked" in design
    assert {m.module: m.status for m in run.metacheck.modules}["repo_check"] == "partial" and any(line.startswith("metacheck repo_check: Repository") for line in run.coverage)
    interpretation = backend.evidence["interpretation"]
    assert "causal_claims: could not check (failed: classifier unreachable)" in interpretation and "RUBRIC causal_claims.md" in interpretation
    assert "10.5555/cited" in backend.evidence["contribution"]
    assert "open_practices: metacheck light green" in design and "RUBRIC open_practices.md" not in design
    assert run.metacheck.converter == "online server TUE grobid 0.8.2 (manuscript uploaded)"
    assert run.metacheck.counts == {"sections": 5, "refs": 25}
    assert any("could not check: causal_claims" in line for line in run.coverage)
    report = (tmp_path / "run" / "review.md").read_text()
    assert "### Metacheck screening" in report and "`stat_check` — light red, 2 row(s)" in report
    assert "`causal_claims` — could not check" in report
    assert "Metacheck" not in strip_review_metadata(report)  # judges see findings only
    ReviewPipeline(CaptureBackend(), profile()).run(paper, output_dir=tmp_path / "run")
    assert calls.count("mc_import.R") == 1  # same input: import reused


def test_leads_are_capped_and_the_cap_is_reported(tmp_path, monkeypatch):
    rows = [{"candidate_id": f"p:all_p_values:t{i}", "text": "p = .04 " * 30} for i in range(200)]
    stub(monkeypatch, [], [module("all_p_values", "ok", "info", rows)])
    backend = CaptureBackend()
    run = ReviewPipeline(backend, profile()).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    leads = backend.evidence["statistical_inference"].split("METACHECK SCREENING LEADS", 1)[1]
    assert len(leads) <= metacheck.LEADS_LIMIT and "further all_p_values row(s) not shown" in leads
    assert any(line.startswith("metacheck leads for statistical_inference:") for line in run.coverage)


def test_text_manuscript_is_typeset_before_import(tmp_path, monkeypatch):
    calls = []
    stub(monkeypatch, calls)
    def typeset(source, directory):
        pdf = directory / "manuscript.pdf"
        pdf.write_bytes(b"%PDF")
        return pdf, "pandoc Markdown to PDF (tectonic), 3 section headings marked"
    monkeypatch.setattr(metacheck, "text_to_pdf", typeset)
    paper = tmp_path / "paper.txt"
    paper.write_text("Method\nWe did it.\n")
    record = RUN_METACHECK(paper, tmp_path / "run")
    assert record.status == "completed" and record.text_conversion.startswith("pandoc")
    assert record.converter.startswith("online server")


def test_no_metacheck_flag_skips_stage_and_says_so(tmp_path):
    assert parser().parse_args(["review", "paper.pdf", "--no-metacheck"]).no_metacheck
    backend = CaptureBackend()
    run = ReviewPipeline(backend, profile(), run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    assert run.metacheck.status == "skipped" and "metacheck: skipped by flag" in run.coverage
    assert "metacheck: skipped by flag" in (tmp_path / "run" / "review.md").read_text()
    assert "METACHECK" not in backend.evidence["statistical_inference"]
