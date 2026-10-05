#!/usr/bin/env python3
"""Flag tool calls in review runs that could have exposed the human reviews of the paper.

Reads each run's review.json (every stage records its tool calls) and flags:
- fetched URLs (including pages opened from earlier search results) and URLs in commands or
  search queries that match the benchmark paper's own DOI, article, manuscript or review pages;
- fetched or requested URLs on a review/commentary site or with a peer-review path
  (REVIEW_DOMAINS, REVIEW_PATHS), including the planted-error benchmark repository;
- search queries naming the paper together with review terms. For planted-error papers a
  query containing the title, or a title part of at least three distinctive words, in order is flagged,
  because the published original is the answer key. A query that only shares most title
  words, as a search for a cited paper on the same topic does, is listed as a warning.

The paper is identified by matching the run's source sha256 against corpus manifests
(`manuscript_sha256`, or `review_input_sha256` for planted-error papers). The open-review,
empirical-pilot and planted-error manifests are read by default; `--manifest` adds others.
`--paper` names a manifest id (planted-error papers are `known-error-N`) instead of matching
by hash, and `--title` / `--block` add identifiers for papers outside the manifests. Queries
are checked against the entry's `title` and any `alt_titles`.

Pages that only appear in a search result list, without being opened, are not flagged. The
model then sees a title and a short snippet, and ordinary topic searches routinely list the
published original of a benchmark paper. A snippet can expose an abstract-level detail, but
few planted errors sit at that level; report this as a limitation rather than a leak.

Verdicts: `flagged` (a contamination candidate), `incomplete` (a model stage failed, lacks
recorded provenance, has a call that never finished, or has a fetch whose opened page is not
recorded, so the record cannot show the run is clean), or `clean`. Exits 1 when any run is not clean.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from reviscope.backend import REVIEW_DOMAINS  # noqa: E402

DEFAULT_MANIFESTS = [ROOT / "eval/corpus/open_peer_review_curated.v1.json",
                     ROOT / "eval/corpus/open_peer_review.v1.json", ROOT / "eval/corpus/empirical_pilot.v1.json",
                     ROOT / "eval/corpus/known_errors.v1.json"]
URL_FIELDS = ("doi", "article_url", "review_url", "review_urls", "manuscript_under_review_url", "archived_manuscript_url",
              "original_urls", "answer_key_urls", "editorial_archive", "other_version_urls")
REVIEW_PATHS = re.compile(r"peer[-_ ]?reviews?|referee|review[-_]history|decision[-_]letter|reviewer[-_]comments|"
                          r"/reviews?/|author[-_]response|elifesciences\.org/reviewed-preprints/.*reviews|"
                          r"dawes-institute/ai-peer-review-benchmark", re.I)
REVIEW_TERMS = re.compile(r"\b(reviews?|reviewers?|referees?|peer[- ]review|decision letter|editor|editorial|"
                          r"pubpeer|commentary|comment|reply|rebuttal|critique|response to)\b", re.I)
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>\])]+")
EXCLUDED_TERM = re.compile(r"(?:^|\s)-(?:\"[^\"]*\"|\S+)")
STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "under", "their", "across", "about"}


def normal_url(url: str) -> str:
    url = url.strip().lower().split("#", 1)[0]
    url = re.sub(r"^https?://(www\.)?", "", url)
    return url.rstrip("/")


def phrase(text: str) -> str:
    """Distinctive words (as in title_words) in order, joined by spaces, padded for whole-word matching."""
    words = [word for word in re.findall(r"[a-z0-9]+", text.casefold()) if len(word) > 3 and word not in STOPWORDS]
    return " " + " ".join(words) + " "


def title_phrases(title: str) -> list[str]:
    """The full title and each colon- or question-mark-separated part with at least three distinctive words."""
    parts = [title, *re.split(r"[:?]", title)]
    return list(dict.fromkeys(p for p in map(phrase, parts) if len(p.split()) >= 3))


def title_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.casefold()) if len(word) > 3 and word not in STOPWORDS}


def load_papers(manifests: list[Path]) -> list[dict[str, Any]]:
    """Paper identities from corpus manifests. Entries with `review_input_sha256` are planted-error papers."""
    papers = []
    for manifest in manifests:
        for entry in json.loads(manifest.read_text(encoding="utf-8"))["entries"]:
            planted = "review_input_sha256" in entry
            blocks = []
            for field in URL_FIELDS:
                value = entry.get(field)
                blocks.extend(value if isinstance(value, list) else [value] if value else [])
            blocks.extend(review["url"] for review in entry.get("human_reviews", []) if review.get("url"))
            osf_guids = {part.lower() for url in blocks
                         if urlsplit(url).hostname in {"osf.io", "www.osf.io"}
                         for part in urlsplit(url).path.split("/")
                         if re.fullmatch(r"[a-zA-Z0-9]{5}|[a-fA-F0-9]{24}", part)}
            osf_guids.update(review["osf_file_id"].lower() for review in entry.get("human_reviews", [])
                             if review.get("osf_file_id"))
            if entry.get("manuscript", {}).get("osf_file_id"):
                osf_guids.add(entry["manuscript"]["osf_file_id"].lower())
            if planted and entry.get("url"):
                blocks.append(entry["url"])
            titles = [title for title in [entry.get("title"), *entry.get("alt_titles", [])] if title]
            papers.append({"id": str(entry.get("id") or f"known-error-{entry['paper']}"), "titles": titles,
                           "sha256": {entry.get("manuscript_sha256"), entry.get("manuscript_text_sha256"),
                                      entry.get("review_input_sha256")} - {None},
                           "blocks": blocks, "osf_guids": sorted(osf_guids), "planted_errors": planted})
    return papers


def identify(run: dict[str, Any], papers: list[dict[str, Any]], paper_id: str | None) -> dict[str, Any] | None:
    if paper_id:
        match = next((p for p in papers if p["id"] == paper_id), None)
        if match is None:
            raise SystemExit(f"Unknown paper id {paper_id!r}")
        return match
    hashes = {source.get("sha256") for source in run.get("sources", [])}
    return next((p for p in papers if p["sha256"] & hashes), None)


def audit_calls(calls: list[dict[str, Any]], paper: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """Reasons to flag the run, and warnings to show without flagging it."""
    blocks = [normal_url(b) for b in (paper or {}).get("blocks", [])]
    dois = [b for b in blocks if b.startswith("10.")] + [b.split("doi.org/", 1)[1] for b in blocks if "doi.org/" in b]
    titles = [title_words(title) for title in (paper or {}).get("titles", [])]
    phrases = [p for title in (paper or {}).get("titles", []) for p in title_phrases(title)]
    reasons, warnings = [], []

    def check_url(url: str, how: str, where: str, *, listed: bool = False) -> None:
        messages = warnings if listed else reasons
        low = normal_url(url)
        host = low.split("/", 1)[0]
        own = any(low == b or low.startswith((b + "/", b + "?")) for b in blocks if not b.startswith("10."))
        parsed = urlsplit("https://" + low)
        if parsed.hostname == "osf.io" or (parsed.hostname or "").endswith(".osf.io"):
            parts = set(re.split(r"[^a-z0-9]+", unquote(parsed.path + "?" + parsed.query)))
            own |= bool(parts & set((paper or {}).get("osf_guids", [])))
        if own or any(d in low for d in dois):
            messages.append(f"{where}: {how} URL of the benchmark paper: {url}")
        elif any(host == d or host.endswith("." + d) for d in REVIEW_DOMAINS):
            messages.append(f"{where}: {how} review/commentary site: {url}")
        elif REVIEW_PATHS.search(low):
            messages.append(f"{where}: {how} peer-review page: {url}")

    for call in calls:
        where = f"{call.get('stage') or 'stage?'}#{call.get('sequence')}"
        for url in dict.fromkeys(filter(None, [call.get("url"), *(call.get("opened_urls") or [])])):
            check_url(url, "fetched", where)
        for url in URL_IN_TEXT.findall(" ".join(filter(None, [call.get("query"), call.get("command")]))):
            check_url(url, "requested", where)
        # Listings remain non-flagging under the existing policy, but retain exposure warnings.
        for url in dict.fromkeys(call.get("result_urls") or []):
            check_url(url, "listed (not opened)", where, listed=True)
        # Excluded terms (-"phrase", -word) keep matching pages out; they are not a search for them.
        query = EXCLUDED_TERM.sub(" ", call.get("query") or "").strip()
        if not query:
            continue
        if any(d in query.lower() for d in dois):
            reasons.append(f"{where}: search for the paper's DOI: {query!r}")
            continue
        words = title_words(query)
        overlap = max((len(title & words) / len(title) for title in titles if title), default=0)
        names_title = any(p in phrase(query) for p in phrases)
        if overlap >= 0.6 and REVIEW_TERMS.search(query):
            reasons.append(f"{where}: search for reviews of this paper: {query!r}")
        elif names_title and paper and paper["planted_errors"]:
            reasons.append(f"{where}: search for the planted-error paper's title (original is the answer key): {query!r}")
        elif overlap >= 0.6:
            warnings.append(f"{where}: query shares most title words but not the title phrase: {query!r}")
    return reasons, warnings


def audit_run(path: Path, papers: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    review = path / "review.json" if path.is_dir() else path
    run = json.loads(review.read_text(encoding="utf-8"))
    paper = identify(run, papers, args.paper)
    if args.title or args.block:
        paper = {"id": (paper or {}).get("id", "manual"), "titles": [args.title] if args.title else (paper or {}).get("titles", []),
                 "blocks": [*(paper or {}).get("blocks", []), *args.block],
                 "osf_guids": (paper or {}).get("osf_guids", []),
                 "planted_errors": args.planted_errors or bool(paper and paper["planted_errors"])}
    stages = run.get("stages", [])
    calls = [call for stage in stages for call in stage.get("tool_calls", [])]
    reasons, warnings = audit_calls(calls, paper)
    gaps = provenance_gaps(stages)
    note = f"paper {paper['id']}" if paper else "paper not identified; only generic review-site checks applied"
    overrides = {key: getattr(args, key) for key in ("paper", "title", "block", "planted_errors") if getattr(args, key)}
    return {"run": str(review.resolve()), "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
            "audit_rules_sha256": audit_rules_hash(papers, overrides), "audit_overrides": overrides,
            "paper": paper and paper["id"], "note": note, "tool_calls": len(calls),
            "verdict": "flagged" if reasons else "incomplete" if gaps else "clean", "reasons": [*reasons, *gaps],
            "warnings": warnings}


def audit_rules_hash(papers: list[dict[str, Any]], overrides: dict | None = None) -> str:
    identities = [{**p, "sha256": sorted(p["sha256"])} for p in papers]
    return hashlib.sha256(Path(__file__).read_bytes() +
                          json.dumps({"papers": identities, "review_domains": sorted(REVIEW_DOMAINS),
                                      "overrides": overrides or {}}, sort_keys=True).encode()).hexdigest()


MODEL_STAGES = re.compile(r"^(study_map|review-.+|verification(?:-.+)?|editorial)$")


def opened_nothing(output: Any) -> bool:
    """An open whose result is empty, or only codex "Internal Error" items without a URL, showed no page."""
    try:
        items = json.loads(output) if isinstance(output, str) else output
    except json.JSONDecodeError:
        return False
    return isinstance(items, list) and all(isinstance(i, dict) and not i.get("url") and i.get("title") == "Internal Error" for i in items)


def provenance_gaps(stages: list[dict[str, Any]]) -> list[str]:
    """Reasons the recorded tool calls may not cover everything the models did."""
    gaps = []
    for stage in stages:
        name = stage.get("name", "?")
        if not MODEL_STAGES.match(name):
            continue
        if stage.get("status") == "failed":
            gaps.append(f"{name}: stage failed ({stage.get('error') or 'no error recorded'}); its tool calls may be incomplete")
        elif stage.get("cache_key") and "tool_calls" not in stage:
            gaps.append(f"{name}: no tool-call provenance recorded")
        for call in stage.get("tool_calls", []):
            if str(call.get("output", "")).startswith("[incomplete"):
                gaps.append(f"{name}#{call.get('sequence')}: call never finished")
            elif (call.get("kind") == "fetch" and not call.get("url") and not call.get("opened_urls")
                  and not call.get("error") and not opened_nothing(call.get("output"))):
                gaps.append(f"{name}#{call.get('sequence')}: fetch without a recorded page URL")
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path, help="Run directories or review.json files")
    parser.add_argument("--manifest", action="append", default=[], type=Path, help="Extra corpus manifest with an `entries` list (repeatable)")
    parser.add_argument("--paper", help="Manifest id of the reviewed paper (default: match by source sha256)")
    parser.add_argument("--title", help="Paper title for query checks when the paper is not in a manifest")
    parser.add_argument("--block", action="append", default=[], help="URL prefix or DOI of the paper's own pages, e.g. its review page (repeatable)")
    parser.add_argument("--planted-errors", action="store_true", help="Treat a title search alone as a leak")
    parser.add_argument("--json", type=Path, help="Write all verdicts to this JSON file")
    args = parser.parse_args()
    papers = load_papers([*DEFAULT_MANIFESTS, *args.manifest])
    results = [audit_run(path, papers, args) for path in args.runs]
    for result in results:
        print(f"{result['verdict'].upper():8} {result['run']} ({result['note']}; {result['tool_calls']} tool calls)")
        for reason in result["reasons"]:
            print(f"    {reason}")
        for warning in result["warnings"]:
            print(f"    warning: {warning}")
    if args.json:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if any(r["verdict"] != "clean" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
