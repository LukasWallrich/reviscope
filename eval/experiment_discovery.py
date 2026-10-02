"""Tool-enabled discovery experiments sharing the pipeline's finalization stages.

Replay imports every issue from a saved plain review. Holistic uses one new review
call with operation-based checks. Both reuse a seed's manuscript, descriptive study
map and metacheck provenance, not its candidate findings or editorial overview.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from reviscope.backend import REVIEW_GUARD, CodexBackend
from reviscope.discovery import DiscoveryResponse
from reviscope.pipeline import ReviewPipeline, _hash
from reviscope.schemas import Evidence, Finding, ReviewRun, StageRecord


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
    """Preserve complete criticism text; map the plain schema's moderate to minor."""
    if data.get("partial"):
        raise ValueError("A partial plain review cannot seed this experiment")
    return [Finding(id=f"plain:{index:02d}", module="plain", claim=issue["description"],
                    rationale=issue["description"], remedy="", status="candidate",
                    severity="minor" if issue["severity"] == "moderate" else issue["severity"],
                    evidence=[Evidence(source_id=source_id, quote=issue["quote"], location=issue["location"])])
            for index, issue in enumerate(data["issues"], 1)]


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
        "verifier_backend": "codex", "verifier_model": "gpt-6.1-sol", "verifier_effort": "high",
        "verification_relationship": "same_model_separate_call",
    })
    stages = [s.model_copy(update={"status": "cached", "duration_seconds": 0})
              for s in seed.stages if s.name == "study_map"]
    stages += [s.model_copy(deep=True) for s in seed.stages if s.name == "metacheck"]
    overview = seed.preliminary_study_map or seed.study_map
    return ReviewRun(metadata=metadata, sources=seed.sources, study_map=overview.model_copy(deep=True),
                     preliminary_study_map=overview.model_copy(deep=True), stages=stages,
                     metacheck=seed.metacheck,
                     coverage=[f"Experimental {mode} discovery; descriptive study map and metacheck imported from {path}"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["replay", "holistic"], required=True)
    parser.add_argument("--seed-review", type=Path, required=True)
    parser.add_argument("--plain-review", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    if args.mode == "replay" and args.plain_review is None:
        parser.error("--plain-review is required for replay")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    pipeline = ReviewPipeline(CodexBackend("gpt-6.1-sol", args.timeout, "high"),
                              progress=lambda message: print(f"{datetime.now(timezone.utc).isoformat()} {message}", flush=True))
    run = seed_draft(args.seed_review, out, pipeline, args.mode)
    inputs = {"mode": args.mode, "seed_sha256": hashlib.sha256(args.seed_review.read_bytes()).hexdigest(),
              "seed_path": str(args.seed_review.resolve()), "code": str(Path(__file__).resolve()),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "backend": pipeline.backend.identity, "backend_version": pipeline.backend.version,
              "limitations": "One run per paper. Descriptive seed is shared with the specialist pilot; this is not an independent end-to-end run."}
    if args.mode == "replay":
        plain = json.loads(args.plain_review.read_bytes())
        manuscript = next(s for s in run.sources if s.kind == "manuscript")
        if plain["sources"][0]["sha256"] != manuscript.sha256:
            raise ValueError("Plain and seed manuscripts differ")
        run.candidates = import_plain(plain, manuscript.id)
        inputs.update(plain_sha256=hashlib.sha256(args.plain_review.read_bytes()).hexdigest(),
                      plain_path=str(args.plain_review.resolve()),
                      adapter="Full descriptions retained as claim and rationale; moderate becomes minor; no separate remedy supplied; external evidence is not represented by the plain schema.")
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
                run.candidates.append(finding.model_copy(update={"id": f"holistic:{index:02d}", "module": "holistic",
                    "status": "candidate", "confidence": None, "verification": None, "verifier_status": None,
                    "verifier_rationale": None, "remedy_status": None, "remedy_verification": None,
                    "editorial_disposition": "publish", "editorial_reason": None, "merged_into": None}))
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
