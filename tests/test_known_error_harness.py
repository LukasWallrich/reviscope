import csv
import json
import runpy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from reviscope.schemas import ReviewRun, RunMetadata, ToolCall

EVAL = Path(__file__).parents[1] / "eval"


def test_partial_adjudication_requires_explicit_diagnostic_opt_in(tmp_path):
    load_inputs = runpy.run_path(str(EVAL / "adjudicate_known_errors.py"))["load_inputs"]
    run = ReviewRun(metadata=RunMetadata(run_id="test", backend="fixture", profile="test",
                                         profile_hash="x", input_hash="x", output_dir=str(tmp_path)),
                    sources=[], partial=True)
    review = tmp_path / "review.json"
    review.write_text(run.model_dump_json())
    labels = tmp_path / "annotations.csv"
    with pytest.raises(ValueError, match="partial"):
        load_inputs(review, labels, "7")  # rejects before opening held-out labels
    with labels.open("w") as handle:
        fields = ["paper", "category", "subcategory", "original_snippet", "modified_snippet", "description"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for _ in range(10):
            writer.writerow({key: "7" if key == "paper" else "test" for key in fields})
    _, partial, errors, _, _ = load_inputs(review, labels, "7", allow_partial=True)
    assert partial and len(errors) == 10


class SearchingBackend:
    name, model, effort, identity = "codex", "gpt-6-luna", "high", "codex:gpt-6-luna:high"

    def __init__(self, fail: bool = False):
        self.fail, self.calls = fail, []

    def generate(self, instruction, evidence, response_model):
        self.calls.append(ToolCall(backend="codex", sequence=0, kind="search", name="web_search",
                                   query="Seeing remembering illusions short-term memory", timestamp=datetime.now(timezone.utc)))
        if self.fail:
            raise TimeoutError("codex timed out")
        return response_model.model_validate({"issues": [{"category": "statistical_errors", "subcategory": "df",
                                                          "description": "d", "quote": "q", "location": "results", "severity": "major"}]})

    def take_tool_calls(self):
        calls, self.calls = self.calls, []
        return calls


def test_plain_review_records_tool_calls_that_the_audit_reads(tmp_path):
    """The plain baseline's output is identified by input hash and its title search is flagged."""
    plain = runpy.run_path(str(EVAL / "plain_review.py"))
    audit = runpy.run_path(str(EVAL / "audit_tool_use.py"))
    manifest = json.loads((EVAL / "corpus" / "known_errors.v1.json").read_text(encoding="utf-8"))
    assert [entry["paper"] for entry in manifest["entries"]] == [str(n) for n in range(1, 11)]
    assert all(entry["title"] and entry["doi"] and entry["original_urls"] and entry["answer_key_urls"] for entry in manifest["entries"])
    paper7 = next(entry for entry in manifest["entries"] if entry["paper"] == "7")
    papers = [{**paper, "sha256": {"placeholder"}} for paper in audit["load_papers"]([EVAL / "corpus" / "known_errors.v1.json"])]
    manuscript = tmp_path / "manuscript.txt"
    manuscript.write_text("Manuscript text.", encoding="utf-8")
    args = type("Args", (), {"paper": None, "title": None, "block": [], "planted_errors": False})()

    for fail, verdict in ((False, "flagged"), (True, "flagged")):
        payload = plain["review"](manuscript, SearchingBackend(fail))
        assert payload["partial"] is fail and payload["stages"][0]["name"] == "review-plain"
        path = tmp_path / "review.json"
        path.write_text(json.dumps(payload))
        papers[6]["sha256"] = {payload["sources"][0]["sha256"]}
        result = audit["audit_run"](path, papers, args)
        assert result["paper"] == "known-error-7" and result["verdict"] == verdict and result["tool_calls"] == 1
        assert ("stage failed" in result["reasons"][-1]) is fail
    assert papers[6]["titles"][0] == paper7["title"]


def test_plain_baseline_without_category_list_keeps_the_output_format():
    plain = runpy.run_path(str(EVAL / "plain_review.py"))
    full, nolist = plain["REVIEW_PROMPT"], plain["without_category_list"](plain["REVIEW_PROMPT"])
    assert "Look carefully for:" in full and "Look carefully for:" not in nolist
    assert "Construct validity issues" not in nolist and "Attrition and missing data issues" not in nolist
    assert nolist.startswith(full[:full.index("Look carefully for:")])
    assert nolist.endswith(full[full.index("For each issue, provide:"):]) and "- category: one of [" in nolist
    assert plain["PROMPT_LABELS"][nolist] != plain["PROMPT_LABELS"][full]
    driver = runpy.run_path(str(EVAL / "run_known_errors.py"))
    args = type("Args", (), {"mode": "plain-nolist", "code": EVAL.parent, "model": "gpt-6-luna", "effort": "high", "timeout": 60})()
    command = driver["review_command"](5, Path("in.txt"), Path("out"), args)
    assert command[1].endswith("plain_review.py") and command[-1] == "--no-category-list"
    args.mode = "plain"
    assert "--no-category-list" not in driver["review_command"](5, Path("in.txt"), Path("out"), args)


def test_trace_places_each_missed_error_at_the_stage_that_lost_it():
    where_lost = runpy.run_path(str(EVAL / "trace_known_errors.py"))["where_lost"]

    def judged(candidate, published="not_detected", ids=("a",)):
        return {"candidate": {"verdict": candidate, "matched_finding_ids": list(ids)}, "published": {"verdict": published}}

    findings = {"a": {"verifier_status": "contradicted", "status": "contradicted", "editorial_disposition": "rejected"},
                "b": {"verifier_status": "unresolved", "status": "unresolved", "editorial_disposition": "needs_review"},
                "c": {"verifier_status": "supported", "status": "llm_supported", "editorial_disposition": "merged"}}
    assert where_lost(judged("detected", "detected"), findings) == "published"
    assert where_lost(judged("not_detected", ids=()), findings) == "never raised"
    assert where_lost(judged("detected"), findings) == "contradicted by verification"
    assert where_lost(judged("detected", ids=("a", "b")), findings) == "unresolved by verification"
    assert where_lost(judged("uncertain", ids=("b", "c")), findings) == "uncertain match; set aside by editorial (merged)"
