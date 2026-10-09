"""Source-grounded deterministic and model-assisted claim verification."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable, Literal, Mapping, Sequence

from .schemas import Evidence, ExternalEvidence, Finding, SourceDocument, ToolCall

@dataclass(frozen=True)
class QuoteVerification:
    status: Literal["supported", "unanchored"]
    source_id: str | None
    source_char_start: int | None
    source_char_end: int | None
    reason: str
    elided: bool = False


# An elision mark after normalization ("…" folds to "..."): three or more dots, optionally
# spaced or bracketed. Each quoted segment around it must be at least this many words long.
_ELLIPSIS = re.compile(r"\s*\[?\s*(?:\.\s*){3,}\]?\s*")
MIN_ELIDED_SEGMENT_WORDS = 3


def _normalize_with_offsets(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    offsets: list[int] = []
    pending_space = False
    replacements = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
                    "−": "-", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}
    pos = 0
    while pos < len(text):
        original = text[pos]
        if original == "-" and pos > 0 and text[pos - 1].isalpha():
            line_end = re.match(r"-\s*\n\s*(?=[^\W\d_])", text[pos:], re.UNICODE)
            if line_end:
                pos += len(line_end.group(0))
                continue
        replacement = replacements.get(original, original)
        # NFKC repairs compatibility glyphs but would silently turn superscript
        # numbers (for example 10³) into different ordinary numeric values.
        if unicodedata.category(original) != "No":
            replacement = unicodedata.normalize("NFKC", replacement)
        for char in replacement:
            if char.isspace():
                pending_space = bool(chars)
            else:
                if pending_space:
                    chars.append(" ")
                    offsets.append(pos)
                    pending_space = False
                chars.append(char)
                offsets.append(pos)
        pos += 1
    return "".join(chars), offsets


def _numeric_boundaries_ok(text: str, start: int, needle: str) -> bool:
    """Reject a substring match that cuts through a larger numeric token."""
    end = start + len(needle)
    def numeric_part(position: int) -> bool:
        char = text[position]
        # A trailing sentence stop or list comma does not extend a number.
        # Decimal/grouping punctuation does when another digit follows it.
        if char in ".,":
            return position + 1 < len(text) and text[position + 1].isnumeric()
        return char.isnumeric() or char in "+-eE×^%‰"

    if needle and start:
        left = (text[start - 1], needle[0])
        if numeric_part(start - 1) and numeric_part(start) and any(char.isnumeric() for char in left):
            return False
    if needle and end < len(text):
        right = (needle[-1], text[end])
        if numeric_part(end - 1) and numeric_part(end) and any(char.isnumeric() for char in right):
            return False
    return True


def _find(normalized: str, needle: str, search_from: int = 0) -> int:
    """First match of needle at or after search_from that does not cut through a number; -1 if none."""
    while (start := normalized.find(needle, search_from)) >= 0:
        if _numeric_boundaries_ok(normalized, start, needle):
            return start
        search_from = start + 1
    return -1


def _find_elided(normalized: str, segments: list[str]) -> tuple[int, int] | None:
    """Span from the first to the last segment when every segment occurs in order without overlap."""
    position, first = 0, None
    for segment in segments:
        start = _find(normalized, segment, position)
        if start < 0:
            return None
        first = start if first is None else first
        position = start + len(segment)
    return (first, position) if first is not None else None


def verify_quote(quote: str, sources: Iterable[Mapping[str, Any] | str], source_id: str | None = None) -> QuoteVerification:
    """Match exact text modulo whitespace. Numeric tokens must match byte-for-byte.

    A quotation shortened with an ellipsis anchors when each segment around the ellipsis is at
    least MIN_ELIDED_SEGMENT_WORDS words long and all segments occur in the same source, in order.
    """
    needle, _ = _normalize_with_offsets(quote.strip())
    if not needle:
        return QuoteVerification("unanchored", None, None, None, "No quotation was supplied.")
    segments = [part for part in _ELLIPSIS.split(needle) if part.strip()] if _ELLIPSIS.search(needle) else []
    segments_usable = bool(segments) and all(len(part.split()) >= MIN_ELIDED_SEGMENT_WORDS for part in segments)
    for index, source in enumerate(sources):
        text = source if isinstance(source, str) else str(source.get("text", ""))
        sid = str(index) if isinstance(source, str) else str(source.get("source_id", source.get("id", index)))
        if source_id is not None and sid != str(source_id):
            continue
        normalized, offsets = _normalize_with_offsets(text)
        start = _find(normalized, needle)
        if start >= 0:
            return QuoteVerification("supported", sid, offsets[start], offsets[start + len(needle) - 1] + 1,
                                     "Quotation matched the cited source modulo whitespace.")
        if segments_usable and (span := _find_elided(normalized, segments)):
            return QuoteVerification("supported", sid, offsets[span[0]], offsets[span[1] - 1] + 1,
                                     f"Elided quotation: all {len(segments)} segments matched the cited source in order.",
                                     elided=True)
    reason = "Quotation was not found in the specified source." if source_id else "Quotation was not found in any supplied source."
    if segments and not segments_usable:
        reason += f" An elided quotation anchors only when every segment has at least {MIN_ELIDED_SEGMENT_WORDS} words."
    return QuoteVerification("unanchored", None, None, None, reason)


def _locator(value: str) -> str:
    """Canonical URL or DOI: no scheme, www., doi.org host, doi: prefix, fragment or trailing slash."""
    value = value.strip().strip("\"'<>()[],;").lower().split("#", 1)[0]
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^www\.", "", value)
    value = re.sub(r"^(dx\.)?doi\.org/|^doi:\s*", "", value)
    return value.rstrip("/.")


def touched(locator: str, calls: Sequence[ToolCall]) -> bool:
    """True if a recorded fetch opened exactly this URL or DOI, or a search query contained it
    as a whole token. Links inside an opened page and longer or shorter URLs do not count."""
    wanted = _locator(locator)

    def names(call: ToolCall) -> list[str]:
        if call.kind == "fetch":
            return [*call.opened_urls, *([call.url] if call.url else [])]
        return (call.query or "").split()

    return bool(wanted) and any(_locator(name) == wanted for call in calls
                                if call.kind in {"search", "fetch"} and not call.error for name in names(call))


def check_external(items: Sequence[ExternalEvidence], checks: Sequence[Mapping[str, Any]],
                   calls: Sequence[ToolCall]) -> list[ExternalEvidence]:
    """Confirmed needs the verifier's `confirmed` verdict and a recorded tool call on the locator."""
    verdicts = {_locator(str(row.get("locator", ""))): row.get("verdict") for row in checks if isinstance(row, Mapping)}
    checked = []
    for item in items:
        verdict = verdicts.get(_locator(item.locator))
        state = ("refuted" if verdict == "refuted" else
                 "confirmed" if verdict == "confirmed" and touched(item.locator, calls) else "unchecked")
        checked.append(item.model_copy(update={"check": state}))
    return checked


_VERDICTS = {"supported", "contradicted", "unresolved"}
_DETERMINISTIC = {"recomputed", "verified_deterministic"}


def _verifier_evidence(rows: Any) -> tuple[list[Evidence], list[str]]:
    """Well-formed verifier quotations, plus a trace note for each malformed row."""
    if rows is None:
        return [], []
    if not isinstance(rows, list):
        return [], ["verifier_evidence=ignored: not a list"]
    items, notes = [], []
    for index, row in enumerate(rows):
        if (isinstance(row, Mapping) and isinstance(row.get("quote"), str) and row["quote"].strip()
                and isinstance(row.get("source_id"), str)):
            items.append(Evidence(source_id=row["source_id"], quote=row["quote"]))
        else:
            notes.append(f"verifier_quote[{index}]=ignored: malformed row")
    return items, notes


def _grounded(item: Evidence, anchor: QuoteVerification, source: SourceDocument | None) -> Evidence:
    """Evidence with deterministic page and character location; model-supplied locations are discarded."""
    page = None
    if source is not None:
        pages = [page_text.page for page_text in source.pages
                 if verify_quote(item.quote, [{"source_id": source.id, "text": page_text.text}], source.id).status == "supported"]
        page = pages[0] if len(pages) == 1 else None
    location = f"source characters {anchor.source_char_start}:{anchor.source_char_end}"
    return item.model_copy(update={"page": page, "location": location + (" (elided quotation)" if anchor.elided else ""),
                                   "source_char_start": anchor.source_char_start,
                                   "source_char_end": anchor.source_char_end})


def verify_findings(findings: Iterable[Finding], sources: Iterable[SourceDocument],
                    model_results: Mapping[str, Mapping[str, Any]] | None = None,
                    relationship: str = "separate_verification_pass",
                    verifier_calls: Sequence[ToolCall] = ()) -> list[Finding]:
    """Anchor quotations and apply the separate verifier's decisions without dropping findings.

    Evidence is every quotation that anchors in its named source: the generator's, plus the
    verifier's own when it supports the claim. Quotations that fail to anchor are dropped from the
    evidence and listed in the verification note. A finding is publishable (`llm_supported`) when
    the verifier supports it and at least one anchored quotation comes from the manuscript itself;
    supplements and preregistrations add support but cannot carry a finding alone. A finding that
    cites required external evidence also needs at least one item confirmed and none refuted.
    The verifier can classify external evidence as optional with an explicit explanation of
    how manuscript evidence and established knowledge support the claim without it. Unchecked
    optional items are dropped from the finding; refuted items always block support.
    """
    source_list = list(sources)
    source_maps = [{"source_id": source.id, "text": source.text} for source in source_list]
    decisions = model_results or {}
    source_by_id = {source.id: source for source in source_list}
    verified: list[Finding] = []
    for finding in findings:
        decision = decisions.get(finding.id)
        raw_verdict = decision.get("status") if decision else None
        verdict = (raw_verdict if raw_verdict in _VERDICTS else "unresolved") if decision else None
        deterministic = finding.status in _DETERMINISTIC
        quoted = [("quote", index, item) for index, item in enumerate(finding.evidence)]
        trace: list[str] = []
        if verdict == "supported" and not deterministic:
            verifier_items, notes = _verifier_evidence(decision.get("evidence"))
            quoted += [("verifier_quote", index, item) for index, item in enumerate(verifier_items)]
            trace += notes
        evidence: list[Evidence] = []
        spans: set[tuple[str | None, int | None, int | None]] = set()
        for label, index, item in quoted:
            anchor = verify_quote(item.quote, source_maps, item.source_id)
            if anchor.status != "supported":
                excerpt = item.quote if len(item.quote) <= 120 else item.quote[:117] + "..."
                trace.append(f"{label}[{index}]=dropped: {anchor.reason} Quotation: “{excerpt}”")
                continue
            trace.append(f"{label}[{index}]={'supported (elided)' if anchor.elided else 'supported'}: {anchor.reason}")
            span = (anchor.source_id, anchor.source_char_start, anchor.source_char_end)
            if span not in spans:
                spans.add(span)
                evidence.append(_grounded(item, anchor, source_by_id.get(item.source_id)))
        manuscript_anchored = any(source_by_id[item.source_id].kind == "manuscript"
                                  for item in evidence if item.source_id in source_by_id)
        external = check_external(finding.external_evidence, decision.get("external_checks", []) if decision else [], verifier_calls)
        dependency = decision.get("external_dependency", "required") if decision else None
        dependency_rationale = str(decision.get("external_dependency_rationale") or "").strip() if decision else None
        checked_external = external
        if (verdict == "supported" and dependency == "optional" and dependency_rationale
                and manuscript_anchored and not any(item.check == "refuted" for item in external)):
            external = [item for item in external if item.check == "confirmed"]
            for item in checked_external:
                if item.check == "unchecked":
                    trace.append(f"external_source_dropped={item.locator}: {dependency_rationale}")
        verifier_rationale = str(decision.get("rationale") or "The verifier supplied no rationale.") if decision else None
        if not evidence:
            status, rationale = "unresolved", "No cited quotation could be anchored in its named source."
        elif not manuscript_anchored:
            status = "unresolved"
            rationale = "No anchored quotation comes from the manuscript itself; supplementary sources cannot carry a finding alone."
        elif deterministic:
            status = finding.status
            rationale = finding.verification or "The claim was established by a deterministic check."
        elif decision is None:
            status = "unresolved"
            rationale = "Evidence quotations were checked, but the substantive claim has not received a separate verification pass."
        elif verdict != "supported":
            status, rationale = verdict, verifier_rationale
        elif any(item.check == "refuted" for item in external):
            status, rationale = "unresolved", "The verifier refuted at least one cited external source."
        elif external and not any(item.check == "confirmed" for item in external):
            status = "unresolved"
            rationale = ("The claim cites external evidence, but no external item was confirmed by the verifier "
                         "with a recorded fetch or search of its URL or DOI.")
        else:
            status, rationale = "llm_supported", verifier_rationale
        trace += [f"claim={status}: {rationale}",
                  f"provenance=deterministic_quote_anchor+{relationship}" if decision else "provenance=deterministic_quote_anchor"]
        if external:
            trace.append("external_evidence=" + ", ".join(f"{item.locator}: {item.check}" for item in external))
        remedy_status = (str(decision.get("remedy_status")) if decision and
                         decision.get("remedy_status") in {"supported", "overreaching", "unresolved"} else None)
        remedy_verification = str(decision.get("remedy_rationale", "")) if decision else None
        verified.append(finding.model_copy(update={"status": status, "verification": "; ".join(trace),
                                                   "evidence": evidence, "external_evidence": external,
                                                   "verifier_status": verdict, "verifier_rationale": verifier_rationale,
                                                   "external_dependency": dependency,
                                                   "external_dependency_rationale": dependency_rationale,
                                                   "remedy_status": remedy_status,
                                                   "remedy_verification": remedy_verification}))
    return verified
