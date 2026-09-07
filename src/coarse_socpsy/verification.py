"""Source-grounded deterministic and model-assisted claim verification."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable, Literal, Mapping

from .schemas import Finding, SourceDocument

@dataclass(frozen=True)
class QuoteVerification:
    status: Literal["supported", "unanchored"]
    source_id: str | None
    source_char_start: int | None
    source_char_end: int | None
    reason: str


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
    def numeric_part(char: str) -> bool:
        return char.isnumeric() or char in ".,+-eE×^%‰"

    if needle and start:
        left = (text[start - 1], needle[0])
        if all(numeric_part(char) for char in left) and any(char.isnumeric() for char in left):
            return False
    if needle and end < len(text):
        right = (needle[-1], text[end])
        if all(numeric_part(char) for char in right) and any(char.isnumeric() for char in right):
            return False
    return True


def verify_quote(quote: str, sources: Iterable[Mapping[str, Any] | str], source_id: str | None = None) -> QuoteVerification:
    """Match exact text modulo whitespace. Numeric tokens must match byte-for-byte."""
    needle, _ = _normalize_with_offsets(quote.strip())
    if not needle:
        return QuoteVerification("unanchored", None, None, None, "No quotation was supplied.")
    for index, source in enumerate(sources):
        text = source if isinstance(source, str) else str(source.get("text", ""))
        sid = str(index) if isinstance(source, str) else str(source.get("source_id", source.get("id", index)))
        if source_id is not None and sid != str(source_id):
            continue
        normalized, offsets = _normalize_with_offsets(text)
        search_from = 0
        while (start := normalized.find(needle, search_from)) >= 0:
            if _numeric_boundaries_ok(normalized, start, needle):
                end_index = start + len(needle) - 1
                return QuoteVerification("supported", sid, offsets[start], offsets[end_index] + 1, "Quotation matched the cited source modulo whitespace.")
            search_from = start + 1
    reason = "Quotation was not found in the specified source." if source_id else "Quotation was not found in any supplied source."
    return QuoteVerification("unanchored", None, None, None, reason)


def verify_findings(findings: Iterable[Finding], sources: Iterable[SourceDocument],
                    model_results: Mapping[str, Mapping[str, Any]] | None = None,
                    relationship: str = "separate_verification_pass") -> list[Finding]:
    """Apply anchors and optional separate-pass claim decisions without dropping findings."""
    source_list = list(sources)
    source_maps = [{"source_id": source.id, "text": source.text} for source in source_list]
    decisions = model_results or {}
    source_by_id = {source.id: source for source in source_list}
    verified: list[Finding] = []
    for finding in findings:
        anchors = [verify_quote(item.quote, source_maps, item.source_id) for item in finding.evidence]
        grounded_evidence = []
        for item, anchor in zip(finding.evidence, anchors):
            page = None
            source = source_by_id.get(item.source_id)
            if anchor.status == "supported" and source is not None:
                page_matches = [page_text.page for page_text in source.pages
                                if verify_quote(item.quote, [{"source_id": source.id, "text": page_text.text}], source.id).status == "supported"]
                if len(page_matches) == 1:
                    page = page_matches[0]
            grounded_evidence.append(item.model_copy(update={
                "page": page,
                "location": (f"source characters {anchor.source_char_start}:{anchor.source_char_end}"
                             if anchor.status == "supported" else None),
                "source_char_start": anchor.source_char_start if anchor.status == "supported" else None,
                "source_char_end": anchor.source_char_end if anchor.status == "supported" else None,
            }))
        anchor_failed = not anchors or any(item.status == "unanchored" for item in anchors)
        decision = decisions.get(finding.id)
        if anchor_failed:
            status = "unresolved"
            rationale = "At least one cited quotation could not be anchored in its named source."
        elif finding.status in {"recomputed", "verified_deterministic"}:
            status = finding.status
            rationale = finding.verification or "The claim was established by a deterministic check."
        elif decision is None:
            status = "unresolved"
            rationale = "Evidence quotations were checked, but the substantive claim has not received a separate verification pass."
        else:
            raw_status = decision.get("status", "unresolved")
            status = raw_status if raw_status in {"supported", "contradicted", "unresolved"} else "unresolved"
            rationale = str(decision.get("rationale", "The separate verification pass supplied no rationale."))
            verifier_evidence = decision.get("evidence", [])
            verifier_anchors = [
                verify_quote(str(item.get("quote", "")), source_maps, str(item.get("source_id", "")))
                for item in verifier_evidence if isinstance(item, Mapping)
            ]
            if status == "supported" and (not verifier_anchors or any(a.status != "supported" for a in verifier_anchors)):
                status = "unresolved"
                rationale = "The model selected supported, but its separately selected evidence was absent or could not be anchored."
            elif status == "supported":
                status = "llm_supported"
        trace = "; ".join(
            [f"quote[{i}]={anchor.status}: {anchor.reason}" for i, anchor in enumerate(anchors)]
            + [f"claim={status}: {rationale}",
               f"provenance=deterministic_quote_anchor+{relationship}" if decision else
               "provenance=deterministic_quote_anchor"]
        )
        remedy_status = (str(decision.get("remedy_status")) if decision and
                         decision.get("remedy_status") in {"supported", "overreaching", "unresolved"} else None)
        remedy_verification = str(decision.get("remedy_rationale", "")) if decision else None
        verified.append(finding.model_copy(update={"status": status, "verification": trace,
                                                   "evidence": grounded_evidence,
                                                   "remedy_status": remedy_status,
                                                   "remedy_verification": remedy_verification}))
    return verified
