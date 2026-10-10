"""Iter4 contracts with synthetic manuscripts and offline model backends."""
import json
import re
import threading

import pytest
from pydantic import ValidationError

from reviscope.backend import Backend
from reviscope.discovery import TOPICS, discovery_instruction, requested_checks
from reviscope.metacheck import REFERENCES, STATISTICS, TRANSPARENCY, route
from reviscope.pipeline import EditorialDecision, ReviewPipeline
from reviscope.profiles import load_profile
from reviscope.render import published_findings, to_html, to_markdown
from reviscope.schemas import Finding, ReviewRun, Severity, StudyMap
from stubs import discovery_payload


class Iter4Backend(Backend):
    name, model, effort = "iter4-test", "offline", "high"

    def __init__(self, findings=None, verdicts=None, edit=None):
        self.findings, self.verdicts, self.edit = findings or {}, verdicts or {}, edit
        self.calls = []

    def generate(self, instruction, evidence, response_model):
        kind = response_model.__name__
        self.calls.append((kind, instruction, evidence))
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="d",
                            contribution_summary="c", strengths=[])
        if kind == "DiscoveryResponse":
            module = next((m for m, topics in TOPICS.items() if topics == requested_checks(instruction)), "other")
            sid = re.search(r"SOURCE_ID: (\S+)", evidence).group(1)
            rows = [{**row, "module": module, "evidence": [{"source_id": sid, "quote": row.get("quote", "Evidence A.")}]}
                    for row in self.findings.get(module, [])]
            return response_model.model_validate(discovery_payload(instruction, rows))
        if kind == "VerificationResponse":
            rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
            if any(self.verdicts.get(row["finding_id"].split(":")[-1]) == "fail" for row in rows):
                raise RuntimeError("Offline verifier failure")
            return response_model.model_validate({"decisions": [{
                "finding_id": row["finding_id"], "status": self.verdicts.get(row["finding_id"].split(":")[-1], "supported"),
                "rationale": "Checked against the synthetic manuscript.", "evidence": row["quoted_evidence"],
                "remedy_status": "supported", "remedy_rationale": "Proportionate."} for row in rows]})
        if kind == "EditorialResponse":
            rows = json.loads(instruction.split("\nFINDINGS\n")[1])
            decisions = self.edit(rows) if self.edit else [{"finding_id": row["id"], "disposition": "keep",
                "reason": "Distinct.", "severity": row["severity"], "priority": i} for i, row in enumerate(rows, 1)]
            return response_model.model_validate({"decisions": decisions, "reconciled_overview": {
                "design_summary": "d", "contribution_summary": "c", "strengths": []}})
        raise AssertionError(kind)


def candidate(identifier, severity="minor", quote="Evidence A."):
    return {"id": identifier, "claim": f"Concern {identifier}.", "rationale": "A central assessment consequence.",
            "remedy": "Clarify the central claim.", "severity": severity, "quote": quote}


def run_pipeline(tmp_path, backend, **options):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("Evidence A. Evidence B. Evidence C. " + "Synthetic manuscript context. " * 50)
    return ReviewPipeline(backend, run_metacheck=False, **options).run(manuscript, output_dir=tmp_path / "out")


@pytest.mark.parametrize("profile_id", ["quantitative_social_science", "social_psychology", "education"])
def test_overview_is_inherited_with_three_checks_and_no_new_metacheck_routing(profile_id):
    profile = load_profile(profile_id)
    assert profile.modules.count("overview") == 1
    assert len(TOPICS["overview"]) == 3
    assert requested_checks(discovery_instruction("overview", profile.module_prompts["overview"])) == TOPICS["overview"]
    assert "one argument from question to conclusion" in profile.module_prompts["overview"]
    assert "Verify the whole-paper criticism" in profile.verification_prompt
    modules = [*profile.modules, "blind_spots"]
    for lead in [*STATISTICS, *REFERENCES, *TRANSPARENCY, "prereg_check", "causal_claims", "unowned"]:
        assert route(lead, modules) == route(lead, [m for m in modules if m != "overview"])
        assert "overview" not in route(lead, modules)


def test_overview_runs_in_parallel_before_blind_spots_and_reaches_finalization(tmp_path):
    barrier = threading.Barrier(2)

    class ParallelBackend(Iter4Backend):
        def generate(self, instruction, evidence, response_model):
            if response_model.__name__ == "DiscoveryResponse":
                checks = requested_checks(instruction)
                if checks in [TOPICS["overview"], TOPICS["contribution"]]:
                    barrier.wait(timeout=5)
                if checks == TOPICS["blind_spots"]:
                    assert "Concern overview." in evidence and "Concern contribution." in evidence
                    assert "overview/consequential_gaps" in evidence
            return super().generate(instruction, evidence, response_model)

    backend = ParallelBackend({"overview": [candidate("overview")], "contribution": [candidate("contribution")]})
    run = run_pipeline(tmp_path, backend, parallel=4)
    assert not run.partial
    assert {f.module for f in published_findings(run)} == {"overview", "contribution"}
    assert next(s for s in run.stages if s.name == "verification-overview-1").status == "completed"
    editorial = next(call[1] for call in backend.calls if call[0] == "EditorialResponse")
    assert '"module":"overview"' in editorial


def test_editorial_reassigns_severity_orders_priorities_and_keeps_discovery_audit(tmp_path):
    final = {"promote": ("major", 2), "demote": ("minor", 1), "first": ("major", 1), "critical": ("critical", 99)}

    def edit(rows):
        assert all(row["discovery_severity"] == row["severity"] for row in rows)
        return [{"finding_id": row["id"], "disposition": "keep", "reason": "Consequence in context.",
                 "severity": final[row["id"].split(":")[-1]][0], "priority": final[row["id"].split(":")[-1]][1]}
                for row in rows]

    backend = Iter4Backend({"overview": [candidate("promote"), candidate("demote", "critical"),
                                         candidate("first"), candidate("critical", "major")]}, edit=edit)
    run = run_pipeline(tmp_path, backend)
    assert not run.partial
    assert [f.id.split(":")[-1] for f in published_findings(run)] == ["critical", "first", "promote", "demote"]
    by_name = {f.id.split(":")[-1]: f for f in run.findings}
    assert by_name["promote"].severity == Severity.major and by_name["promote"].discovery_severity == Severity.minor
    assert by_name["demote"].severity == Severity.minor and by_name["demote"].discovery_severity == Severity.critical
    assert [f.severity for f in run.candidates] == [Severity.minor, Severity.critical, Severity.minor, Severity.major]
    assert all(f.status == "llm_supported" for f in run.findings)
    # Rendering a stored run also enforces the order, rather than relying on list insertion.
    run.findings.reverse()
    markdown = to_markdown(run)
    assert markdown.index("### 1. Critical") < markdown.index("### 2. Major: Concern first.")
    stored = ReviewRun.model_validate_json((tmp_path / "out/review.json").read_text())
    assert [f.priority for f in stored.findings] == [99, 1, 2, 1]
    instruction = next(call[1] for call in backend.calls if call[0] == "EditorialResponse")
    assert "Severity never overrides verification status" in instruction and "immutable" not in instruction
    assert "Missing information is major only when a central claim cannot be assessed without it" in instruction


def test_editorial_schema_requires_keep_severity_but_allows_other_dispositions_without_it():
    assert {"severity", "priority"} <= EditorialDecision.model_json_schema()["properties"].keys()
    for severity in [None, "invalid"]:
        with pytest.raises(ValidationError):
            EditorialDecision(finding_id="a", disposition="keep", reason="r", severity=severity)
    for disposition in ["merge", "reject", "needs_review"]:
        assert EditorialDecision(finding_id="a", disposition=disposition, reason="r").severity is None
    with pytest.raises(ValidationError):
        EditorialDecision(finding_id="a", disposition="keep", reason="r", severity="major", priority=0)
    legacy = Finding(id="a", module="m", claim="c", rationale="r", remedy="fix")
    assert legacy.discovery_severity is None and legacy.priority is None and legacy.merged_points == []


def test_priority_ties_and_missing_priorities_keep_a_stable_order(tmp_path):
    priorities = {"missing": None, "second": 2, "tie_a": 1, "tie_b": 1}

    def edit(rows):
        return [{"finding_id": row["id"], "disposition": "keep", "reason": "Distinct.", "severity": "major",
                 "priority": priorities[row["id"].split(":")[-1]]} for row in rows]

    backend = Iter4Backend({"overview": [candidate(name) for name in priorities]}, edit=edit)
    run = run_pipeline(tmp_path, backend)
    assert not run.partial
    assert [f.id.split(":")[-1] for f in published_findings(run)] == ["tie_a", "tie_b", "second", "missing"]


def test_missing_editorial_keep_severity_fails_closed(tmp_path):
    backend = Iter4Backend({"overview": [candidate("a")]}, edit=lambda rows: [
        {"finding_id": row["id"], "disposition": "keep", "reason": "Missing severity."} for row in rows])
    run = run_pipeline(tmp_path, backend)
    assert run.partial and not published_findings(run)
    assert next(s for s in run.stages if s.name == "editorial").status == "failed"
    assert run.findings[0].status == "llm_supported"  # severity never changes verification


def merge_into_overview(rows):
    target = next(row for row in rows if row["module"] == "overview")
    return [{"finding_id": row["id"], "disposition": "keep" if row is target else "merge",
             "reason": "Same underlying issue.", "target_id": None if row is target else target["id"],
             "severity": "major" if row is target else None, "priority": 1 if row is target else None}
            for row in rows]


def test_merge_folds_distinct_claims_and_only_anchored_quotes_without_rewriting(tmp_path):
    rows = {"overview": [candidate("whole")], "design": [candidate("design", quote="Evidence B.")],
            "measurement": [candidate("measurement", quote="Invented quotation.")]}

    class CorrectedQuoteBackend(Iter4Backend):
        def generate(self, instruction, evidence, response_model):
            result = super().generate(instruction, evidence, response_model)
            if response_model.__name__ == "VerificationResponse":
                for decision in result.decisions:
                    if decision.finding_id.startswith("measurement:"):
                        decision.evidence[0].quote = "Evidence C."
            return result

    run = run_pipeline(tmp_path, CorrectedQuoteBackend(rows, edit=merge_into_overview))
    assert not run.partial
    kept = published_findings(run)
    assert len(kept) == 1 and kept[0].claim == "Concern whole."
    points = kept[0].merged_points
    assert [p.claim for p in points] == ["Concern design.", "Concern measurement."]
    assert [p.evidence[0].quote for p in points] == ["Evidence B.", "Evidence C."]
    assert all(e.source_char_start is not None and e.location for p in points for e in p.evidence)
    assert {p.finding_id for p in points} == {f.id for f in run.findings if f.editorial_disposition == "merged"}
    assert len(run.candidates) == len(run.findings) == 3
    markdown = to_markdown(run).split("## Coverage and audit")[0]
    assert "Also raised by other modules:" in markdown
    assert all(p.claim in markdown and p.evidence[0].quote in markdown for p in points)
    assert "Invented quotation." not in markdown
    assert "Also raised by other modules:" in to_html(markdown)
    rerun = run_pipeline(tmp_path, CorrectedQuoteBackend(rows, edit=merge_into_overview))
    assert published_findings(rerun)[0].merged_points == points
    assert all(s.status == "cached" for s in rerun.stages if s.name != "metacheck")


@pytest.mark.parametrize("verdict", ["unresolved", "contradicted", "fail", "external_unchecked"])
def test_merge_does_not_fold_nonpublishable_sources_even_when_editorial_requests_it(tmp_path, verdict):
    source = candidate("source", quote="Evidence B.")
    if verdict == "external_unchecked":
        source["external_evidence"] = [{"url": "https://example.org/unopened", "quote": "External assertion.",
                                        "shows": "Required support."}]
    backend = Iter4Backend({"overview": [candidate("whole")], "design": [source]},
                           verdicts={"source": "supported" if verdict == "external_unchecked" else verdict},
                           edit=merge_into_overview)
    run = run_pipeline(tmp_path, backend)
    assert published_findings(run)[0].merged_points == []
    source_finding = next(f for f in run.findings if f.module == "design")
    assert source_finding.editorial_disposition in {"needs_review", "rejected"} and source_finding.merged_into is None
    assert source_finding.status not in {"supported", "llm_supported", "recomputed", "verified_deterministic"}


def test_exact_duplicate_folds_into_editorials_kept_target(tmp_path):
    rows = {"overview": [candidate("same")], "design": [candidate("same", quote="Evidence B.")]}
    run = run_pipeline(tmp_path, Iter4Backend(rows, edit=merge_into_overview))
    assert not run.partial
    kept = published_findings(run)
    assert len(kept) == 1 and kept[0].module == "overview"
    assert kept[0].merged_points[0].module == "design"
