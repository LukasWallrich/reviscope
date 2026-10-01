import json

from docx import Document

from reviscope import metacheck
from reviscope.backend import Backend
from reviscope.cli import parser
from reviscope.evaluation import strip_review_metadata
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Profile, StudyMap
from stubs import discovery_payload

RUN_METACHECK = metacheck.run_metacheck  # conftest replaces the stage; these tests stub only its external calls


class CaptureBackend(Backend):
    name, model, effort = "capture", "m", "low"

    def __init__(self):
        self.evidence = {}

    def generate(self, instruction, evidence, response_model):
        kind = response_model.__name__
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="d", contribution_summary="c", strengths=[])
        if kind == "DiscoveryResponse":
            self.evidence[instruction.split()[1]] = evidence
            return response_model.model_validate(discovery_payload(instruction, []))
        return response_model.model_validate({"decisions": [], "reconciled_overview": {"design_summary": "d", "contribution_summary": "c", "strengths": []}})


def module(name, status, light, rows, error=None, warnings=()):
    return {"module": name, "status": status, "traffic_light": light, "summary_text": f"{name} summary", "table": rows,
            "error": error, "warnings": list(warnings)}


OUTPUTS = [
    module("stat_check", "ok", "red", [{"candidate_id": "p:stat_check:t3", "text": "t(20) = 2.1, p = .20", "computed_p": 0.048,
                                        "error": True, "text_id": 3, "formatted": "dropped"},
                                       {"candidate_id": "p:stat_check:t4", "text": "F(0, 9) = 0", "computed_p": 0.0, "df1": 0, "error": True,
                                        "decision_error": False},
                                       {"candidate_id": "p:stat_check:t5", "text": "t(30) = 2.5, p = .018", "error": False}]),
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
    assert '"computed_p": 0.0, "df1": 0, "error": true, "decision_error": false' in stats  # zeroes and false are data, not empty fields
    assert "p:stat_check:t5" not in stats and "1 further row(s) not listed: recomputed p-value consistent" in stats
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
    assert "### Metacheck screening" in report and "`stat_check` — light red, 3 row(s) (1 filtered as not a candidate: recomputed" in report
    assert any(line.startswith("metacheck stat_check: 1 of 3 row(s) filtered as not a candidate") for line in run.coverage)
    assert "`causal_claims` — could not check" in report
    assert "Metacheck" not in strip_review_metadata(report)  # judges see findings only
    ReviewPipeline(CaptureBackend(), profile()).run(paper, output_dir=tmp_path / "run")
    assert calls.count("mc_import.R") == 1  # same input: import reused


def test_every_candidate_row_is_passed_on_whole(tmp_path, monkeypatch):
    rows = [{"candidate_id": f"p:power:r{i}", "text": f"paragraph {i} " + "power analysis " * 500} for i in range(200)]
    stub(monkeypatch, [], [module("power", "ok", "yellow", rows)])
    backend = CaptureBackend()
    ReviewPipeline(backend, profile()).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    stats = backend.evidence["statistical_inference"]
    assert all(f'"candidate_id": "p:power:r{i}", "module": "power", "text": {json.dumps(row["text"])}' in stats
               for i, row in enumerate(rows))


FILTER_CASES = {  # module: (row, passed on as a lead)
    "stat_check": [({"error": False}, False), ({"error": True}, True), ({"error": None}, True)],
    "stat_p_exact": [({"imprecise": False, "zero": False}, False), ({"imprecise": True, "zero": False}, True),
                     ({"imprecise": False, "zero": True}, True), ({"imprecise": None, "zero": False}, True)],
    "stat_effect_size": [({"test": "t-test", "es": "d = 0.5", "d_coherence": "match_under_assumptions"}, False),
                         ({"test": "F-test", "es": "eta = .1; eta = .2", "eta_coherence": "match_under_assumptions; no_match"}, True),
                         ({"test": "t-test", "es": "d = 0.5", "d_coherence": "indeterminate"}, True),
                         ({"test": "t-test", "d_coherence": "match_under_assumptions"}, True)],  # no effect size reported
    "ref_accuracy": [({"no_match": False, "doi_mismatch": False, "year_mismatch": None}, False),
                     ({"no_match": False, "year_mismatch": True}, True), ({"no_match": True}, True), ({"doi_mismatch": False}, True)],
    "ref_summary": [({"retractionwatch": "Retraction"}, False)],
    "code_check": [({"checked": True, "parse_error": False, "code_abs_path": 0, "loaded_files_missing": 0,
                     "percentage_comment": 0.2, "library_max_between": None}, False),
                   ({"checked": True, "parse_error": False, "code_abs_path": 0, "loaded_files_missing": 1,
                     "percentage_comment": 0.2, "library_max_between": None}, True),
                   ({"checked": False, "file_name": "late.R"}, True)],  # beyond the file limit: not checked
    "ref_retraction": [({"retractionwatch": "Retraction"}, True)],
}


def test_rows_are_filtered_only_when_the_module_marks_them_fine(tmp_path):
    from reviscope.schemas import MetacheckModule, MetacheckRecord

    (tmp_path / "modules").mkdir()
    modules = []
    for name, cases in FILTER_CASES.items():
        rows = [{"candidate_id": f"p:{name}:r{i}", **row} for i, (row, _) in enumerate(cases)]
        (tmp_path / "modules" / f"{name}.json").write_text(json.dumps(module(name, "ok", "yellow", rows)))
        modules.append(MetacheckModule(module=name, status="ok", traffic_light="yellow", n_rows=len(rows)))
    counted = {m.module: m for m in metacheck._count_filtered(tmp_path, modules)}
    record = MetacheckRecord(status="completed", output_dir=str(tmp_path), modules=list(counted.values()))
    text = metacheck.leads(record, ["contribution", "design", "statistical_inference"])
    text = "\n".join(text.values())
    for name, cases in FILTER_CASES.items():
        dropped = sum(not kept for _, kept in cases)
        assert counted[name].n_filtered == dropped and (counted[name].filter_rule is not None) == bool(dropped)
        for i, (_, kept) in enumerate(cases):
            assert (f'"candidate_id": "p:{name}:r{i}"' in text) == kept, (name, i)
    assert "## ref_accuracy: metacheck light yellow; 3 candidate row(s); 1 further row(s) not listed: CrossRef match found" in text


def test_p_value_inventory_is_kept_unless_the_flagging_modules_ran(tmp_path):
    from reviscope.schemas import MetacheckModule

    (tmp_path / "modules").mkdir()
    p_row = {"item_id": "t3", "text": "p = .03", "p_value": 0.03}
    for name in ("all_p_values", "stat_p_exact", "stat_p_nonsig"):
        (tmp_path / "modules" / f"{name}.json").write_text(json.dumps(module(name, "ok", "info", [{"candidate_id": f"p:{name}:t3", **p_row}])))
    ran = [MetacheckModule(module=name, status="ok") for name in ("all_p_values", "stat_p_exact", "stat_p_nonsig")]
    assert metacheck.candidate_rows(tmp_path, ran)["all_p_values"][1] == 1
    failed = [ran[0], ran[1], MetacheckModule(module="stat_p_nonsig", status="failed")]
    assert metacheck.candidate_rows(tmp_path, failed)["all_p_values"][1:] == (0, None)


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
    assert record.status == "partial" and record.text_conversion.startswith("pandoc")  # causal_claims failed
    assert record.converter.startswith("online server") and record.lookup_date
    key = metacheck.reuse_key(paper)
    assert {"conversion", "pandoc", "tectonic"} <= set(key) and "conversion" not in metacheck.reuse_key(manuscript(tmp_path))


def test_unreadable_screening_output_is_recorded_not_raised(tmp_path, monkeypatch):
    stub(monkeypatch, [])
    record = RUN_METACHECK(manuscript(tmp_path), tmp_path / "direct")
    assert record.status == "partial" and "could not check: causal_claims" in metacheck.describe(record)
    mc_dir = tmp_path / "direct" / "metacheck"
    (mc_dir / "modules" / "stat_check.json").write_text("{not json")
    (mc_dir / "modules" / "repo_check.json").write_text("[]")
    broken = [metacheck._module(mc_dir, {"module": name, "status": "ok"}) for name in ("stat_check", "repo_check", "ref_pubpeer")]
    assert [m.status for m in broken] == ["failed", "failed", "ok"] and "module output unreadable" in broken[0].error
    (mc_dir / "modules" / "power.json").mkdir()  # reading it raises IsADirectoryError
    assert metacheck.fingerprint(record) != metacheck.fingerprint(record.model_copy(update={"output_dir": None}))

    def unreadable(*_):
        raise PermissionError("modules/power.json")
    monkeypatch.setattr(metacheck, "leads", unreadable)
    run = ReviewPipeline(CaptureBackend(), profile()).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    assert run.metacheck.status == "failed" and "screening output unreadable: PermissionError" in run.metacheck.reason
    assert run.metacheck.modules and run.partial and (tmp_path / "run" / "review.md").is_file()


def test_no_metacheck_flag_skips_stage_and_says_so(tmp_path):
    assert parser().parse_args(["review", "paper.pdf", "--no-metacheck"]).no_metacheck
    backend = CaptureBackend()
    run = ReviewPipeline(backend, profile(), run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "run")
    assert run.metacheck.status == "skipped" and "metacheck: skipped by flag" in run.coverage
    assert "metacheck: skipped by flag" in (tmp_path / "run" / "review.md").read_text()
    assert "METACHECK" not in backend.evidence["statistical_inference"]


def test_fingerprint_depends_on_module_content_not_run_location(tmp_path):
    from reviscope.schemas import MetacheckRecord

    for name in ("a", "b"):
        (tmp_path / name / "modules").mkdir(parents=True)
        (tmp_path / name / "modules" / "stat_check.json").write_text('{"rows": 1}')
    first, moved = (MetacheckRecord(status="completed", output_dir=str(tmp_path / name)) for name in ("a", "b"))
    assert metacheck.fingerprint(first) == metacheck.fingerprint(moved)
    (tmp_path / "b" / "modules" / "stat_check.json").write_text('{"rows": 2}')
    assert metacheck.fingerprint(first) != metacheck.fingerprint(moved)


def test_finished_screening_is_reused_and_timestamps_do_not_change_the_fingerprint(tmp_path, monkeypatch):
    calls = []
    stub(monkeypatch, calls)
    paper = manuscript(tmp_path)
    first = metacheck.run_metacheck(paper, tmp_path / "run")
    assert calls.count("mc_run.R") == 2
    second = metacheck.run_metacheck(paper, tmp_path / "run")
    assert calls.count("mc_run.R") == 2 and calls.count("mc_import.R") == 1
    restamped = second.model_copy(update={"lookup_date": "2030-01-01", "output_dir": second.output_dir,
                                          "modules": [m.model_copy(update={"run_at": "2030-01-01T00:00:00Z"}) for m in second.modules]})
    assert metacheck.fingerprint(first) == metacheck.fingerprint(second) == metacheck.fingerprint(restamped)
