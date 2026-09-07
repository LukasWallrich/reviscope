#!/usr/bin/env python3
"""Discover submission-proximate PsyArXiv files for a journal sample.

This is a discovery aid, not an admission rule. It queries Crossref for journal
articles and PsyArXiv candidates, then checks OSF's primary-file version history
and the publisher page. Network responses are cached outside version control.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

USER_AGENT = "coarse-socpsy-preprint-discovery/0.1"
PSYARXIV_PREFIXES = ("10.31234", "10.31219")


def _normal(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class CachedHTTP:
    def __init__(self, root: Path, delay: float = 0.08):
        self.directory = root
        self.directory.mkdir(parents=True, exist_ok=True)
        self.delay = delay

    def get(self, url: str, params: dict[str, object] | None = None, *, text: bool = False) -> Any:
        full = url
        if params:
            full += "?" + urllib.parse.urlencode(params)
        suffix = ".txt" if text else ".json"
        target = self.directory / (_digest(full) + suffix)
        if not target.exists():
            for attempt in range(4):
                request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        target.write_bytes(response.read())
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 and exc.code < 500:
                        raise
                    if attempt == 3:
                        raise
                    retry_after = exc.headers.get("Retry-After")
                    wait = min(float(retry_after), 10.0) if retry_after and retry_after.isdigit() else 1.5 * (2**attempt)
                    time.sleep(wait)
            time.sleep(self.delay)
        raw = target.read_text(errors="replace")
        return raw if text else json.loads(raw)


def _date_parts(value: dict[str, Any] | None) -> date | None:
    try:
        parts = value["date-parts"][0]
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _families(work: dict[str, Any]) -> set[str]:
    return {_normal(a.get("family", "")) for a in work.get("author", []) if a.get("family")}


def journal_works(http: CachedHTTP, issn: str, rows: int, query: str | None) -> list[dict[str, Any]]:
    params: dict[str, object] = {
        "rows": rows,
        "filter": "type:journal-article,from-pub-date:2020-01-01",
        "select": "DOI,title,author,published,URL",
        "sort": "published",
        "order": "desc",
    }
    if query:
        params["query.bibliographic"] = query
        params.pop("sort")
        params.pop("order")
    return http.get(f"https://api.crossref.org/journals/{issn}/works", params)["message"]["items"]


def preprint_candidates(http: CachedHTTP, work: dict[str, Any]) -> list[dict[str, Any]]:
    title = work["title"][0]
    results: list[dict[str, Any]] = []
    for prefix in PSYARXIV_PREFIXES:
        payload = http.get(
            f"https://api.crossref.org/prefixes/{prefix}/works",
            {
                "query.title": title,
                "rows": 8,
                "filter": "type:posted-content",
                "select": "DOI,title,author,published,posted,URL",
            },
        )
        results.extend(payload["message"]["items"])
    article_authors = _families(work)
    candidates = []
    for item in results:
        title_score = SequenceMatcher(None, _normal(title), _normal(item["title"][0])).ratio()
        overlap = sorted(article_authors & _families(item))
        if title_score >= 0.55 and overlap:
            item = dict(item)
            item["title_score"] = round(title_score, 4)
            item["author_overlap"] = overlap
            candidates.append(item)
    unique = {item["DOI"].casefold(): item for item in candidates}
    return sorted(unique.values(), key=lambda x: x["title_score"], reverse=True)


def osf_versions(http: CachedHTTP, doi: str) -> dict[str, Any] | None:
    match = re.search(r"osf\.io/([a-z0-9]+(?:_v[0-9]+)?)", doi, re.I)
    if not match:
        return None
    node = match.group(1)
    try:
        # A bare OSF ID can resolve to the latest record version. Prefer the
        # explicitly immutable v1 record when it exists.
        base = re.sub(r"_v[0-9]+$", "", node, flags=re.I)
        if re.search(r"_v[0-9]+$", node, re.I):
            preprint = http.get(f"https://api.osf.io/v2/preprints/{node}/")["data"]
        else:
            try:
                preprint = http.get(f"https://api.osf.io/v2/preprints/{base}_v1/")["data"]
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                preprint = http.get(f"https://api.osf.io/v2/preprints/{node}/")["data"]
        relation = preprint["relationships"]["primary_file"]["links"]["related"]["href"]
        primary = http.get(relation)["data"]
        versions_url = f"https://api.osf.io/v2/files/{primary['id']}/versions/"
        page = http.get(versions_url)
        versions = list(page["data"])
        while page.get("links", {}).get("next"):
            page = http.get(page["links"]["next"])
            versions.extend(page["data"])
    except (KeyError, urllib.error.HTTPError):
        return None
    return {
        "record_id": preprint["id"],
        "record_date_published": preprint["attributes"].get("date_published"),
        "primary_file_id": primary["id"],
        "primary_file_name": primary["attributes"].get("name"),
        "versions_api_url": versions_url,
        "versions": [
            {
                "revision": version["id"],
                "date_created": version["attributes"].get("date_created"),
                "size": version["attributes"].get("size"),
                "download_url": version["links"].get("download"),
            }
            for version in versions
        ],
    }


def nature_metadata(http: CachedHTTP, doi: str) -> dict[str, Any]:
    url = "https://www.nature.com/articles/" + doi.rsplit("/", 1)[-1]
    page = http.get(url, text=True)
    received = re.search(r"Received.*?<time[^>]*datetime=\"([^\"]+)", page, re.S)
    if not received:
        received = re.search(r"Received:\s*</?[^>]*>?\s*([0-9]{1,2}\s+\w+\s+[0-9]{4})", page)
    received_value = received.group(1) if received else None
    review = re.search(r'href="([^"]+)"[^>]*>[^<]*(?:transparent\s+)?peer review file', page, re.I)
    return {
        "article_url": url,
        "received": received_value,
        "peer_review_url": html.unescape(review.group(1)) if review else None,
    }


def _parse_iso_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%d %B %Y").date()
        except ValueError:
            return None


def discover(http: CachedHTTP, issn: str, rows: int, query: str | None) -> dict[str, Any]:
    works = journal_works(http, issn, rows, query)
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, work in enumerate(works, 1):
        try:
            candidates = preprint_candidates(http, work)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            errors.append({"article_doi": work.get("DOI", ""), "stage": "preprint_search", "error": type(exc).__name__})
            continue
        for preprint in candidates:
            version_info = osf_versions(http, preprint["DOI"])
            if not version_info:
                errors.append({"article_doi": work["DOI"], "stage": "osf_resolution", "error": "no_data"})
                continue
            try:
                publisher = nature_metadata(http, work["DOI"])
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                errors.append({"article_doi": work["DOI"], "stage": "publisher_metadata", "error": type(exc).__name__})
                publisher = {"article_url": work.get("URL"), "received": None, "peer_review_url": None}
            received = _parse_iso_day(publisher["received"])
            for version in version_info["versions"]:
                version_day = _parse_iso_day(version["date_created"])
                record_day = _parse_iso_day(version_info["record_date_published"])
                public_day = max(d for d in (version_day, record_day) if d) if (version_day or record_day) else None
                version["file_created_day_gap"] = (version_day - received).days if received and version_day else None
                version["public_artifact_date"] = public_day.isoformat() if public_day else None
                version["signed_day_gap"] = (public_day - received).days if received and public_day else None
            ranked = [v for v in version_info["versions"] if v["signed_day_gap"] is not None]
            nearest = min(ranked, key=lambda v: abs(v["signed_day_gap"])) if ranked else None
            matches.append({
                "article_doi": work["DOI"],
                "article_title": work["title"][0],
                "article_published": str(_date_parts(work.get("published"))) if _date_parts(work.get("published")) else None,
                **publisher,
                "preprint_doi": preprint["DOI"],
                "preprint_title": preprint["title"][0],
                "title_score": preprint["title_score"],
                "author_overlap": preprint["author_overlap"],
                "candidate_status": "unconfirmed_title_author_match",
                **version_info,
                "nearest_version": nearest,
            })
        if index % 20 == 0:
            print(f"checked {index}/{len(works)}; retained {len(matches)}", flush=True)
    matches.sort(key=lambda m: abs(m["nearest_version"]["signed_day_gap"]) if m["nearest_version"] else 10**9)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "query": {"issn": issn, "rows": rows, "bibliographic_query": query},
        "method": "Crossref journal sample -> Crossref PsyArXiv title candidates -> author overlap -> OSF primary-file versions -> publisher HTML",
        "caveats": [
            "This is candidate discovery, not proof that a preprint file is the submitted manuscript.",
            "OSF DOI is not treated as a filterable preprint API field.",
            "A mutable preprint landing record may serve a post-review file; use the recorded revision URL.",
        ],
        "articles_checked": len(works),
        "request_failures": errors,
        "matches": matches,
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    csv_path = output.with_suffix(".csv")
    fields = ["article_doi", "article_title", "received", "preprint_doi", "record_date_published", "revision", "revision_date", "signed_day_gap", "peer_review_url", "download_url", "title_score"]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for match in result["matches"]:
            nearest = match.get("nearest_version") or {}
            writer.writerow({
                "article_doi": match["article_doi"], "article_title": match["article_title"],
                "received": match["received"], "preprint_doi": match["preprint_doi"],
                "record_date_published": match["record_date_published"], "revision": nearest.get("revision"),
                "revision_date": nearest.get("date_created"), "signed_day_gap": nearest.get("signed_day_gap"),
                "peer_review_url": match["peer_review_url"], "download_url": nearest.get("download_url"),
                "title_score": match["title_score"],
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issn", required=True)
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--query")
    parser.add_argument("--cache", type=Path, default=Path("eval/corpus/cache/discovery"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 500:
        parser.error("--rows must be between 1 and 500")
    result = discover(CachedHTTP(args.cache), args.issn, args.rows, args.query)
    write_outputs(result, args.output)
    print(f"wrote {args.output} and {args.output.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
