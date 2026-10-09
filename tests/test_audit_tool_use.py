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


def audit(path, title=None):
    args = type("Args", (), {"paper": None, "title": title, "block": [], "planted_errors": bool(title)})()
    return AUDIT["audit_run"](path, PAPERS, args)


def test_audit_flags_review_pages_and_review_searches_for_the_identified_paper(tmp_path):
    result = audit(run_file(tmp_path, [
        call(0, "fetch", url="https://peerj.com/articles/236v0.1/reviews/2/"),
        call(1, "search", query="Being there brief visit neighbourhood social attitudes reviewer comments"),
        call(2, "fetch", url="https://pubpeer.com/publications/ABC"),
        call(3, "search", query="neighbourhood deprivation trust", output='[{"url": "https://peerj.com/articles/236/"}]'),
    ]))
    assert result["paper"] == "open-review-paper" and result["verdict"] == "flagged"
    # #3 only lists the paper among search results; listing alone is not flagged.
    assert [r.split(":", 1)[0] for r in result["reasons"]] == ["review-contribution#0", "review-contribution#1", "review-contribution#2"]


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


def test_audit_warns_but_does_not_flag_a_cited_paper_search_sharing_title_words(tmp_path):
    query = "Lewczuk 2020 moral disapproval addiction general behaviors interaction frequency moral incongruence"
    title = "Moral Incongruence and Addiction: A Registered Report"
    result = audit(run_file(tmp_path, [call(0, "search", query=query)]), title=title)
    assert result["verdict"] == "clean" and "title words" in result["warnings"][0]
    flagged = audit(run_file(tmp_path, [call(0, "search", query="moral incongruence and addiction registered report")]), title=title)
    assert flagged["verdict"] == "flagged"
    excluded = audit(run_file(tmp_path, [call(0, "search", query='"PPMI" "unique to" -"Moral Incongruence and Addiction" -registered'),
                                         call(1, "fetch", output="[]")]), title=title)
    assert excluded["verdict"] == "clean" and not excluded["warnings"]


def test_audit_ignores_listed_results_and_reports_incomplete_provenance(tmp_path):
    listed = audit(run_file(tmp_path, [call(0, "search", query="effect size norms", result_urls=["https://pubpeer.com/publications/X"])]))
    assert listed["verdict"] == "clean"
    opened = audit(run_file(tmp_path, [call(0, "fetch", url="https://pubpeer.com/publications/X")]))
    assert opened["verdict"] == "flagged" and "review/commentary site" in opened["reasons"][0]
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"sources": [{"sha256": "aaa"}], "stages": [
        {"name": "review-design", "status": "failed", "error": "TimeoutError: codex timed out", "tool_calls": []},
        {"name": "verification-design-1", "status": "completed", "cache_key": "k"}]}))
    result = audit(path)
    assert result["verdict"] == "incomplete" and len(result["reasons"]) == 2


def test_audit_checks_pages_opened_by_reference_and_unresolved_fetches(tmp_path):
    from datetime import datetime, timezone
    from reviscope.backend import parse_codex_events

    events = [{"type": "item.completed", "item": {"id": "1", "type": "web_search", "action": {"type": "open_page"},
                                                  "results": [{"url": "https://pubpeer.com/publications/ABC"}]}},
              {"type": "item.completed", "item": {"id": "2", "type": "web_search", "action": {"type": "open_page"}, "results": "page text"}}]
    parsed, _ = parse_codex_events("\n".join(json.dumps(e) for e in events), datetime.now(timezone.utc))
    calls = [{**c.model_dump(mode="json"), "stage": "review-contribution"} for c in parsed]
    result = audit(run_file(tmp_path, calls))
    assert result["verdict"] == "flagged"
    assert result["reasons"] == ["review-contribution#0: fetched review/commentary site: https://pubpeer.com/publications/ABC",
                                 "review-contribution#1: fetch without a recorded page URL"]



def test_criticism_judge_results_are_audited_through_their_grouped_stages(tmp_path):
    import runpy
    from pathlib import Path as _Path
    audit = runpy.run_path(str(_Path(__file__).parents[1] / "eval" / "audit_tool_use.py"))
    result = {"sources": [{"sha256": "abc"}], "stages": {"judge codex": [{"name": "judge", "status": "completed", "cache_key": "k",
              "tool_calls": [{"kind": "search", "query": "the paper title openreview reviews", "sequence": 0}]}]}}
    (tmp_path / "result.json").write_text(json.dumps(result))
    args = type("Args", (), {"paper": None, "title": "the paper title", "block": [], "planted_errors": False})()
    verdict = audit["audit_run"](tmp_path, [], args)
    assert verdict["tool_calls"] == 1 and verdict["run"].endswith("result.json")
    assert verdict["verdict"] == "flagged" and "search for reviews of this paper" in verdict["reasons"][0]
