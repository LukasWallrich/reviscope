import json
import re
from datetime import datetime, timezone

import pytest

from reviscope.backend import Backend
from reviscope.criticism_judge import (ClusterResponse, JudgeResponse, Variant, _kappa, calibrate, cluster_variants,
                                       combine, extract_arm, judge_paper, macro_summary, summary_markdown)
from reviscope.ingest import ingest
from reviscope.normalization import ReviewInventory
from reviscope.schemas import Evidence, Finding, ReviewRun, RunMetadata, ToolCall

TEXT = ("Participants were 120 students. The effect was d = 0.70 in Study 1. We conclude the effect is causal. "
        "A limitation is the student sample. " + "Further manuscript context. " * 40)


def manuscript(tmp_path):
    path = tmp_path / "paper.txt"
    path.write_text(TEXT)
    return path


def finding(fid, claim, *, module="statistics", status="llm_supported", disposition="publish", verifier="supported",
            severity="major", remedy_status="supported", quote="The effect was d = 0.70 in Study 1.", source_id="x"):
    return Finding(id=fid, module=module, claim=claim, rationale=f"Rationale for {claim}", remedy=f"Fix {claim}",
                   severity=severity, status=status, editorial_disposition=disposition, verifier_status=verifier,
                   remedy_status=remedy_status, evidence=[Evidence(source_id=source_id, quote=quote, location="source characters 1:2")])


def pipeline_run(tmp_path, name, findings):
    paper = manuscript(tmp_path)
    source = ingest(paper)
    rows = [f.model_copy(update={"evidence": [e.model_copy(update={"source_id": source.id}) for e in f.evidence]}) for f in findings]
    run = ReviewRun(metadata=RunMetadata(run_id="r", backend="codex", profile="social_psychology", profile_hash="h",
                                         input_hash="i", output_dir=str(tmp_path)), sources=[source], findings=rows)
    path = tmp_path / name / "review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.model_dump_json())
    return path


def plain_run(tmp_path, name, descriptions):
    import hashlib
    path = tmp_path / name / "review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(manuscript(tmp_path).read_bytes()).hexdigest()
    path.write_text(json.dumps({"partial": False, "sources": [{"id": "manuscript", "kind": "manuscript", "sha256": sha}],
                                "issues": [{"category": "statistical_errors", "subcategory": "s", "description": d,
                                            "quote": "Participants were 120 students.", "location": "methods",
                                            "severity": "major"} for d in descriptions]}))
    return path


def topic(text):
    for word in ("causal", "effect size", "sample", "typo", "power"):
        if word in text.lower():
            return word
    return text


class Clusterer(Backend):
    """Clusters by topic keyword; optionally violates the partition first."""
    name, model = "stubcluster", "c"

    def __init__(self, violate=0):
        self.violate, self.prompts = violate, []

    def generate(self, instruction, evidence, response_model):
        assert response_model is ClusterResponse
        self.prompts.append(instruction + evidence)
        rows = json.loads(evidence.split("\n", 1)[1])
        groups = {}
        for row in rows:
            key = topic(" ".join(row["claims"]) if "claims" in row else row["claim"])
            groups.setdefault(key, []).append(row["id"])
        clusters = [{"cluster_id": f"c{i}", "label": key, "variant_ids": ids} for i, (key, ids) in enumerate(groups.items())]
        if self.violate:
            self.violate -= 1
            clusters[0]["variant_ids"] = clusters[0]["variant_ids"][1:] + ["Vunknown"]
        return ClusterResponse.model_validate({"clusters": clusters})


VERDICTS = {"causal": ("supported", 3), "effect size": ("contradicted", 2), "sample": ("supported", 1),
            "typo": ("unresolved", 0), "power": ("supported", 2)}


class Judge(Backend):
    """Answers by topic keyword; records one exec tool call per batch."""
    def __init__(self, name="stubjudge", model="j", flip=(), fail=0):
        self.name, self.model, self.flip, self.fail = name, model, set(flip), fail
        self.prompts, self._tool_calls = [], []

    def generate(self, instruction, evidence, response_model):
        assert response_model is JudgeResponse
        self.prompts.append(instruction + evidence)
        self._tool_calls.append(ToolCall(backend=self.name, sequence=0, kind="exec", name="Bash", command="python -c 1",
                                         timestamp=datetime.now(timezone.utc)))
        if self.fail:
            self.fail -= 1
            raise RuntimeError("judge crashed")
        rows = []
        for vid, claim in re.findall(r"CRITICISM (\S+)\nClaim: (.*)", evidence):
            verdict, materiality = VERDICTS.get(topic(claim), ("not_assessable", 0))
            if topic(claim) in self.flip:
                verdict = "contradicted"
            part = "supported" if verdict == "supported" else verdict
            rows.append({"variant_id": vid, "premise": part, "inference": "not_stated", "consequence": "not_stated",
                         "correctness": verdict, "explanation": "checked",
                         "manuscript_quotes": [{"source_id": "wrong-id", "quote": "We conclude the effect is causal."},
                                               {"source_id": "x", "quote": "Not in the paper."}],
                         "alleges_error": "sample" not in claim.lower(), "materiality": materiality,
                         "remedy_necessity": "essential", "remedy_proportionate": "no" if "effect size" in claim.lower() else "yes",
                         "remedy_valid": "yes", "concrete_benefit": "yes" if "sample" in claim.lower() else "not_applicable",
                         "generic": "sample" in claim.lower(), "restates_own_limitation": "sample" in claim.lower()})
        return JudgeResponse.model_validate({"judgments": rows})


def arms(tmp_path):
    spec1 = pipeline_run(tmp_path, "spec1", [
        finding("statistics:0:a", "The causal claim is unsupported by the design.", module="interpretation"),
        finding("statistics:1:b", "The effect size is misreported.", severity="critical"),
        finding("statistics:2:c", "Power analysis is missing for Study 1.", module="statistics"),
        finding("statistics:3:d", "A typo in table 2 may change the result.", status="unresolved", disposition="needs_review",
                verifier="unresolved", severity="minor"),
        finding("statistics:4:e", "Rejected concern about power", status="contradicted", verifier="contradicted")])
    spec2 = pipeline_run(tmp_path, "spec2", [finding("x:0:a", "Causal language overreaches.", module="interpretation")])
    plain = plain_run(tmp_path, "plain", ["The student sample limits generalisation.", "The causal inference is too strong."])
    return [("specialist", spec1), ("specialist", spec2), ("plain", plain)]


def run_paper(tmp_path, judges=None, clusterer=None, arm_list=None, **kwargs):
    judges = judges or {"a": lambda: Judge("fam-a"), "b": lambda: Judge("fam-b", flip={"power"})}
    return judge_paper("p1", manuscript(tmp_path), arm_list or arms(tmp_path), tmp_path / "out", judge_factories=judges,
                       clusterer=clusterer or Clusterer(), normalizer=None, workers=1, **kwargs)


def test_extraction_takes_author_visible_findings_and_hides_withheld_remedies(tmp_path):
    source = ingest(manuscript(tmp_path))
    path = pipeline_run(tmp_path, "r", [finding("m:0:a", "Shown claim", remedy_status="overreaching"),
                                        finding("m:1:b", "Unresolved claim", status="unresolved", disposition="needs_review", verifier="unresolved"),
                                        finding("m:2:c", "Merged claim", disposition="merged")])
    run, variants, origins = extract_arm("spec", "spec/1", path, [source])
    assert [v.claim for v in variants] == ["Shown claim", "Unresolved claim"]
    assert [o.display for o in origins] == ["published", "unresolved"]
    assert all(v.remedy is None for v in variants) and all(o.remedy_withheld for o in origins)
    assert origins[0].module == "statistics" and origins[0].severity == "major" and origins[0].quote_anchoring == [True]
    assert run.format == "pipeline" and run.output_words > 0
    # Variant ids are opaque and stable.
    assert variants[0].id == extract_arm("other", "other/1", path, [source])[1][0].id
    assert "spec" not in variants[0].id


def test_plain_reviews_in_both_formats_keep_an_optional_remedy(tmp_path):
    import hashlib
    paper = manuscript(tmp_path)
    sha = hashlib.sha256(paper.read_bytes()).hexdigest()
    path = tmp_path / "general.json"
    path.write_text(json.dumps({"sources": [{"id": "manuscript", "kind": "manuscript", "sha256": sha},
                                            {"id": "supplement", "kind": "supplement", "sha256": "other"}],
                                "issues": [{"category": "inference", "description": "The causal claim is too strong.",
                                            "remedy": "Soften the claim.", "remedy_necessity": "essential",
                                            "quote": "We conclude the effect is causal.", "location": "discussion", "severity": "major"}]}))
    run, variants, origins = extract_arm("plain", "plain/1", path, [ingest(paper)])
    assert variants[0].remedy == "Soften the claim." and origins[0].kind == "essential" and origins[0].quote_anchoring == [True]
    run, variants, origins = extract_arm("plain", "plain/1", plain_run(tmp_path, "dawes", ["The sample is small."]), [ingest(paper)])
    assert variants[0].remedy is None and variants[0].quotes == ["Participants were 120 students."]


def test_extraction_rejects_a_run_of_another_manuscript(tmp_path):
    path = pipeline_run(tmp_path, "r", [finding("m:0:a", "Claim")])
    other = tmp_path / "other.txt"
    other.write_text("A different manuscript. " * 60)
    with pytest.raises(ValueError, match="does not match"):
        extract_arm("spec", "spec/1", path, [ingest(other)])


def test_free_text_report_is_normalized_and_strengths_are_excluded(tmp_path):
    report = tmp_path / "human.md"
    report.write_text("The design is elegant. The causal claim is too strong; please soften it.")

    class Normalizer(Backend):
        name, model = "norm", "n"

        def generate(self, instruction, evidence, response_model):
            assert response_model is ReviewInventory
            return ReviewInventory.model_validate({"issues": [
                {"issue_id": "i1", "assessment_type": "strength", "evaluation": "Elegant design", "rationale": "",
                 "evidence": [], "remedy": "", "source_review_spans": ["The design is elegant."]},
                {"issue_id": "i2", "assessment_type": "criticism", "evaluation": "The causal claim is too strong", "rationale": "",
                 "evidence": [], "remedy": "please soften it", "source_review_spans": ["The causal claim is too strong; please soften it."]}]})

    result = judge_paper("p1", manuscript(tmp_path), [("human", report)], tmp_path / "out", judge_factories={"a": lambda: Judge()},
                         clusterer=Clusterer(), normalizer=Normalizer(), workers=1)
    assert [v["claim"] for v in result["variants"]] == ["The causal claim is too strong"]
    assert result["runs"][0]["output_words"] == len(report.read_text().split())
    assert any(s["name"] == "normalize" for s in result["stages"]["extraction"])


def test_prompts_are_origin_blind_and_clusters_partition_every_variant(tmp_path):
    clusterer, judge = Clusterer(), Judge()
    result = run_paper(tmp_path, judges={"a": lambda: judge}, clusterer=clusterer)
    prompts = "\n".join(clusterer.prompts + judge.prompts)
    for leaked in ("specialist", "plain", "statistics:", "interpretation", "llm_supported", "critical", "needs_review", "Severity"):
        assert leaked not in prompts
    assert "Rejected concern" not in prompts  # contradicted findings are not author-visible
    ids = [v for c in result["clusters"] for v in c["variant_ids"]]
    assert sorted(ids) == sorted(v["id"] for v in result["variants"])
    assert not result["partial"]


def test_cluster_violation_is_retried_then_repaired_and_recorded(tmp_path):
    variants = [Variant(id=f"V{i}", claim=c) for i, c in enumerate(["causal one", "causal two", "sample"])]
    clusters, stages, record = cluster_variants(variants, Clusterer(violate=1), tmp_path)
    assert record["batches"][0]["attempts"] == 2 and record["batches"][0]["violations"] and not record["batches"][0]["repairs"]
    clusters, stages, record = cluster_variants(variants, Clusterer(violate=2), tmp_path / "again")
    assert record["batches"][0]["repairs"]
    assert sorted(v for c in clusters for v in c["variant_ids"]) == ["V0", "V1", "V2"]
    many = [Variant(id=f"V{i:02d}", claim=["causal", "sample", "power"][i % 3] + f" {i}") for i in range(10)]
    clusters, stages, record = cluster_variants(many, Clusterer(), tmp_path / "batched", batch_size=4)
    assert len(record["batches"]) == 3 and record["merge"] is not None and len(clusters) == 3


def test_judgments_are_derived_conservatively_and_quotes_anchor_checked(tmp_path):
    result = run_paper(tmp_path)
    rows = list(result["judgments"]["a"].values())
    assert all(r["manuscript_quotes"][0]["anchored"] and not r["manuscript_quotes"][1]["anchored"] for r in rows)
    assert all(r["quotes_anchored"] == 1 for r in rows)
    judge_stage = result["stages"]["judge:a"][0]
    assert judge_stage["tool_calls"][0]["command"] == "python -c 1" and judge_stage["tool_calls"][0]["stage"] == "judge"


def test_metrics_per_run_issue_level_and_agreement(tmp_path):
    result = run_paper(tmp_path)
    metrics = result["metrics"]
    runs = {row["run"]: row for row in metrics["views"]["a"]["per_run"]}
    spec1 = runs["specialist/1"]["author_visible"]
    assert spec1["variants"] == 4 and spec1["supported"] == 2 and spec1["contradicted"] == 1 and spec1["unresolved"] == 1
    assert spec1["supported_of_resolved"] == round(2 / 3, 4) and spec1["supported_material"] == 2
    assert spec1["serious_harms"] == 1  # contradicted critical effect-size claim
    assert runs["specialist/1"]["published_only"]["variants"] == 3
    plain = runs["plain/1"]["author_visible"]
    assert plain["supported_beneficial_suggestions"] == 1 and plain["generic"] == 1 and plain["restates_own_limitation"] == 1
    issues = metrics["views"]["a"]["issues"]
    # power and effect size are specialist-only; causal is shared with plain.
    assert issues["per_arm"]["specialist"]["unique_supported_material"] == 1
    assert issues["per_arm"]["specialist"]["unique_by_module"] == {"statistics": 1}
    assert issues["per_arm"]["plain"]["unique_supported_material"] == 0
    causal = next(row for row in issues["stability"] if row["label"] == "causal")
    assert causal["arms"]["specialist"] == {"runs": 2, "detected_runs": 2, "detection_frequency": 1.0, "supported_runs": 2}
    # Family b contradicts the power claim: the combined view must not count it as supported.
    combined = {row["run"]: row for row in metrics["views"]["combined"]["per_run"]}
    assert combined["specialist/1"]["author_visible"]["supported"] == 1
    agree = metrics["agreement"]["a~b"]
    assert agree["n"] == 7 and agree["correctness_agreement"] == round(6 / 7, 4)
    assert [d["claim"] for d in agree["disagreements"]] == ["Power analysis is missing for Study 1."]
    summary = macro_summary([result, result | {"paper_id": "p2"}])
    assert summary["macro"]["a"]["specialist"]["papers"] == 2
    assert "| specialist |" in summary_markdown(summary)


def test_reuse_judges_only_new_variants(tmp_path):
    first = Judge()
    run_paper(tmp_path, judges={"a": lambda: first}, arm_list=arms(tmp_path)[:1])
    assert len(first.prompts) == 1
    second = Judge()
    result = run_paper(tmp_path, judges={"a": lambda: second})
    assert len(second.prompts) == 1  # one batch for the three new variants only
    assert sum(r["reused"] for r in result["judgments"]["a"].values()) == 4
    third = Judge()
    run_paper(tmp_path, judges={"a": lambda: third})
    assert third.prompts == []


def test_failed_batch_is_retried_and_persistent_failure_marks_partial(tmp_path):
    shared = Judge(fail=1)
    result = run_paper(tmp_path, judges={"a": lambda: shared})
    assert not result["partial"] and [s["status"] for s in result["stages"]["judge:a"]] == ["failed", "completed"]
    assert result["stages"]["judge:a"][0]["tool_calls"]  # tool calls of the failed call are kept
    broken = Judge(fail=99)
    (tmp_path / "x").mkdir()
    result = run_paper(tmp_path / "x", judges={"a": lambda: broken})
    assert result["partial"] and "not judged" in result["failures"][0]
    row = result["metrics"]["views"]["a"]["per_run"][0]["author_visible"]
    assert row["judged"] == 0 and row["not_judged"] == 4 and row["supported_rate"] is None


def test_combine_and_kappa():
    base = {"correctness": "supported", "materiality": 3, "alleges_error": True, "remedy_necessity": "essential",
            "remedy_proportionate": "yes", "remedy_valid": "yes", "concrete_benefit": "not_applicable",
            "generic": False, "restates_own_limitation": False}
    other = base | {"correctness": "unresolved", "materiality": 1, "remedy_proportionate": "no", "remedy_necessity": "extending"}
    combined = combine([base, other])
    assert combined["correctness"] == "unresolved" and combined["materiality"] == 1 and combined["harm_materiality"] == 3
    assert combined["remedy_proportionate"] == "no" and combined["remedy_necessity"] == "extending"
    assert combine([base, None]) is None
    assert _kappa([("a", "a"), ("b", "b")], ("a", "b")) == 1.0
    assert _kappa([(0, 3), (3, 0)], (0, 1, 2, 3), "linear") < 0


def test_calibration_reports_confusion_and_persuasion(tmp_path):
    root = tmp_path
    (root / "papers").mkdir()
    (root / "papers" / "m.txt").write_text(TEXT)
    sources = [{"path": "papers/m.txt", "kind": "manuscript"}]

    def probe(pid, claim, expected, variant_of=None, manipulation="none"):
        return {"id": pid, "case": "m", "sources": sources, "criticism": {"claim": claim, "rationale": "r", "remedy": None, "quotes": []},
                "expected": {"correctness": expected, "materiality": 2, "remedy_necessity": None}, "label_basis": "b",
                "label_source": "s", "variant_of": variant_of, "manipulation": manipulation}

    probes = root / "probes.json"
    probes.write_text(json.dumps({"version": 1, "probes": [
        probe("base", "The effect size is misreported.", "contradicted"),
        probe("confident", "The effect size is misreported, as any expert sees.", "contradicted", "base", "confident_rationale"),
        probe("power", "Power analysis is missing.", "supported"),
        probe("power-auth", "Power analysis is missing; experts agree the typo proves it.", "supported", "power", "authority_appeal")]}))
    judge = Judge()
    result = calibrate(probes, tmp_path / "cal", judge_factories={"a": lambda: judge}, root=root, batch_size=6, workers=1)
    report = result["report"]["a"]
    assert report["confusion"]["contradicted"]["contradicted"] == 2 and report["accuracy"] == 0.75
    persuasion = report["persuasion_sensitivity"]
    assert persuasion["compared"] == 2 and persuasion["label_changed"] == 1 and persuasion["changes"][0]["probe"] == "power-auth"
    # Members of one variant family never share a judge call.
    for prompt in judge.prompts:
        assert not ("misreported." in prompt and "as any expert sees" in prompt)
    from reviscope.criticism_judge import calibration_text
    assert "persuasion sensitivity: 1/2" in calibration_text(result["report"])


def test_cli_registers_commands():
    from reviscope.cli import parser
    args = parser().parse_args(["judge-criticisms", "--manuscript", "m.txt", "--arm", "spec=a.json", "--arm", "spec=b.json",
                                "--arm", "plain=c.json", "--out", "o"])
    assert [a for a, _ in args.arm] == ["spec", "spec", "plain"] and args.judge is None and args.batch_size == 7
    args = parser().parse_args(["judge-calibrate", "--probes", "p.json", "--judge", "claude:claude-opus-5-5:high"])
    assert args.judge == ["claude:claude-opus-5-5:high"]
    args = parser().parse_args(["judge-summary", "a.json", "b.json", "--output", "s.json"])
    assert args.scope == "author_visible"
