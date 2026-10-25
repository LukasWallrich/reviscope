"""Single-call baseline review with the Dawes benchmark's taxonomy prompt.

Sends `REVIEW_PROMPT` from the benchmark (commit 3d91883, benchmark/prompts.py)
to one model call. With --no-category-list the prompt's "Look carefully for:" list,
which names exactly the ten planted-error categories, is removed; the output format,
including the category field, is unchanged. The call runs with the same tools as the pipeline's review stages (web
search, fetching, sandboxed shell). Writes the benchmark's `{"issues": [...]}`
format plus the provenance `eval/audit_tool_use.py` reads: `sources` (manuscript
sha256) and one `review-plain` stage with every recorded tool call. A failed call
still writes the file, with `partial: true`, a failed stage and the tool calls
made before the failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from reviscope.backend import Backend, ClaudeBackend, CodexBackend

MODELS = {"gpt-6-luna": CodexBackend, "gpt-6.1-sol": CodexBackend, "claude-opus-5-5": ClaudeBackend}
STAGE = "review-plain"

REVIEW_PROMPT = """You are an expert scientific peer reviewer with deep methodological expertise. \
Review the following manuscript and identify all methodological, statistical, and conceptual issues.

Look carefully for:
- Statistical errors (wrong test statistics, inconsistent values, incorrect parameters)
- Methodological design problems (missing controls, inadequate blinding, underpowered subgroups)
- Construct validity issues (measures that don't match constructs, operationalization mismatches)
- Causal inference problems (unaddressed confounds, inappropriate causal claims from correlational data)
- Internal consistency issues (contradictions between sections, numbers that don't add up)
- Reporting completeness gaps (missing details needed to evaluate or replicate the study)
- Generalizability overclaims (sample limitations not acknowledged, inappropriate extrapolation)
- Theoretical/conceptual problems (misapplied frameworks, misused terms, wrong predictions)
- Analytic flexibility concerns (undisclosed researcher degrees of freedom, missing pre-registration details)
- Attrition and missing data issues (unaddressed dropout, inappropriate handling of missing data)

For each issue, provide:
- category: one of [statistical_errors, methodological_design, construct_validity, causal_inference, internal_consistency, reporting_completeness, generalizability, theoretical_conceptual, analytic_flexibility, attrition_missing_data]
- subcategory: a brief label for the specific type of issue
- description: detailed explanation of the problem and why it matters
- quote: the exact text from the manuscript that contains or demonstrates the issue
- location: which section (introduction, methods, results, discussion)
- severity: one of [critical, major, moderate, minor]

Return ONLY a JSON object: {"issues": [...]}

Be thorough and precise. Focus on problems that affect validity, replicability, or interpretation."""


def without_category_list(prompt: str) -> str:
    """The prompt without its "Look carefully for:" category list."""
    start, end = prompt.index("Look carefully for:\n"), prompt.index("For each issue, provide:")
    return prompt[:start] + prompt[end:]


GENERAL_PROMPT = """You are an expert peer reviewer for a quantitative social psychology journal, with strong \
methodological and statistical expertise. Review the complete manuscript, including any supplements, as you would \
for the editor. Identify every substantive problem with the theory and claimed contribution, the design, measurement, \
statistical analysis, internal consistency, interpretation and reporting. Recompute reported numbers with code where \
the manuscript gives enough information, and open cited sources when a criticism depends on what they say. Make every \
point specific to this manuscript and explain its consequence for the paper's conclusions; do not add generic advice \
or repeat limitations the authors already acknowledge unless a claim goes beyond them. Recommend the smallest remedy \
that resolves each problem and say whether it is essential to support the claims as stated, would strengthen the \
paper, or would extend it beyond its current scope.

For each issue, provide:
- category: a brief label for the type of issue
- description: the problem, the evidence for it, and why it matters
- remedy: what the authors should do
- remedy_necessity: one of [essential, strengthening, extending]
- quote: the exact text from the manuscript that contains or demonstrates the issue
- location: which section or table
- severity: one of [critical, major, moderate, minor]

Return ONLY a JSON object: {"issues": [...]}"""

PROMPT_LABELS = {REVIEW_PROMPT: "Dawes benchmark REVIEW_PROMPT (taxonomy-guided)",
                 without_category_list(REVIEW_PROMPT): "Dawes benchmark REVIEW_PROMPT without the 'Look carefully for:' category list",
                 GENERAL_PROMPT: "General one-call review (0.5.0 development baseline)"}


class Issue(BaseModel):
    category: Literal["statistical_errors", "methodological_design", "construct_validity", "causal_inference",
                      "internal_consistency", "reporting_completeness", "generalizability",
                      "theoretical_conceptual", "analytic_flexibility", "attrition_missing_data"]
    subcategory: str
    description: str
    quote: str
    location: str
    severity: Literal["critical", "major", "moderate", "minor"]


class Issues(BaseModel):
    issues: list[Issue]


class GeneralIssue(BaseModel):
    category: str
    description: str
    remedy: str
    remedy_necessity: Literal["essential", "strengthening", "extending"]
    quote: str
    location: str
    severity: Literal["critical", "major", "moderate", "minor"]


class GeneralIssues(BaseModel):
    issues: list[GeneralIssue]


def manuscript_text(manuscript: Path, supplements: list[Path]) -> tuple[str, list[dict[str, str]]]:
    """Plain text stays verbatim (as in earlier baseline runs); other formats and supplements use the
    pipeline's ingestion and SOURCE_ID framing."""
    if not supplements and manuscript.suffix.lower() in {".md", ".txt"}:
        raw = manuscript.read_bytes()
        return raw.decode("utf-8"), [{"id": "manuscript", "path": str(manuscript.resolve()), "kind": "manuscript",
                                      "sha256": hashlib.sha256(raw).hexdigest()}]
    from reviscope.ingest import ingest
    from reviscope.pipeline import ReviewPipeline
    sources = [ingest(manuscript)] + [ingest(path, "supplement") for path in supplements]
    return ReviewPipeline._evidence(sources), [{"id": s.id, "path": str(Path(s.path).resolve()), "kind": s.kind,
                                               "sha256": s.sha256} for s in sources]


def review(manuscript: Path, backend: Backend, prompt: str = REVIEW_PROMPT, supplements: list[Path] | None = None) -> dict[str, object]:
    """Run the one-call review and return the review.json payload, failed or not."""
    text, sources = manuscript_text(manuscript, supplements or [])
    schema = GeneralIssues if prompt == GENERAL_PROMPT else Issues
    stage: dict[str, object] = {"name": STAGE, "status": "completed"}
    started = time.monotonic()
    issues: list[dict[str, object]] = []
    try:
        issues = [item.model_dump() for item in backend.generate(prompt, text, schema).issues]
    except Exception as exc:  # keep the provenance of a failed call
        stage.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    calls = [call.model_copy(update={"stage": STAGE}).model_dump(mode="json") for call in backend.take_tool_calls()]
    stage.update(duration_seconds=round(time.monotonic() - started, 1), tool_calls=calls)
    return {"generator": backend.identity, "generator_version": backend.version, "prompt": PROMPT_LABELS[prompt],
            "partial": stage["status"] == "failed",
            "sources": sources,
            "stages": [stage], "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", choices=sorted(MODELS), default="gpt-6-luna")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=3600, help="per-call timeout in seconds")
    parser.add_argument("--no-category-list", action="store_true", help='remove the "Look carefully for:" category list from the prompt')
    parser.add_argument("--prompt", choices=["dawes", "general"], default="dawes",
                        help="dawes: the benchmark's prompt (archived baselines); general: the 0.5.0 development baseline")
    parser.add_argument("--supplement", action="append", type=Path, default=[])
    args = parser.parse_args()

    if args.prompt == "general":
        prompt = GENERAL_PROMPT
    else:
        prompt = without_category_list(REVIEW_PROMPT) if args.no_category_list else REVIEW_PROMPT
    payload = review(args.manuscript, MODELS[args.model](args.model, args.timeout, args.effort), prompt, args.supplement)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    stage = payload["stages"][0]
    print(f"{stage['status']}: {len(payload['issues'])} issues, {len(stage['tool_calls'])} tool calls -> {args.output}")
    return 1 if payload["partial"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
