"""Refuse manuscripts or run directories that touch the fenced validation set.

Usage:
    .venv/bin/python eval/check_fence.py PATH [PATH ...]

PATH may be a manuscript file or a run directory. Exit status 0 means no fenced
identifier was found; 3 means at least one fenced match (details on stderr); 2
means the splits manifest is missing or invalid. Run drivers call
``assert_not_fenced`` (or this script) on every manuscript before generation and
on the run directory before judging. See docs/CORPUS_SPLITS.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "eval/corpus/splits.v1.json"
TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".log", ".html", ".csv", ".yaml", ".yml", ".tex", ".rtf"}
MAX_TEXT_BYTES = 50_000_000


class FencedInputError(RuntimeError):
    """Raised when an input belongs to the fenced validation set."""


def _norm_doi(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(".")


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_fence(path: Path = SPLITS) -> dict:
    """Return fenced identifiers: file hashes, DOIs, URLs, case IDs and titles."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported splits schema_version")
    hashes: dict[str, str] = {}
    dois: dict[str, str] = {}
    urls: dict[str, str] = {}
    titles: dict[str, str] = {}
    ids: set[str] = set()
    for case in manifest["cases"]:
        if case["split"] != "fenced_validation":
            continue
        ids.add(case["id"])
        for digest in case.get("fence_sha256", []):
            hashes[digest.lower()] = case["id"]
        for doi in filter(None, [case.get("doi"), *case.get("fence_dois", [])]):
            dois[_norm_doi(doi)] = case["id"]
        for url in case.get("fence_urls", []):
            urls[url.rstrip("/")] = case["id"]
        if case.get("title") and len(_norm_text(case["title"])) >= 25:
            titles[_norm_text(case["title"])] = case["id"]
    if not ids:
        raise ValueError("splits manifest defines no fenced cases")
    return {"hashes": hashes, "dois": dois, "urls": urls, "titles": titles, "ids": ids}


def _is_fence_definition(path: Path) -> bool:
    """Code snapshots copy the splits manifest and this checker; they are not run inputs."""
    return re.fullmatch(r"splits\.v\d+\.json", path.name) is not None or path.name == "check_fence.py"


def _files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    elif path.is_dir():
        yield from (p for p in sorted(path.rglob("*")) if p.is_file() and not _is_fence_definition(p))
    else:
        raise FileNotFoundError(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _extracted_text(path: Path) -> str:
    """Best-effort text for PDFs/DOCX so renamed or converted inputs are caught by title."""
    try:
        from reviscope.ingest import ingest
    except ImportError:
        return ""
    try:
        return ingest(path).text[:20000]
    except Exception:
        return ""


def _mentions(value: str, text: str) -> bool:
    """Substring match that does not let 10.7717/peerj.287 match peerj.2870 or osf.io/abcde match abcdef."""
    return re.search(re.escape(value) + r"(?![0-9a-z])", text) is not None


INPUT_PARTS = {"inputs", "input", "manuscript", "manuscripts"}


def _is_input(path: Path, root: Path) -> bool:
    """Directly named files, and files under an inputs/manuscript directory, are generation inputs."""
    if path == root:
        return True
    return any(part.lower() in INPUT_PARTS for part in path.relative_to(root).parts[:-1])


def scan(paths: Iterable[Path], fence: dict | None = None) -> tuple[list[str], list[str]]:
    """Return (refusals, warnings) for every fenced match in ``paths``.

    File hashes, recorded fenced hashes, fenced case IDs and fenced source URLs always
    refuse. A fenced DOI or title refuses in a generation input; elsewhere in a run
    directory (for example a citation found by web search) it is reported as a warning.
    """
    fence = fence or load_fence()
    refusals: list[str] = []
    warnings: list[str] = []
    for root in map(Path, paths):
        for path in _files(root):
            digest = _sha256(path)
            if digest in fence["hashes"]:
                refusals.append(f"{path}: sha256 of fenced case {fence['hashes'][digest]}")
                continue
            suffix = path.suffix.lower()
            if suffix in TEXT_SUFFIXES and path.stat().st_size <= MAX_TEXT_BYTES:
                text = path.read_text(encoding="utf-8", errors="replace")
            elif suffix in {".pdf", ".docx"}:
                text = _extracted_text(path)
            else:
                continue
            lowered = text.lower()
            for value, case in fence["hashes"].items():
                if value in lowered:
                    refusals.append(f"{path}: records sha256 of fenced case {case}")
            for value, case in fence["urls"].items():
                if _mentions(value.lower(), lowered):
                    refusals.append(f"{path}: mentions source URL of fenced case {case}")
            for value in fence["ids"]:
                if re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", text):
                    refusals.append(f"{path}: mentions fenced case ID {value}")
            mentions = [f"{path}: mentions DOI {value} of fenced case {case}"
                        for value, case in fence["dois"].items() if _mentions(value, lowered)]
            normalized = _norm_text(text)
            mentions += [f"{path}: contains title of fenced case {case}"
                         for value, case in fence["titles"].items() if value in normalized]
            (refusals if _is_input(path, root) else warnings).extend(mentions)
    return sorted(set(refusals)), sorted(set(warnings))


def find_matches(paths: Iterable[Path], fence: dict | None = None) -> list[str]:
    """Return the refusing matches only."""
    return scan(paths, fence)[0]


def assert_not_fenced(*paths: Path | str, splits: Path = SPLITS) -> None:
    """Raise FencedInputError if any path matches the fenced validation set."""
    matches = find_matches([Path(p) for p in paths], load_fence(splits))
    if matches:
        raise FencedInputError("fenced validation input refused:\n" + "\n".join(matches))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="manuscript files or run directories")
    parser.add_argument("--splits", type=Path, default=SPLITS)
    args = parser.parse_args(argv)
    try:
        fence = load_fence(args.splits)
    except (OSError, ValueError, KeyError) as error:
        print(f"check_fence: cannot load {args.splits}: {error}", file=sys.stderr)
        return 2
    try:
        matches, warnings = scan(args.paths, fence)
    except FileNotFoundError as error:
        print(f"check_fence: no such path: {error}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if matches:
        print("REFUSED: input touches the fenced validation set", file=sys.stderr)
        for match in matches:
            print(f"  {match}", file=sys.stderr)
        return 3
    print(f"ok: no fenced case found in {len(args.paths)} path(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
