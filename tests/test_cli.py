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
