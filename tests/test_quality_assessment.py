"""Offline regressions for assessment bookkeeping; judges remain unvalidated."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "eval"))
spec = importlib.util.spec_from_file_location("quality_eval", ROOT / "eval/assess_criticisms.py")
quality = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quality
spec.loader.exec_module(quality)


def test_identical_nested_items_are_judged_once_without_merging_distinct_rationale():
    body = {"claim": "A concern", "rationale": "An inference", "remedy": None,
            "evidence": ["premise"], "external_evidence": []}
    rows = [{**body, "origin": {"arm": "holistic", "id": "broad:1"}},
            {**copy.deepcopy(body), "origin": {"arm": "audit", "id": "broad:1"}},
            {**body, "rationale": "A different inference", "origin": {"arm": "audit", "id": "audit:1"}}]
    original = copy.deepcopy(rows)
    unique = quality.deduplicate_items(rows)
    assert len(unique) == 2 and len(unique[0]["_origins"]) == 2
    assert unique[0]["evidence"] == ["premise"]
    assert rows == original  # extracting origins must not corrupt the native inputs


def test_quote_rederivation_retains_raw_labels_and_rejects_false_evidence():
    row = {"claim_status": "unresolved", "raw_claim_status": "supported",
           "supporting_evidence": ["p = .88"], "counterevidence": []}
    fixed = quality.checked_labels(row, "The statistic was p = .88. Next.")
    assert fixed["claim_status"] == "supported" and fixed["raw_claim_status"] == "supported"
    assert row["claim_status"] == "unresolved"
    for quote in ["p = .8", "p = .89", "missing evidence"]:
        bad = quality.checked_labels({**row, "supporting_evidence": [quote]}, "The statistic was p = .88.")
        assert bad["claim_status"] == "unresolved" and bad["raw_claim_status"] == "supported"
    defeated = quality.checked_labels({**row, "raw_claim_status": "contradicted",
                                       "supporting_evidence": [], "counterevidence": ["p = .88"]}, "p = .88.")
    assert defeated["claim_status"] == "contradicted"


def test_archive_preserves_exact_prior_condition(tmp_path):
    path = tmp_path / "case.json"
    raw = b'{"cache_key":"old","invalid":["malformed judgment"]}\n'
    path.write_bytes(raw)
    quality.archive(path)
    quality.archive(path)
    saved = list((tmp_path / "history").glob("*.json"))
    assert len(saved) == 1 and saved[0].read_bytes() == raw
    path.write_text(json.dumps({"cache_key": "new"}))
    assert saved[0].read_bytes() == raw


def test_repaired_quote_strips_stale_note_but_retains_original_limits():
    note = "Scientific scope uncertain. Deterministic check: missing relevant exact manuscript evidence."
    fixed = quality.checked_labels({"claim_status": "unresolved", "raw_claim_status": "supported",
                                    "supporting_evidence": ["p = .88"], "counterevidence": [], "limits": note}, "p = .88.")
    assert fixed["limits"] == "Scientific scope uncertain."
    assert fixed["original_limits"] == note


def test_packet_records_shared_new_unconfirmed_and_not_published_with_reasons(tmp_path, monkeypatch):
    from reviscope.schemas import Evidence, Finding, ReviewRun, RunMetadata, SourceDocument
    source = tmp_path / "manuscript.txt"
    source.write_text("p = .88. This is the submitted text.")
    entry = {"case": "case", "paper_id": "paper", "input": str(source),
             "manuscript_sha256": quality.sha(source), "profile": "quantitative_social_science"}
    monkeypatch.setattr(quality, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(quality, "LAUNCH", {"inputs": [entry]}, raising=False)
    monkeypatch.setattr(quality, "checked_audit", lambda *args: {})  # gate regressions live in test_audit_tool_use
    manuscript = SourceDocument(id="main", path=str(source), kind="manuscript", sha256=quality.sha(source), text=source.read_text(), pages=[])
    meta = RunMetadata(run_id="test", backend="fixture", profile=entry["profile"], profile_hash="x", input_hash="x", output_dir=str(tmp_path))
    def finding(id_, **kwargs):
        return Finding(id=id_, module="broad", claim=id_, rationale="A bounded reason", remedy="Clarify",
                       evidence=[Evidence(source_id="main", quote="p = .88", location="text")],
                       status="llm_supported", remedy_status="supported", **kwargs)
    shared, dropped = finding("broad:1"), finding("broad:2")
    uncertain = finding("audit:unresolved").model_copy(update={"status": "unresolved", "verifier_status": "unresolved"})
    merged = dropped.model_copy(update={"editorial_disposition": "merged", "editorial_reason": "same underlying issue", "merged_into": "evidence_audit:1"})
    holistic = ReviewRun(metadata=meta, sources=[manuscript], findings=[shared, dropped])
    audit = ReviewRun(metadata=meta, sources=[manuscript], findings=[shared, merged, finding("evidence_audit:1"), uncertain])
    for arm, run in [("holistic", holistic), ("audit", audit)]:
        path = tmp_path / "reviews" / arm / "case" / "review.json"
        path.parent.mkdir(parents=True)
        path.write_text(run.model_dump_json())
    packet, origins, _, _ = quality.packet("case")
    assert len(packet["criticisms"]) == 3 and sum(len(x) for x in origins.values()) == 4
    prov = json.loads((tmp_path / "criticism-packets-v2/case.origins.json").read_text())
    assert prov["unconfirmed_author_visible_excluded"]["audit"] == ["audit:unresolved"]
    assert prov["audit_inherited_ids"] == ["broad:1"] and prov["audit_new_ids"] == ["evidence_audit:1"]
    removed = prov["holistic_not_published_in_audit"]
    assert removed == [{"id": "broad:2", "present_in_audit": True, "audit_status": "llm_supported", "audit_disposition": "merged",
                        "audit_reason": "same underlying issue", "merge_target": "evidence_audit:1"}]
    before = (tmp_path / "criticism-packets-v2/case.json").read_bytes()
    (tmp_path / "reviews/audit/case/review.json").write_text(audit.model_copy(update={"partial": True}).model_dump_json())
    quality.packet("case")
    prov = json.loads((tmp_path / "criticism-packets-v2/case.origins.json").read_text())
    assert prov["holistic_not_published_in_audit"] is None and prov["audit_new_ids"] is None
    assert any(x["arm"] == "audit" and x["reason"] == "partial report" for x in prov["excluded"])
    assert before in [p.read_bytes() for p in (tmp_path / "criticism-packets-v2/history").glob("*.json")]


def test_comparison_reuses_identical_condition_and_archives_changed_or_invalid(tmp_path, monkeypatch):
    import compare_development_reviews as comparison
    calls = []
    class Backend:
        identity = "fixture:judge"
        version = "fixture-version"
        def __init__(self, *args, **kwargs):
            pass
    async def judge(cases, backend):
        calls.append(cases)
        return {"invalid": [], "aggregate": {"counts": {"tie": 1}}, "judgments": []}
    monkeypatch.setattr(comparison, "ClaudeBackend", Backend)
    monkeypatch.setattr(comparison, "run_comparisons", judge)
    job = {"paper_id": "p", "manuscript": "source", "left_text": "A", "right_text": "B",
           "case": "case", "left": "audit", "right": "plain", "audit_groups": {}, "source_hashes": {}}
    out = tmp_path / "comparisons-v4"
    comparison.compare(job, "claude-opus-5-5", out)
    target = out / "claude-opus-5-5/case/audit-vs-plain.json"
    original = target.read_bytes()
    comparison.compare(job, "claude-opus-5-5", out)
    assert len(calls) == 1
    changed_job = {**job, "right_text": "Different criticism"}
    changed = comparison.compare(changed_job, "claude-opus-5-5", out)
    assert len(calls) == 2 and changed["protocol"] == "development-criticism-comparison-v4"
    assert original in [p.read_bytes() for p in target.parent.joinpath("history").glob("*.json")]
    changed["invalid"] = ["invalid judgment"]
    target.write_text(json.dumps(changed))
    invalid = target.read_bytes()
    comparison.compare(changed_job, "claude-opus-5-5", out)
    assert len(calls) == 3
    assert invalid in [p.read_bytes() for p in target.parent.joinpath("history").glob("*.json")]


def test_matcher_rederivation_reuses_raw_judge_and_binds_packet(tmp_path, monkeypatch):
    monkeypatch.setattr(quality, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(quality, "LAUNCH", {"code": str(tmp_path / "original-generation-code")}, raising=False)
    calls = []
    class Backend:
        identity, version = "fixture:judge", "v1"
        def __init__(self, *args, **kwargs):
            pass
        def generate(self, *args):
            calls.append(args)
            return quality.QualityAssessment(assessments=[quality.CriticismAssessment(
                item_id="item-001", claim_status="supported", rationale_status="supported",
                remedy_status="not_separately_supplied", consequence="localized",
                supporting_evidence=["p = .88"], counterevidence=[], reasoning="Bounded inference", limits="Scope")],
                groups=[quality.CriticismGroup(member_ids=["item-001"], common_issue_and_consequence="One issue")],
                missed_material_questions=[], overall_qualified_assessment="Not expert validation")
    monkeypatch.setattr(quality, "ClaudeBackend", Backend)
    data = {"manuscript": "p = .88.", "criticisms": [{"item_id": "item-001", "claim": "A bounded concern"}]}
    origins = {"item-001": [{"arm": "holistic", "id": "broad:1"}, {"arm": "audit", "id": "broad:1"}]}
    path = tmp_path / "criticism-packets-v2/case.json"
    quality.save(path, data)
    snapshot = path.parent / "history" / ("case-" + quality.sha(path) + ".json")
    snapshot.parent.mkdir()
    snapshot.write_bytes(path.read_bytes())
    quality.save(path.with_suffix(".origins.json"), {"origins": origins})
    packet = (data, origins, {"holistic": "hash", "audit": "hash"}, [])
    quality.assess("case", "claude-opus-5-5", packet)
    target = tmp_path / "criticism-assessments-v2/claude-opus-5-5/case.json"
    first = json.loads(target.read_text())
    monkeypatch.setattr(quality, "method_hash", lambda: "repaired-bookkeeping-condition")
    quality.assess("case", "claude-opus-5-5", packet)
    second = json.loads(target.read_text())
    assert len(calls) == 1 and first["raw_judge_sha256"] == second["raw_judge_sha256"]
    assert first["cache_key"] == second["cache_key"] and second["method_sha256"] == "repaired-bookkeeping-condition"
    assert second["packet_sha256"] == quality.sha(snapshot) and second["origins"] == origins
    assert any(p.exists() for p in target.parent.joinpath("history").glob("*.json"))


def test_unresolved_raw_label_still_exposes_failed_quote_check():
    note = "Scope unknown. Deterministic check: missing relevant exact manuscript evidence."
    row = quality.checked_labels({"claim_status": "unresolved", "raw_claim_status": "unresolved",
                                  "supporting_evidence": ["invented text"], "counterevidence": [], "limits": note}, "Real text.")
    assert row["claim_status"] == "unresolved" and not row["quote_check_only_disagreement"]
    assert not row["quote_check_passed"] and row["limits"] == note
    assert row["unmatched_evidence"] == ["invented text"]


def test_repaired_matcher_guard_rejects_old_semantics_and_original_snapshot(monkeypatch):
    from types import SimpleNamespace
    import pytest
    import reviscope.verification as verification
    module_path = Path(verification.__file__).resolve()
    with pytest.raises(ValueError, match="original frozen"):
        quality.require_repaired_matcher({"code": str(module_path.parent.parent)})
    monkeypatch.setattr(quality, "verify_quote", lambda *args: SimpleNamespace(status="unanchored"))
    with pytest.raises(ValueError, match="repaired numeric quote matcher"):
        quality.require_repaired_matcher({"code": "/tmp/unrelated-code"})


def test_v4_comparison_refuses_legacy_prompt_before_model_call(tmp_path, monkeypatch):
    import pytest
    import compare_development_reviews as comparison
    class Backend:
        identity, version = "fixture", "v"
        def __init__(self, *args, **kwargs):
            pass
    monkeypatch.setattr(comparison, "ClaudeBackend", Backend)
    monkeypatch.setattr(comparison, "comparison_parts", lambda case: ("Legacy prompt", "Source"))
    job = {"paper_id": "p", "manuscript": "source", "left_text": "A", "right_text": "B",
           "case": "case", "left": "audit", "right": "plain", "audit_groups": {}, "source_hashes": {}}
    with pytest.raises(ValueError, match="visual/genre prompt"):
        comparison.compare(job, "claude-opus-5-5", tmp_path / "comparisons-v4")
    assert not list(tmp_path.rglob("*.json"))


def test_offline_rewrap_refuses_missing_raw_cache_without_call(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(quality, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(quality, "LAUNCH", {"code": str(tmp_path / "original-generation")}, raising=False)
    class Backend:
        identity, version = "fixture", "v"
        def __init__(self, *args, **kwargs):
            pass
        def generate(self, *args):
            raise AssertionError("Offline mode must never call a judge")
    monkeypatch.setattr(quality, "ClaudeBackend", Backend)
    data = {"manuscript": "p = .88.", "criticisms": [{"item_id": "item-001", "claim": "Concern"}]}
    quality.save(tmp_path / "criticism-packets-v2/case.json", data)
    origins = {"item-001": [{"arm": "plain", "id": "plain:0"}]}
    with pytest.raises(ValueError, match="Offline rederivation requires"):
        quality.assess("case", "claude-opus-5-5", (data, origins, {}, []), offline=True)
    assert not list(tmp_path.joinpath("criticism-judge-raw-v2").rglob("*.json"))
