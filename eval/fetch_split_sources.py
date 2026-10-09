"""Download hash-pinned sources for cases in eval/corpus/splits.v1.json.

Development and judge_calibration cases go to
``eval/corpus/cache/corpus-splits-v1/<id>/`` with extracted manuscript text and
anonymized per-report comparator texts. Fenced cases go only to the separately
ignored ``eval/corpus/fenced/<id>/`` as untouched raw files: nothing is
extracted or written beside them, so curators do not read them by accident.

    .venv/bin/python eval/fetch_split_sources.py                 # development + judge_calibration
    .venv/bin/python eval/fetch_split_sources.py --split fenced_validation

Cases whose sources live in other manifests (curated Meta-Psychology, Dawes,
PeerJ 236, owner paper) are prepared by the scripts named in their ``local``
record.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import runpy
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from reviscope.ingest import ingest

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "eval/corpus/splits.v1.json"
CACHE = ROOT / "eval/corpus/cache/corpus-splits-v1"
FENCED = ROOT / "eval/corpus/fenced"
PREPARE = runpy.run_path(str(Path(__file__).with_name("prepare_open_reviews.py")))
USER_AGENT = "reviscope-corpus/1 (research; contact via repository owner)"


def fetch(url: str, expected: str, path: Path) -> bytes:
    """Return the pinned bytes, reusing a cached file only if its hash matches."""
    if path.exists():
        raw = path.read_bytes()
    else:
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = response.read()
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        if raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Hash mismatch for {url}; the source must be re-verified before use")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return raw


def _html_text(raw: bytes, keep_links: bool) -> str:
    text = raw.decode("utf8", "replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S)
    if keep_links:
        text = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>', r" [\1] ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text)


def peerj_reports(raw: bytes) -> list[str]:
    """Split the Version 0.1 section of an archived PeerJ review history into reports."""
    text = _html_text(raw, keep_links=False)
    start = text.find("Version 0.1\n(original submission)")
    text = text[start if start >= 0 else text.find("Version 0.1"):]
    first = text.find("Basic reporting")
    lines = text[:first].split("\n")
    position = text[:first].rfind("\n".join(lines[-4:-1])) if len(lines) > 4 else 0
    reports = []
    pattern = r"Peer Review #(\d+) of [^\n]*\n(?:[^\n]*\n){0,3}?\s*PeerJ(?:\nhttps://doi\.org/10\.7287/peerj\.\d+v0\.1/reviews/\d+)?"
    for match in re.finditer(pattern, text):
        reports.append(text[position:match.end()])
        position = match.end()
    return reports


def pci_reports(raw: bytes) -> list[str]:
    """Return the evaluation-round-1 reports from an archived PCI RR recommendation page."""
    text = _html_text(raw, keep_links=True)
    marker = "Evaluation round \n#1" if "Evaluation round \n#1" in text else "Evaluation round\n#1"
    section = text[text.find(marker):]
    end = section.find("User comments")
    section = section[:end] if end > 0 else section
    return ["Reviewed by " + part for part in re.split(r"\nReviewed by ", section)[1:]]


def anonymize_html_report(text: str, kind: str, reviewer: str | None) -> str:
    """Drop reviewer headers, profile/ORCID/review-DOI links and name-only signature lines.

    Every other line, including praise and minor comments, is kept.
    """
    lines = text.strip().splitlines()
    if kind == "peerj_v0.1":
        lines = lines[3:]  # reviewer name, separator, date
        cut = next((i for i, line in enumerate(lines) if line.startswith("Cite this review as")), len(lines))
        lines = lines[:cut]
    elif lines and lines[0].startswith("Reviewed by"):
        date = next((i for i, line in enumerate(lines[:8]) if re.match(r"^\s*,\s*\d{1,2} [A-Z][a-z]{2} \d{4}", line)), None)
        lines = lines[date + 1:] if date is not None else lines[1:]
    names = set()
    if reviewer and not reviewer.lower().startswith(("reviewer", "anonymous")):
        names = {reviewer.strip().lower(), *(token.lower() for token in reviewer.replace(".", " ").split() if len(token) > 2)}
    kept = [line for line in lines
            if not re.search(r"user_public_page|orcid\.org/|pci\.rr\.\d+\.rev\d+", line)
            and line.strip().strip(",-").strip().lower() not in names]
    return "\n".join(kept).strip() + "\n"


def report_text(path: Path) -> str:
    """Extract a report; RTF reports (common in the Meta-Psychology archive) go through LibreOffice."""
    if path.suffix.lower() != ".rtf":
        extracted = ingest(path)
        if extracted.extraction_warnings:
            raise ValueError(f"Review extraction needs inspection: {extracted.extraction_warnings}")
        return extracted.text
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if not office:
        raise ValueError(f"LibreOffice is required to extract RTF report {path}")
    with tempfile.TemporaryDirectory() as out:
        subprocess.run([office, "--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", out, str(path)],
                       check=True, capture_output=True, timeout=180)
        text = (Path(out) / f"{path.stem}.txt").read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError(f"No text could be extracted from {path}")
    return text


def report_section(text: str, extract: dict) -> str:
    """Apply declared in-line replacements, then the curated manifest's bounded, de-identified selection."""
    for old, new in extract.get("replace", []):
        if text.count(old) != 1:
            raise ValueError(f"Review replacement marker is absent or ambiguous: {old}")
        text = text.replace(old, new)
    return PREPARE["review_section"](text, extract)


def prepare_case(case: dict, fenced: bool) -> dict:
    root = (FENCED if fenced else CACHE) / case["id"]
    record = {"id": case["id"], "split": case["split"], "files": []}
    raws: dict[str, bytes] = {}
    for source in case["sources"]:
        folder = "manuscript" if source["role"] == "manuscript" else "human-reviews"
        path = root / folder / source["filename"]
        raws[source["filename"]] = fetch(source["url"], source["sha256"], path)
        record["files"].append({"path": str(path.relative_to(ROOT)), "sha256": source["sha256"], "role": source["role"]})
    if fenced:
        return record
    manuscript = next(s for s in case["sources"] if s["role"] == "manuscript")
    path = root / "manuscript" / manuscript["filename"]
    source = ingest(path)
    path.with_suffix(".txt").write_text(source.text)
    record["manuscript_text_sha256"] = hashlib.sha256(source.text.encode()).hexdigest()
    record["extraction_warnings"] = source.extraction_warnings
    comparators = root / "comparators"
    comparators.mkdir(exist_ok=True)
    record["comparators"] = []
    history = next((s for s in case["sources"] if s["role"] == "review_history"), None)
    if history:
        raw = raws[history["filename"]]
        reports = peerj_reports(raw) if history["extraction"] == "peerj_v0.1" else pci_reports(raw)
        if len(reports) != len(case["reviews"]):
            raise ValueError(f"{case['id']}: expected {len(case['reviews'])} reports, extracted {len(reports)}")
        for review, report in zip(case["reviews"], reports):
            if hashlib.sha256(report.encode()).hexdigest() != review["derived_text_sha256"]:
                raise ValueError(f"{case['id']}/{review['id']}: derived report text changed")
            text = anonymize_html_report(report, history["extraction"], review.get("reviewer"))
            (comparators / f"{review['id']}.txt").write_text(text)
            record["comparators"].append({"id": review["id"], "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    else:
        for review in case["reviews"]:
            source = next(s for s in case["sources"] if s["role"] == "review" and
                          (s.get("review_id") == review["id"] or (review.get("bundle") and "review_id" not in s)))
            text = report_section(report_text(root / "human-reviews" / source["filename"]), review.get("extract", {}))
            (comparators / f"{review['id']}.txt").write_text(text)
            record["comparators"].append({"id": review["id"], "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
    (root / "prepared.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", type=Path, default=SPLITS)
    parser.add_argument("--split", action="append", choices=["development", "judge_calibration", "fenced_validation"])
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    wanted = set(args.split or ["development", "judge_calibration"])
    cases = [c for c in json.loads(args.splits.read_text())["cases"] if c["split"] in wanted and c.get("sources")]
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
    for case in cases:
        record = prepare_case(case, fenced=case["split"] == "fenced_validation")
        print(f"{case['split']}: {case['id']} ({len(record['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
