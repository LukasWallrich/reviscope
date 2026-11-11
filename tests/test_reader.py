"""The final reader pass: revised wording, its number check, and how the report and audit show it."""

import json

import pytest

from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.reader import ReaderRevision, apply_revision, numbers
from reviscope.schemas import Evidence, Finding, SourceDocument
from test_integration_contracts import ScriptedBackend, manuscript, profile, support_all


def test_numbers_compare_canonical_forms():
    assert numbers("p = .05, N = 1,200, d = 0.50") == {"0.05", "1200", "0.5"}
    assert numbers("b = −0.3 in Studies 1,2") == {"-0.3", "1", "2"}
    assert numbers("Study 2-3") == {"2", "3"}


SOURCE = SourceDocument(id="m", kind="manuscript", path="p.md", sha256="0",
                        text="We excluded participants who failed checks. Final N = 212.")


def finding(kind="defect"):
    return Finding(id="f1", module="m", kind=kind, claim="The exclusion count is missing.",
                   rationale="Of 240 recruited, the paper never says how many were excluded.", remedy="Report it.",
                   status="llm_supported", evidence=[Evidence(source_id="m", quote="We excluded participants who failed checks.")])


def test_revision_without_new_numbers_is_used():
    revised = apply_revision(finding(), ReaderRevision(id="f1", claim="The number of excluded participants is not reported.",
                                                       rationale="The paper recruited 240 people but does not say how many it excluded.",
                                                       remedy="State how many were excluded and why.", changes="Plainer."), True, [SOURCE])
    assert revised.reader.claim.startswith("The number") and revised.reader.remedy.startswith("State")
    assert revised.reader.rejected == [] and revised.claim == "The exclusion count is missing."


def test_revision_adding_a_number_keeps_the_original_field():
    revised = apply_revision(finding(), ReaderRevision(id="f1", claim="Exclusions are missing.",
                                                       rationale="Of 240 recruited, 28 were excluded silently."), True, [SOURCE])
    assert revised.reader.claim == "Exclusions are missing." and revised.reader.rationale is None
    assert "28" in revised.reader.rejected[0]


def test_wording_only_for_reporting_clarifications_with_placeholders_and_location():
    draft = ReaderRevision(id="f1", claim="c", rationale="r", wording="We excluded [n] of 240 participants; final N = 212.",
                           wording_location="Method, Participants, after the exclusion sentence")
    assert apply_revision(finding("defect"), draft, True, [SOURCE]).reader.wording is None
    assert apply_revision(finding("clarification_request"), draft, False, [SOURCE]).reader.wording is None
    accepted = apply_revision(finding("clarification_request"), draft, True, [SOURCE]).reader
    assert accepted.wording.startswith("We excluded [n]") and accepted.wording_location.startswith("Method")
    invented = draft.model_copy(update={"wording": "We excluded 17 participants."})
    assert apply_revision(finding("clarification_request"), invented, True, [SOURCE]).reader.wording is None
    unplaced = draft.model_copy(update={"wording_location": ""})
    assert "no usable location" in apply_revision(finding("clarification_request"), unplaced, True, [SOURCE]).reader.rejected[0]


class ReaderBackend(ScriptedBackend):
    def __init__(self, reader, **kwargs):
        super().__init__(**kwargs)
        self.reader = reader

    def generate(self, instruction, evidence, response_model):
        if response_model.__name__ == "ReaderResponse":
            self.calls.append((response_model.__name__, instruction))
            return response_model.model_validate(self.reader(instruction))
        return super().generate(instruction, evidence, response_model)


def run(tmp_path, reader):
    paper = manuscript(tmp_path)
    row = Finding(id="x", module="a", claim="Original claim", rationale="Original rationale", remedy="Original remedy",
                  kind="clarification_request", evidence=[Evidence(source_id=ingest(paper).id, quote="Quoted source sentence.")]).model_dump()
    editorial = lambda instruction: [{"finding_id": json.loads(instruction.split("\nFINDINGS\n", 1)[1])[0]["id"],
                                      "disposition": "keep", "reason": "ok", "severity": "major"}]
    generator = ReaderBackend(reader, modules={"RUN a": [row]}, editorial=editorial)
    result = ReviewPipeline(generator, profile("a"), ScriptedBackend(model="verifier", verify=verify)).run(paper, output_dir=tmp_path / "out")
    return result, generator, (tmp_path / "out" / "review.md").read_text(), (tmp_path / "out" / "audit.md").read_text()


def verify(instruction):
    return [{**row, "remedy_status": "supported", "remedy_rationale": "proportionate"} for row in support_all(instruction)]


def items(instruction):
    return json.loads(instruction.split("\nITEMS\n", 1)[1].split("\nCURRENT OVERVIEW\n", 1)[0])


@pytest.mark.reader_pass
def test_report_shows_reader_wording_and_audit_keeps_the_original(tmp_path):
    def reader(instruction):
        assert "REVIEW AS DRAFTED" in instruction and "Original claim" in instruction
        item = items(instruction)[0]
        assert item["wording_allowed"] and item["remedy_shown"] and item["verification_notes"] == ["checked", "proportionate"]
        return {"revisions": [{"id": item["id"], "claim": "Clearer claim", "rationale": "Clearer rationale", "remedy": "Clearer remedy",
                               "changes": "Plainer wording.", "doubt": "Page 2 may already report this.",
                               "wording": "We report [detail].", "wording_location": "Method, after the first sentence"}],
                "overview": {"design_summary": "Clearer design", "contribution_summary": "c", "strengths": []},
                "report_notes": ["Items agree."]}

    result, _, review, audit = run(tmp_path, reader)
    assert not result.partial, [(s.name, s.error) for s in result.stages if s.error]
    assert result.findings[0].claim == "Original claim"
    assert "### 1. Major: Clearer claim" in review and "Original claim" not in review
    assert "**The problem.** Clearer rationale" in review and "Clearer remedy" in review
    assert "**Possible wording.** Method, after the first sentence. Square brackets" in review and "    We report [detail]." in review
    assert "Clearer design" in review and "Original claim" in audit and "Page 2 may already report this." in audit
    assert "Original overview: d" in audit and "Items agree." in audit
    html = (tmp_path / "out" / "review.html").read_text()
    assert "Clearer claim" in html and "class='wording'" in html and "href='audit.html'" in html


@pytest.mark.reader_pass
def test_reader_failure_shows_original_wording_and_marks_partial(tmp_path):
    def reader(instruction):
        return {"revisions": [{"id": "unknown", "claim": "x", "rationale": "y"}]}

    result, _, review, audit = run(tmp_path, reader)
    assert result.partial and "Original claim" in review and "Partial review" in review
    assert "reader: stage failed" in audit and "`reader` — failed" in audit


def test_merge_plan_folds_like_items_and_cross_references_mixed_ones():
    from reviscope.reader import ReaderMergeProposal as M, plan_merges
    a, b, c, d = (Finding(id=i, module="m", claim=i, rationale="r", remedy="x") for i in "abcd")
    items = [("finding 1", a, "published"), ("finding 2", b, "published"), ("unconfirmed concern 1", c, "unresolved"),
             ("unconfirmed concern 2", d, "unresolved")]
    records, fold, see_also = plan_merges(items, [M(source="a", target="b"), M(source="b", target="a"), M(source="c", target="a"),
                                                  M(source="d", target="d"), M(source="zz", target="a")])
    assert fold == {"a": "b"} and see_also == {"c": "b"}
    assert [r.outcome for r in records] == ["merged", "refused", "cross-reference", "refused", "refused"]


def three_rows(source_id):
    return [Finding(id=i, module="a", claim=claim, rationale=f"{claim} rationale with 40 cases", remedy="Report it.",
                    kind="clarification_request", evidence=[Evidence(source_id=source_id, quote="Quoted source sentence.")]).model_dump()
            for i, claim in (("x", "First claim"), ("y", "Second claim"), ("z", "Third claim"))]


@pytest.mark.reader_pass
def test_reader_merges_repeated_findings_and_links_an_unconfirmed_concern(tmp_path):
    paper = manuscript(tmp_path)
    def editorial(instruction):
        rows = json.loads(instruction.split("\nFINDINGS\n", 1)[1])
        return [{"finding_id": r["id"], "disposition": "keep", "reason": "ok", "priority": 1,
                 "severity": "major" if "First" in r["claim"] else "minor"} for r in rows]
    def verifier(instruction):
        block = json.loads(instruction.split("CANDIDATES\n", 1)[1].split("\nDISCIPLINE RULES", 1)[0])
        third = {c["finding_id"] for c in block if c["claim"] == "Third claim"}
        return [{**row, **({"status": "unresolved", "rationale": "cannot tell"} if row["finding_id"] in third else {})}
                for row in verify(instruction)]
    def reader(instruction):
        ids = {item["claim"].split()[0]: item["id"] for item in items(instruction)}
        return {"revisions": [{"id": ids["Second"], "claim": "Combined claim", "rationale": "Both rationales, 40 cases."}],
                "merges": [{"source": ids["First"], "target": ids["Second"], "reason": "Same point."},
                           {"source": ids["Third"], "target": ids["First"], "reason": "Same point again."}]}
    generator = ReaderBackend(reader, modules={"RUN a": three_rows(ingest(paper).id)}, editorial=editorial)
    result = ReviewPipeline(generator, profile("a"), ScriptedBackend(model="verifier", verify=verifier)).run(paper, output_dir=tmp_path / "out")
    review, audit = ((tmp_path / "out" / name).read_text() for name in ("review.md", "audit.md"))
    assert not result.partial, [(s.name, s.error) for s in result.stages if s.error]
    assert "### 1. Major: Combined claim" in review and "### 2." not in review  # severity raised from minor
    assert "- First claim" in review and "**See also finding 1**" in review and "Third claim" in review
    assert [m.outcome for m in result.reader_merges] == ["merged", "cross-reference"]
    assert "severity raised from minor to major" in audit and "Merged by the reader pass: Same point." in audit
    assert "href='#finding-1'" in (tmp_path / "out" / "review.html").read_text()
