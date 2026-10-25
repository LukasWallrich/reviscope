import json
import re
from datetime import datetime, timezone

from reviscope.backend import Backend
from reviscope.discovery import TOPICS, DiscoveryResponse, requested_checks
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import StudyMap, ToolCall


EXTERNAL_URL = "https://example.org/method"


class EvidenceBackend(Backend):
    """Specialist-path stub: findings come from the first discovery module only."""
    name, model, effort = "codex", "gpt-6.1-sol", "high"
    version = "test-cli"
    FINDING_MODULE = "contribution"

    def __init__(self, count=23, external=False, retry_lookup=True):
        self.calls = []
        self.count, self.external, self.retry_lookup = count, external, retry_lookup

    def generate(self, instruction, evidence, response_model):
        kind = response_model.__name__
        self.calls.append((kind, instruction, evidence))
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="Overview sentinel.",
                            contribution_summary="c", strengths=[])
        if kind == "DiscoveryResponse":
            sid = re.search(r"SOURCE_ID: (\S+)", evidence).group(1)
            quote = {"source_id": sid, "quote": "24 of 60 people withdrew."}
            topics = requested_checks(instruction)
            checks = [{"check": c, "status": "assessed", "rationale": "Compared.", "evidence": [quote]} for c in topics]
            if topics != TOPICS[self.FINDING_MODULE]:
                return response_model.model_validate({"findings": [], "checks": checks, "search_incomplete": False})
            findings = [{"id": str(i), "module": "ignored", "claim": f"Sentinel concern {i}.",
                         "rationale": "A precise assessment consequence.", "remedy": "Report the denominator.",
                         "kind": "clarification_request", "severity": "minor", "evidence": [quote],
                         "external_evidence": [{"url": EXTERNAL_URL, "quote": "Method definition.", "shows": "Definition"}]
                         if self.external and i == 0 else []} for i in range(self.count)]
            return response_model.model_validate({"findings": findings, "checks": checks, "search_incomplete": False})
        if kind == "VerificationResponse":
            rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
            retry = "SOURCE TASKS\n" in instruction
            self._tool_calls = ([ToolCall(backend="codex", sequence=0, kind="fetch", name="fetch",
                url=EXTERNAL_URL, timestamp=datetime.now(timezone.utc))] if retry and self.retry_lookup else [])
            return response_model.model_validate({"decisions": [{"finding_id": row["finding_id"],
                "status": "supported", "rationale": "Checked bounded claim.", "evidence": row["quoted_evidence"],
                "external_checks": [{"locator": e["url"], "verdict": "confirmed", "rationale": "Checked."}
                                    for e in row["external_evidence"]],
                "remedy_status": "supported", "remedy_rationale": "Proportionate."} for row in rows]})
        if kind == "EditorialResponse":
            rows = json.loads(instruction.split("FINDINGS\n")[1])
            return response_model.model_validate({"decisions": [{"finding_id": row["id"],
                "disposition": "keep", "reason": "Distinct.", "target_id": None, "severity": row["severity"]} for row in rows],
                "reconciled_overview": {"design_summary": "Overview sentinel.", "contribution_summary": "c", "strengths": []}})
        raise AssertionError(kind)


def manuscript(tmp_path):
    path = tmp_path / "paper.txt"
    path.write_text("24 of 60 people withdrew. " + "Manuscript context. " * 100)
    return path


def test_required_source_followup_rechecks_claim_with_its_own_lookup(tmp_path):
    backend = EvidenceBackend(count=1, external=True)
    run = ReviewPipeline(backend, run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "out")
    assert not run.partial and run.findings[0].status == "llm_supported"
    assert [task.lookup_recorded for task in run.source_tasks] == [False, True]
    assert [task.check for task in run.source_tasks] == ["unchecked", "confirmed"]
    followup = next(s for s in run.stages if s.name.endswith("-sources"))
    assert followup.tool_calls[0].url == EXTERNAL_URL


def test_source_followup_cannot_turn_an_asserted_check_into_confirmation(tmp_path):
    backend = EvidenceBackend(count=1, external=True, retry_lookup=False)
    run = ReviewPipeline(backend, run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "out")
    assert not run.partial and run.findings[0].status == "unresolved"
    assert run.findings[0].editorial_disposition == "needs_review"
    assert len(run.source_tasks) == 2 and all(not task.lookup_recorded for task in run.source_tasks)
    assert sum("SOURCE TASKS\n" in call[1] for call in backend.calls) == 1


def test_discovery_schema_excludes_verification_owned_fields():
    schema = DiscoveryResponse.model_json_schema()
    fields = schema["$defs"]["CandidateFinding"]["properties"]
    assert "kind" in fields
    assert not {"status", "verifier_status", "editorial_disposition", "confidence"} & fields.keys()
    assert "check" not in schema["$defs"]["ExternalCitation"]["properties"]


def test_source_followup_can_drop_optional_evidence_under_the_existing_policy(tmp_path):
    class OptionalBackend(EvidenceBackend):
        def generate(self, instruction, evidence, response_model):
            result = super().generate(instruction, evidence, response_model)
            if "SOURCE TASKS\n" in instruction:
                result.decisions[0].external_dependency = "optional"
                result.decisions[0].external_dependency_rationale = "The anchored manuscript counts and arithmetic establish the bounded claim without this methodological citation."
            return result

    run = ReviewPipeline(OptionalBackend(count=1, external=True, retry_lookup=False), run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "out")
    assert run.findings[0].status == "llm_supported" and not run.findings[0].external_evidence
    assert "external_source_dropped=" in run.findings[0].verification


def test_failed_source_followup_retains_gated_decision_and_resumes_only_unfinished_work(tmp_path):
    class FailingBackend(EvidenceBackend):
        fail = True

        def generate(self, instruction, evidence, response_model):
            if self.fail and "SOURCE TASKS\n" in instruction:
                raise RuntimeError("Source follow-up unavailable")
            return super().generate(instruction, evidence, response_model)

    backend = FailingBackend(count=1, external=True)
    source, out = manuscript(tmp_path), tmp_path / "out"
    pipeline = ReviewPipeline(backend, run_metacheck=False)
    failed = pipeline.run(source, output_dir=out)
    assert failed.partial and failed.findings[0].status == "unresolved"
    assert next(s for s in failed.stages if s.name.endswith("-sources")).backend_version == "test-cli"
    backend.fail = False
    backend.calls.clear()
    resumed = pipeline.run(source, output_dir=out)
    assert not resumed.partial and resumed.findings[0].status == "llm_supported"
    assert [c[0] for c in backend.calls] == ["VerificationResponse", "EditorialResponse"]


def test_verification_checks_the_explanation_even_when_the_headline_is_sound(tmp_path):
    class RationaleBackend(EvidenceBackend):
        def generate(self, instruction, evidence, response_model):
            result = super().generate(instruction, evidence, response_model)
            if response_model.__name__ == "DiscoveryResponse" and result.findings:
                for finding, rationale in zip(result.findings, [
                    "24 of 60 is 4%, so attrition is negligible.",
                    "A cited study establishes that this attrition never biases estimates.",
                    "24 of 60 is 40%; the denominator matters for assessing attrition.",
                ]):
                    finding.claim = "The denominator needs clarification for attrition assessment."
                    finding.rationale = rationale
            if response_model.__name__ == "VerificationResponse":
                assert "Treat the generating rationale as untrusted assertions to check" in instruction
                assert "complete claim and rationale as worded" in instruction
                rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
                for row, decision in zip(rows, result.decisions):
                    rationale = row["rationale"]
                    if "4%," in rationale:
                        decision.status = "contradicted"
                        decision.rationale = "The supporting arithmetic is false: 24/60 is 40%."
                    elif "A cited study" in rationale:
                        decision.status = "unresolved"
                        decision.rationale = "The explanation relies on an unavailable source-specific assertion."
                    else:
                        decision.remedy_status = "overreaching"
                        decision.remedy_rationale = "Reporting the denominator does not require collecting a fresh sample."
            return result

    run = ReviewPipeline(RationaleBackend(count=3), run_metacheck=False).run(
        manuscript(tmp_path), output_dir=tmp_path / "out")
    assert not run.partial
    assert [f.status for f in run.findings] == ["contradicted", "unresolved", "llm_supported"]
    assert run.findings[0].rationale == "24 of 60 is 4%, so attrition is negligible."
    assert run.findings[2].editorial_disposition == "publish"
    markdown = (tmp_path / "out" / "review.md").read_text()
    published = markdown.split("## Concerns the verifier could not confirm")[0]
    assert "40%; the denominator matters" in published
    assert "4%, so attrition" not in published
    assert "Proposed response withheld" in published


def test_source_followup_receives_and_reassesses_the_full_explanation(tmp_path):
    class RationaleRetryBackend(EvidenceBackend):
        def generate(self, instruction, evidence, response_model):
            result = super().generate(instruction, evidence, response_model)
            if response_model.__name__ == "DiscoveryResponse" and result.findings:
                result.findings[0].rationale = "This method guarantees unbiased estimates under attrition."
            if response_model.__name__ == "VerificationResponse":
                rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
                assert rows[0]["rationale"] == "This method guarantees unbiased estimates under attrition."
                if "SOURCE TASKS\n" in instruction:
                    assert "Reassess each complete claim and rationale" in instruction
                    result.decisions[0].status = "contradicted"
                    result.decisions[0].rationale = "The opened method does not guarantee the property asserted in the explanation."
                    result.decisions[0].external_checks[0].verdict = "refuted"
            return result

    run = ReviewPipeline(RationaleRetryBackend(count=1, external=True), run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "out")
    assert not run.partial and run.findings[0].status == "contradicted"
    assert run.findings[0].editorial_disposition != "publish"
    assert [task.lookup_recorded for task in run.source_tasks] == [False, True]
    assert run.source_tasks[-1].check == "refuted"


def test_concurrent_stages_keep_their_own_tool_calls_and_match_a_sequential_run(tmp_path):
    import threading
    import time

    class ConcurrentBackend(EvidenceBackend):
        active = peak = 0
        lock = threading.Lock()

        def generate(self, instruction, evidence, response_model):
            if response_model.__name__ == "DiscoveryResponse":
                with self.lock:
                    type(self).active += 1
                    type(self).peak = max(type(self).peak, type(self).active)
                time.sleep(0.05)
                topic = requested_checks(instruction)[0]
                self._record([ToolCall(backend="codex", sequence=0, kind="exec", name="shell",
                                       command=f"echo {topic}", output=topic, timestamp=datetime.now(timezone.utc))])
                with self.lock:
                    type(self).active -= 1
            return super().generate(instruction, evidence, response_model)

        def _record(self, calls):
            self._tool_calls.extend(calls)

    source = manuscript(tmp_path)
    concurrent = ReviewPipeline(ConcurrentBackend(count=2), run_metacheck=False, parallel=4).run(source, output_dir=tmp_path / "a")
    assert ConcurrentBackend.peak > 1
    for stage in concurrent.stages:
        if stage.name.startswith("review-") and stage.name != "review-blind_spots":
            module = stage.name.removeprefix("review-")
            assert [c.output for c in stage.tool_calls] == [TOPICS[module][0]], stage.name
            assert stage.status == "completed"
    sequential = ReviewPipeline(ConcurrentBackend(count=2), run_metacheck=False, parallel=1).run(source, output_dir=tmp_path / "b")
    assert [f.id for f in concurrent.candidates] == [f.id for f in sequential.candidates]
    assert [s.name for s in concurrent.stages] == [s.name for s in sequential.stages]
