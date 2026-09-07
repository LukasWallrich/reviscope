import json

import pytest

from coarse_socpsy.normalization import (
    InventoryAudit,
    ReviewInventory,
    audit_inventory,
    normalize_review,
    render_inventory,
)


class StubBackend:
    def __init__(self, inventory=None, audit=None, identity="stub:model:test"):
        self.inventory, self.audit = inventory, audit
        self.identity = identity

    def generate(self, instruction, evidence, response_model):
        if response_model is ReviewInventory:
            return ReviewInventory.model_validate(self.inventory)
        if response_model is InventoryAudit:
            return InventoryAudit.model_validate(self.audit)
        raise AssertionError(response_model)


def inventory(span="The estimate is overstated."):
    return {"issues": [{"issue_id": "i1", "assessment_type": "criticism", "evaluation": "Estimate is overstated",
                         "rationale": "The review says so", "evidence": [], "remedy": "Qualify it",
                         "qualifications": ["May depend on the model"], "source_review_spans": [span]}]}


def clean_audit():
    return {"faithful": True, "complete": True, "missing_issues": [],
            "unsupported_issue_ids": [], "duplicate_issue_ids": [], "rationale": "Complete"}


def test_normalization_requires_exact_source_spans_and_renders():
    source = "The estimate is overstated. Please qualify it."
    result = normalize_review(source, StubBackend(inventory()))
    assert result["deterministic_checks"]["all_source_spans_matched"]
    assert "Estimate is overstated" in render_inventory(result)


def test_unmatched_span_blocks_rendering():
    result = normalize_review("Different text", StubBackend(inventory()))
    assert not result["deterministic_checks"]["all_source_spans_matched"]
    with pytest.raises(ValueError, match="deterministic checks"):
        render_inventory(result)


def test_audit_eligibility_requires_complete_faithful_unique_inventory():
    source = "The estimate is overstated. Please qualify it."
    normalized = normalize_review(source, StubBackend(inventory()))
    result = audit_inventory(source, normalized, StubBackend(audit=clean_audit(), identity="audit:model:test"))
    assert result["comparison_eligible"]

    incomplete = clean_audit() | {"complete": False, "missing_issues": [
        {"description": "Remedy omitted", "source_review_spans": ["Please qualify it."]}]}
    result = audit_inventory(source, normalized, StubBackend(audit=incomplete, identity="audit:model:test"))
    assert not result["comparison_eligible"]


def test_audit_rejects_inventory_from_different_review():
    normalized = normalize_review("The estimate is overstated.", StubBackend(inventory()))
    with pytest.raises(ValueError, match="different review"):
        audit_inventory("Another review", normalized, StubBackend(audit=clean_audit()))


def test_cli_registers_normalize_review():
    from coarse_socpsy.cli import parser
    args = parser().parse_args(["normalize-review", "create", "--review", "r.txt", "--output", "o.json",
                                "--backend", "openrouter", "--model", "z-ai/glm-5.3-flash"])
    assert args.max_tokens == 6000
