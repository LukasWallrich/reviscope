"""Offline transport/gating probes, with scripted judgments, not model-quality tests."""
from reviscope.discovery import discovery_instruction, requested_checks, TOPICS
from reviscope.pipeline import ReviewPipeline
from reviscope.profiles import load_profile
from reviscope.reasoning import ARGUMENT_ASSESSMENT, LITERATURE_ASSESSMENT, MATERIAL_ASSESSMENT
from test_verification_flow import EvidenceBackend, manuscript


def test_guidance_reaches_specialist_profiles_without_new_coverage_topics():
    for profile_id in ("quantitative_social_science", "social_psychology", "education"):
        profile = load_profile(profile_id)
        for module in ("contribution", "interpretation", "measurement"):
            instruction = discovery_instruction(module, profile.module_prompts[module])
            assert ARGUMENT_ASSESSMENT in instruction
            assert requested_checks(instruction) == TOPICS[module]
            if module == "contribution":
                assert LITERATURE_ASSESSMENT in instruction
            else:
                assert MATERIAL_ASSESSMENT in instruction
        assert "sentence order" in profile.verification_prompt
        assert "supplements resolve" in profile.verification_prompt
        for module in ("social_psychology_context", "education_context"):
            if module in profile.modules:
                assert MATERIAL_ASSESSMENT in discovery_instruction(module, profile.module_prompts[module])


def test_verifier_applies_the_reasoning_criteria_on_the_specialist_path(tmp_path):
    backend = EvidenceBackend(count=1)
    run = ReviewPipeline(backend, run_metacheck=False).run(manuscript(tmp_path), output_dir=tmp_path / "out")
    verification = [instruction for kind, instruction, _ in backend.calls if kind == "VerificationResponse"]
    assert not run.partial and verification
    assert all(ARGUMENT_ASSESSMENT in instruction and LITERATURE_ASSESSMENT in instruction for instruction in verification)
