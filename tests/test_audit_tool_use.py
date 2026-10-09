import json
import runpy
from pathlib import Path

AUDIT = runpy.run_path(str(Path(__file__).parents[1] / "eval/audit_tool_use.py"))
PAPERS = AUDIT["load_papers"]([Path(__file__).parent / "fixtures/audit_papers.json"])


def run_file(tmp_path, calls, sha="aaa"):
    path = tmp_path / "review.json"
    stage = {"name": "review-contribution", "status": "completed", "tool_calls": calls}
    path.write_text(json.dumps({"sources": [{"sha256": sha, "kind": "manuscript"}], "stages": [stage]}))
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


def test_curated_training_papers_are_identified_and_all_review_routes_flagged(tmp_path):
    papers = AUDIT["load_papers"](AUDIT["DEFAULT_MANIFESTS"])
    manifest = json.loads((Path(__file__).parents[1] / "eval/corpus/open_peer_review_curated.v1.json").read_text())
    assert manifest["dataset_role"] == "training_development"
    for entry in manifest["entries"]:
        args = type("Args", (), {"paper": None, "title": None, "block": [], "planted_errors": False})()
        urls = [entry["editorial_archive"], *entry["other_version_urls"],
                *(r["url"] for r in entry["human_reviews"])]
        for url in urls:
            path = run_file(tmp_path, [call(0, "fetch", url=url)], sha=entry["manuscript_text_sha256"])
            result = AUDIT["audit_run"](path, papers, args)
            assert result["paper"] == entry["id"] and result["verdict"] == "flagged"
        listed = run_file(tmp_path, [call(0, "search", query="ordinary literature query", result_urls=urls)],
                          sha=entry["manuscript_text_sha256"])
        result = AUDIT["audit_run"](listed, papers, args)
        assert result["verdict"] == "clean" and len(result["warnings"]) == len(set(urls))
        assert result["review_sha256"] and result["audit_rules_sha256"]


def test_comparison_rejects_unidentified_stale_or_unclean_audits(tmp_path, monkeypatch):
    import hashlib
    import pytest
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "eval"))
    compare = runpy.run_path(str(Path(__file__).parents[1] / "eval/compare_development_reviews.py"))
    review = run_file(tmp_path, [])
    data = json.loads(review.read_text())
    data["metadata"] = {"profile": "education"}
    review.write_text(json.dumps(data))
    row = {"paper": "paper-id", "run": str(review), "verdict": "clean",
           "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
           "audit_rules_sha256": compare["audit_rules_hash"](compare["load_papers"](compare["DEFAULT_MANIFESTS"]))}
    target = tmp_path / "tool-audit.json"
    target.write_text(json.dumps([row]))
    assert compare["checked_audit"](review, "paper-id", "aaa", "education")["verdict"] == "clean"
    for patch in ({"paper": None}, {"paper": "other-paper"}, {"review_sha256": "old"},
                  {"run": str(tmp_path / "other.json")}, {"audit_rules_sha256": "old"},
                  {"verdict": "flagged"}, {"verdict": "incomplete"}):
        target.write_text(json.dumps([{**row, **patch}]))
        with pytest.raises(ValueError):
            compare["checked_audit"](review, "paper-id", "aaa", "education")

    target.write_text(json.dumps([row]))
    with pytest.raises(ValueError, match="input differs"):
        compare["checked_audit"](review, "paper-id", "other-input", "education")


def test_osf_aliases_and_lnu_mirrors_do_not_escape_curated_identity(tmp_path):
    papers = AUDIT["load_papers"](AUDIT["DEFAULT_MANIFESTS"])
    entry = next(p for p in papers if p["id"] == "metapsych-bonetto-2764-round1")
    args = type("Args", (), {"paper": None, "title": None, "block": [], "planted_errors": False})()
    for url in ("https://osf.io/unjf5/", "https://osf.io/unjf5/download", "https://osf.io/download/unjf5",
                "https://files.osf.io/v1/resources/vxqj5/providers/osfstorage/placeholder",
                "https://files.osf.io/v1/resources/other/providers/osfstorage/" + next(g for g in entry["osf_guids"] if len(g) == 24),
                "https://conferences.lnu.se/index.php/metapsychology/article/download/2764/3250",
                "https://mfr.osf.io/render?url=https%3A%2F%2Fosf.io%2Funjf5%2Fdownload"):
        path = run_file(tmp_path, [call(0, "fetch", url=url)], sha=next(iter(entry["sha256"])))
        assert AUDIT["audit_run"](path, papers, args)["verdict"] == "flagged"
    # A different OSF study and a hostname merely containing 'osf.io' remain legitimate sources.
    for url in ("https://osf.io/abcde/", "https://not-osf.io/unjf5/"):
        path = run_file(tmp_path, [call(0, "fetch", url=url)], sha=next(iter(entry["sha256"])))
        assert AUDIT["audit_run"](path, papers, args)["verdict"] == "clean"


def test_audit_rule_identity_includes_manual_overrides_and_review_domains(monkeypatch):
    baseline = AUDIT["audit_rules_hash"](PAPERS)
    assert baseline != AUDIT["audit_rules_hash"](PAPERS, {"title": "Different title"})
    globals_ = AUDIT["audit_rules_hash"].__globals__
    monkeypatch.setitem(globals_, "REVIEW_DOMAINS", (*globals_["REVIEW_DOMAINS"], "additional-review.org"))
    assert baseline != AUDIT["audit_rules_hash"](PAPERS)


def test_comparison_requires_the_curated_profile(tmp_path, monkeypatch):
    import pytest
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "eval"))
    compare = runpy.run_path(str(Path(__file__).parents[1] / "eval/compare_development_reviews.py"))
    review = run_file(tmp_path, [])
    data = json.loads(review.read_text());data["metadata"] = {"profile": "social_psychology"}
    review.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="curated case profile"):
        compare["checked_audit"](review, "paper-id", "aaa", "education")
