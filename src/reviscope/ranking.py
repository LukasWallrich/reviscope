"""Bounded listwise ranking of multiple peer reviews for one manuscript."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .backend import Backend, ClaudeBackend, CodexBackend
from .evaluation import _write_json, read_review
from .normalization import validate_normalized_pair


PROMPT_VERSION = "listwise-review-ranking-v1"
CRITERIA = {"correctness", "importance", "specificity", "source_grounding", "uncertainty", "actionability"}


class RankGroup(BaseModel):
    labels: list[str] = Field(min_length=1)
    rationale: str


class CriterionRank(BaseModel):
    criterion: str
    rank_groups: list[list[str]]
    rationale: str


class ListwiseJudgment(BaseModel):
    overall_rank_groups: list[RankGroup] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str
    criteria: list[CriterionRank] = Field(min_length=6, max_length=6)


def _review_labels(count: int) -> list[str]:
    if not 2 <= count <= 12:
        raise ValueError("listwise ranking requires 2 to 12 reviews")
    return [chr(ord("A") + i) for i in range(count)]


def _permutation(count: int, paper_id: str, seed: int, repetition: int) -> list[int]:
    digest = hashlib.sha256(f"{paper_id}:{seed}:{repetition}".encode()).digest()
    order = list(range(count))
    random.Random(digest).shuffle(order)
    return order


def ranking_instruction(labels: list[str]) -> str:
    return f"""Rank peer reviews {', '.join(labels)} against the supplied manuscript.
Use tied rank groups when reviews are substantively equivalent. Every label must appear exactly once overall.
Judge substantive correctness, importance, specificity, source grounding, recognition of uncertainty, and actionable
advice. Do not reward prose style, formatting, length, number of listed issues, or apparent human/model authorship.
For each criterion named exactly correctness, importance, specificity, source_grounding, uncertainty, and
actionability, provide rank groups and a concise rationale. Return the strongest group first."""


def rank_once(manuscript: str, reviews: list[dict[str, str]], backend: Backend, *,
              paper_id: str, seed: int, repetition: int) -> dict[str, Any]:
    labels = _review_labels(len(reviews))
    order = _permutation(len(reviews), paper_id, seed, repetition)
    mapping = {label: reviews[index]["id"] for label, index in zip(labels, order)}
    evidence = "MANUSCRIPT\n" + manuscript
    for label, index in zip(labels, order):
        evidence += f"\n\nREVIEW {label}\n{reviews[index]['text']}"
    judgment = backend.generate(ranking_instruction(labels), evidence, ListwiseJudgment)
    flattened = [label for group in judgment.overall_rank_groups for label in group.labels]
    if len(flattened) != len(labels) or set(flattened) != set(labels):
        raise ValueError("listwise judgment must rank every blinded label exactly once")
    if {row.criterion for row in judgment.criteria} != CRITERIA:
        raise ValueError("listwise judgment must return each required criterion exactly once")
    ranks: dict[str, float] = {}
    position = 1
    deblinded_groups = []
    for group in judgment.overall_rank_groups:
        end = position + len(group.labels) - 1
        average = (position + end) / 2
        ids = [mapping[label] for label in group.labels]
        for review_id in ids:
            ranks[review_id] = average
        deblinded_groups.append({"review_ids": ids, "rank": average, "rationale": group.rationale})
        position = end + 1
    criterion_rows = []
    for criterion in judgment.criteria:
        criterion_labels = [label for group in criterion.rank_groups for label in group]
        if len(criterion_labels) != len(labels) or set(criterion_labels) != set(labels):
            raise ValueError(f"criterion {criterion.criterion} must rank every blinded label exactly once")
        criterion_rows.append({"criterion": criterion.criterion,
                               "rank_groups": [[mapping[label] for label in group] for group in criterion.rank_groups],
                               "rationale": criterion.rationale})
    return {"paper_id": paper_id, "repetition": repetition, "seed": seed, "judge": backend.identity,
            "label_mapping": mapping, "rank_groups": deblinded_groups, "ranks": ranks,
            "confidence": judgment.confidence, "rationale": judgment.rationale,
            "criterion_judgments": criterion_rows}


def summarize_rankings(rows: list[Mapping[str, Any]], review_ids: list[str]) -> dict[str, Any]:
    distributions = {review_id: [float(row["ranks"][review_id]) for row in rows] for review_id in review_ids}
    mean_ranks = {review_id: sum(values) / len(values) for review_id, values in distributions.items()}
    pairwise = []
    for i, left in enumerate(review_ids):
        for right in review_ids[i + 1:]:
            left_wins = sum(row["ranks"][left] < row["ranks"][right] for row in rows)
            right_wins = sum(row["ranks"][right] < row["ranks"][left] for row in rows)
            pairwise.append({"left": left, "right": right, "left_above": left_wins,
                             "right_above": right_wins, "tied": len(rows) - left_wins - right_wins})
    return {"paper_count": 1, "judgment_count": len(rows), "repeated_presentations_are_not_independent_papers": True,
            "pairwise_count_ceiling_per_direction": len(rows),
            "rank_distributions": distributions, "mean_rank": mean_ranks,
            "borda_score": {key: len(review_ids) - value for key, value in mean_ranks.items()},
            "implied_pairwise_counts": pairwise}


def _complete_presentations(payload: Mapping[str, Any]) -> bool:
    config = payload.get("ranking_config", {})
    count = config.get("presentations")
    rows = payload.get("judgments", [])
    if not isinstance(count, int) or payload.get("invalid") or payload.get("summary") is None:
        return False
    repetitions = [row.get("repetition") for row in rows]
    review_ids = set(payload.get("review_kinds", {}))
    return (len(rows) == count and sorted(repetitions) == list(range(count))
            and all(set(row.get("ranks", {})) == review_ids for row in rows))


def _load_manifest(path: Path) -> tuple[str, str, list[dict[str, str]], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("reviews", [])
    ids = [str(row["id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("review IDs must be unique")
    kinds = [str(row["kind"]) for row in rows]
    expected = data.get("expected_composition")
    if expected:
        if len(rows) != sum(int(value) for value in expected.values()) or any(kinds.count(kind) != count for kind, count in expected.items()):
            raise ValueError("review pool does not match the manifest's expected composition")
    for row in rows:
        if str(row["kind"]) == "ai" and not row.get("generator_model"):
            raise ValueError("each AI review requires generator_model provenance")
    loaded, normalized_payloads = [], []
    for row in rows:
        review_path = Path(row["path"])
        payload = json.loads(review_path.read_text()) if review_path.suffix.lower() == ".json" else None
        is_audited_normalization = isinstance(payload, Mapping) and payload.get("audit_schema_version") == 1
        if row["kind"] == "ai" and not is_audited_normalization:
            if not isinstance(payload, Mapping) or payload.get("partial"):
                raise ValueError(f"AI review {row['id']} must be a complete review JSON")
            actual_model = payload.get("metadata", {}).get("model")
            if actual_model != row["generator_model"]:
                raise ValueError(f"AI review {row['id']} generator model does not match its manifest")
        if is_audited_normalization:
            normalized_payloads.append(payload)
        loaded.append({"id": str(row["id"]), "kind": str(row["kind"]),
                       "generator_model": row.get("generator_model"), "text": read_review(review_path)})
    if normalized_payloads:
        if len(normalized_payloads) != len(rows):
            raise ValueError("a ranking condition cannot mix original and normalized reviews")
        for payload in normalized_payloads[1:]:
            validate_normalized_pair(normalized_payloads[0], payload)
    from .ingest import ingest
    manuscript = ingest(Path(data["manuscript"])).text
    return str(data["paper_id"]), manuscript, loaded, str(data.get("condition", "original"))


def command(args: argparse.Namespace) -> int:
    paper_id, manuscript, reviews, condition = _load_manifest(args.manifest)
    backend: Backend = (ClaudeBackend(args.model, args.timeout, args.effort) if args.backend == "claude"
                        else CodexBackend(args.model, args.timeout, args.effort))
    config = {"backend": backend.identity, "prompt_version": PROMPT_VERSION, "seed": args.seed,
              "presentations": args.presentations, "condition": condition,
              "content_sha256": hashlib.sha256(json.dumps({"manuscript": manuscript, "reviews": reviews}, sort_keys=True).encode()).hexdigest()}
    judgments: list[dict[str, Any]] = []
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if prior.get("ranking_config") == config and _complete_presentations(prior):
            return 0
        if prior.get("ranking_config") == config:
            judgments = [row for row in prior.get("judgments", [])
                         if isinstance(row.get("repetition"), int) and 0 <= row["repetition"] < args.presentations]
            if len({row["repetition"] for row in judgments}) != len(judgments):
                raise ValueError("ranking resume contains duplicate presentations")
    invalid = []
    completed = {row["repetition"] for row in judgments}
    for repetition in range(args.presentations):
        if repetition in completed:
            continue
        try:
            judgments.append(rank_once(manuscript, reviews, backend, paper_id=paper_id,
                                       seed=args.seed, repetition=repetition))
        except Exception as exc:
            invalid.append({"repetition": repetition, "error_type": type(exc).__name__, "error": str(exc)})
        progress = {"ranking_config": config, "review_kinds": {row["id"]: row["kind"] for row in reviews},
                    "review_provenance": {row["id"]: {"kind": row["kind"], "generator_model": row.get("generator_model")} for row in reviews},
                    "judgments": judgments, "invalid": invalid, "summary": None}
        _write_json(progress, args.output)
    payload = {"ranking_config": config, "review_kinds": {row["id"]: row["kind"] for row in reviews},
               "review_provenance": {row["id"]: {"kind": row["kind"], "generator_model": row.get("generator_model")} for row in reviews},
               "judgments": judgments, "invalid": invalid,
               "summary": summarize_rankings(judgments, [row["id"] for row in reviews]) if not invalid else None}
    _write_json(payload, args.output)
    return 2 if invalid else 0


def aggregate_command(args: argparse.Namespace) -> int:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
    if any(not _complete_presentations(payload) for payload in payloads):
        raise ValueError("cannot aggregate incomplete or invalid ranking outputs")
    identities = [payload["ranking_config"]["backend"] for payload in payloads]
    if len(identities) != len(set(identities)):
        raise ValueError("cannot aggregate duplicate judge identities")
    base = payloads[0]["ranking_config"]
    for payload in payloads[1:]:
        config = payload["ranking_config"]
        for field in ("prompt_version", "seed", "presentations", "condition", "content_sha256"):
            if config.get(field) != base.get(field):
                raise ValueError(f"ranking outputs differ on {field}")
    review_ids = list(payloads[0]["review_kinds"])
    rows = [row for payload in payloads for row in payload["judgments"]]
    by_judge = {payload["ranking_config"]["backend"]: payload["summary"] for payload in payloads}
    _write_json({"paper_count": 1, "judge_count": len(payloads),
                 "presentations_per_judge": base["presentations"],
                 "condition": base["condition"], "by_judge": by_judge,
                 "combined_descriptive_summary": summarize_rankings(rows, review_ids),
                 "inference_note": "Judges and shuffled presentations are repeated measurements of one paper, not additional papers."},
                args.output)
    return 0


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("rank-reviews", help="rank a bounded review pool in seeded blinded orders")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--backend", choices=["codex", "claude"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="high")
    parser.add_argument("--presentations", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--timeout", type=int, default=900)
    parser.set_defaults(func=command)
    aggregate = subparsers.add_parser("aggregate-review-ranks", help="combine separate judge-family ranking outputs")
    aggregate.add_argument("inputs", nargs="+", type=Path)
    aggregate.add_argument("--output", required=True, type=Path)
    aggregate.set_defaults(func=aggregate_command)
