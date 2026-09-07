#!/usr/bin/env python3
"""Discover near-submission preprints for Royal Society behavioural papers.

This is a read-only corpus-discovery helper. It queries Europe PMC for article
metadata/full text and Crossref for posted-content title matches, then emits
JSON candidates. It never downloads review text or calls a language model.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CROSSREF = "https://api.crossref.org/works"
JOURNALS = ["Royal Society Open Science", "Proceedings of the Royal Society B: Biological Sciences"]
TERMS = re.compile(
    r"social|cognit|behavio|cultur|cooperat|trust|moral|decision|judg|"
    r"personality|attitude|belief|human|psycholog|language|learning|inequal|norm",
    re.I,
)


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def date_parts(item: dict) -> str | None:
    parts = item.get("published", {}).get("date-parts", [[]])[0]
    if len(parts) >= 3:
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    return None


def get(url: str, params: dict[str, object] | None = None) -> tuple[int, str]:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "coarse-socpsy-corpus-discovery/0.1"})
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, ""
    except URLError:
        return 0, ""


def received_date(pmcid: str) -> str | None:
    status, xml = get(f"{EPMC}/{pmcid}/fullTextXML")
    if status != 200:
        return None
    root = ET.fromstring(xml)
    for node in root.iter("date"):
        if node.get("date-type") != "received":
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: child.text for child in node}
        if all(fields.get(key) for key in ("year", "month", "day")):
            return date(int(fields["year"]), int(fields["month"]), int(fields["day"])).isoformat()
    prose = re.search(r"Received\s+(\d{4})\s+([A-Z][a-z]{2})\s+(\d{1,2})", xml)
    if prose:
        months = {name: number for number, name in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
        return date(int(prose.group(1)), months[prose.group(2)], int(prose.group(3))).isoformat()
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-journal", type=int, default=75)
    parser.add_argument("--from-date", default="2021-01-01")
    parser.add_argument("--until-date", default="2026-12-31")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    screened, relevant, matches, query_failures = 0, 0, [], 0
    for journal in JOURNALS:
        query = f'JOURNAL:"{journal}" AND FIRST_PDATE:[{args.from_date} TO {args.until_date}]'
        status, body = get(
            f"{EPMC}/search",
            {"query": query, "format": "json", "pageSize": args.per_journal, "resultType": "core"},
        )
        if status != 200:
            query_failures += 1
            continue
        payload = json.loads(body)
        for article in payload["resultList"]["result"]:
            screened += 1
            title = article.get("title", "")
            abstract = article.get("abstractText", "") or ""
            if not TERMS.search(title + " " + abstract):
                continue
            relevant += 1
            # Crossref's public pool is shared and rate limited. Keep this
            # deliberately slow; failures are recorded rather than retried in
            # a way that could amplify a 429 response.
            time.sleep(0.25)
            status, body = get(
                CROSSREF,
                {"query.title": title, "filter": "type:posted-content", "rows": 3,
                 "select": "DOI,title,published,URL"},
            )
            if status != 200:
                query_failures += 1
                time.sleep(1.0 if status == 429 else 0.2)
                continue
            best = None
            for candidate in json.loads(body)["message"]["items"]:
                candidate_title = (candidate.get("title") or [""])[0]
                score = SequenceMatcher(None, norm(title), norm(candidate_title)).ratio()
                if best is None or score > best[0]:
                    best = (score, candidate, candidate_title)
            if not best or best[0] < 0.86 or not article.get("pmcid"):
                continue
            received = received_date(article["pmcid"])
            posted = date_parts(best[1])
            gap = (date.fromisoformat(posted) - date.fromisoformat(received)).days if received and posted else None
            matches.append({
                "journal": journal, "title": title, "doi": article.get("doi"), "pmcid": article["pmcid"],
                "received": received, "preprint_title": best[2], "preprint_doi": best[1].get("DOI"),
                "preprint_url": best[1].get("URL"), "preprint_posted": posted,
                "day_gap": gap, "title_similarity": round(best[0], 4),
                "review_url": f"https://www.webofscience.com/api/gateway/wos/peer-review/{article.get('doi')}",
            })
            time.sleep(0.15)
    result = {"screened": screened, "heuristically_relevant": relevant,
              "query_failures": query_failures, "matches": matches}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"screened": screened, "relevant": relevant,
                      "query_failures": query_failures, "matches": len(matches),
                      "within_7": sum(x["day_gap"] is not None and abs(x["day_gap"]) <= 7 for x in matches),
                      "within_30": sum(x["day_gap"] is not None and abs(x["day_gap"]) <= 30 for x in matches)}))


if __name__ == "__main__":
    main()
