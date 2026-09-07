import asyncio
import json

from coarse_socpsy.evaluation import (
    aggregate_pairwise,
    audit_summary,
    build_pairwise_cases,
    import_dawes_errors,
    judge_case,
    load_corpus,
    planted_error_recall,
    sample_finding_audit,
    verify_finding,
    read_review,
)


def test_manifest_is_frozen_and_ineligible_versions_are_excluded():
    path = "eval/corpus/open_peer_review.v1.json"
    assert len(load_corpus(path, eligible_only=False)) == 5
    assert [x["id"] for x in load_corpus(path)] == [
        "metapsych-bartos-schimmack-2022-round1",
        "metapsych-brunner-schimmack-2020-round1-williams",
    ]


def test_blinding_is_order_swapped_and_aggregation_is_by_paper():
    paper = {"paper_id": "p1", "manuscript": "source", "candidate_review": "new", "reference_review": "human"}
    cases = build_pairwise_cases([paper], seed=4)
    assert len(cases) == 2
    assert cases[0].hidden_labels["A"] != cases[1].hidden_labels["A"]

    async def judge(prompt):
        # Pick the review whose literal content is 'new', irrespective of position.
        return {"winner": "A" if "REVIEW A\nnew" in prompt else "B", "confidence": .8, "rationale": "grounded"}

    rows = asyncio.run(_judge_all(cases, judge))
    summary = aggregate_pairwise(rows)
    assert summary["paper_count"] == 1
    assert summary["counts"]["candidate"] == 1
    assert summary["candidate_preference_wilson_95"][0] < 1


async def _judge_all(cases, backend):
    return [await judge_case(case, backend) for case in cases]


def test_audit_strata_are_disjoint_and_reported_separately():
    findings = [
        {"finding_id": "a", "severity": "minor"},
        {"finding_id": "b", "severity": "critical", "verifier_disagreement": True},
        {"finding_id": "c", "severity": "major", "verification_status": "unresolved"},
    ]
    samples = sample_finding_audit(findings, random_n=1, targeted_n=2, seed=9)
    assert {x["finding_id"] for x in samples["random"]}.isdisjoint(x["finding_id"] for x in samples["targeted"])
    assert all(row["stratum"] == name for name, rows in samples.items() for row in rows)
    result = audit_summary([
        {"stratum": "random", "verdict": "supported"},
        {"stratum": "targeted", "verdict": "contradicted"},
    ])
    assert result["random"]["supported_rate_among_resolved"] == 1
    assert result["targeted"]["supported_rate_among_resolved"] == 0


def test_dawes_import_and_recall(tmp_path):
    source = tmp_path / "errors.json"
    source.write_text(json.dumps({"errors": [{"id": 1}, {"error_id": "e2"}]}))
    errors = import_dawes_errors(source)
    assert [x["error_id"] for x in errors] == ["1", "e2"]
    score = planted_error_recall([{"matched_error_ids": ["e2", "unknown"]}], ["1", "e2"])
    assert score["recall"] == .5

    csv_source = tmp_path / "error_insertions.csv"
    csv_source.write_text("paper,category,subcategory,modified_snippet,description\n1,stats,p_value,bad,error\n1,design,sampling,bad2,error2\n")
    assert [x["error_id"] for x in import_dawes_errors(csv_source)] == ["1-01", "1-02"]


def test_core_backend_protocol_and_failure_capture():
    class Output:
        def model_dump(self):
            return {"winner": "A", "confidence": .5, "rationale": "source", "criteria": []}

    class Backend:
        def generate(self, instruction, evidence, response_model):
            assert response_model.__name__ == "JudgeOutput"
            assert "Do not reward length" in instruction
            assert "Do not reward length" not in evidence
            return Output()

    paper = {"paper_id": "p", "manuscript": "m", "candidate_review": "Backend: codex\nreview", "reference_review": "h"}
    cases = build_pairwise_cases([paper], order_swap=False)
    assert not cases[0].review_a.startswith("Backend:") and not cases[0].review_b.startswith("Backend:")
    from coarse_socpsy.evaluation import run_comparisons
    result = asyncio.run(run_comparisons(cases, Backend()))
    assert len(result["judgments"]) == 1
    assert result["invalid"] == []

    from coarse_socpsy.evaluation import JudgeOutput
    schema = JudgeOutput.model_json_schema()
    assert schema["properties"]["criteria"]["type"] == "array"


def test_source_grounded_verification_with_core_backend():
    class Output:
        def model_dump(self):
            return {"verdict": "unresolved", "confidence": .7, "supporting_evidence": [],
                    "counterevidence": ["limitations acknowledged"], "reasoning": "both sides checked"}
    class Backend:
        def generate(self, instruction, evidence, response_model):
            assert "defeats" in instruction and "MANUSCRIPT" in evidence
            return Output()
    row = asyncio.run(verify_finding("limitations acknowledged", {"finding_id": "f1", "claim": "omitted"}, Backend()))
    assert row["verdict"] == "unresolved"


def test_verification_repairs_when_any_evidence_quote_is_unmatched():
    calls = 0
    class Output:
        def __init__(self, value): self.value = value
        def model_dump(self): return self.value
    class Backend:
        def generate(self, instruction, evidence, response_model):
            nonlocal calls
            calls += 1
            if calls == 1:
                return Output({"verdict": "contradicted", "confidence": .9, "supporting_evidence": ["invented"],
                               "counterevidence": ["exact source", "table ... excerpt"], "reasoning": "checked"})
            assert "UNMATCHED EXCERPTS" in evidence and "do not use" in instruction
            return Output({"verdict": "contradicted", "confidence": .85, "supporting_evidence": [],
                           "counterevidence": ["exact source"], "reasoning": "reassessed"})
    row = asyncio.run(verify_finding("The exact source is here.", {"id": "negative", "claim": "false"}, Backend()))
    assert row["verdict"] == "contradicted"
    assert row["raw_model_verdict"] == "contradicted" and row["repaired_model_verdict"] == "contradicted"
    assert row["evidence_check"] == "passed_after_repair"
    assert row["matched_counterevidence"] == ["exact source"]


def test_read_canonical_review_hides_provenance(tmp_path):
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"metadata": {"backend": "codex"}, "findings": [
        {"severity": "major", "claim": "Claim", "rationale": "Why", "remedy": "Fix"}]}))
    text = read_review(path)
    assert "codex" not in text and "Claim" in text and "Fix" in text

    from coarse_socpsy.render import to_markdown
    from coarse_socpsy.schemas import ReviewRun, RunMetadata
    run = ReviewRun(metadata=RunMetadata(run_id="x", backend="codex", model="luna", profile="social",
                    profile_hash="p", input_hash="i", output_dir="o"), sources=[])
    rendered = tmp_path / "rendered.md"
    rendered.write_text(to_markdown(run))
    cleaned = read_review(rendered)
    assert "Backend:" not in cleaned and "Profile:" not in cleaned


def test_comparison_records_partial_invalid_order():
    calls = 0
    async def flaky(prompt):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("judge unavailable")
        return {"winner": "tie", "confidence": .5, "rationale": "insufficient difference"}
    paper = {"paper_id": "p", "manuscript": "m", "candidate_review": "c", "reference_review": "r"}
    from coarse_socpsy.evaluation import run_comparisons
    result = asyncio.run(run_comparisons(build_pairwise_cases([paper]), flaky))
    assert len(result["judgments"]) == 1
    assert result["invalid"][0]["case_id"].endswith("order-2")
    assert result["aggregate"]["paper_count"] == 0
    assert result["aggregate"]["incomplete_judge_pairs"] == [{"paper_id": "p", "judge": "function"}]


def test_candidate_plus_tie_is_not_a_win():
    result = aggregate_pairwise([
        {"paper_id": "p", "order": "candidate_first", "winner": "candidate"},
        {"paper_id": "p", "order": "reference_first", "winner": "tie"},
    ])
    assert result["paper_outcomes"] == {"p": "tie"}
    assert result["counts"]["candidate"] == 0


def test_audit_sample_summary_round_trip():
    samples = sample_finding_audit([
        {"finding_id": "one", "status": "unresolved", "severity": "major"},
        {"finding_id": "two", "status": "supported", "severity": "minor"},
    ], random_n=1, targeted_n=1, seed=1)
    adjudicated = [{**row, "verdict": "supported"} for rows in samples.values() for row in rows]
    summary = audit_summary(adjudicated)
    assert summary["random"]["n"] == 1 and summary["targeted"]["n"] == 1


def test_two_judges_are_aggregated_without_pseudoreplication():
    rows = [
        {"paper_id": "p", "judge": "family-a", "order": "candidate_first", "winner": "candidate"},
        {"paper_id": "p", "judge": "family-a", "order": "reference_first", "winner": "candidate"},
        {"paper_id": "p", "judge": "family-b", "order": "candidate_first", "winner": "reference"},
        {"paper_id": "p", "judge": "family-b", "order": "reference_first", "winner": "reference"},
    ]
    result = aggregate_pairwise(rows)
    assert result["paper_count"] == 1
    assert result["paper_outcomes"] == {"p": "tie"}
    assert result["judge_outcomes"]["p"] == {"family-a": "candidate", "family-b": "reference"}
    assert result["judge_disagreement_papers"] == ["p"]


def test_read_review_and_audit_exclude_set_aside_by_default(tmp_path):
    path = tmp_path / "review.json"
    findings = [
        {"id": "keep", "severity": "major", "claim": "Shown", "rationale": "r", "remedy": "x",
         "editorial_disposition": "publish", "status": "supported"},
        {"id": "drop", "severity": "major", "claim": "Hidden", "rationale": "r", "remedy": "x",
         "editorial_disposition": "rejected", "status": "supported"},
    ]
    path.write_text(json.dumps({"findings": findings}))
    assert "Shown" in read_review(path) and "Hidden" not in read_review(path)
    normalized = [{"finding_id": row["id"], **row} for row in findings]
    default = sample_finding_audit(normalized, random_n=2, targeted_n=0)
    explicit = sample_finding_audit(normalized, random_n=2, targeted_n=0, include_set_aside=True)
    assert len(default["random"]) == 1 and len(explicit["random"]) == 2


def test_legacy_null_editorial_disposition_is_read_but_explicit_reject_is_set_asError():
    # Null occurs in legacy partial runs whose editorial stage never completed;
    # the compare CLI separately requires --allow-partial and marks it ineligible.
    rows = [{"finding_id": "legacy", "editorial_disposition": None}]
    assert sample_finding_audit(rows, random_n=1, targeted_n=0)["random"][0]["finding_id"] == "legacy"
