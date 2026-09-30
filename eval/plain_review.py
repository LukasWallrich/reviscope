"""Single-call baseline review with the Dawes benchmark's taxonomy prompt.

Sends `REVIEW_PROMPT` from the benchmark (commit 3d91883, benchmark/prompts.py)
to one model call through the same tool-free backend the pipeline uses, and
writes `{"issues": [...]}` in the benchmark's own review format.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from reviscope.backend import ClaudeBackend, CodexBackend

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--backend", choices=["codex", "claude"], default="codex")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--effort", default="max")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    backend = (CodexBackend if args.backend == "codex" else ClaudeBackend)(args.model, args.timeout, args.effort)
    result = backend.generate(REVIEW_PROMPT, args.manuscript.read_text(encoding="utf-8"), Issues)
    payload = {"generator": backend.identity, "prompt": "Dawes benchmark REVIEW_PROMPT (taxonomy-guided)",
               **result.model_dump()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"{len(result.issues)} issues -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
