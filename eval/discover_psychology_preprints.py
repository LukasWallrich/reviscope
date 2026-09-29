#!/usr/bin/env python3
"""Discover PsyArXiv relations for a bounded set of journal articles.

This is a discovery aid, not an eligibility classifier. It queries Crossref for
recent journal works, searches the PsyArXiv DOI prefix by title, and retains only
explicit ``is-preprint-of`` DOI relations back to the journal work. Historical
OSF file versions and publisher receipt dates still require separate checks.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import urllib.error

JOURNALS = {
    "European Journal of Personality": "1099-0984",
    "Quarterly Journal of Experimental Psychology": "1747-0218",
    "Journal of Community Psychology": "1520-6629",
    "BMC Psychology": "2050-7283",
}
AGENT = "reviscope-preprint-discovery/0.1"
CACHE = Path("eval/corpus/cache/crossref-psychology-discovery")


def get(url: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
                cached.write_text(json.dumps(payload), encoding="utf-8")
                return payload
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def works(issn: str, rows: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "filter": "from-pub-date:2019-01-01,type:journal-article",
            "sort": "published",
            "order": "desc",
            "rows": rows,
            "select": "DOI,title,published",
        }
    )
    return get(f"https://api.crossref.org/journals/{issn}/works?{params}")["message"]["items"]


def preprint_matches(work: dict) -> list[dict]:
    title = work.get("title", [""])[0]
    params = urllib.parse.urlencode(
        {"query.title": title, "rows": 3, "select": "DOI,title,relation,published"}
    )
    items = get(f"https://api.crossref.org/prefixes/10.31234/works?{params}")["message"]["items"]
    target = work["DOI"].lower()
    found = []
    for item in items:
        related = item.get("relation", {}).get("is-preprint-of", [])
        if not any(entry.get("id", "").lower() == target for entry in related):
            continue
        candidate_title = item.get("title", [""])[0]
        item["title_similarity"] = round(
            difflib.SequenceMatcher(None, title.casefold(), candidate_title.casefold()).ratio(), 3
        )
        found.append(item)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-journal", type=int, default=25)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.per_journal < 1 or args.per_journal * len(JOURNALS) > 100:
        parser.error("bounded search requires 1–25 works per journal (100 total maximum)")

    result = {
        "search_limit": args.per_journal * len(JOURNALS),
        "method": "recent Crossref journal works; exact is-preprint-of DOI relations only",
        "journals": {},
        "failed_requests": [],
    }
    for journal, issn in JOURNALS.items():
        examined = works(issn, args.per_journal)
        matches = []
        for work in examined:
            try:
                for preprint in preprint_matches(work):
                    matches.append({"article": work, "preprint": preprint})
            except Exception as error:
                result["failed_requests"].append(
                    {"article_doi": work.get("DOI"), "error": f"{type(error).__name__}: {error}"}
                )
            time.sleep(0.5)
        result["journals"][journal] = {"examined": len(examined), "matches": matches}
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
