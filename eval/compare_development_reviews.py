"""Blinded criticism-focused comparisons of archived AI and held-out human reports."""

import argparse
import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from reviscope.backend import ClaudeBackend, CodexBackend
from reviscope.evaluation import build_pairwise_cases, comparison_parts, run_comparisons


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_text(data):
    """Strip model, stage, support badges and application metadata from criticism prose."""
    if data.get("partial"):
        raise ValueError("Partial reviews are excluded from the primary quality comparisons")
    if "issues" in data:
        return "\n\n".join(f"{row['severity'].upper()}: {row['subcategory']}\n{row['description']}\n"
                          f"Evidence: {row['quote']}\nLocation: {row['location']}" for row in data["issues"])
    chunks = []
    for row in data["findings"]:
        if row["editorial_disposition"] != "publish" or row["status"] in {"candidate", "unverified", "unresolved", "contradicted"}:
            continue
        text = f"{row['severity'].upper()}: {row['claim']}\n{row['rationale']}"
        if row.get("remedy_status") not in {"overreaching", "unresolved"}:
            text += "\nSuggested response: " + row["remedy"]
        text += "\n" + "\n".join("Evidence: " + item["quote"] for item in row["evidence"])
        # External checks are audit provenance, not evidence of truth for a preference judge.
        text += "\n" + "\n".join(f"External evidence: {item['quote']} ({item.get('url') or item.get('doi')})"
                                  for item in row.get("external_evidence", []))
        chunks.append(text.strip())
    return "\n\n".join(chunks) or "No supported findings were published."


def compare(job, model, out):
    backend = ClaudeBackend(model, effort="high", tools=False) if model == "claude-opus-5-5" else CodexBackend(model, effort="high", tools=False)
    paper = {"paper_id": job["paper_id"], "manuscript": job["manuscript"],
             "candidate_review": job["left_text"], "reference_review": job["right_text"]}
    cases = build_pairwise_cases([paper], seed=42, order_swap=True)
    # Artifact hashes record provenance. The complete judge prompts and its model
    # settings determine reuse; CLI-version metadata does not enter the key.
    key = hashlib.sha256(json.dumps({"input": [comparison_parts(case) for case in cases], "backend": backend.identity,
                                   "protocol": "development-criticism-comparison-v3"}, sort_keys=True).encode()).hexdigest()
    target = out / model / job["case"] / (job["left"] + "-vs-" + job["right"] + ".json")
    if target.exists():
        prior = json.loads(target.read_text())
        if prior.get("cache_key") == key and not prior.get("invalid"):
            prior.update(audit_groups=job["audit_groups"], source_hashes=job["source_hashes"])
            target.write_text(json.dumps(prior, indent=2) + "\n")
            return prior
    result = asyncio.run(run_comparisons(cases, backend))
    result.update(cache_key=key, model=model, backend_version=backend.version, case=job["case"],
                  paper_id=job["paper_id"], left=job["left"], right=job["right"],
                  audit_groups=job["audit_groups"], source_hashes=job["source_hashes"],
                  representation="criticism-focused, metadata stripped; no study overview, support badge or stage IDs",
                  protocol="development-criticism-comparison-v3",
                  reviewer_independence="Human reports are judge-only inputs; generator sessions do not receive them")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{model} {job['case']} {job['left']} vs {job['right']}: {result['aggregate']['counts']}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path("eval/corpus/cache/open-review-curation-20261002"))
    parser.add_argument("--cases", nargs="+", default=["bonetto", "ziano"])
    parser.add_argument("--arms", nargs="+", choices=["plain", "holistic", "audit"], default=["plain", "holistic", "audit"])
    parser.add_argument("--model", choices=["claude-opus-5-5", "gpt-6.1-sol"], default="claude-opus-5-5")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--ai-only", action="store_true", help="Judge AI contrasts without human comparators")
    args = parser.parse_args()
    jobs = []
    for case in args.cases:
        prepared = json.loads((args.corpus / case / "prepared.json").read_text())
        manuscript = Path(prepared["manuscript_text"])
        assert sha(manuscript) == prepared["manuscript_text_sha256"]
        texts, hashes, audits = {}, {}, {}
        for arm in args.arms:
            path = args.root / "reviews" / arm / case / "review.json"
            texts[arm] = review_text(json.loads(path.read_text()))
            hashes[arm] = sha(path)
            audit = json.loads((path.parent / "tool-audit.json").read_text())
            audits[arm] = audit[0]["verdict"]
        pairs = [(left, right) for left, right in (("holistic", "plain"), ("audit", "holistic"), ("audit", "plain"))
                 if left in texts and right in texts]
        if not args.ai_only:
            for reference in prepared["human_reviews"]:
                path = Path(reference["path"])
                assert sha(path) == reference["text_sha256"]
                label = "human-" + reference["id"]
                texts[label], hashes[label], audits[label] = path.read_text(), sha(path), "held_out_human"
                pairs.extend((arm, label) for arm in args.arms)
        for left, right in pairs:
            jobs.append({"case": case, "paper_id": prepared["paper_id"], "left": left, "right": right,
                         "manuscript": manuscript.read_text(), "left_text": texts[left], "right_text": texts[right],
                         "audit_groups": {left: audits[left], right: audits[right]},
                         "source_hashes": {"manuscript": sha(manuscript), left: hashes[left], right: hashes[right]}})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: compare(job, args.model, args.root / "comparisons"), jobs))
    return 2 if any(result["invalid"] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
