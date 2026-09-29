import pytest

from reviscope.profiles import ProfileError, available_profiles, load_profile, load_profile_path


def test_social_psychology_inherits_base_protocols():
    profile = load_profile("social_psychology")
    assert profile.modules[:2] == ["contribution", "design"]
    assert "social_psychology_context" in profile.modules
    assert "Never infer inadequate power" in profile.module_prompts["design"]
    assert "preregistration" in profile.module_prompts["social_psychology_context"]
    assert profile.metadata["ancestry"] == ["quantitative_social_science", "social_psychology"]


def test_education_is_explicitly_unvalidated_extension():
    profile = load_profile("education")
    assert profile.metadata["status"] == "demonstration_unvalidated"
    assert profile.metadata["validated"] is False
    assert "education_context" in profile.modules


def test_unknown_profile_fails_loudly():
    with pytest.raises(ProfileError, match="Unknown profile"):
        load_profile("clinical_phrenology")
    assert {"education", "quantitative_social_science", "social_psychology",
            "quantitative_social_science_v2", "social_psychology_v2"} <= set(available_profiles())


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


def test_shipped_external_education_example_inherits_v2_calibration():
    from pathlib import Path

    example = Path(__file__).parents[1] / "examples" / "education_profile"
    profile = load_profile_path(example)
    assert "quantitative_social_science_v2" in profile.metadata["ancestry"]
    assert profile.metadata["validated"] is False
    assert "education_context" in profile.modules
    assert "invalidates a central result" in profile.metadata["severity_guidance"]["critical"]
    assert "acknowledge a design limitation" in profile.module_prompts["design"]
    assert "This example is not a validated education-review rubric" in profile.module_prompts["education_context"]


def test_v2_profile_preserves_v1_and_adds_scientific_restraint_contracts():
    original = load_profile("social_psychology")
    revised = load_profile("social_psychology_v2")
    assert original.metadata["version"] == "0.1.0"
    assert revised.metadata["version"] == "0.2.0"
    effective = "\n".join(revised.module_prompts.values())
    for required in (
        "at most one consolidated reviewability finding",
        "Do not ask authors to preregister a completed study",
        "acknowledge a design limitation",
        "Compare numerical claims in prose with relevant tables",
        "Do not restate an author-acknowledged limitation",
        "Prefer one consolidated issue",
    ):
        assert required in effective
    assert "maximum finding count is a ceiling, never a target" in revised.editorial_prompt
    assert "classify the proposed remedy" in revised.verification_prompt
