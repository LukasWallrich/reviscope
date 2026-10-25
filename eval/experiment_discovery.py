"""Tool-enabled discovery experiments sharing the pipeline's finalization stages.

Replay imports every issue from a saved plain review. Holistic uses one new review
call with operation-based checks. Both reuse a seed's sources, descriptive study
map and metacheck provenance, not its candidate findings or editorial overview.
Replay can instead build a descriptive study map from supplied documents, skipping
metacheck. Discovery and editorial use Sol; verification defaults to Opus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from reviscope.backend import REVIEW_GUARD, ClaudeBackend, CodexBackend
from reviscope.discovery import DiscoveryResponse
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline, _hash
from reviscope.schemas import Evidence, Finding, MetacheckRecord, ReviewRun, RunMetadata, StageRecord


CHECKS = ("analysis_recipe", "categorical_facts", "scores_and_populations", "claims_and_inference")
HOLISTIC_PROMPT = """Review the complete supplied manuscript as an expert quantitative
social-science reviewer. Identify every distinct, consequential problem in validity,
replicability or interpretation. Read it as one argument, tracking how the question,
observations, analyses and conclusions fit together. Return all justified findings;
there is no quota or finding limit. Do not manufacture problems or repeat acknowledged
limitations unless another claim exceeds them. Separate a demonstrated error from an
unreported decision or an optional improvement. Missing information alone is not major
or critical without a demonstrated material consequence.

Use these named operations and record the actual passages or quantities compared:
analysis_recipe: trace effect metrics, variances, transformations and their order,
aggregation, model selection, sensitivity alternatives and back-transformation. Keep
reported operations separate from assumptions used for your own calculations.
categorical_facts: compare sites, populations, eligibility, counts, units, periods,
variable definitions and labels across prose, tables and supplements.
scores_and_populations: trace response codes, item weights, missing-item rules,
standardization, averaging and routing to the final score and analytic population.
claims_and_inference: test whether the design and measurements address the question,
the stated analysis tests the intended claim, uncertainty supports the conclusion,
and sampling or calibration supports population statements.

For a specification conflict, quote both passages and explain the unresolved decision
without guessing which implementation occurred. A reporting omission must prevent
reproducing or assessing a stated analysis or interpreting a particular conclusion.
Check the whole manuscript and supplied or accessible linked methods before asserting
absence. Do not demand a particular method merely because another valid method exists.
Recompute numerical criticisms with the sandboxed shell, recording inputs and
assumptions. Fetch cited external sources for source-specific assertions and use web
search when it can settle novelty or another consequential external question.
Every finding requires an exact manuscript quotation with a valid SOURCE_ID. Put
source-specific external support in external_evidence with its URL or DOI, an exact
source quotation, and what it shows. Give the smallest justified remedy.
Return one checks entry for each named operation, with evidence for assessed entries
and an explicit reason for insufficient_evidence, not_applicable or not_checked.
Set search_incomplete when an operation cannot be completed. Coverage is an account of
the comparisons made, not a guarantee that all errors were found.
"""


def import_plain(data: dict, source_id: str) -> list[Finding]:
    """Preserve descriptions and general-format remedies; map moderate to minor."""
    if data.get("partial"):
        raise ValueError("A partial plain review cannot seed this experiment")
    return [Finding(id=f"plain:{index:02d}", module="plain", claim=issue["description"],
                    rationale=issue["description"], remedy=issue.get("remedy", ""), status="candidate",
                    remedy_necessity=(issue.get("remedy_necessity")
                                      if "remedy" in issue and issue.get("remedy_necessity")
                                      in ("essential", "strengthening", "extending") else None),
                    severity="minor" if issue["severity"] == "moderate" else issue["severity"],
                    evidence=[Evidence(source_id=source_id, quote=issue["quote"], location=issue["location"])])
            for index, issue in enumerate(data["issues"], 1)]


def verifier_metadata(pipeline: ReviewPipeline) -> dict:
    backend, verifier = pipeline.backend, pipeline.verifier_backend
    relationship = ("deterministic_fixture" if backend.name == "fixture" else
                    "same_model_separate_call" if (backend.name, backend.model) == (verifier.name, verifier.model) else
                    "different_model_same_family" if backend.name == verifier.name else "different_model_family")
    return {"verifier_backend": verifier.name, "verifier_model": verifier.model,
            "verifier_effort": verifier.effort, "verification_relationship": relationship}


def seed_draft(path: Path, out: Path, pipeline: ReviewPipeline, mode: str) -> ReviewRun:
    seed = ReviewRun.model_validate_json(path.read_bytes())
    if seed.partial:
        raise ValueError("A partial pipeline review cannot provide the descriptive seed")
    if (seed.metadata.backend, seed.metadata.model, seed.metadata.effort) != ("codex", "gpt-6.1-sol", "high"):
        raise ValueError("The experiment uses a Sol/high descriptive seed and reviewer")
    metadata = seed.metadata.model_copy(update={
        "run_id": f"{seed.metadata.run_id}-{mode}", "created_at": datetime.now(timezone.utc),
        "profile_hash": pipeline.profile_hash, "output_dir": str(out),
        "engine_version": pipeline.STAGE_VERSION,
        **verifier_metadata(pipeline),
    })
    stages = [s.model_copy(update={"status": "cached", "duration_seconds": 0})
              for s in seed.stages if s.name == "study_map"]
    stages += [s.model_copy(deep=True) for s in seed.stages if s.name == "metacheck"]
    overview = seed.preliminary_study_map or seed.study_map
    return ReviewRun(metadata=metadata, sources=seed.sources, study_map=overview.model_copy(deep=True),
                     preliminary_study_map=overview.model_copy(deep=True), stages=stages,
                     metacheck=seed.metacheck,
                     coverage=[f"Experimental {mode} discovery; descriptive study map and metacheck imported from {path}"])


def manuscript_draft(manuscript: Path, supplements: list[Path], out: Path, pipeline: ReviewPipeline) -> ReviewRun:
    sources = [ingest(manuscript)] + [ingest(path, "supplement") for path in supplements]
    input_hash = _hash([(s.kind, s.sha256, _hash(s.text)) for s in sources])
    metadata = RunMetadata(run_id=f"{input_hash[:12]}-replay", backend=pipeline.backend.name,
                           model=pipeline.backend.model, effort=pipeline.backend.effort,
                           profile=pipeline.profile.id, profile_hash=pipeline.profile_hash,
                           input_hash=input_hash, output_dir=str(out), engine_version=pipeline.STAGE_VERSION,
                           **verifier_metadata(pipeline))
    skipped = MetacheckRecord(status="skipped", reason="skipped: replay seed uses only the descriptive study map")
    run = ReviewRun(metadata=metadata, sources=sources, metacheck=skipped,
                    coverage=["Experimental replay discovery; descriptive study map built from supplied sources",
                              f"metacheck: {skipped.reason}"])
    for source in sources:
        run.coverage.extend(f"{source.id}: {warning}" for warning in source.extraction_warnings)
        if source.extraction_warnings:
            run.partial = True
    pipeline._study_map(run, out, input_hash, pipeline._evidence(sources))
    run.stages.append(StageRecord(name="metacheck", status="skipped", error=skipped.reason))
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["replay", "holistic"], required=True)
    seed = parser.add_mutually_exclusive_group(required=True)
    seed.add_argument("--seed-review", type=Path)
    seed.add_argument("--manuscript", type=Path)
    parser.add_argument("--supplement", action="append", type=Path, default=[])
    parser.add_argument("--plain-review", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--verifier-backend", choices=["codex", "claude"], default="claude")
    parser.add_argument("--verifier-model", default="claude-opus-5-5")
    parser.add_argument("--verifier-effort", default="high")
    parser.add_argument("--parallel", type=int, default=2)
    args = parser.parse_args()
    if args.mode == "replay" and args.plain_review is None:
        parser.error("--plain-review is required for replay")
    if args.mode == "holistic" and args.seed_review is None:
        parser.error("--seed-review is required for holistic")
    if args.supplement and args.manuscript is None:
        parser.error("--supplement requires --manuscript; saved seeds already include their sources")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    verifier_class = ClaudeBackend if args.verifier_backend == "claude" else CodexBackend
    verifier = verifier_class(args.verifier_model, args.timeout, args.verifier_effort)
    pipeline = ReviewPipeline(CodexBackend("gpt-6.1-sol", args.timeout, "high"),
                              verifier_backend=verifier, parallel=args.parallel, run_metacheck=False,
                              progress=lambda message: print(f"{datetime.now(timezone.utc).isoformat()} {message}", flush=True))
    run = (seed_draft(args.seed_review, out, pipeline, args.mode) if args.seed_review else
           manuscript_draft(args.manuscript, args.supplement, out, pipeline))
    inputs = {"mode": args.mode, "code": str(Path(__file__).resolve()),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "backend": pipeline.backend.identity, "backend_version": pipeline.backend.version,
              "verifier_backend": args.verifier_backend, "verifier_model": args.verifier_model,
              "verifier_effort": args.verifier_effort, "verifier": verifier.identity,
              "verifier_backend_version": verifier.version, "parallel": args.parallel, "timeout": args.timeout,
              "seed_mode": "imported" if args.seed_review else "study_map",
              "sources": [{"kind": s.kind, "path": s.path, "sha256": s.sha256} for s in run.sources],
              "limitations": ("One run per paper. Descriptive seed is shared with the specialist pilot; this is not an independent end-to-end run."
                              if args.seed_review else "One run per paper. Plain discovery is imported; only the descriptive study map and finalization are run here. Metacheck is skipped.")}
    if args.seed_review:
        inputs.update(seed_sha256=hashlib.sha256(args.seed_review.read_bytes()).hexdigest(),
                      seed_path=str(args.seed_review.resolve()))
    else:
        inputs.update(manuscript_path=str(args.manuscript.resolve()),
                      supplement_paths=[str(path.resolve()) for path in args.supplement])
    if args.mode == "replay":
        plain = json.loads(args.plain_review.read_bytes())
        manuscript = next(s for s in run.sources if s.kind == "manuscript")
        plain_manuscript = next(s for s in plain["sources"] if s["kind"] == "manuscript")
        if plain_manuscript["sha256"] != manuscript.sha256:
            raise ValueError("Plain and seed manuscripts differ")
        run.candidates = import_plain(plain, manuscript.id)
        inputs.update(plain_sha256=hashlib.sha256(args.plain_review.read_bytes()).hexdigest(),
                      plain_path=str(args.plain_review.resolve()),
                      adapter="Full descriptions retained as claim and rationale; moderate becomes minor; general-format remedies and valid remedy_necessity labels retained; older Dawes issues have no separate remedy; external evidence is not represented by the plain schema.")
        for row in plain["stages"]:
            stage = StageRecord.model_validate(row)
            stage = stage.model_copy(update={"status": "cached", "duration_seconds": 0,
                                            "artifact": str(args.plain_review.resolve()),
                                            "backend_version": plain.get("generator_version") or "not recorded in imported artifact"})
            run.stages.append(stage)
        run.coverage.append(inputs["adapter"])
    else:
        instruction = HOLISTIC_PROMPT + "\nSeverity guidance: " + json.dumps(pipeline.profile.metadata.get("severity_guidance", {}))
        evidence = "STUDY MAP\n" + run.study_map.model_dump_json() + "\n" + pipeline._evidence(run.sources)
        if run.metacheck:
            from reviscope.metacheck import leads
            evidence += "\nUNVERIFIED METACHECK LEADS\n" + "\n".join(leads(run.metacheck, pipeline.profile.modules).values())
        stage = None
        try:
            response, stage = pipeline._cached(out, "review-holistic",
                {"instruction_hash": _hash(REVIEW_GUARD + instruction), "evidence": _hash(evidence)},
                DiscoveryResponse, lambda: pipeline.backend.generate(instruction, evidence, DiscoveryResponse))
            names = [c.check for c in response.checks]
            if set(names) != set(CHECKS) or len(names) != len(set(names)):
                run.coverage.append("holistic: operation coverage has missing, unknown or duplicate entries; findings retained")
            for index, finding in enumerate(response.findings, 1):
                run.candidates.append(Finding.model_validate({**finding.model_dump(),
                    "id": f"holistic:{index:02d}", "module": "holistic"}))
            run.stages.append(stage)
            run.coverage.extend(f"holistic/{c.check}: {c.status} — {c.rationale}" for c in response.checks)
            if response.search_incomplete:
                run.coverage.append("holistic: discovery reports an incomplete operation audit")
        except Exception as exc:
            run.partial = True
            run.stages.append(pipeline._failed("review-holistic", exc, stage))
    (out / "experiment.json").write_text(json.dumps(inputs, indent=2) + "\n")
    result = pipeline._finalize(run, out)
    published = [f for f in result.findings if f.editorial_disposition == "publish"]
    print(f"Completed: {len(result.candidates)} candidates, {len(published)} published, partial={result.partial}", flush=True)
    return 2 if result.partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
