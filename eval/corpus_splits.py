"""Recompute and check the reproducible case-split draw in eval/corpus/splits.v1.json.

Usage:
    .venv/bin/python eval/corpus_splits.py            # verify recorded splits
    .venv/bin/python eval/corpus_splits.py --show     # print the draw order

The rule is recorded in the manifest's ``split_rule``. Each case has an
``assignment.basis``:

* ``fixed``: assigned by exposure or prior curation (reason recorded);
* ``fence_draw``: verified exact, ordinary empirical, social/personality, never
  exposed. Within each stratum, cases are ordered by sha256(seed|id); the first
  ceil(fraction * n) are fenced and the rest alternate judge_calibration,
  development;
* ``alternate_draw``: verified but not fence-eligible (methodological, adjacent
  or Stage 2 registered reports). Within each stratum, ordered the same way and
  alternated development, judge_calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "eval/corpus/splits.v1.json"
SPLIT_NAMES = {"development", "judge_calibration", "fenced_validation", "excluded"}


def rank(seed: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}|{case_id}".encode()).hexdigest()


def draw(cases: list[dict], rule: dict) -> dict[str, str]:
    """Return the split implied by the recorded rule for every non-fixed case."""
    seed = rule["seed"]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for case in cases:
        basis = case["assignment"]["basis"]
        if basis in {"fence_draw", "alternate_draw"}:
            groups[(basis, case["assignment"]["stratum"])].append(case["id"])
    result: dict[str, str] = {}
    for (basis, _stratum), ids in sorted(groups.items()):
        ordered = sorted(ids, key=lambda case_id: rank(seed, case_id))
        if basis == "fence_draw":
            fenced = math.ceil(rule["fenced_fraction"] * len(ordered))
            cycle = rule["fence_draw_remainder_cycle"]
            for index, case_id in enumerate(ordered):
                result[case_id] = "fenced_validation" if index < fenced else cycle[(index - fenced) % len(cycle)]
        else:
            cycle = rule["alternate_draw_cycle"]
            for index, case_id in enumerate(ordered):
                result[case_id] = cycle[index % len(cycle)]
    return result


def check(manifest: dict) -> list[str]:
    """Return problems: wrong draws, invalid splits, duplicates or an undersized fence."""
    problems: list[str] = []
    cases = manifest["cases"]
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        problems.append("duplicate case ids")
    expected = draw(cases, manifest["split_rule"])
    for case in cases:
        if case["split"] not in SPLIT_NAMES:
            problems.append(f"{case['id']}: unknown split {case['split']}")
        if case["id"] in expected and expected[case["id"]] != case["split"]:
            problems.append(f"{case['id']}: recorded {case['split']}, rule gives {expected[case['id']]}")
        if case["assignment"]["basis"] == "fixed" and not case["assignment"].get("reason"):
            problems.append(f"{case['id']}: fixed assignment without reason")
        if case["split"] == "fenced_validation":
            if not case.get("ordinary_empirical") or case.get("exposure"):
                problems.append(f"{case['id']}: fenced case must be ordinary empirical and unexposed")
            if not case.get("fence_sha256"):
                problems.append(f"{case['id']}: fenced case lacks hashes")
    fenced = sum(case["split"] == "fenced_validation" for case in cases)
    if fenced < manifest["split_rule"]["minimum_fenced"]:
        problems.append(f"only {fenced} fenced cases")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", type=Path, default=SPLITS)
    parser.add_argument("--show", action="store_true", help="print the ranked draw")
    args = parser.parse_args(argv)
    manifest = json.loads(args.splits.read_text(encoding="utf-8"))
    if args.show:
        seed = manifest["split_rule"]["seed"]
        drawn = draw(manifest["cases"], manifest["split_rule"])
        rows = sorted((c["assignment"]["basis"], c["assignment"].get("stratum", ""), rank(seed, c["id"]), c["id"])
                      for c in manifest["cases"] if c["id"] in drawn)
        for basis, stratum, digest, case_id in rows:
            print(f"{basis:15} {stratum:28} {digest[:12]} {drawn[case_id]:18} {case_id}")
    problems = check(manifest)
    for problem in problems:
        print(f"problem: {problem}", file=sys.stderr)
    counts: dict[str, int] = defaultdict(int)
    for case in manifest["cases"]:
        counts[case["split"]] += 1
    print(", ".join(f"{name}={counts[name]}" for name in sorted(counts)))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
