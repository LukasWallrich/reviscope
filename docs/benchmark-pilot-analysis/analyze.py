"""Compute descriptive pilot comparisons from saved reviews and manual matches."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import NormalDist


REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read(path: Path):
    return json.loads(path.read_text())


def safety_reconstruction() -> dict:
    """Fit intercept-only Fisher-z REML to the rounded manuscript table."""
    correlations = [.083, -.205, -.335, -.445, -.396, -.280, -.303]
    sample_sizes = [90, 90, 80, 116, 94, 374, 81]
    effects = [math.atanh(r) for r in correlations]
    variances = [1 / (n - 3) for n in sample_sizes]

    def fit(tau2: float) -> tuple[float, float, float]:
        weights = [1 / (v + tau2) for v in variances]
        total = sum(weights)
        mean = sum(w * y for w, y in zip(weights, effects)) / total
        objective = .5 * (
            sum(math.log(v + tau2) for v in variances)
            + math.log(total)
            + sum(w * (y - mean) ** 2 for w, y in zip(weights, effects))
        )
        return objective, mean, math.sqrt(1 / total)

    low, high = 0., 1.
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(120):
        left = high - ratio * (high - low)
        right = low + ratio * (high - low)
        if fit(left)[0] < fit(right)[0]:
            high = right
        else:
            low = left
    tau2 = (low + high) / 2
    if fit(0.)[0] < fit(tau2)[0]:
        tau2 = 0.
    _, mean, se = fit(tau2)
    critical = NormalDist().inv_cdf(.975)
    return {
        "inputs_r": correlations,
        "inputs_n": sample_sizes,
        "assumptions": "Fisher-z effects, variances 1/(N-3), intercept-only REML, normal 95% intervals; rounded inputs, not the original analysis output",
        "tau2": tau2,
        "pooled_r": math.tanh(mean),
        "se_z": se,
        "ci": [math.tanh(mean + sign * critical * se) for sign in (-1, 1)],
        "pi": [math.tanh(mean + sign * critical * math.sqrt(tau2 + se * se)) for sign in (-1, 1)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, default=REPO / "runs/known-errors-0.4.1/reviews/pipeline_gpt-6.1-sol_high_social_psychology")
    parser.add_argument("--plain-root", type=Path, default=REPO / "runs/known-errors-all/reviews/plain_gpt-6.1-sol_high")
    parser.add_argument("--output", type=Path, default=HERE / "analysis.json")
    args = parser.parse_args()
    matching = read(HERE / "overlap.json")
    papers = {}
    totals = Counter()
    for paper in (5, 9):
        pipeline = read(args.pipeline_root / f"paper-{paper:02d}/review.json")
        plain = read(args.plain_root / f"paper-{paper:02d}/review.json")
        published = [f for f in pipeline["findings"] if f["editorial_disposition"] == "publish" and f["status"] not in {"candidate", "unverified", "unresolved", "contradicted"}]
        mapping = matching["papers"][str(paper)]
        assert set(mapping) == {f["id"] for f in published}, "Matching must cover every published finding exactly."
        assert all(1 <= i <= len(plain["issues"]) for ids in mapping.values() for i in ids)
        p_stages = [s for s in pipeline["stages"] if s["name"] != "metacheck"]
        p_seconds = sum(s["duration_seconds"] or 0 for s in p_stages)
        b_seconds = sum(s["duration_seconds"] or 0 for s in plain["stages"])
        p_tools = Counter(t["kind"] for s in p_stages for t in s.get("tool_calls", []))
        b_tools = Counter(t["kind"] for s in plain["stages"] for t in s.get("tool_calls", []))
        counts = {
            "candidates": len(pipeline["candidates"]),
            "published": len(published),
            "plain_issues": len(plain["issues"]),
            "verifier_supported": sum(f["verifier_status"] == "supported" for f in pipeline["findings"]),
            "verifier_unresolved": sum(f["verifier_status"] == "unresolved" for f in pipeline["findings"]),
            "verifier_contradicted": sum(f["verifier_status"] == "contradicted" for f in pipeline["findings"]),
            "final_llm_supported": sum(f["status"] == "llm_supported" for f in pipeline["findings"]),
            "pipeline_model_calls": len(p_stages),
            "plain_model_calls": len(plain["stages"]),
            "pipeline_stage_seconds": p_seconds,
            "plain_stage_seconds": b_seconds,
            "pipeline_tool_records": sum(p_tools.values()),
            "plain_tool_records": sum(b_tools.values()),
            "matched_pipeline_findings": sum(bool(ids) for ids in mapping.values()),
            "unmatched_pipeline_findings": sum(not ids for ids in mapping.values()),
        }
        totals.update(counts)
        module_counts = {}
        for f in pipeline["findings"]:
            module_counts.setdefault(f["module"], Counter())[f["editorial_disposition"]] += 1
        papers[str(paper)] = {
            **counts,
            "pipeline_tools": dict(p_tools),
            "plain_tools": dict(b_tools),
            "published_severity": dict(Counter(f["severity"] for f in published)),
            "plain_severity": dict(Counter(f["severity"] for f in plain["issues"])),
            "editorial_disposition": dict(Counter(f["editorial_disposition"] for f in pipeline["findings"])),
            "verifier_status": dict(Counter(f["verifier_status"] for f in pipeline["findings"])),
            "published_remedy_status": dict(Counter(f["remedy_status"] for f in published)),
            "module_disposition": {k: dict(v) for k, v in module_counts.items()},
            "unmatched_pipeline_ids": [k for k, ids in mapping.items() if not ids],
            "plain_indices_with_counterpart": sorted({i for ids in mapping.values() for i in ids}),
        }
    result = {
        "scope": "Sol only; two clean pilot papers, one run each. Descriptive artifact comparison; no inference of run-to-run effects or precision. Stage-duration sums exclude metacheck and are not billing data or campaign elapsed time. Plain and pipeline runs use different machines and CLI versions.",
        "matching_method": matching["method"],
        "papers": papers,
        "totals": dict(totals),
        "model_call_ratio": totals["pipeline_model_calls"] / totals["plain_model_calls"],
        "stage_duration_ratio": totals["pipeline_stage_seconds"] / totals["plain_stage_seconds"],
        "safety_pi_reconstruction": safety_reconstruction(),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "totals": result["totals"], "stage_duration_ratio": result["stage_duration_ratio"], "safety_pi": result["safety_pi_reconstruction"]["pi"]}, indent=2))


if __name__ == "__main__":
    main()
