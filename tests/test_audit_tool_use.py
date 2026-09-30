import json
import runpy
from pathlib import Path

AUDIT = runpy.run_path(str(Path(__file__).parents[1] / "eval/audit_tool_use.py"))
PAPERS = AUDIT["load_papers"]([Path(__file__).parent / "fixtures/audit_papers.json"])


def run_file(tmp_path, calls, sha="aaa"):
    path = tmp_path / "review.json"
    stage = {"name": "review-contribution", "status": "completed", "tool_calls": calls}
    path.write_text(json.dumps({"sources": [{"sha256": sha}], "stages": [stage]}))
    return path


def call(sequence, kind, **fields):
    return {"stage": "review-contribution", "sequence": sequence, "kind": kind, "output": "", **fields}


def audit(path):
    args = type("Args", (), {"paper": None, "title": None, "block": [], "planted_errors": False})()
    return AUDIT["audit_run"](path, PAPERS, args)


def test_audit_flags_review_pages_and_review_searches_for_the_identified_paper(tmp_path):
    result = audit(run_file(tmp_path, [
        call(0, "fetch", url="https://peerj.com/articles/236v0.1/reviews/2/"),
        call(1, "search", query="Being there brief visit neighbourhood social attitudes reviewer comments"),
        call(2, "fetch", url="https://pubpeer.com/publications/ABC"),
        call(3, "search", query="neighbourhood deprivation trust", output='[{"url": "https://peerj.com/articles/236/"}]'),
    ]))
    assert result["paper"] == "open-review-paper" and result["verdict"] == "flagged"
    assert [r.split(":", 1)[0] for r in result["reasons"]] == ["review-contribution#0", "review-contribution#1", "review-contribution#2", "review-contribution#3"]


def test_audit_passes_ordinary_literature_checks(tmp_path):
    result = audit(run_file(tmp_path, [
        call(0, "search", query="Cohen 1992 power primer"),
        call(1, "fetch", url="https://api.crossref.org/works/10.1037/0033-2909.112.1.155"),
        call(2, "exec", command="python3 -c 'print(1)'"),
    ]))
    assert result["verdict"] == "clean" and result["tool_calls"] == 3


def test_audit_flags_title_search_alone_for_planted_error_papers(tmp_path):
    result = audit(run_file(tmp_path, [call(0, "search", query="illusions in short-term memory mirrored letter")], sha="bbb"))
    assert result["paper"] == "known-error-7" and "planted-error" in result["reasons"][0]
