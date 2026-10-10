from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field, model_validator

from .backend import REVIEW_GUARD, Backend, CodexBackend
from .ingest import ingest
from .render import finding_order, render_all
from .reasoning import REASONING_ASSESSMENT
from . import metacheck
from .discovery import BLIND_SPOT_PROMPT, BLIND_SPOTS, DiscoveryResponse, discovery_instruction, validate_discovery
from .schemas import SUPPORTED_STATUSES, Evidence, ExternalCheck, ExternalSourceTask, Finding, MergedPoint, MetacheckRecord, Profile, ReviewRun, RunMetadata, Severity, SourceDocument, StageProvenance, StageRecord, StudyMap


class VerificationDecision(BaseModel):
    finding_id: str
    status: Literal["supported", "contradicted", "unresolved"]
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)
    external_checks: list[ExternalCheck] = Field(default_factory=list)
    external_dependency: Literal["required", "optional"] = "required"
    external_dependency_rationale: str = ""
    remedy_status: Literal["supported", "overreaching", "unresolved"] = "unresolved"
    remedy_rationale: str = ""


class VerificationResponse(BaseModel):
    decisions: list[VerificationDecision]


class EditorialDecision(BaseModel):
    finding_id: str
    disposition: Literal["keep", "merge", "reject", "needs_review"]
    reason: str
    target_id: str | None = None
    severity: Severity | None = None
    priority: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _keep_severity(self) -> "EditorialDecision":
        if self.disposition == "keep" and self.severity is None:
            raise ValueError("Editorial keep decisions require severity")
        return self


class ReconciledOverview(BaseModel):
    design_summary: str | None
    contribution_summary: str | None
    strengths: list[str]


class EditorialResponse(BaseModel):
    decisions: list[EditorialDecision]
    reconciled_overview: ReconciledOverview | None = None




def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _write_atomic(path: Path, payload: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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


# Format of the tool-call sidecars and the event parsing behind them; a change invalidates cached stages.
PROVENANCE_VERSION = "3"

CLAIM_SCOPE = """Evaluate the complete claim at its stated scope; the kind label does not
override its wording or the discipline criteria. For defect, test whether the alleged
error is established. For specification_conflict, locate both passages and establish
that they refer to the same quantity or decision and conflict as written; determining
which implementation occurred is a separate allegation. For clarification_request,
check whether the named information is absent from the complete supplied material and
accessible linked methods, and whether it is needed for the specific assessment or
reproduction identified in the claim. Distinguish absence from inspected material from
absence everywhere. Do not demand proof of incorrect implementation to assess a bounded
reporting claim, or support a broader implementation allegation from an omission. An
inaccessible source essential to the claim leaves it unresolved. Missing information
without a specific assessment consequence is not automatically a supported criticism.
""" + "When assessing a criticism about a manuscript inference, apply the following criteria to the criticized connection and the criticism itself. These are assessment criteria, not requests to add output fields.\n" + REASONING_ASSESSMENT


class ReviewPipeline:
    STAGE_VERSION = "0.4.3a1"  # cache semantics of stages; bump only when a stage's behaviour changes

    def __init__(self, backend: Backend | None = None, profile: str | Path | Profile = "social_psychology", verifier_backend: Backend | None = None, progress: Callable[[str], None] | None = None, run_metacheck: bool = True, parallel: int = 4):
        self.backend = backend or CodexBackend(model="gpt-6-luna", effort="high")
        self.verifier_backend = verifier_backend or self.backend
        if not all(getattr(b, "tools", True) for b in (self.backend, self.verifier_backend)):
            raise ValueError("Review stages run only on tool-enabled backends; tools=False is for judges and normalizers")
        self.progress = progress or (lambda _: None)
        self.profile, self.profile_hash = _load_profile(profile)
        self.run_metacheck = run_metacheck
        if parallel < 1:
            raise ValueError("parallel must be at least 1")
        self.parallel = parallel
        self._prefetched: dict[str, tuple[BaseModel, StageRecord] | BaseException] = {}

    @staticmethod
    def _evidence(sources: list[SourceDocument]) -> str:
        chunks = []
        for source in sources:
            chunks.append(f"SOURCE_ID: {source.id}\nTYPE: {source.kind}\nCONTENT BEGIN\n{source.text}\nCONTENT END")
        return "\n\n".join(chunks)

    def _cached(self, out: Path, name: str, inputs: object, model_type: type[BaseModel], fn: Callable[[], BaseModel], backend: Backend | None = None) -> tuple[BaseModel, StageRecord]:
        """Run or reuse one model stage. Tool calls are stored in a sidecar next to the artifact."""
        backend = backend or self.backend
        components = self._stage_components(name, inputs, model_type, backend)
        key = _hash(components)
        if key in self._prefetched:  # computed concurrently by _prefetch; keeps its original record
            outcome = self._prefetched.pop(key)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        artifact = out / "stages" / f"{name}-{key}.json"
        tools_artifact = artifact.with_suffix(".tools.json")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.is_file() and tools_artifact.is_file():  # a stage without its provenance sidecar is rerun
            self.progress(f"{name}: cache hit")
            recorded = StageProvenance.model_validate_json(tools_artifact.read_bytes())
            return model_type.model_validate_json(artifact.read_text()), StageRecord(name=name, status="cached", cache_key=key, artifact=str(artifact), key_components=components, duration_seconds=0, backend_version=recorded.backend_version, tool_calls=recorded.tool_calls)
        self.progress(f"{name}: started")
        started = time.monotonic()
        backend.take_tool_calls()
        try:
            value = fn()
        except Exception as exc:
            exc.tool_calls = [call.model_copy(update={"stage": name}) for call in backend.take_tool_calls()]  # type: ignore[attr-defined]
            raise
        calls = [call.model_copy(update={"stage": name}) for call in backend.take_tool_calls()]
        _write_atomic(tools_artifact, StageProvenance(backend_version=backend.version, tool_calls=calls).model_dump_json(indent=2))
        _write_atomic(artifact, value.model_dump_json(indent=2))
        elapsed = time.monotonic() - started
        self.progress(f"{name}: completed in {elapsed:.1f}s ({len(calls)} tool calls)")
        return value, StageRecord(name=name, status="completed", cache_key=key, artifact=str(artifact), key_components=components, duration_seconds=elapsed, backend_version=backend.version, tool_calls=calls)

    def _stage_components(self, name: str, inputs: object, model_type: type[BaseModel], backend: Backend) -> dict[str, object]:
        return {"stage": name, "version": self.STAGE_VERSION, "provenance": PROVENANCE_VERSION, "schema_hash": _hash(model_type.model_json_schema()), "inputs": inputs, "backend": backend.identity, "profile": self.profile_hash}

    def _prefetch(self, out: Path, jobs: list[tuple[str, object, type[BaseModel], Callable[[], BaseModel], Backend]]) -> None:
        """Run independent model stages concurrently. The sequential code that follows consumes each
        outcome through _cached, so ordering, failure handling and provenance stay unchanged."""
        if self.parallel < 2 or len(jobs) < 2:
            return
        def run_one(job: tuple[str, object, type[BaseModel], Callable[[], BaseModel], Backend]) -> None:
            name, inputs, model_type, fn, backend = job
            key = _hash(self._stage_components(name, inputs, model_type, backend))
            try:
                self._prefetched[key] = self._cached(out, name, inputs, model_type, fn, backend)
            except BaseException as exc:
                self._prefetched[key] = exc
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            list(pool.map(run_one, jobs))

    def _metacheck(self, manuscript: Path, out: Path, modules: list[str]) -> tuple[MetacheckRecord, str, dict[str, str]]:
        """Screening record, its fingerprint and the leads per review module. Screening never
        aborts the review: any error, including unreadable output, becomes a failed record."""
        if not self.run_metacheck:
            record = MetacheckRecord(status="skipped", reason="skipped by flag")
            return record, metacheck.fingerprint(record), {}
        self.progress("metacheck: started")
        started = time.monotonic()
        try:
            record = metacheck.run_metacheck(manuscript, out, self.progress)
        except Exception as exc:
            record = MetacheckRecord(status="failed", reason=f"{type(exc).__name__}: {exc}")
        try:
            result = record, metacheck.fingerprint(record), metacheck.leads(record, modules)
        except Exception as exc:
            record = MetacheckRecord(status="failed", reason=f"screening output unreadable: {type(exc).__name__}: {exc}", modules=record.modules)
            result = record, metacheck.fingerprint(record), {}
        self.progress(f"metacheck: {record.status} in {time.monotonic() - started:.1f}s")
        return result

    def _failed(self, name: str, exc: Exception, stage: StageRecord | None = None) -> StageRecord:
        """Failed-stage record keeping the tool calls of the model call, including when the call
        returned but its output was rejected afterwards (`stage`)."""
        self.progress(f"{name}: failed ({type(exc).__name__})")
        calls = getattr(exc, "tool_calls", None) or (stage.tool_calls if stage else [])
        backend = self.verifier_backend if name.startswith("verification-") else self.backend
        return StageRecord(name=name, status="failed", error=f"{type(exc).__name__}: {exc}", tool_calls=calls,
                           backend_version=stage.backend_version if stage else backend.version)

    def run(self, manuscript: str | Path, *, supplements: list[str | Path] | None = None, preregistrations: list[str | Path] | None = None, output_dir: str | Path = "review-run") -> ReviewRun:
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        sources = [ingest(manuscript)]
        sources += [ingest(p, "supplement") for p in supplements or []]
        sources += [ingest(p, "preregistration") for p in preregistrations or []]
        input_hash = _hash([(s.kind, s.sha256, _hash(s.text)) for s in sources])
        metadata = RunMetadata(run_id=input_hash[:12], backend=self.backend.name, model=self.backend.model, effort=self.backend.effort,
                               verifier_backend=self.verifier_backend.name, verifier_model=self.verifier_backend.model,
                               verifier_effort=self.verifier_backend.effort,
                               verification_relationship=("deterministic_fixture" if self.backend.name == "fixture" else
                                                          "same_model_separate_call" if (self.backend.name, self.backend.model) == (self.verifier_backend.name, self.verifier_backend.model) else
                                                          "different_model_same_family" if self.backend.name == self.verifier_backend.name else
                                                          "different_model_family"),
                               profile=self.profile.id, profile_hash=self.profile_hash,
                               input_hash=input_hash, output_dir=str(out))
        run = ReviewRun(metadata=metadata, sources=sources)
        for source in sources:
            run.coverage.extend(f"{source.id}: {warning}" for warning in source.extraction_warnings)
            if source.extraction_warnings:
                run.partial = True
        evidence = self._evidence(sources)
        if len(evidence) > 150_000:
            run.coverage.append(f"Long-context review: {len(evidence):,} extracted characters were supplied without truncation; backend context limits may cause explicit stage failures.")
        manuscript_chars = sum(len(source.text.strip()) for source in sources if source.kind == "manuscript")
        insufficient = self.backend.name in {"codex", "claude"} and manuscript_chars < 1000 and not any(source.kind != "manuscript" for source in sources)
        self._study_map(run, out, input_hash, evidence)
        if insufficient:
            run.partial = True
            excerpt = next(source for source in sources if source.kind == "manuscript").text.strip()[:300]
            run.candidates.append(Finding(id="intake:insufficient-material", module="intake", claim="The supplied material is incomplete for a substantive peer review.", rationale=f"Only {manuscript_chars} manuscript characters were available, which is insufficient to assess design, measurement, results, and interpretation.", remedy="Supply the complete manuscript and any relevant supplements or preregistration.", severity="minor", evidence=[{"source_id": sources[0].id, "quote": excerpt}], status="verified_deterministic", verification="This is an intake limitation, determined from extracted input length, rather than a methodological criticism."))
            run.coverage.append("intake: insufficient manuscript material; discovery was not run")
        modules = [*self.profile.modules, BLIND_SPOTS]
        if insufficient:
            skipped = MetacheckRecord(status="skipped", reason="skipped: insufficient manuscript material")
            run.metacheck, metacheck_fingerprint, leads = skipped, metacheck.fingerprint(skipped), {}
        else:
            run.metacheck, metacheck_fingerprint, leads = self._metacheck(Path(sources[0].path), out, modules)
        run.coverage.append(metacheck.describe(run.metacheck))
        run.coverage.extend(f"metacheck {m.module}: {warning[:200]}" for m in run.metacheck.modules if m.status == "partial" for warning in m.warnings)
        if run.metacheck.status == "failed":
            run.partial = True
        run.stages.append(StageRecord(name="metacheck", status={"completed": "completed", "partial": "completed", "failed": "failed"}.get(run.metacheck.status, "skipped"),
                                      artifact=run.metacheck.output_dir,
                                      error=None if run.metacheck.status == "completed" else run.metacheck.reason or metacheck.describe(run.metacheck)))
        run.coverage.extend(f"metacheck {m.module}: {m.n_filtered} of {m.n_rows} row(s) filtered as not a candidate ({m.filter_rule})"
                            for m in run.metacheck.modules if m.n_filtered)
        def discovery_job(module: str, prompt: str) -> tuple[str, object, type[BaseModel], Callable[[], BaseModel], Backend]:
            module_evidence = f"STUDY MAP\n{run.study_map.model_dump_json()}\n\n{evidence}"
            if module in leads:
                module_evidence += "\n\n" + leads[module]
            if module == BLIND_SPOTS:
                module_evidence += "\nEXISTING CANDIDATES\n" + _canonical([{"id": f.id, "claim": f.claim, "rationale": f.rationale} for f in run.candidates])
                module_evidence += "\nCOVERAGE LEDGER\n" + _canonical(run.coverage)
            severity_rules = _canonical(self.profile.metadata.get("severity_guidance", {}))
            final_instruction = discovery_instruction(module, prompt) + "\nSeverity guidance: " + severity_rules
            def generate_findings(p=final_instruction, e=module_evidence, m=module):
                value = self.backend.generate(p, e, DiscoveryResponse)
                raw_dir = out / "raw-discovery"
                raw_dir.mkdir(exist_ok=True)
                raw_key = _hash({"instruction": p, "evidence": e, "backend": self.backend.identity, "schema": DiscoveryResponse.model_json_schema()})
                (raw_dir / f"{m}-{raw_key}.json").write_text(value.model_dump_json(indent=2), encoding="utf-8")
                return validate_discovery(value, m, sources)
            inputs = {"sources": input_hash, "upstream": _hash(module_evidence), "instruction_hash": _hash(REVIEW_GUARD + final_instruction), "metacheck": metacheck_fingerprint, "leads": _hash(leads.get(module, ""))}
            return f"review-{module}", inputs, DiscoveryResponse, generate_findings, self.backend

        if not insufficient:  # profile modules are independent; the blind-spot pass needs their candidates
            self._prefetch(out, [discovery_job(m, self.profile.module_prompts[m]) for m in modules
                                 if m != BLIND_SPOTS and self.profile.module_prompts.get(m)])
        for module in modules:
            if insufficient:
                run.stages.append(StageRecord(name=f"review-{module}", status="skipped", error="Insufficient manuscript material"))
                continue
            prompt = BLIND_SPOT_PROMPT if module == BLIND_SPOTS else self.profile.module_prompts.get(module)
            if not prompt:
                run.partial = True
                run.coverage.append(f"{module}: not assessed (profile has no prompt)")
                run.stages.append(StageRecord(name=f"review-{module}", status="skipped", error="No module prompt"))
                continue
            try:
                name, inputs, model_type, generate_findings, backend = discovery_job(module, prompt)
                result, stage = self._cached(out, name, inputs, model_type, generate_findings, backend)
                result = validate_discovery(result, module, sources)
                run.coverage.extend(f"{module}/{c.check}: {c.status} — {c.rationale}" for c in result.checks)
                if result.search_incomplete or any(c.status == "not_checked" for c in result.checks):
                    run.coverage.append(f"{module}: discovery reported incomplete by the model or missing coverage entries")
                for position, finding in enumerate(result.findings):
                    run.candidates.append(Finding.model_validate({**finding.model_dump(),
                        "id": f"{module}:{position}:{finding.id or 'finding'}", "module": module}))
                run.stages.append(stage)
            except Exception as exc:
                run.partial = True
                run.coverage.append(f"{module}: not assessed (stage failed)")
                run.stages.append(self._failed(f"review-{module}", exc))
        return self._finalize(run, out, insufficient=insufficient)

    def _study_map(self, run: ReviewRun, out: Path, input_hash: str, evidence: str) -> None:
        try:
            study_instruction = "Extract the research question, claimed contribution, overall design, distinct studies, and concrete evidence-based strengths. Describe the contribution as the manuscript claims it; later stages assess novelty. Anchor claims in exact quotations with valid SOURCE_ID values. This is descriptive synthesis, not fault-finding."
            result, stage = self._cached(out, "study_map", {"sources": input_hash, "instruction_hash": _hash(REVIEW_GUARD + study_instruction)}, StudyMap, lambda: self.backend.generate(study_instruction, evidence, StudyMap))
            run.study_map = result  # type: ignore[assignment]
            run.preliminary_study_map = result.model_copy(deep=True)  # type: ignore[union-attr]
            run.stages.append(stage)
        except Exception as exc:
            run.partial = True
            run.stages.append(self._failed("study_map", exc))

    def _verification_job(self, batch: list[Finding], candidate_by_id: dict[str, Finding], evidence: str) -> tuple[list[dict[str, object]], str, dict[str, object], Callable[[], BaseModel]]:
        """Compact candidates, instruction, cache inputs and model call for one verification batch."""
        def quoted(f: Finding) -> list[dict[str, object]]:
            anchored_quotes = {(e.source_id, e.quote) for e in f.evidence}
            return [{"source_id": e.source_id, "quote": e.quote, "anchored": (e.source_id, e.quote) in anchored_quotes}
                    for e in candidate_by_id[f.id].evidence]
        compact = [{"finding_id": f.id, "module": f.module, "study_id": f.study_id, "claim": f.claim,
                    "kind": f.kind, "rationale": f.rationale, "remedy": f.remedy, "remedy_necessity": f.remedy_necessity, "quoted_evidence": quoted(f),
                    "external_evidence": [e.model_dump() for e in f.external_evidence]} for f in batch]
        instruction = "Run a separate verification pass for each criticism using its claim, explanatory rationale, proposed remedy, quoted evidence, cited external evidence, and the untrusted sources. Treat the generating rationale as untrusted assertions to check, never as evidence. Check every substantive factual premise, calculation, source attribution and inference in both the claim and rationale. Assess citation-claim agreement, causal and generalization claims, and the stated consequence of methodological or conceptual concerns at their actual scope. A plausible headline is insufficient when its rationale contains a false or unresolved substantive assertion; judge the complete criticism as written, without silently repairing or discarding its explanation. Supported requires the claim and its explanatory reasoning to be established; contradicted applies when a substantive assertion is refuted, and unresolved when a necessary premise cannot be settled. Reasoned methodological judgments and explicitly conditional concerns can be supported without proving an implementation error, provided their premises and scope are justified. Quoted evidence marked anchored=false was not found verbatim in its named source; locate the passage it refers to or disregard it. Actively seek defeating context. Open every cited external source (URL or DOI) with your tools and check that the quotation appears there and shows what is claimed; recompute any numerical claim with code. Classify external_dependency as required or optional and explain it in external_dependency_rationale. Use optional only when the complete claim and rationale as worded follow from anchored manuscript evidence and established methodological or disciplinary knowledge without relying on the cited external items; identify that evidence and knowledge explicitly. Familiarity with an unusual claim or with a specific source is not enough. A source-specific quotation, attribution, novelty claim, or unusual empirical assertion requires external verification. Attempt to open every source even when optional. If an inaccessible source is necessary to establish any substantive assertion in the claim or rationale, use unresolved; do not assert its contents from memory. Unchecked optional items are removed from the published finding. Refuted evidence blocks support even when labelled optional. For every cited external item return one external_checks entry with its URL or DOI as locator and a verdict: confirmed, refuted or not_found. Return one decision per finding_id; status must be supported, contradicted, or unresolved. Use unresolved when the sources and your checks can neither establish nor rule out the complete criticism, and state in rationale what would settle it: readers see that rationale next to unresolved concerns. Separately classify remedy_status as supported, overreaching, or unresolved and explain it in remedy_rationale. Check that the remedy addresses the established concern and is necessary and proportionate, and that its remedy_necessity label (essential, strengthening or extending) is accurate; a remedy labelled essential that the claims do not require is overreaching; an overreaching or unresolved remedy is withheld without invalidating an otherwise supported claim and rationale. Every supported claim decision must include in evidence the exact manuscript quotations, with valid source_id values, that you checked the claim against. Quote verbatim; mark an omission inside a quotation with an ellipsis (...). Evidence may be empty for contradicted or unresolved decisions. Do not assess severity or treat the generating rationale as evidence.\n\nCANDIDATES\n" + _canonical(compact)
        verification_instruction = instruction + "\nDISCIPLINE RULES\n" + self.profile.verification_prompt + "\n" + CLAIM_SCOPE
        inputs = {
            "upstream": _hash([f.model_dump() for f in batch]), "evidence": _hash(evidence),
            "instruction_hash": _hash(REVIEW_GUARD + verification_instruction)}
        return compact, verification_instruction, inputs, lambda: self.verifier_backend.generate(verification_instruction, evidence, VerificationResponse)

    def _finalize(self, run: ReviewRun, out: Path, *, insufficient: bool = False) -> ReviewRun:
        """Verify, edit and render a draft while retaining its discovery provenance."""
        sources = run.sources
        evidence = self._evidence(sources)
        from .verification import verify_findings

        run.candidates = [f.model_copy(update={"discovery_severity": f.discovery_severity or f.severity})
                          for f in run.candidates]
        anchored = verify_findings(run.candidates, sources)
        pending = [f for f in anchored if f.status == "unresolved"]
        if not pending:
            run.findings = anchored
            run.metadata.verification_relationship = "not_run"
            run.stages.append(StageRecord(name="verification", status="completed"))
        else:
            candidate_by_id = {f.id: f for f in run.candidates}
            verified_by_id = {f.id: f for f in anchored}
            groups: dict[str, list[Finding]] = {}
            for finding in pending:
                groups.setdefault(finding.module, []).append(finding)
            successful_batches = 0
            jobs = []
            for module, findings in groups.items():
                for offset in range(0, len(findings), 10):
                    _, _, inputs, verify_call = self._verification_job(findings[offset:offset + 10], candidate_by_id, evidence)
                    jobs.append((f"verification-{module}-{offset // 10 + 1}", inputs, VerificationResponse, verify_call, self.verifier_backend))
            self._prefetch(out, jobs)
            for module, findings in groups.items():
                for offset in range(0, len(findings), 10):
                    batch = findings[offset:offset + 10]
                    name = f"verification-{module}-{offset // 10 + 1}"
                    stage = None
                    try:
                        compact, verification_instruction, inputs, verify_call = self._verification_job(batch, candidate_by_id, evidence)
                        verification, stage = self._cached(out, name, inputs, VerificationResponse, verify_call, self.verifier_backend)
                        returned_ids = [d.finding_id for d in verification.decisions]
                        expected_ids = {f.id for f in batch}
                        if len(returned_ids) != len(set(returned_ids)) or not set(returned_ids) <= expected_ids:
                            raise ValueError("Verifier returned duplicate or unknown finding IDs")
                        missing_ids = expected_ids - set(returned_ids)
                        if missing_ids and self.verifier_backend.name != "fixture":
                            raise ValueError(f"Verifier omitted finding IDs: {', '.join(sorted(missing_ids))}")
                        decisions = {d.finding_id: d.model_dump() for d in verification.decisions}
                        verified = verify_findings([candidate_by_id[f.id] for f in batch], sources, decisions,
                                                   run.metadata.verification_relationship, stage.tool_calls)
                        verified_by_id.update({f.id: f for f in verified})
                        run.stages.append(stage)
                        self._source_tasks(run, name, [candidate_by_id[f.id] for f in batch], decisions, stage.tool_calls, verified)
                        self._finish_source_tasks(run, out, name, compact, verification_instruction, evidence,
                                                  candidate_by_id, verified, verified_by_id)
                        successful_batches += 1
                    except Exception as exc:
                        if stage and stage.artifact:
                            Path(stage.artifact).unlink(missing_ok=True)
                        run.partial = True
                        run.stages.append(self._failed(name, exc, stage))
                        for finding in batch:
                            verified_by_id[finding.id] = finding.model_copy(update={
                                "status": "unverified", "verification": f"Verification failed: {type(exc).__name__}: {exc}"})
            run.findings = [verified_by_id[f.id] for f in anchored]
            if not successful_batches:
                run.metadata.verification_relationship = "not_run"
        editorial_stage: StageRecord | None = None
        try:
            editorial_input = [f.model_dump() for f in run.findings]
            if insufficient:
                self.progress("editorial: skipped (insufficient material)")
                decisions = EditorialResponse(decisions=[], reconciled_overview=None)
                stage = StageRecord(name="editorial", status="skipped", error="Insufficient manuscript material")
            elif self.backend.name == "fixture":
                self.progress("editorial: started")
                decisions = EditorialResponse(decisions=[], reconciled_overview=None)
                stage = StageRecord(name="editorial", status="completed")
            else:
                instruction = self.profile.editorial_prompt + "\nSEVERITY GUIDANCE\n" + _canonical(self.profile.metadata.get("severity_guidance", {})) + "\nReturn a decision for every finding. disposition must be keep, merge, reject, or needs_review. A merge requires target_id. The number of published findings is not limited: never reject a finding or mark it needs_review because of how many other findings there are. Assign final severity and a positive integer priority for every keep decision, with all findings in view; lower priority numbers come first within each severity. Critical means a demonstrated error that invalidates a central result. Major means a supported issue that could change a central conclusion or its interpretation, an internal inconsistency affecting a reported result, or missing analysis or information without which a central claim cannot be assessed. Minor means a local, presentational or reporting issue without such consequence. Missing information is major only when a central claim cannot be assessed without it. Discovery severity is provisional and retained for audit. Severity never overrides verification status. The manuscript supplies context for the reconciled overview and proportionality, not a replacement verification pass. Keep distinct, proportionately stated supported findings under the editorial rules; do not override factual verification on a fresh substantive reading. If you identify a factual disagreement with verification, use needs_review and explain it for audit rather than silently rejecting it. Also return reconciled_overview: revise the preliminary design summary, contribution summary, and strengths only as needed to remove or qualify statements contradicted by supported findings. Preserve accurate statements and do not invent facts. Do not change verification status, finding IDs, or substantive text.\nPRELIMINARY STUDY MAP\n" + _canonical(run.study_map.model_dump()) + "\nFINDINGS\n" + _canonical(editorial_input)
                decisions, stage = self._cached(out, "editorial", {"upstream": _hash(editorial_input),
                    "evidence": _hash(evidence), "instruction_hash": _hash(REVIEW_GUARD + instruction)}, EditorialResponse,
                    lambda: self.backend.generate(instruction, evidence, EditorialResponse))
                editorial_stage = stage
            editorial_rows = decisions.decisions  # type: ignore[attr-defined]
            if not insufficient and self.backend.name != "fixture" and decisions.reconciled_overview is None:  # type: ignore[union-attr]
                raise ValueError("Editorial stage omitted the reconciled overview")
            if decisions.reconciled_overview is not None:  # type: ignore[union-attr]
                reconciled = decisions.reconciled_overview  # type: ignore[union-attr]
                if run.study_map.design_summary is not None and reconciled.design_summary is None:
                    raise ValueError("Editorial stage erased the preliminary design summary")
                if run.study_map.contribution_summary is not None and reconciled.contribution_summary is None:
                    raise ValueError("Editorial stage erased the preliminary contribution summary")
            finding_ids = {f.id for f in run.findings}
            if len({d.finding_id for d in editorial_rows}) != len(editorial_rows) or any(d.finding_id not in finding_ids for d in editorial_rows):
                raise ValueError("Editorial stage returned duplicate or unknown finding IDs")
            by_id = {d.finding_id: d for d in editorial_rows}
            if not insufficient and self.backend.name != "fixture" and set(by_id) != finding_ids:
                raise ValueError("Editorial stage omitted one or more finding IDs")
            groups: dict[tuple[str, str | None], list[Finding]] = {}
            for finding in run.findings:
                groups.setdefault((" ".join(finding.claim.lower().split()), finding.study_id), []).append(finding)
            epistemic_rank = {"recomputed": 5, "verified_deterministic": 5, "supported": 4, "llm_supported": 4, "unresolved": 2, "candidate": 1, "unverified": 0, "contradicted": -1}
            duplicate_winner = {key: max(items, key=lambda f: (epistemic_rank.get(f.status, 0),
                by_id.get(f.id) is not None and by_id[f.id].disposition == "keep", len(f.evidence), f.id)).id
                for key, items in groups.items()}
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
                        target_finding = finding_by_id.get(decision.target_id or "")
                        target_decision = by_id.get(decision.target_id or "")
                        valid_target = (target_finding is not None and decision.target_id != finding.id and
                                        target_decision is not None and target_decision.disposition == "keep" and
                                        epistemic_rank.get(target_finding.status, 0) >= epistemic_rank.get(finding.status, 0))
                        if valid_target:
                            target_key = (" ".join(target_finding.claim.lower().split()), target_finding.study_id)
                            valid_target = duplicate_winner[target_key] == decision.target_id
                        if valid_target:
                            disposition, merged_into = "merged", decision.target_id
                        else:
                            disposition = "needs_review"
                            reason = f"Invalid editorial merge target; original reason: {decision.reason}"
                    else:
                        disposition = "rejected"
                    if reason is None:
                        reason = decision.reason
                else:
                    if decision:
                        reason = decision.reason
                        if decision.disposition == "needs_review":
                            disposition = "needs_review"
                updates = {"editorial_disposition": disposition, "editorial_reason": reason, "merged_into": merged_into}
                if decision and decision.disposition == "keep" and disposition == "publish" and finding.status in SUPPORTED_STATUSES:
                    updates.update(severity=decision.severity, priority=decision.priority)
                edited.append(finding.model_copy(update=updates))
            quarantined: list[Finding] = []
            for finding in edited:
                if finding.status == "contradicted":
                    finding = finding.model_copy(update={"editorial_disposition": "rejected", "editorial_reason": "Claim was contradicted during verification.", "merged_into": None})
                elif finding.status in {"candidate", "unverified", "unresolved"}:
                    finding = finding.model_copy(update={"editorial_disposition": "needs_review", "editorial_reason": f"Claim is not established by verification (status {finding.status}).", "merged_into": None})
                quarantined.append(finding)
            run.findings = quarantined
            final_by_id = {f.id: f for f in run.findings}
            repaired_findings = []
            merge_repair_needed = False
            for finding in run.findings:
                if finding.editorial_disposition == "merged":
                    target = final_by_id.get(finding.merged_into or "")
                    if target is None or target.editorial_disposition != "publish" or target.status not in SUPPORTED_STATUSES:
                        merge_repair_needed = True
                        finding = finding.model_copy(update={"editorial_disposition": "needs_review", "merged_into": None,
                                                             "editorial_reason": "Merge target was not publishable; retained for review."})
                repaired_findings.append(finding)
            related: dict[str, list[MergedPoint]] = {}
            for finding in repaired_findings:
                if finding.editorial_disposition == "merged" and finding.status in SUPPORTED_STATUSES and finding.merged_into:
                    related.setdefault(finding.merged_into, []).append(MergedPoint(
                        finding_id=finding.id, module=finding.module, claim=finding.claim,
                        evidence=[e for e in finding.evidence if e.source_char_start is not None]))
            folded = [f.model_copy(update={"merged_points": related.get(f.id, [])}) for f in repaired_findings]
            run.findings = sorted(folded, key=finding_order)
            if merge_repair_needed:
                run.partial = True
                run.coverage.append("editorial: invalid merge target was retained as needs_review")
            if decisions.reconciled_overview is not None:  # type: ignore[union-attr]
                overview = decisions.reconciled_overview  # type: ignore[union-attr]
                run.study_map = run.study_map.model_copy(update={"design_summary": overview.design_summary,
                                                                  "contribution_summary": overview.contribution_summary,
                                                                  "strengths": overview.strengths})
            run.stages.append(stage)
            if self.backend.name == "fixture":
                self.progress("editorial: completed in 0.0s")
        except Exception as exc:
            if editorial_stage and editorial_stage.artifact:
                Path(editorial_stage.artifact).unlink(missing_ok=True)
            run.partial = True
            run.findings = [finding.model_copy(update={"editorial_disposition": "needs_review",
                                                        "editorial_reason": f"Editorial stage failed: {type(exc).__name__}: {exc}",
                                                        "merged_into": None}) for finding in run.findings]
            run.stages.append(self._failed("editorial", exc, editorial_stage))
        self.progress("render: started")
        render_all(run, out)
        self.progress("render: completed")
        return run

    @staticmethod
    def _source_tasks(run, name, candidates, decisions, calls, verified):
        from .verification import check_external, touched

        statuses = {f.id: f.status for f in verified}
        for candidate in candidates:
            decision = decisions.get(candidate.id, {})
            for item in check_external(candidate.external_evidence, decision.get("external_checks", []), calls):
                run.source_tasks.append(ExternalSourceTask(finding_id=candidate.id, locator=item.locator,
                    stage=name, dependency=decision.get("external_dependency", "required"),
                    lookup_recorded=touched(item.locator, calls), check=item.check,
                    claim_status=statuses[candidate.id]))

    def _finish_source_tasks(self, run, out, name, compact, instruction, evidence, candidates, verified, by_id):
        """One full re-verification for supported claims held by an unperformed required lookup."""
        from .verification import verify_findings

        missing = {task.finding_id for task in run.source_tasks if task.stage == name and
                   task.dependency == "required" and not task.lookup_recorded}
        retry = [f for f in verified if f.id in missing and f.status == "unresolved" and
                 f.verifier_status == "supported" and "no external item was confirmed" in (f.verification or "") and
                 not any(e.check == "refuted" for e in f.external_evidence)]
        if not retry:
            return
        retry_ids = {f.id for f in retry}
        rows = [row for row in compact if row["finding_id"] in retry_ids]
        locators = {f.id: list(dict.fromkeys(e.locator for e in candidates[f.id].external_evidence)) for f in retry}
        task_instruction = instruction.split("\n\nCANDIDATES\n", 1)[0] + (
            "\nA prior attempt supported these claims without the recorded source checks required to establish them. "
            "Reassess each complete claim and rationale from the sources with defeating context; do not assume the prior verdict. "
            "Open each listed locator with your tools in this call. A copied quotation or an assertion of a lookup "
            "does not count as a fetch/search. Inaccessibility or unfinished essential checks mean unresolved. "
            "Return a complete decision, anchored manuscript evidence and an external verdict for every item.\n"
            "SOURCE TASKS\n" + _canonical(locators) + "\n\nCANDIDATES\n" + _canonical(rows) +
            "\nDISCIPLINE RULES\n" + self.profile.verification_prompt + "\n" + CLAIM_SCOPE)
        stage = None
        try:
            result, stage = self._cached(out, name + "-sources", {
                "upstream": _hash(rows), "evidence": _hash(evidence),
                "instruction_hash": _hash(REVIEW_GUARD + task_instruction)}, VerificationResponse,
                lambda: self.verifier_backend.generate(task_instruction, evidence, VerificationResponse), self.verifier_backend)
            returned = [d.finding_id for d in result.decisions]
            if len(returned) != len(set(returned)) or set(returned) != retry_ids:
                raise ValueError("Source follow-up returned duplicate, missing or unknown finding IDs")
            decisions = {d.finding_id: d.model_dump() for d in result.decisions}
            originals = [candidates[f.id] for f in retry]
            checked = verify_findings(originals, run.sources, decisions,
                                      run.metadata.verification_relationship, stage.tool_calls)
            by_id.update({f.id: f for f in checked})
            run.stages.append(stage)
            self._source_tasks(run, stage.name, originals, decisions, stage.tool_calls, checked)
            run.coverage.append(f"{stage.name}: {len(retry)} claim(s) reassessed for unfinished required-source checks; "
                                f"{sum(f.status == 'llm_supported' for f in checked)} supported under the same gates")
        except Exception as exc:
            if stage and stage.artifact:
                Path(stage.artifact).unlink(missing_ok=True)
            run.partial = True
            run.stages.append(self._failed(name + "-sources", exc, stage))
            run.coverage.append(f"{name}-sources: follow-up failed; initial gated decisions retained")


def review(manuscript: str | Path, **kwargs: object) -> ReviewRun:
    backend = kwargs.pop("backend", None)
    profile = kwargs.pop("profile", "social_psychology")
    verifier_backend = kwargs.pop("verifier_backend", None)
    progress = kwargs.pop("progress", None)
    run_metacheck = kwargs.pop("run_metacheck", True)
    return ReviewPipeline(backend=backend, profile=profile, verifier_backend=verifier_backend,
                          progress=progress, run_metacheck=run_metacheck).run(manuscript, **kwargs)
