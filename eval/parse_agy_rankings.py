"""Validate and deblind three agy listwise judgments produced from frozen prompts."""

import argparse
import hashlib
import json
from pathlib import Path

from reviscope.backend import _extract_json
from reviscope.ranking import (ListwiseJudgment, PROMPT_VERSION, _load_manifest,
                                    rank_once, summarize_rankings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()
    paper_id, manuscript, reviews, condition = _load_manifest(args.manifest)
    rows = []
    for repetition in range(3):
        repaired = args.input_directory / f"output-{repetition}-repaired.txt"
        path = repaired if repaired.exists() else args.input_directory / f"output-{repetition}.txt"
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        raw = _extract_json(wrapper["response"])
        raw_confidence = raw["confidence"]
        if not 0 <= raw_confidence <= 1:
            raise ValueError(f"agy confidence for repetition {repetition} remains outside 0..1")
        confidence = raw_confidence
        groups = [{"labels": group, "rationale": ""} if isinstance(group, list) else group
                  for group in raw["overall_rank_groups"]]
        criteria = [{"criterion": item.get("criterion") or item.get("name"),
                     "rank_groups": item["rank_groups"], "rationale": item["rationale"]}
                    for item in raw["criteria"]]
        parsed = ListwiseJudgment.model_validate({"overall_rank_groups": groups,
                                                   "confidence": confidence,
                                                   "rationale": raw["rationale"],
                                                   "criteria": criteria})

        class ParsedBackend:
            identity = "agy:Gemini 3.8 Flash (High):high"
            def generate(self, *_args):
                return parsed

        row = rank_once(manuscript, reviews, ParsedBackend(), paper_id=paper_id,
                        seed=args.seed, repetition=repetition)
        row["agy_provenance"] = {
            "conversation_id": wrapper.get("conversation_id"), "status": wrapper.get("status"),
            "raw_output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "adapter": "list rank groups wrapped without changing membership/order; criterion name alias normalized",
            "raw_confidence": raw_confidence,
            "confidence_transform": None,
        }
        rows.append(row)
    config = {"backend": "agy:Gemini 3.8 Flash (High):high", "prompt_version": PROMPT_VERSION,
              "seed": args.seed, "presentations": 3, "condition": condition,
              "content_sha256": hashlib.sha256(json.dumps({"manuscript": manuscript, "reviews": reviews},
                                                           sort_keys=True).encode()).hexdigest()}
    payload = {"ranking_config": config, "review_kinds": {r["id"]: r["kind"] for r in reviews},
               "review_provenance": {r["id"]: {"kind": r["kind"], "generator_model": r.get("generator_model")} for r in reviews},
               "judgments": rows, "invalid": [], "summary": summarize_rankings(rows, [r["id"] for r in reviews]),
               "adapter_note": "Two agy outputs returned list rank groups rather than RankGroup objects; the deterministic adapter wrapped them without changing order. Repetition 0 used one bounded same-model schema repair because its first confidence was outside 0..1; raw outputs are retained."}
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
