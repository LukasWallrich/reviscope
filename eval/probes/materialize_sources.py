"""Copy criticism-probe source documents into the gitignored eval/probes/sources/.

Probe manuscripts are licensed or unpublished, so the repository stores only their
canonical locations and SHA-256 digests. Sources live in the main checkout's gitignored
``runs/`` and ``eval/corpus/cache/`` trees. Each file is copied byte-for-byte; a
digest mismatch aborts, because probe quotes and labels were checked against these
exact bytes. The judge reads the copy through ``reviscope.ingest.ingest``.

Usage: python eval/probes/materialize_sources.py [--root MAIN_CHECKOUT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCES = HERE / "sources"

# target (relative to eval/probes/sources) -> (canonical path relative to main checkout, sha256)
MANIFEST: dict[str, tuple[str, str]] = {
    "dawes-01/manuscript.txt": ("runs/known-errors-all/inputs/paper-01/manuscript.review-input.txt",
                                "101e3196fc43ba700a39889c8bb74e977294144245a27fe4568756bed89c6ece"),
    "dawes-04/manuscript.txt": ("runs/known-errors-all/inputs/paper-04/manuscript.review-input.txt",
                                "3a6db23a329dcd61c4c5e2ed721ab91665e15e295b4b8e71e355731ba3ec1cfa"),
    "dawes-05/manuscript.txt": ("runs/known-errors-all/inputs/paper-05/manuscript.review-input.txt",
                                "b247e1f36a2f3cf2b17b5580c7392feaeb6f52bff23a97d546d9e190551cef31"),
    "dawes-07/manuscript.txt": ("runs/known-errors-all/inputs/paper-07/manuscript.review-input.txt",
                                "79ab80c20627018e129da7f431f7efcf9891fa92e3aa927bbf1ba575944601bc"),
    "dawes-10/manuscript.txt": ("runs/known-errors-all/inputs/paper-10/manuscript.review-input.txt",
                                "d71cbddf969106491f96117b82904524083ece4da221d807bf841612e75002ab"),
    "bonetto/manuscript.txt": ("eval/corpus/cache/open-review-curation-20261002/bonetto/manuscript/original.txt",
                               "bf652e17864470d6a4457626ace5df38853e68b4e25ca83bdc7be124b11332e8"),
    "ziano/manuscript.txt": ("eval/corpus/cache/open-review-curation-20261002/ziano/manuscript/original.txt",
                             "4e9f603c25e98169f6cb95ce6e5b3304bf2968cda1a1399a85850ce9944ba5d8"),
    "owner-negativity/main-manuscript.pdf": ("runs/owner-paper-20261009/inputs/main-manuscript.pdf",
                                             "3fa95c2a90056c19d27e020270fe7570cd6f135a49249d5fee4889b4f14b3859"),
    "owner-negativity/technical-supplement.pdf": ("runs/owner-paper-20261009/inputs/technical-supplement.pdf",
                                                  "adbf84c64e6ae3c5d92ab21d641068322143a50f80590d3721eab9ed5a9e1dfd"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main_checkout() -> Path:
    """The main checkout owns runs/ and the corpus cache; a worktree shares its git dir."""
    out = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    return Path(out).parent


def materialize(root: Path) -> dict[str, dict[str, str]]:
    record = {}
    for target, (canonical, digest) in MANIFEST.items():
        src, dst = root / canonical, SOURCES / target
        if not src.is_file():
            raise FileNotFoundError(f"Missing canonical source {src}")
        if (actual := sha256(src)) != digest:
            raise ValueError(f"{src}: sha256 {actual} != recorded {digest}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        record[target] = {"canonical": canonical, "sha256": digest}
    (SOURCES / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, help="main checkout containing runs/ and eval/corpus/cache/")
    args = parser.parse_args()
    done = materialize((args.root or main_checkout()).resolve())
    print(f"Materialized {len(done)} sources into {SOURCES}")
