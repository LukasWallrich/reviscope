from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from .backend import Backend, CodexBackend
from .ingest import ingest
from .render import render_all
from .schemas import Evidence, Finding, Profile, ReviewRun, RunMetadata, SourceDocument, StageRecord, StudyMap


class FindingsResponse(BaseModel):
    findings: list[Finding] = Field(max_length=5)


class VerificationDecision(BaseModel):
    finding_id: str
    status: Literal["supported", "contradicted", "unresolved"]
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class VerificationResponse(BaseModel):
    decisions: list[VerificationDecision]


class EditorialDecision(BaseModel):
    finding_id: str
    disposition: Literal["keep", "merge", "reject", "needs_review"]
    reason: str
    target_id: str | None = None


class EditorialResponse(BaseModel):
    decisions: list[EditorialDecision]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _load_profile(profile: str | Path | Profile) -> tuple[Profile, str]:
    if isinstance(profile, Profile):
        return profile, _hash(profile.model_dump())
    path = Path(profile)
    if path.is_dir():
        from .profiles import load_profile_path

        value = load_profile_path(path)
        return value, _hash(value.model_dump())
    if path.is_file():
        if path.suffix.lower() == ".json":
            value = Profile.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            value = Profile.from_path(path)
        return value, _hash(value.model_dump())
    try:
        from .profiles import load_profile
    except ImportError as exc:
        raise ValueError(f"Profile {profile!r} is not a file and no bundled profile loader is installed") from exc
    value = load_profile(str(profile))
    return value, _hash(value.model_dump())


class ReviewPipeline:
    STAGE_VERSION = "alpha-2"

    def __init__(self, backend: Backend | None = None, profile: str | Path | Profile = "social_psychology", verifier_backend: Backend | None = None, progress: Callable[[str], None] | None = None, max_findings: int = 12):
        self.backend = backend or CodexBackend(model="gpt-5.6-luna", effort="max")
        self.verifier_backend = verifier_backend or self.backend
        self.progress = progress or (lambda _: None)
        if max_findings < 1:
            raise ValueError("max_findings must be positive")
        self.max_findings = max_findings
        self.profile, self.profile_hash = _load_profile(profile)

    @staticmethod
    def _evidence(sources: list[SourceDocument]) -> str:
        chunks = []
        for source in sources:
            chunks.append(f"SOURCE_ID: {source.id}\nTYPE: {source.kind}\nCONTENT BEGIN\n{source.text}\nCONTENT END")
        return "\n\n".join(chunks)

    def _cached(self, out: Path, name: str, inputs: object, model_type: type[BaseModel], fn: Callable[[], BaseModel], backend_identity: str | None = None) -> tuple[BaseModel, StageRecord]:
        components = {"stage": name, "version": self.STAGE_VERSION, "schema_hash": _hash(model_type.model_json_schema()), "inputs": inputs, "backend": backend_identity or self.backend.identity, "profile": self.profile_hash}
        key = _hash(components)
        artifact = out / "stages" / f"{name}-{key}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.is_file():
            self.progress(f"{name}: cache hit")
            return model_type.model_validate_json(artifact.read_text()), StageRecord(name=name, status="cached", cache_key=key, artifact=str(artifact), key_components=components)
        self.progress(f"{name}: started")
        started = time.monotonic()
        value = fn()
        payload = value.model_dump_json(indent=2)
        fd, temporary = tempfile.mkstemp(prefix=f".{name}-", suffix=".json", dir=artifact.parent)
        verification_artifact: str | None = None
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temporary, artifact)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.progress(f"{name}: completed in {time.monotonic() - started:.1f}s")
        return value, StageRecord(name=name, status="completed", cache_key=key, artifact=str(artifact), key_components=components)

    def run(self, manuscript: str | Path, *, supplements: list[str | Path] | None = None, preregistrations: list[str | Path] | None = None, output_dir: str | Path = "review-run") -> ReviewRun:
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        sources = [ingest(manuscript)]
        sources += [ingest(p, "supplement") for p in supplements or []]
        sources += [ingest(p, "preregistration") for p in preregistrations or []]
        input_hash = _hash([(s.kind, s.sha256) for s in sources])
        metadata = RunMetadata(run_id=input_hash[:12], backend=self.backend.name, model=self.backend.model, effort=self.backend.effort,
                               verifier_backend=self.verifier_backend.name, verifier_model=self.verifier_backend.model,
                               verifier_effort=self.verifier_backend.effort, profile=self.profile.id, profile_hash=self.profile_hash,
                               input_hash=input_hash, output_dir=str(out))
        run = ReviewRun(metadata=metadata, sources=sources)
        for source in sources:
            run.coverage.extend(f"{source.id}: {warning}" for warning in source.extraction_warnings)
            if source.extraction_warnings:
                run.partial = True
        evidence = self._evidence(sources)
        if len(evidence) > 150_000:
            run.coverage.append(f"Long-context review: {len(evidence):,} extracted characters were supplied without truncation; backend context limits may cause explicit stage failures.")
        try:
            result, stage = self._cached(out, "study_map", {"sources": input_hash}, StudyMap, lambda: self.backend.generate("Extract the research question, claimed contribution, overall design, distinct studies, and concrete evidence-based strengths. Do not make external novelty claims. Anchor claims in exact quotations with valid SOURCE_ID values. This is descriptive synthesis, not fault-finding.", evidence, StudyMap))
            run.study_map = result  # type: ignore[assignment]
            run.stages.append(stage)
        except Exception as exc:
            self.progress(f"study_map: failed ({type(exc).__name__})")
            run.partial = True
            run.stages.append(StageRecord(name="study_map", status="failed", error=f"{type(exc).__name__}: {exc}"))
        for module in self.profile.modules:
            prompt = self.profile.module_prompts.get(module)
            if not prompt:
                run.partial = True
                run.coverage.append(f"{module}: not assessed (profile has no prompt)")
                run.stages.append(StageRecord(name=f"review-{module}", status="skipped", error="No module prompt"))
                continue
            try:
                module_evidence = f"STUDY MAP\n{run.study_map.model_dump_json()}\n\n{evidence}"
                result, stage = self._cached(out, f"review-{module}", {"sources": input_hash, "upstream": _hash(run.study_map.model_dump()), "prompt": prompt}, FindingsResponse, lambda p=prompt, e=module_evidence: self.backend.generate(p + "\nReturn zero to five prioritized findings. Every finding must cite exact evidence and use a valid SOURCE_ID.", e, FindingsResponse))
                for position, finding in enumerate(result.findings):  # type: ignore[attr-defined]
                    run.candidates.append(finding.model_copy(update={"id": f"{module}:{position}:{finding.id or 'finding'}", "module": module, "status": "candidate", "confidence": None, "verification": None, "editorial_disposition": "publish", "editorial_reason": None, "merged_into": None}))
                run.stages.append(stage)
                run.coverage.append(f"{module}: assessed")
            except Exception as exc:
                self.progress(f"review-{module}: failed ({type(exc).__name__})")
                run.partial = True
                run.coverage.append(f"{module}: not assessed (stage failed)")
                run.stages.append(StageRecord(name=f"review-{module}", status="failed", error=f"{type(exc).__name__}: {exc}"))
        try:
            from .checks import run_statistical_checks

            self.progress("statistical-checks: started")
            started_checks = time.monotonic()
            check_report = run_statistical_checks([s.model_dump() for s in sources])
            check_components = {"stage": "statistical-checks", "version": self.STAGE_VERSION, "sources": input_hash, "checker": "reported-statistics-v1"}
            check_key = _hash(check_components)
            check_artifact = out / "stages" / f"statistical-checks-{check_key}.json"
            check_artifact.parent.mkdir(parents=True, exist_ok=True)
            if not check_artifact.exists():
                fd, temporary = tempfile.mkstemp(prefix=".statistical-checks-", suffix=".json", dir=check_artifact.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(check_report.to_dict(), handle, indent=2)
                    os.replace(temporary, check_artifact)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            run.coverage.append(f"statistical arithmetic: checked {check_report.coverage.checked} of {check_report.coverage.eligible} eligible reports")
            for position, item in enumerate(check_report.findings):
                if item.consistent is False:
                    source = next(s for s in sources if s.id == item.source_id)
                    run.candidates.append(Finding(id=f"statistical_check:{position}", module="statistical_check", claim="A reported test statistic and p-value may be arithmetically inconsistent under the checker's assumptions.", rationale=item.explanation, remedy="Verify the statistic, degrees of freedom, tail convention, and reported p-value against the analysis output.", severity="major", evidence=[{"source_id": source.id, "quote": item.reported}], status="candidate", verification=f"Deterministic screening recomputed p={item.computed_p:.6g}; independent verification is still required."))
            run.stages.append(StageRecord(name="statistical-checks", status="completed", cache_key=check_key, artifact=str(check_artifact), key_components=check_components))
            self.progress(f"statistical-checks: completed in {time.monotonic() - started_checks:.1f}s")
        except Exception as exc:
            self.progress(f"statistical-checks: failed ({type(exc).__name__})")
            run.partial = True
            run.stages.append(StageRecord(name="statistical-checks", status="failed", error=f"{type(exc).__name__}: {exc}"))
        try:
            from .verification import verify_findings

            anchored = verify_findings(run.candidates, sources)
            pending = [f for f in anchored if f.status == "unresolved"]
            if pending:
                compact = [{"finding_id": f.id, "claim": f.claim, "quoted_evidence": [e.model_dump() for e in f.evidence]} for f in pending]
                instruction = "Independently verify each criticism using only its claim, quoted evidence, and the untrusted sources. Actively seek defeating context. Return one decision per finding_id; status must be supported, contradicted, or unresolved. Every supported decision must include at least one independently selected exact quotation with its valid source_id in evidence; supported with empty evidence is forbidden. Evidence may be empty for contradicted or unresolved decisions. Do not assess severity and do not rely on the generating rationale.\n\nCANDIDATES\n" + _canonical(compact)
                verification, stage = self._cached(out, "verification", {"upstream": _hash([f.model_dump() for f in anchored]), "prompt": self.profile.verification_prompt}, VerificationResponse, lambda: self.verifier_backend.generate(instruction + "\nDISCIPLINE RULES\n" + self.profile.verification_prompt, evidence, VerificationResponse), self.verifier_backend.identity)
                verification_artifact = stage.artifact
                decisions = {d.finding_id: d.model_dump() for d in verification.decisions}  # type: ignore[attr-defined]
                returned_ids = [d.finding_id for d in verification.decisions]  # type: ignore[attr-defined]
                expected_ids = {f.id for f in pending}
                if len(returned_ids) != len(set(returned_ids)) or not set(returned_ids) <= expected_ids:
                    raise ValueError("Verifier returned duplicate or unknown finding IDs")
                missing_ids = expected_ids - set(returned_ids)
                if missing_ids and self.verifier_backend.name != "fixture":
                    if stage.artifact:
                        Path(stage.artifact).unlink(missing_ok=True)
                    raise ValueError(f"Verifier omitted finding IDs: {', '.join(sorted(missing_ids))}")
                run.findings = verify_findings(run.candidates, sources, decisions)
                run.stages.append(stage)
            else:
                run.findings = anchored
                run.stages.append(StageRecord(name="verification", status="completed"))
        except ImportError:
            run.findings = [f.model_copy(update={"status": "unverified", "verification": "Verification component unavailable."}) for f in run.candidates]
            run.partial = True
            run.stages.append(StageRecord(name="verification", status="skipped", error="Verification component unavailable"))
        except Exception as exc:
            if verification_artifact:
                Path(verification_artifact).unlink(missing_ok=True)
            self.progress(f"verification: failed ({type(exc).__name__})")
            run.findings = [f.model_copy(update={"status": "unverified", "verification": f"Verification failed: {type(exc).__name__}: {exc}"}) for f in run.candidates]
            run.partial = True
            run.stages.append(StageRecord(name="verification", status="failed", error=f"{type(exc).__name__}: {exc}"))
        editorial_artifact: str | None = None
        try:
            editorial_input = [f.model_dump() for f in run.findings]
            if self.backend.name == "fixture":
                self.progress("editorial: started")
                decisions = EditorialResponse(decisions=[])
                stage = StageRecord(name="editorial", status="completed")
            else:
                instruction = self.profile.editorial_prompt + "\nReturn a decision for every finding. disposition must be keep, merge, reject, or needs_review. A merge requires target_id. Do not change verification status, finding IDs, or substantive text.\nFINDINGS\n" + _canonical(editorial_input)
                decisions, stage = self._cached(out, "editorial", {"upstream": _hash(editorial_input), "rules": self.profile.editorial_prompt}, EditorialResponse, lambda: self.backend.generate(instruction, "No additional manuscript evidence is supplied at editorial stage.", EditorialResponse))
                editorial_artifact = stage.artifact
            editorial_rows = decisions.decisions  # type: ignore[attr-defined]
            finding_ids = {f.id for f in run.findings}
            if len({d.finding_id for d in editorial_rows}) != len(editorial_rows) or any(d.finding_id not in finding_ids for d in editorial_rows):
                raise ValueError("Editorial stage returned duplicate or unknown finding IDs")
            by_id = {d.finding_id: d for d in editorial_rows}
            if self.backend.name != "fixture" and set(by_id) != finding_ids:
                raise ValueError("Editorial stage omitted one or more finding IDs")
            for decision in editorial_rows:
                if decision.disposition == "merge":
                    target = by_id.get(decision.target_id or "")
                    if not decision.target_id or decision.target_id == decision.finding_id or decision.target_id not in finding_ids or (target and target.disposition in {"merge", "reject"}):
                        raise ValueError(f"Invalid or chained editorial merge target for {decision.finding_id}")
            groups: dict[tuple[str, str | None], list[Finding]] = {}
            for finding in run.findings:
                groups.setdefault((" ".join(finding.claim.lower().split()), finding.study_id), []).append(finding)
            epistemic_rank = {"recomputed": 5, "verified_deterministic": 5, "supported": 4, "llm_supported": 4, "unresolved": 2, "candidate": 1, "unverified": 0, "contradicted": -1}
            duplicate_winner = {key: max(items, key=lambda f: (epistemic_rank.get(f.status, 0), len(f.evidence), f.id)).id for key, items in groups.items()}
            finding_by_id = {f.id: f for f in run.findings}
            edited: list[Finding] = []
            for finding in run.findings:
                key = (" ".join(finding.claim.lower().split()), finding.study_id)
                decision = by_id.get(finding.id)
                disposition, reason, merged_into = "publish", None, None
                if duplicate_winner[key] != finding.id:
                    disposition, merged_into = "merged", duplicate_winner[key]
                    reason = f"Exact duplicate of {merged_into}."
                elif decision and decision.disposition in {"merge", "reject"}:
                    if decision.disposition == "merge":
                        if not decision.target_id or decision.target_id == finding.id or decision.target_id not in {f.id for f in run.findings}:
                            raise ValueError(f"Invalid editorial merge target for {finding.id}")
                        target_finding = finding_by_id[decision.target_id]
                        target_key = (" ".join(target_finding.claim.lower().split()), target_finding.study_id)
                        if duplicate_winner[target_key] != decision.target_id:
                            raise ValueError(f"Editorial merge target {decision.target_id} is itself an exact duplicate")
                        disposition, merged_into = "merged", decision.target_id
                    else:
                        disposition = "rejected"
                    reason = decision.reason
                else:
                    if decision:
                        reason = decision.reason
                edited.append(finding.model_copy(update={"editorial_disposition": disposition, "editorial_reason": reason, "merged_into": merged_into}))
            run.findings = edited
            rank = {"critical": 0, "major": 1, "minor": 2}
            protected_targets = {f.merged_into for f in run.findings if f.editorial_disposition == "merged" and f.merged_into}
            publishable = sorted((f for f in run.findings if f.editorial_disposition == "publish" and f.status != "contradicted"), key=lambda f: (0 if f.id in protected_targets else 1, rank[f.severity.value], f.id))
            if len(protected_targets) > self.max_findings:
                raise ValueError("Editorial merge targets exceed the configured publication cap")
            overflow = {f.id for f in publishable[self.max_findings:]}
            run.findings = [f.model_copy(update={"editorial_disposition": "cap", "editorial_reason": f"Below configured top-{self.max_findings} publication cap."}) if f.id in overflow else f for f in run.findings]
            final_by_id = {f.id: f for f in run.findings}
            for finding in run.findings:
                if finding.editorial_disposition == "merged":
                    target = final_by_id.get(finding.merged_into or "")
                    if target is None or target.editorial_disposition != "publish" or target.status == "contradicted":
                        raise ValueError(f"Merged finding {finding.id} points to a non-publishable target")
            run.stages.append(stage)
            if self.backend.name == "fixture":
                self.progress("editorial: completed in 0.0s")
        except Exception as exc:
            if editorial_artifact:
                Path(editorial_artifact).unlink(missing_ok=True)
            self.progress(f"editorial: failed ({type(exc).__name__})")
            run.partial = True
            run.stages.append(StageRecord(name="editorial", status="failed", error=f"{type(exc).__name__}: {exc}"))
        self.progress("render: started")
        render_all(run, out)
        self.progress("render: completed")
        return run


def review(manuscript: str | Path, **kwargs: object) -> ReviewRun:
    backend = kwargs.pop("backend", None)
    profile = kwargs.pop("profile", "social_psychology")
    verifier_backend = kwargs.pop("verifier_backend", None)
    progress = kwargs.pop("progress", None)
    max_findings = kwargs.pop("max_findings", 12)
    return ReviewPipeline(backend=backend, profile=profile, verifier_backend=verifier_backend,
                          progress=progress, max_findings=max_findings).run(manuscript, **kwargs)
