from reviscope.cli import parser


def test_verifier_effort_can_override_generation_effort():
    args = parser().parse_args([
        "review", "paper.md", "--effort", "max",
        "--verifier-backend", "claude", "--verifier-effort", "high",
    ])
    assert args.effort == "max"
    assert args.verifier_effort == "high"


def test_verifier_effort_defaults_to_generation_effort_at_execution():
    args = parser().parse_args(["review", "paper.md", "--effort", "xhigh"])
    assert args.verifier_effort is None


def test_review_defaults_to_high_effort_and_one_hour_timeout():
    args = parser().parse_args(["review", "paper.md"])
    assert (args.effort, args.timeout) == ("high", 3600)


def test_holistic_audit_arguments_and_pinned_backend_defaults():
    from reviscope.backend import ClaudeBackend, CodexBackend

    args = parser().parse_args(["review", "paper.md", "--strategy", "holistic", "--evidence-audit"])
    assert args.strategy == "holistic" and args.evidence_audit
    assert (ClaudeBackend().model, ClaudeBackend().effort) == ("claude-opus-5-5", "high")
    assert (CodexBackend().model, CodexBackend().effort) == ("gpt-6-luna", "high")
