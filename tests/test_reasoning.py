"""Offline transport/gating probes, with scripted judgments, not model-quality tests."""
import json
import re
from pathlib import Path

import pytest

from reviscope.discovery import discovery_instruction, requested_checks, TOPICS
from reviscope.evidence_review import AuditOperation, EvidenceAudit
from reviscope.pipeline import ReviewPipeline
from reviscope.profiles import load_profile
from reviscope.reasoning import ARGUMENT_ASSESSMENT, LITERATURE_ASSESSMENT, MATERIAL_ASSESSMENT
from test_evidence_review import EvidenceBackend, manuscript

PROBES = json.loads((Path(__file__).parent / "fixtures/reasoning_probes.json").read_text())


class ProbeBackend(EvidenceBackend):
    def __init__(self, probe):
        super().__init__(count=0)
        self.probe = probe

    def generate(self, instruction, evidence, response_model):
        if response_model.__name__ == "VerificationResponse":
            assert ARGUMENT_ASSESSMENT in instruction
            assert LITERATURE_ASSESSMENT in instruction
            assert MATERIAL_ASSESSMENT in instruction
        if response_model is not EvidenceAudit:
            return super().generate(instruction, evidence, response_model)
        self.calls.append(("EvidenceAudit", instruction, evidence))
        assert "Overview sentinel" not in evidence
        assert ARGUMENT_ASSESSMENT in instruction
        assert LITERATURE_ASSESSMENT in instruction
        assert MATERIAL_ASSESSMENT in instruction
        source_ids = re.findall(r"SOURCE_ID: (\S+)", evidence)
        p = self.probe
        claim = {"source_id": source_ids[0], "quote": p["claim"]}
        premise = {"source_id": source_ids[-1] if p.get("supplement") else source_ids[0],
                   "quote": p.get("premise", p["claim"])}
        operation = {"question": "Does the supplied evidence establish this claim?",
                     "evidence": [claim], "reported_inputs": [p["text"]], "assumptions": [],
                     "method": "Compare the claim with supplied sources and alternatives.",
                     "result": p["result"], "status": p["status"],
                     "reasoning_trace": {"claim": claim, "premises": [
                         {"source_id": source_ids[0], "quote": quote} for quote in p["premises"]]
                         if p.get("premises") else [premise],
                         "inferential_step": p["step"], "defeating_context": [
                             {"source_id": source_ids[0], "quote": p["defeater"]}]
                             if p.get("defeater") else []}}
        if p.get("relation"):
            operation["literature_relation"] = {"claim": claim, **p["relation"]}
        findings = [{"id": p["id"], "module": "ignored", "claim": p["result"],
                     "rationale": p["step"], "remedy": "Clarify the bounded inference.",
                     "kind": "clarification_request" if p["status"] == "unresolved" else "defect",
                     "severity": "minor", "evidence": [claim],
                     "external_evidence": p.get("relation", {}).get("source_evidence", [])}]
        return response_model.model_validate({"operations": [operation],
            "findings": findings if p["finding"] else [], "search_incomplete": False,
            "checks": [{"check": name, "status": "assessed", "rationale": "Scripted fixture check.",
                        "evidence": [claim]} for name in TOPICS["evidence_audit"]]})


@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p["id"])
def test_reasoning_records_survive_pipeline_without_creating_findings(probe, tmp_path):
    source = tmp_path / "paper.txt"
    source.write_text(probe["text"] + "\n" + "Manuscript context. " * 100)
    supplements = []
    if probe.get("supplement"):
        supplement = tmp_path / "supplement.txt"
        supplement.write_text(probe["supplement"])
        supplements.append(supplement)
    backend = ProbeBackend(probe)
    out = tmp_path / "run"
    pipeline = ReviewPipeline(backend, strategy="holistic", evidence_audit=True, run_metacheck=False)
    run = pipeline.run(source, supplements=supplements, output_dir=out)
    assert not run.partial
    stage = next(s for s in run.stages if s.name == "review-evidence_audit")
    audit = EvidenceAudit.model_validate_json(Path(stage.artifact).read_text())
    operation = audit.operations[0]
    assert operation.reasoning_trace.inferential_step == probe["step"]
    if probe.get("premises"):
        assert [e.quote for e in operation.reasoning_trace.premises] == probe["premises"]
    assert operation.status == probe["status"]
    assert operation.result == probe["result"]
    n = len(operation.manuscript_evidence())
    assert any(f"{n}/{n} quotation anchors" in row for row in run.coverage)
    assert len(run.candidates) == int(probe["finding"])
    assert [s.name for s in run.stages].count("review-evidence_audit") == 1
    if probe.get("relation"):
        # Source passages in an operation are discovery records, never confirmation.
        assert operation.literature_relation.targets == probe["relation"]["targets"]
        assert "check" not in operation.literature_relation.source_evidence[0].model_dump()
        if probe["finding"]:
            assert run.findings[0].status == "unresolved"
            assert run.findings[0].editorial_disposition == "needs_review"
            assert all(not task.lookup_recorded for task in run.source_tasks)
    if probe.get("supplement"):
        assert operation.reasoning_trace.premises[0].source_id.startswith("supplement-")
    backend.calls.clear()
    pipeline.run(source, supplements=supplements, output_dir=out)
    assert not backend.calls


def test_nested_evidence_is_anchored_and_never_promotes_an_operation(tmp_path):
    probe = {**PROBES[0], "premise": "Invented support not in the manuscript."}
    source = tmp_path / "paper.txt"
    source.write_text(probe["text"] + "Manuscript context. " * 100)
    run = ReviewPipeline(ProbeBackend(probe), strategy="holistic", evidence_audit=True,
                         run_metacheck=False).run(source, output_dir=tmp_path / "out")
    assert any("1/2 quotation anchors" in row for row in run.coverage)
    assert not run.candidates and not run.findings


def test_old_calculation_contract_remains_readable():
    operation = AuditOperation(question="Sum?", reported_inputs=["2", "3"], assumptions=[],
                               method="Add", code="print(2+3)", result="5", status="checked")
    assert operation.reasoning_trace is None and operation.literature_relation is None
    assert AuditOperation.model_validate_json(operation.model_dump_json()) == operation


def test_guidance_reaches_specialist_profiles_without_new_coverage_topics():
    for profile_id in ("quantitative_social_science", "social_psychology", "education"):
        profile = load_profile(profile_id)
        for module in ("contribution", "interpretation", "measurement"):
            instruction = discovery_instruction(module, profile.module_prompts[module])
            assert ARGUMENT_ASSESSMENT in instruction
            assert requested_checks(instruction) == TOPICS[module]
            if module == "contribution":
                assert LITERATURE_ASSESSMENT in instruction
            else:
                assert MATERIAL_ASSESSMENT in instruction
        assert "sentence order" in profile.verification_prompt
        assert "supplements resolve" in profile.verification_prompt
        for module in ("social_psychology_context", "education_context"):
            if module in profile.modules:
                assert MATERIAL_ASSESSMENT in discovery_instruction(module, profile.module_prompts[module])


def test_instruction_change_invalidates_discovery_but_reuses_unchanged_verification(tmp_path, monkeypatch):
    from reviscope import evidence_review
    backend = EvidenceBackend(count=1)
    source, out = manuscript(tmp_path), tmp_path / "run"
    pipeline = ReviewPipeline(backend, strategy="holistic", evidence_audit=True, run_metacheck=False)
    before = pipeline.run(source, output_dir=out)
    monkeypatch.setattr(evidence_review, "REVIEW_RULES", evidence_review.REVIEW_RULES + "\nUpdated assessment guidance.")
    backend.calls.clear()
    after = pipeline.run(source, output_dir=out)
    assert [call[0] for call in backend.calls] == ["BroadReview", "EvidenceAudit"]
    for name in ("review-broad", "review-evidence_audit"):
        old = next(s for s in before.stages if s.name == name)
        new = next(s for s in after.stages if s.name == name)
        assert old.cache_key != new.cache_key
    assert all(s.status == "cached" for s in after.stages if s.name.startswith("verification-"))
