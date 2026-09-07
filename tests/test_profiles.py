import pytest

from coarse_socpsy.profiles import ProfileError, available_profiles, load_profile, load_profile_path


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
