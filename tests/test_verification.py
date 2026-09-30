import pytest

from reviscope.schemas import Evidence, Finding, PageText, SourceDocument
from reviscope.verification import verify_findings, verify_quote


def source(text="The multi-\nlevel estimate was −0.25 (SE = 0.10)."):
    return SourceDocument(id="main", path="paper.pdf", kind="manuscript", sha256="x", text=text,
                          pages=[PageText(page=4, text=text)])


def test_quote_normalization_handles_pdf_artifacts_and_preserves_anchor():
    result = verify_quote("The multilevel estimate was -0.25 (SE = 0.10).", [source().model_dump()], "main")
    assert result.status == "supported"
    assert result.source_id == "main"
    assert result.source_char_start == 0


def test_quote_does_not_fuzz_numeric_substitutions():
    result = verify_quote("estimate was -0.35", [source().model_dump()], "main")
    assert result.status == "unanchored"


def test_quote_normalization_never_collapses_numeric_ranges():
    result = verify_quote("The range was 23.", [source("The range was 2-3.").model_dump()], "main")
    assert result.status == "unanchored"


def test_quote_normalization_never_dehyphenates_numeric_linebreaks():
    result = verify_quote("The range was 23.", [source("The range was 2-\n3.").model_dump()], "main")
    assert result.status == "unanchored"


def test_quote_numeric_match_cannot_end_inside_longer_decimal():
    result = verify_quote("estimate was -0.2", [source("The estimate was -0.25.").model_dump()], "main")
    assert result.status == "unanchored"


def test_quote_normalization_preserves_superscript_numbers():
    result = verify_quote("value was 103", [source("The value was 10³.").model_dump()], "main")
    assert result.status == "unanchored"


def test_quote_numeric_match_cannot_truncate_superscript_exponent_or_grouping():
    assert verify_quote("value was 10", [source("The value was 10³.").model_dump()], "main").status == "unanchored"
    assert verify_quote("value was 1", [source("The value was 1e3.").model_dump()], "main").status == "unanchored"
    assert verify_quote("value was -1", [source("The value was -1,000.").model_dump()], "main").status == "unanchored"


def test_numeric_boundary_logic_does_not_reject_ordinary_prose():
    assert verify_quote("values were positive", [source("The values were positive.").model_dump()], "main").status == "supported"


def test_findings_are_retained_and_unresolved_without_claim_verifier():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was −0.25")])
    result = verify_findings([finding], [source()])
    assert len(result) == 1
    assert result[0].status == "unresolved"
    assert "quote[0]=supported" in result[0].verification


def test_bad_anchor_overrides_model_approval():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was 99")])
    result = verify_findings([finding], [source()], {"f1": {"status": "supported", "rationale": "looks right"}})
    assert result[0].status == "unresolved"


def test_model_support_requires_anchored_independent_evidence():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was −0.25")])
    decision = {"f1": {"status": "supported", "rationale": "yes", "evidence": []}}
    assert verify_findings([finding], [source()], decision)[0].status == "unresolved"


def test_model_support_with_independent_evidence_is_kept_as_supported():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was −0.25")])
    decision = {"f1": {"status": "supported", "rationale": "yes",
                       "evidence": [{"source_id": "main", "quote": "SE = 0.10"}]}}
    assert verify_findings([finding], [source()], decision)[0].status == "llm_supported"


def test_deterministic_provenance_replaces_model_page_and_location():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="multilevel estimate was -0.25",
                                         page=999, location="invented")])
    result = verify_findings([finding], [source()])[0].evidence[0]
    assert result.page == 4
    assert result.location.startswith("source characters ")
    assert source().text[result.source_char_start:result.source_char_end] == "multi-\nlevel estimate was −0.25"


def test_numeric_sign_and_effect_change_cannot_anchor():
    assert verify_quote("estimate was +0.25", [source().model_dump()], "main").status == "unanchored"


def test_valid_verifier_evidence_rescues_bad_generator_quotes_with_fresh_locations():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was 99")])
    original = finding.model_dump()
    decision = {"f1": {"status": "supported", "rationale": "Checked against source",
                       "evidence": [{"source_id": "main", "quote": "SE = 0.10", "page": 999,
                                     "location": "invented", "source_char_start": 999}]}}
    result = verify_findings([finding], [source()], decision)[0]
    assert result.status == "llm_supported"
    assert [item.quote for item in result.evidence] == ["SE = 0.10"]
    ev = result.evidence[0]
    assert ev.page == 4
    assert source().text[ev.source_char_start:ev.source_char_end] == ev.quote
    assert ev.location == f"source characters {ev.source_char_start}:{ev.source_char_end}"
    assert "original_quote[0]=unanchored" in result.verification
    assert finding.model_dump() == original


@pytest.mark.parametrize("evidence", [
    [], None, [None], [{"quote": "SE = 0.10"}],
    [{"source_id": "other", "quote": "SE = 0.10"}],
    [{"source_id": "main", "quote": "SE = 0.20"}],
    [{"source_id": "main", "quote": "SE = 0.10"}, None],
    [{"source_id": "main", "quote": "SE = 0.10"}, {"source_id": "main", "quote": "invented"}],
])
@pytest.mark.parametrize("original_quote", ["invented", "SE = 0.10"])
def test_invalid_replacement_evidence_cannot_approve(evidence, original_quote):
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote=original_quote)])
    decision = {"f1": {"status": "supported", "evidence": evidence}}
    assert verify_findings([finding], [source()], decision)[0].status == "unresolved"


def test_publication_needs_a_manuscript_anchor_and_a_confirmed_external_source():
    from datetime import datetime, timezone
    from reviscope.schemas import ToolCall
    quote = "The multilevel estimate was -0.25"
    supplement = SourceDocument(id="supp", path="s.pdf", kind="supplement", sha256="y", text="Supplement says 42 items.")
    external = {"url": "https://doi.org/10.1/X", "doi": None, "quote": "Cited study reports d = 0.2.", "shows": "Cited effect is small."}
    decision = {"status": "supported", "rationale": "ok", "remedy_status": "supported", "remedy_rationale": "",
                "evidence": [{"source_id": "main", "quote": quote}],
                "external_checks": [{"locator": "https://doi.org/10.1/x", "verdict": "confirmed", "rationale": "opened"}]}
    fetch = ToolCall(backend="t", sequence=0, kind="fetch", name="WebFetch", url="https://doi.org/10.1/x", timestamp=datetime.now(timezone.utc))
    supplement_only = Finding(id="s", module="m", claim="c", rationale="r", remedy="x",
                              evidence=[Evidence(source_id="supp", quote="Supplement says 42 items.")])
    cited = Finding(id="e", module="m", claim="c", rationale="r", remedy="x", evidence=[Evidence(source_id="main", quote=quote)],
                    external_evidence=[external])
    supp_decision = {**decision, "evidence": [{"source_id": "supp", "quote": "Supplement says 42 items."}], "external_checks": []}
    result = verify_findings([supplement_only, cited], [source(), supplement], {"s": supp_decision, "e": decision}, verifier_calls=[fetch])
    assert result[0].status == "unresolved" and "manuscript itself" in result[0].verification
    assert result[1].status == "llm_supported" and result[1].external_evidence[0].check == "confirmed"
    unchecked = verify_findings([cited], [source()], {"e": decision}, verifier_calls=[])[0]
    assert unchecked.status == "unresolved" and unchecked.external_evidence[0].check == "unchecked"
    refuted = verify_findings([cited], [source()], {"e": {**decision, "external_checks": [
        {"locator": external["url"], "verdict": "refuted", "rationale": "says d = 0.8"}]}}, verifier_calls=[fetch])[0]
    assert refuted.status == "unresolved" and refuted.external_evidence[0].check == "refuted"
    with pytest.raises(ValueError, match="url or doi"):
        Finding(id="x", module="m", claim="c", rationale="r", remedy="x", external_evidence=[{"quote": "q", "shows": "s"}])
