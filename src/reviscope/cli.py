from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .backend import ClaudeBackend, CodexBackend, FixtureBackend
from .pipeline import ReviewPipeline
from .evaluation import register as register_evaluation
from .normalization import register as register_normalization
from .ranking import register as register_ranking
from .profiles import available_profiles


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reviscope", description="Auditable social-science manuscript review")
    sub = p.add_subparsers(dest="command", required=True)
    profiles = sub.add_parser("profiles", help="list bundled discipline profiles")
    profiles.set_defaults(func=lambda _args: _print_profiles())
    review = sub.add_parser("review")
    review.add_argument("manuscript")
    review.add_argument("--supplement", action="append", default=[])
    review.add_argument("--preregistration", action="append", default=[])
    review.add_argument("--profile", default="social_psychology", help="bundled profile id or profile directory (default: social_psychology)")
    review.add_argument("--parallel", type=int, default=4,
                        help="model stages run concurrently: independent modules, then verification batches (default 4)")
    review.add_argument("--backend", choices=["codex", "claude", "fixture"], default="codex")
    review.add_argument("--model", choices=["gpt-6-luna", "gpt-6.1-sol", "claude-opus-5-5"])
    review.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="high")
    review.add_argument("--verifier-backend", choices=["codex", "claude"], help="Optional independent verification backend")
    review.add_argument("--verifier-model", choices=["gpt-6-luna", "gpt-6.1-sol", "claude-opus-5-5"])
    review.add_argument("--verifier-effort", choices=["low", "medium", "high", "xhigh", "max"],
                        help="verification reasoning effort (defaults to --effort)")
    review.add_argument("--timeout", type=int, default=3600, help="per-model-call timeout in seconds (default: 3600)")
    review.add_argument("--out", default="review-run")
    review.add_argument("--quiet", action="store_true")
    review.add_argument("--no-metacheck", action="store_true", help="skip the metacheck screening stage (runs by default)")
    review.set_defaults(func=_review_command)
    register_evaluation(sub)
    register_normalization(sub)
    register_ranking(sub)
    return p


def _print_profiles() -> int:
    print("\n".join(available_profiles()))
    return 0


def _review_command(args: argparse.Namespace) -> int:
    if args.backend == "fixture":
        backend = FixtureBackend()
        print("WARNING: fixture backend creates deterministic demo output; it is not an AI review.", file=sys.stderr)
    elif args.backend == "claude":
        backend = ClaudeBackend(args.model, args.timeout, args.effort)
    else:
        backend = CodexBackend(args.model or "gpt-6-luna", args.timeout, args.effort)
    verifier = None
    verifier_effort = args.verifier_effort or args.effort
    if args.verifier_backend == "claude":
        verifier = ClaudeBackend(args.verifier_model, args.timeout, verifier_effort)
    elif args.verifier_backend == "codex":
        verifier = CodexBackend(args.verifier_model or "gpt-6-luna", args.timeout, verifier_effort)
    try:
        output_dir = Path(args.out).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "run.log"
        def progress(message: str) -> None:
            line = f"{datetime.now(timezone.utc).isoformat()} {message}"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            if not args.quiet:
                print(message, file=sys.stderr, flush=True)
        run = ReviewPipeline(backend, args.profile, verifier_backend=verifier, progress=progress,
                             run_metacheck=not args.no_metacheck, parallel=args.parallel).run(
            args.manuscript, supplements=args.supplement, preregistrations=args.preregistration, output_dir=args.out)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {'partial' if run.partial else 'complete'} review to {args.out}")
    return 2 if run.partial else 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
