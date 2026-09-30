"""Download the Dawes planted-error benchmark and prepare blind review inputs.

Each paper gets `inputs/paper-NN/manuscript.review-input.txt`: the modified DOCX
body text with the benchmark banner paragraph (which announces the planted
errors) and following blank lines removed. Annotations go to a separate
`ground_truth/` directory and are never passed to review generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from reviscope.ingest import _docx

COMMIT = "3d9188343eebd4312d3bfbde6822cfa4eaf32fb4"
RAW = f"https://raw.githubusercontent.com/Dawes-Institute/ai-peer-review-benchmark/{COMMIT}/"
BANNER = "BENCHMARK ARTIFACT"
ROOT = Path(__file__).resolve().parents[1]


def fetch(relative: str, target: Path) -> str:
    if not target.exists():
        with urllib.request.urlopen(RAW + urllib.parse.quote(relative)) as response:
            data = response.read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.with_suffix(".tmp").write_bytes(data)
        target.with_suffix(".tmp").replace(target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def review_input(docx: Path) -> str:
    lines = _docx(docx).split("\n")
    if not lines[0].startswith(BANNER):
        raise ValueError(f"{docx}: first paragraph is not the benchmark banner")
    start = 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    return "\n".join(lines[start:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    args = parser.parse_args()

    labels = args.root / "ground_truth" / "error_insertions.csv"
    labels_sha = fetch("error_insertions.csv", labels)
    for paper in range(1, 11):
        directory = args.root / "inputs" / f"paper-{paper:02d}"
        docx = directory / "manuscript.modified.docx"
        docx_sha = fetch(f"modified papers/{paper}.docx", docx)
        text = review_input(docx)
        (directory / "manuscript.review-input.txt").write_text(text, encoding="utf-8")
        provenance = {
            "paper": str(paper),
            "commit": COMMIT,
            "url": RAW + urllib.parse.quote(f"modified papers/{paper}.docx"),
            "sha256": docx_sha,
            "review_input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "license": "CC BY 4.0 per upstream source manifest",
            "generation_input": "manuscript.review-input.txt",
            "transformation": "DOCX body extraction; remove only initial benchmark banner paragraph and subsequent blank lines.",
            "labels": f"../../ground_truth/error_insertions.csv (sha256 {labels_sha}); exclude from generation",
        }
        (directory / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"paper {paper:2d}: {len(text):6d} chars, input sha256 {provenance['review_input_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
