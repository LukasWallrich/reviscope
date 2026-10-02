"""Download hash-pinned submitted manuscripts and prepare held-out human reviews."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import urllib.request
from pathlib import Path

from reviscope.evaluation import load_corpus
from reviscope.ingest import ingest


ROOT = Path(__file__).resolve().parents[1]


def pinned_download(path: Path, url: str, expected: str) -> None:
    if path.exists():
        raw = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=90) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Hash mismatch: {path}; source versions must be rechecked")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def review_section(text: str, record: dict) -> str:
    """Select an explicitly bounded report and remove declared identity metadata."""
    start = record.get("start_after")
    end = record.get("end_before")
    if start:
        if text.count(start) != 1:
            raise ValueError(f"Review section marker is absent or ambiguous: {start}")
        text = text.split(start, 1)[1]
    if end:
        if text.count(end) != 1:
            raise ValueError(f"Review section marker is absent or ambiguous: {end}")
        text = text.split(end, 1)[0]
    remove = set(record.get("remove_identity_lines", []))
    lines = [line for line in text.splitlines() if line.strip() not in remove and not
             re.match(r"^\s*(?:\[Review by |Review by:|Completed:|Recommendation:|Reviewer:)", line)]
    result = "\n".join(lines).strip()
    if not result:
        raise ValueError("Empty human review after declared section extraction")
    return result + "\n"


def prepare(entry: dict, cache: Path) -> dict:
    directory = cache / entry["cache_key"]
    manuscript = entry["manuscript"]
    path = directory / "manuscript" / manuscript["filename"]
    pinned_download(path, entry["manuscript_under_review_url"], entry["manuscript_sha256"])
    source = ingest(path)
    path.with_suffix(".txt").write_text(source.text)
    if source.extraction_warnings:
        raise ValueError(f"Manuscript extraction needs inspection: {source.extraction_warnings}")
    prepared = []
    for review in entry["human_reviews"]:
        raw_path = directory / "human-reviews" / review["filename"]
        pinned_download(raw_path, review["url"], review["sha256"])
        extracted = ingest(raw_path)
        if extracted.extraction_warnings:
            raise ValueError(f"Review extraction needs inspection: {extracted.extraction_warnings}")
        text = review_section(extracted.text, review)
        target = directory / "comparators" / f"{review['id']}.txt"
        target.parent.mkdir(exist_ok=True)
        target.write_text(text)
        prepared.append({"id": review["id"], "path": str(target.resolve()),
                         "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "words": len(text.split())})
    result = {"paper_id": entry["id"], "manuscript": str(path.resolve()),
              "manuscript_text": str(path.with_suffix('.txt').resolve()),
              "manuscript_text_sha256": hashlib.sha256(source.text.encode()).hexdigest(),
              "human_reviews": prepared, "primary_review_id": entry["primary_review_id"],
              "profile": entry["recommended_profile"],
              "parser_versions": {package: importlib.metadata.version(package) for package in ("pypdf", "fonttools", "python-docx")},
              "leakage_boundary": "Generate from manuscript only; human-reviews and comparators are held-out judge inputs."}
    (directory / "prepared.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "eval/corpus/open_peer_review_curated.v1.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "eval/corpus/cache/open-review-curation-20261002")
    parser.add_argument("--case", action="append", help="Paper ID; omit to prepare every eligible case")
    args = parser.parse_args()
    entries = load_corpus(args.manifest)
    if args.case:
        unknown = set(args.case) - {e["id"] for e in entries}
        if unknown:
            parser.error(f"Unknown eligible cases: {sorted(unknown)}")
        entries = [e for e in entries if e["id"] in args.case]
    results = [prepare(entry, args.cache) for entry in entries]
    args.cache.mkdir(parents=True, exist_ok=True)
    (args.cache / "prepared.json").write_text(json.dumps(results, indent=2) + "\n")
    for result in results:
        print(f"{result['paper_id']}: submitted manuscript + {len(result['human_reviews'])} human reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
