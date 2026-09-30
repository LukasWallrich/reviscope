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


def test_anchored_generator_quote_suffices_when_verifier_supports():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was −0.25")])
    decision = {"f1": {"status": "supported", "rationale": "yes", "evidence": []}}
    result = verify_findings([finding], [source()], decision)[0]
    assert result.status == "llm_supported" and result.verifier_status == "supported"


def test_one_failed_quote_is_dropped_without_blocking_the_finding():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was 99"),
                                Evidence(source_id="main", quote="SE = 0.10")])
    decision = {"f1": {"status": "supported", "rationale": "yes", "evidence": []}}
    result = verify_findings([finding], [source()], decision)[0]
    assert result.status == "llm_supported"
    assert [item.quote for item in result.evidence] == ["SE = 0.10"]
    assert "quote[0]=dropped" in result.verification and "“estimate was 99”" in result.verification
    assert "quote[1]=supported" in result.verification


def test_elided_quotation_anchors_when_every_segment_occurs_in_order():
    text = ("Participants were recruited from a university pool in 2021. Of these, 24 were excluded "
            "for failing attention checks, leaving a final sample of 176 students.")
    doc = source(text).model_dump()
    elided = verify_quote("Participants were recruited from a university pool … leaving a final sample of 176 students.", [doc], "main")
    assert elided.status == "supported" and elided.elided
    assert text[elided.source_char_start:elided.source_char_end].startswith("Participants were")
    assert text[elided.source_char_start:elided.source_char_end].endswith("176 students.")
    assert verify_quote("Participants were recruited ... [...] 24 were excluded for failing", [doc], "main").elided
    assert not verify_quote("Participants were recruited from a university pool", [doc], "main").elided
    for bad in ("leaving a final sample ... Participants were recruited",  # out of order
                "Participants were recruited ... 176",                     # segment shorter than three words
                "Participants were recruited ... final sample of 17",       # cuts through a number
                "Participants were recruited ... from a college pool"):     # segment not in source
        assert verify_quote(bad, [doc], "main").status == "unanchored", bad
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="Of these, 24 were excluded... a final sample of 176 students.")])
    result = verify_findings([finding], [source(text)], {"f1": {"status": "supported", "rationale": "yes"}})[0]
    assert result.status == "llm_supported"
    assert result.evidence[0].location.endswith("(elided quotation)")
    assert "quote[0]=supported (elided)" in result.verification


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


def test_anchored_verifier_quote_carries_a_finding_whose_generator_quotes_all_fail():
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
    assert "quote[0]=dropped" in result.verification and "verifier_quote[0]=supported" in result.verification
    assert finding.model_dump() == original


@pytest.mark.parametrize("evidence, verifier_anchors", [
    ([], False), (None, False), ([None], False), ([{"quote": "SE = 0.10"}], False),
    ([{"source_id": "other", "quote": "SE = 0.10"}], False),
    ([{"source_id": "main", "quote": "SE = 0.20"}], False),
    ([{"source_id": "main", "quote": "SE = 0.10"}, None], True),
    ([{"source_id": "main", "quote": "SE = 0.10"}, {"source_id": "main", "quote": "invented"}], True),
])
@pytest.mark.parametrize("generator_anchors, original_quote", [(False, "invented"), (True, "SE = 0.10")])
def test_support_needs_one_anchored_manuscript_quote_from_either_side(evidence, verifier_anchors,
                                                                      generator_anchors, original_quote):
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote=original_quote)])
    decision = {"f1": {"status": "supported", "evidence": evidence}}
    result = verify_findings([finding], [source()], decision)[0]
    assert result.status == ("llm_supported" if generator_anchors or verifier_anchors else "unresolved")
    assert all(item.location for item in result.evidence) and len(result.evidence) <= 1


def test_verifier_quotes_are_not_evidence_for_a_claim_it_does_not_support():
    finding = Finding(id="f1", module="design", claim="Concern", rationale="Why", remedy="Clarify",
                      evidence=[Evidence(source_id="main", quote="estimate was −0.25")])
    decision = {"f1": {"status": "unresolved", "rationale": "The design section does not say.",
                       "evidence": [{"source_id": "main", "quote": "SE = 0.10"}]}}
    result = verify_findings([finding], [source()], decision)[0]
    assert (result.status, result.verifier_status) == ("unresolved", "unresolved")
    assert result.verifier_rationale == "The design section does not say."
    assert [item.quote for item in result.evidence] == ["estimate was −0.25"]


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


def test_external_source_counts_as_checked_only_when_opened_or_named_in_a_query():
    from datetime import datetime, timezone
    from reviscope.schemas import ToolCall
    from reviscope.verification import touched

    def call(kind, **fields):
        return ToolCall(backend="t", sequence=0, kind=kind, name=kind, timestamp=datetime.now(timezone.utc), **fields)

    listed = call("search", query="stereotyping disorder", result_urls=["https://pubmed.ncbi.nlm.nih.gov/21474762/"])
    assert not touched("https://pubmed.ncbi.nlm.nih.gov/21474762/", [listed])
    assert touched("https://pubmed.ncbi.nlm.nih.gov/21474762/", [call("fetch", opened_urls=["http://www.pubmed.ncbi.nlm.nih.gov/21474762"])])
    assert touched("10.1126/science.1201068", [call("search", query='"10.1126/science.1201068" retraction')])
    assert touched("https://doi.org/10.1126/science.1201068", [call("fetch", url="https://dx.doi.org/10.1126/science.1201068")])
    assert not touched("10.1126/science.1201068", [call("fetch", url="https://doi.org/10.1126/science.1201068", error=True)])
    index = call("fetch", url="https://example.org/index", opened_urls=["https://example.org/index"],
                 result_urls=["https://example.org/source"])  # the page links to the source; the source was not opened
    assert not touched("https://example.org/source", [index])
    assert not touched("https://example.org/source/extra", [call("fetch", opened_urls=["https://example.org/source"])])
    assert not touched("https://example.org/source", [call("fetch", opened_urls=["https://example.org/source/extra"])])
    assert not touched("10.1126/science.12010", [call("search", query="10.1126/science.1201068")])
    assert not touched("https://example.org/source", [call("search", query="example.org/source/extra review")])


def test_one_refuted_external_source_blocks_support():
    from datetime import datetime, timezone
    from reviscope.schemas import ToolCall
    quote = "The multilevel estimate was -0.25"
    urls = ["https://example.org/a", "https://example.org/b", "https://example.org/c"]
    finding = Finding(id="e", module="m", claim="c", rationale="r", remedy="x", evidence=[Evidence(source_id="main", quote=quote)],
                      external_evidence=[{"url": url, "quote": "q", "shows": "s"} for url in urls])
    verdicts = {urls[0]: "confirmed", urls[1]: "refuted", urls[2]: "not_found"}
    decision = {"status": "supported", "rationale": "ok", "evidence": [{"source_id": "main", "quote": quote}],
                "external_checks": [{"locator": url, "verdict": verdict, "rationale": "opened"} for url, verdict in verdicts.items()]}
    opened = [ToolCall(backend="t", sequence=i, kind="fetch", name="WebFetch", url=url, opened_urls=[url],
                       timestamp=datetime.now(timezone.utc)) for i, url in enumerate(urls[:2])]
    result = verify_findings([finding], [source()], {"e": decision}, verifier_calls=opened)[0]
    assert [item.check for item in result.external_evidence] == ["confirmed", "refuted", "unchecked"]
    assert result.status == "unresolved" and "refuted" in result.verification
