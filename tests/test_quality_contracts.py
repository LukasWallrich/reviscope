from __future__ import annotations

import json
import re

from reviscope.backend import Backend
from reviscope.pipeline import ReviewPipeline
from reviscope.profiles import load_profile
from reviscope.schemas import Evidence, Finding, Profile, StudyMap


_DEFAULT_OVERVIEW = object()


class QualityBackend(Backend):
    name = "quality"

    def __init__(self, *, model="generator", findings=(), verification=None, editorial=None,
                 fail_verification=False, fail_editorial=False, reconciled_overview=_DEFAULT_OVERVIEW):
        self.model, self.effort = model, "high"
        self.findings = list(findings)
        self.verification = verification
        self.editorial = editorial
        self.fail_verification, self.fail_editorial = fail_verification, fail_editorial
        self.reconciled_overview = ({"design_summary": "d", "contribution_summary": "c", "strengths": []}
                                    if reconciled_overview is _DEFAULT_OVERVIEW else reconciled_overview)
        self.instructions = []

    def generate(self, instruction, evidence, response_model):
        self.instructions.append((response_model.__name__, instruction))
        name = response_model.__name__
        if name == "StudyMap":
            return StudyMap(studies=[], research_question="q", design_summary="d",
                            contribution_summary="c", strengths=[])
        if name == "FindingsResponse":
            source_id = re.search(r"SOURCE_ID:\s*(\S+)", evidence).group(1)
            rows = []
            for row in self.findings:
                value = dict(row)
                value["evidence"] = [{"source_id": source_id, "quote": value.pop("quote", "Evidence A.")}]
                rows.append(value)
            return response_model.model_validate({"findings": rows})
        if name == "VerificationResponse":
            if self.fail_verification:
                raise RuntimeError("verifier unavailable")
            candidates = json.loads(instruction.split("CANDIDATES\n", 1)[1].split("\nDISCIPLINE RULES", 1)[0])
            rows = self.verification(candidates) if callable(self.verification) else self.verification
            return response_model.model_validate({"decisions": rows or []})
        if name == "EditorialResponse":
            if self.fail_editorial:
                raise RuntimeError("editor unavailable")
            findings = json.loads(instruction.split("FINDINGS\n", 1)[1])
            rows = self.editorial(findings) if callable(self.editorial) else self.editorial
            return response_model.model_validate({"decisions": rows or [], "reconciled_overview": self.reconciled_overview})
        raise AssertionError(name)


def paper(tmp_path, extra=""):
    path = tmp_path / "paper.md"
    path.write_text("Evidence A. Evidence B. " + "Substantive manuscript context. " * 45 + extra)
    return path


def one_module():
    return Profile(id="quality", title="Quality", modules=["review"],
                   module_prompts={"review": "review"}, verification_prompt="verify",
                   editorial_prompt="edit", metadata={"severity_guidance": {
                       "minor": "localized", "major": "changes a central inference",
                       "critical": "invalidates a central result"}})


def candidate(identifier, severity="major", quote="Evidence A."):
    return {"id": identifier, "module": "x", "claim": f"Claim {identifier}",
            "rationale": "reason", "remedy": "response", "severity": severity,
            "status": "candidate", "quote": quote}


def decision(item, status="supported"):
    quote = item["quoted_evidence"][0]
    return {"finding_id": item["finding_id"], "status": status, "rationale": "checked",
            "evidence": [quote] if status == "supported" else [],
            "remedy_status": "supported", "remedy_rationale": "proportionate"}


def keep_all(rows):
    return [{"finding_id": row["id"], "disposition": "keep", "reason": "retain", "target_id": None}
            for row in rows]


def test_verifier_exception_yields_rendered_partial_audit(tmp_path):
    generator = QualityBackend(findings=[candidate("a")], editorial=keep_all)
    verifier = QualityBackend(model="verifier", fail_verification=True)
    run = ReviewPipeline(generator, one_module(), verifier).run(paper(tmp_path), output_dir=tmp_path / "out")
    assert run.partial and (tmp_path / "out" / "review.json").is_file()
    assert next(stage for stage in run.stages if stage.name == "verification").status == "failed"
    assert run.metadata.verification_relationship == "not_run"
    assert all(item.editorial_disposition == "needs_review" for item in run.findings)
    assert "### Major:" not in (tmp_path / "out" / "review.md").read_text()


def test_editorial_exception_never_publishes_uncapped_unfiltered_findings(tmp_path):
    generator = QualityBackend(findings=[candidate("a"), candidate("b", quote="Evidence B.")],
                               fail_editorial=True)
    verifier = QualityBackend(model="verifier", verification=lambda rows: [decision(row) for row in rows])
    run = ReviewPipeline(generator, one_module(), verifier).run(paper(tmp_path), output_dir=tmp_path / "out")
    assert run.partial
    assert all(item.editorial_disposition == "needs_review" for item in run.findings)
    assert "### Major:" not in (tmp_path / "out" / "review.md").read_text()


def test_effective_v2_severity_guidance_reaches_generation_and_editor(tmp_path):
    backend = QualityBackend(findings=[], editorial=[])
    ReviewPipeline(backend, load_profile("social_psychology_v2"), backend).run(
        paper(tmp_path), output_dir=tmp_path / "out")
    generation = "\n".join(text for kind, text in backend.instructions if kind == "FindingsResponse")
    assert "invalidates a central result" in generation
    assert "return zero findings" in generation.lower()


def test_merge_cannot_move_supported_finding_into_lower_support_target(tmp_path):
    generator = QualityBackend(findings=[candidate("strong"), candidate("weak", quote="Evidence B.")])
    def verify(rows):
        return [decision(rows[0], "supported"), decision(rows[1], "unresolved")]
    def edit(rows):
        return [
            {"finding_id": rows[0]["id"], "disposition": "merge", "reason": "combine", "target_id": rows[1]["id"]},
            {"finding_id": rows[1]["id"], "disposition": "keep", "reason": "target", "target_id": None},
        ]
    generator.editorial = edit
    run = ReviewPipeline(generator, one_module(), QualityBackend(model="verifier", verification=verify)).run(
        paper(tmp_path), output_dir=tmp_path / "out")
    strong = next(item for item in run.findings if "strong" in item.id)
    assert strong.editorial_disposition == "needs_review" and strong.merged_into is None


def test_publication_cap_prioritizes_support_before_severity(tmp_path):
    generator = QualityBackend(findings=[candidate("weak", "major"),
                                         candidate("strong", "minor", "Evidence B.")], editorial=keep_all)
    verifier = QualityBackend(model="verifier", verification=lambda rows: [
        decision(rows[0], "unresolved"), decision(rows[1], "supported")])
    run = ReviewPipeline(generator, one_module(), verifier, max_findings=1).run(
        paper(tmp_path), output_dir=tmp_path / "out")
    published = [item for item in run.findings if item.editorial_disposition == "publish"]
    assert len(published) == 1 and "strong" in published[0].id


def test_uncertain_statistical_screening_lead_is_not_automatically_major(tmp_path):
    manuscript = paper(tmp_path, " Reported result: t(18) = 2.10, p = .90.")
    backend = QualityBackend(findings=[], editorial=keep_all)
    run = ReviewPipeline(backend, Profile(id="stats", title="Stats", modules=[]),
                         QualityBackend(model="verifier", verification=lambda rows: [decision(row) for row in rows])).run(
        manuscript, output_dir=tmp_path / "out")
    lead = next(item for item in run.candidates if item.module == "statistical_check")
    assert lead.severity.value == "minor"


def test_editorial_reconciles_overview_while_preserving_preliminary_map(tmp_path):
    generator = QualityBackend(findings=[candidate("a")], editorial=keep_all,
                               reconciled_overview={"design_summary": "Qualified design account.",
                                                    "contribution_summary": "Contribution after assessment.",
                                                    "strengths": ["A supported strength."]})
    verifier = QualityBackend(model="verifier", verification=lambda rows: [decision(row) for row in rows])
    run = ReviewPipeline(generator, one_module(), verifier).run(paper(tmp_path), output_dir=tmp_path / "out")
    assert run.preliminary_study_map is not None
    assert run.preliminary_study_map.design_summary == "d"
    assert run.study_map.design_summary == "Qualified design account."
    assert run.study_map.strengths == ["A supported strength."]


def test_nonfixture_editor_must_return_reconciled_overview(tmp_path):
    generator = QualityBackend(findings=[candidate("a")], editorial=keep_all, reconciled_overview=None)
    verifier = QualityBackend(model="verifier", verification=lambda rows: [decision(row) for row in rows])
    run = ReviewPipeline(generator, one_module(), verifier).run(paper(tmp_path), output_dir=tmp_path / "out")
    assert run.partial
    assert next(item for item in run.stages if item.name == "editorial").status == "failed"
    assert all(item.editorial_disposition == "needs_review" for item in run.findings)


def test_reconciliation_cannot_erase_preliminary_nonnull_summary(tmp_path):
    generator = QualityBackend(findings=[candidate("a")], editorial=keep_all,
                               reconciled_overview={"design_summary": None,
                                                    "contribution_summary": "c",
                                                    "strengths": []})
    verifier = QualityBackend(model="verifier", verification=lambda rows: [decision(row) for row in rows])
    run = ReviewPipeline(generator, one_module(), verifier).run(paper(tmp_path), output_dir=tmp_path / "out")
    assert run.partial
    assert next(item for item in run.stages if item.name == "editorial").status == "failed"
