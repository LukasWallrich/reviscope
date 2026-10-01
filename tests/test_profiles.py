import pytest

from reviscope.profiles import ProfileError, available_profiles, load_profile, load_profile_path


def test_social_psychology_inherits_base_protocols():
    profile = load_profile("social_psychology")
    assert profile.modules[:2] == ["contribution", "design"]
    assert "social_psychology_context" in profile.modules
    assert "never from N alone" in profile.module_prompts["design"]
    assert "preregistration" in profile.module_prompts["social_psychology_context"]
    assert profile.metadata["ancestry"] == ["quantitative_social_science", "social_psychology"]


# Benchmark error category -> owning module and the coverage check that names it.
CATEGORY_OWNERS = {
    "statistical errors": ("statistical_inference", "statistical_errors"),
    "methodological design": ("design", "confounds_and_controls"),
    "construct validity": ("measurement", "construct_validity"),
    "causal inference": ("interpretation", "causal_inference"),
    "internal consistency": ("consistency", "cross_section_agreement"),
    "reporting completeness": ("consistency", "planned_versus_reported_analyses"),
    "generalizability": ("interpretation", "generalizability"),
    "theoretical/conceptual problems": ("contribution", "theoretical_argument"),
    "analytic flexibility": ("statistical_inference", "analytic_flexibility"),
    "attrition and missing data": ("design", "attrition_and_missing_data"),
}


@pytest.mark.parametrize("category", CATEGORY_OWNERS)
def test_every_error_category_has_an_owning_module_and_coverage_check(category):
    from reviscope.discovery import TOPICS

    module, check = CATEGORY_OWNERS[category]
    profile = load_profile("social_psychology")
    assert module in profile.modules and check in TOPICS[module]
    assert f"For {check}," in profile.module_prompts[module]


def test_power_is_judged_by_computed_sensitivity_for_each_claimed_inference():
    from reviscope.discovery import TOPICS

    prompts = load_profile("quantitative_social_science").module_prompts
    assert "power_and_sensitivity" in TOPICS["statistical_inference"]
    power = prompts["statistical_inference"]
    for phrase in ("target effect size", "recompute it with code", "interactions, subgroup analyses and equivalence tests",
                   "never judge it from N alone", "never request observed or post-hoc power"):
        assert phrase in power


def test_education_is_explicitly_unvalidated_extension():
    profile = load_profile("education")
    assert profile.metadata["status"] == "demonstration_unvalidated"
    assert profile.metadata["validated"] is False
    assert "education_context" in profile.modules


def test_unknown_profile_fails_loudly():
    with pytest.raises(ProfileError, match="Unknown profile"):
        load_profile("clinical_phrenology")
    assert set(available_profiles()) == {"education", "quantitative_social_science", "social_psychology"}


def test_external_profile_can_extend_bundled_base(tmp_path):
    folder = tmp_path / "political_science"
    folder.mkdir()
    (folder / "profile.json").write_text(
        '{"id":"political_science","name":"Political science demo","extends":"quantitative_social_science",'
        '"modules":["institutions"],"terminology":{"participant":"respondent or polity"}}')
    (folder / "institutions.generation.md").write_text("Assess institutional scope.")
    (folder / "institutions.verification.md").write_text("Verify the institution and jurisdiction.")
    profile = load_profile_path(folder)
    assert profile.modules[-1] == "institutions"
    assert "respondent or polity" in profile.module_prompts["design"]
    assert "institution and jurisdiction" in profile.verification_prompt


def test_shipped_external_education_example_inherits_bundled_calibration():
    from pathlib import Path

    example = Path(__file__).parents[1] / "examples" / "education_profile"
    profile = load_profile_path(example)
    assert profile.metadata["ancestry"] == ["quantitative_social_science", "education_local_example"]
    assert profile.metadata["validated"] is False
    assert "education_context" in profile.modules
    assert "invalidates a central result" in profile.metadata["severity_guidance"]["critical"]
    assert "acknowledge a design limitation" in profile.module_prompts["design"]
    assert "This example is not a validated education-review rubric" in profile.module_prompts["education_context"]


def test_single_profile_merges_restraint_and_coverage_rules_without_quotas():
    profile = load_profile("social_psychology")
    assert profile.metadata["terminology"]["construct"] == "psychological construct"
    effective = "\n".join([*profile.module_prompts.values(), profile.verification_prompt, profile.editorial_prompt])
    for required in (
        "single consolidated reviewability finding",
        "Do not ask authors to preregister a completed study",
        "acknowledge a design limitation",
        "Recompute reported quantities with code",
        "Audit strong exclusionary or universal claims",
        "Do not restate an author-acknowledged limitation",
        "Evaluate whether the design distinguishes the claimed mechanism",
        "classify the proposed remedy",
        "The number of published findings is not limited",
    ):
        assert required in effective, required
    lowered = effective.lower()
    for banned in ("override", "v2 ", "v3 ", "at most", "zero to three", "prefer one", "maximum finding count",
                   "short review", "spending findings", "prioritize"):
        assert banned not in lowered, banned
