import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel

from reviscope.backend import (REVIEW_DOMAINS, ClaudeBackend, CodexBackend, FixtureBackend, SubprocessBackend,
                               parse_claude_events, parse_codex_events)
from reviscope.pipeline import ReviewPipeline

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def test_codex_event_stream_yields_search_exec_and_final_message():
    calls, final = parse_codex_events((FIXTURES / "codex_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["search", "exec", "exec", "exec"]
    assert calls[0].query == "Cohen 1992 A power primer Psychological Bulletin DOI" and "pubmed" in calls[0].output
    assert calls[0].result_urls[0] == "https://pubmed.ncbi.nlm.nih.gov/19565683/"
    assert "scipy" in calls[1].command and calls[1].output.startswith("0.0502")
    assert json.loads(final)["doi"] == "10.1037/0033-2909.112.1.155"


def test_codex_parser_keeps_every_query_and_marks_failed_or_unfinished_calls():
    events = [
        {"type": "item.completed", "item": {"id": "1", "type": "web_search", "action": {"type": "search", "query": "effect sizes ...", "queries": ["effect sizes", "paper title reviews"]}}},
        {"type": "item.completed", "item": {"id": "2", "type": "command_execution", "command": "rm x", "status": "declined", "exit_code": None}},
        {"type": "item.completed", "item": {"id": "4", "type": "web_search", "action": {"type": "open_page"}, "results": [{"url": "https://pubmed.ncbi.nlm.nih.gov/21474762/"}]}},
        {"type": "item.started", "item": {"id": "3", "type": "command_execution", "command": "python3 slow.py"}},
    ]
    calls, _ = parse_codex_events("\n".join(json.dumps(e) for e in events), NOW)
    assert [c.query for c in calls[:2]] == ["effect sizes", "paper title reviews"]
    assert calls[2].error and calls[4].error and "incomplete" in calls[4].output
    assert calls[3].kind == "fetch" and calls[3].opened_urls == ["https://pubmed.ncbi.nlm.nih.gov/21474762/"] and not calls[3].error
    failed_open = {"type": "item.completed", "item": {"id": "5", "type": "web_search", "action": {"type": "open_page"},
                                                     "results": [{"type": "text_result", "ref_id": "turn1view0", "title": "Internal Error"}]}}
    [failed], _ = parse_codex_events(json.dumps(failed_open), NOW)
    assert failed.kind == "fetch" and failed.error and not failed.opened_urls


def test_claude_event_stream_pairs_tool_uses_with_results_and_records_refusals():
    calls, final = parse_claude_events((FIXTURES / "claude_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["exec", "exec", "exec", "fetch", "fetch"]
    assert calls[0].error and "operation not permitted" in calls[0].output
    assert "sandbox_violations" in calls[2].output
    assert calls[3].url == "https://pubpeer.com/" and calls[3].error
    assert calls[4].url == "https://example.org/" and not calls[4].error
    assert '"exampleorg":true' in final


def test_review_backends_sandbox_the_shell_and_judges_have_no_tools():
    tmp = Path("/tmp/reviscope-test")
    codex = CodexBackend("gpt-6-luna", effort="low").command(tmp)
    assert 'web_search="live"' in codex and 'default_permissions="reviscope"' in codex and codex[-1] == "-"
    profile = next(part for part in codex if part.startswith("permissions.reviscope="))
    assert f'"{Path.home()}"="deny"' in profile and '":workspace_roots"={"."="write"}' in profile and "network={enabled=false}" in profile
    assert "allow_login_shell=false" in codex and "--sandbox" not in codex
    claude_backend = ClaudeBackend("claude-opus-5-5", effort="low")
    claude = claude_backend.command(tmp)
    settings = json.loads(claude[claude.index("--settings") + 1])["sandbox"]
    assert settings["failIfUnavailable"] and not settings["allowUnsandboxedCommands"]
    assert "Bash" in claude[claude.index("--allowedTools") + 1].split(",")  # no one can answer a permission prompt
    assert settings["filesystem"]["denyRead"] == ["~/"] and settings["network"] == {"strictAllowlist": True, "allowedDomains": []}
    assert f"WebFetch(domain:{REVIEW_DOMAINS[0]})" in json.loads(claude[claude.index("--settings") + 1])["permissions"]["deny"]
    assert claude_backend.environment(tmp)["CLAUDE_CODE_TMPDIR"] == str(tmp)
    judge = ClaudeBackend("claude-opus-5-5", effort="low", tools=False).command(tmp)
    for flag in ("--restricted", "--safe-mode", "--no-session-persistence"):
        assert flag in claude and flag in judge
    assert judge[judge.index("--tools") + 1] == ""
    assert 'web_search="disabled"' in CodexBackend("gpt-6-luna", effort="low", tools=False).command(tmp)
    assert CodexBackend("gpt-6-luna", effort="low").identity != CodexBackend("gpt-6-luna", effort="low", tools=False).identity
    assert FixtureBackend().take_tool_calls() == []
    with pytest.raises(ValueError, match="tool-enabled"):
        ReviewPipeline(CodexBackend("gpt-6-luna", tools=False))


class Answer(BaseModel):
    value: int


class ScriptBackend(SubprocessBackend):
    """Runs a shell script instead of a model CLI; stdout is parsed as a Claude event stream."""

    name, binary = "script", "sh"

    def __init__(self, script: str, timeout: int = 60):
        super().__init__("script", timeout)
        self.script = script

    def command(self, tmp):
        return ["sh", "-c", self.script]

    def _parse(self, stdout, started):
        return parse_claude_events(stdout, started)


def test_timeout_keeps_partial_tool_calls_and_kills_the_process_group(tmp_path):
    marker = tmp_path / "child-alive"
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "WebFetch", "input": {"url": "https://example.org/"}}]}}
    backend = ScriptBackend(f"echo '{json.dumps(use)}'; (sleep 3; touch {marker}) & sleep 30", timeout=1)
    with pytest.raises(TimeoutError):
        backend.generate("task", "evidence", Answer)
    calls = backend.take_tool_calls()
    assert calls[0].url == "https://example.org/" and calls[0].error
    time.sleep(3.5)
    assert not marker.exists()


def test_interrupt_kills_the_process_group_and_keeps_tool_calls(tmp_path):
    import os
    import signal
    import threading

    marker = tmp_path / "child-alive"
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "WebFetch", "input": {"url": "https://example.org/"}}]}}
    backend = ScriptBackend(f"echo '{json.dumps(use)}'; (sleep 3; touch {marker}) & sleep 30")
    threading.Timer(1, os.kill, (os.getpid(), signal.SIGINT)).start()  # as Ctrl-C would
    with pytest.raises(KeyboardInterrupt):
        backend.generate("task", "evidence", Answer)
    assert backend.take_tool_calls()[0].url == "https://example.org/"
    time.sleep(3.5)
    assert not marker.exists()


def test_schema_repair_repeats_the_original_task_and_the_validation_error():
    prompts = []

    class Repairing(ScriptBackend):
        def _run(self, prompt, response_model, images=None):
            prompts.append(prompt)
            return '{"value": "not a number"}' if len(prompts) == 1 else '{"value": 3}'

    assert Repairing("").generate("count the studies", "MANUSCRIPT TEXT", Answer).value == 3
    assert "count the studies" in prompts[1] and "MANUSCRIPT TEXT" in prompts[1] and "valid integer" in prompts[1]


def test_managed_policy_that_widens_the_sandbox_blocks_tool_calls_and_changes_identity(tmp_path, monkeypatch):
    from reviscope import backend as backend_module

    claude_file, codex_file = tmp_path / "managed-settings.json", tmp_path / "requirements.toml"
    monkeypatch.setattr(backend_module, "MANAGED_POLICY", {"claude": (claude_file,), "codex": (codex_file,)})
    before = ClaudeBackend("claude-opus-5-5").identity
    claude_file.write_text(json.dumps({"sandbox": {"network": {"strictAllowlist": True, "allowedDomains": []},
                                                   "filesystem": {"allowRead": ["/usr/share"]}}}))
    backend_module.check_managed_policy("claude")  # narrowing or neutral settings pass
    assert ClaudeBackend("claude-opus-5-5").identity != before
    for widening in ({"sandbox": {"excludedCommands": ["python3"]}}, {"sandbox": {"allowUnsandboxedCommands": True}},
                     {"sandbox": {"filesystem": {"allowRead": ["~/.ssh"]}}}, {"sandbox": {"network": {"allowedDomains": ["example.org"]}}}):
        claude_file.write_text(json.dumps(widening))
        with pytest.raises(backend_module.PolicyError, match="widens the review sandbox"):
            ClaudeBackend("claude-opus-5-5").generate("task", "evidence", Answer)
    codex_file.write_text('[permissions.x]\nnetwork = { enabled = false }\n')
    backend_module.check_managed_policy("codex")
    for widening in ('sandbox_mode = "danger-full-access"\n', '[sandbox_workspace_write]\nnetwork_access = true\n',
                     '[permissions.x.network]\nenabled = true\n', f'[permissions.x.filesystem]\n"{Path.home()}/.aws" = "read"\n',
                     '[permissions.x.filesystem."~/proj"]\n"." = "write"\n'):
        codex_file.write_text(widening)
        with pytest.raises(backend_module.PolicyError):
            backend_module.check_managed_policy("codex")


def test_codex_on_linux_runs_a_binary_installed_outside_the_home_directory(tmp_path, monkeypatch):
    from reviscope import backend as backend_module

    home, system = tmp_path / "home", tmp_path / "opt"
    for directory in (home / "bin", system / "bin"):
        directory.mkdir(parents=True)
        (directory / "codex").write_text("#!/bin/sh\n")
        (directory / "codex").chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(backend_module.sys, "platform", "linux")
    monkeypatch.setenv("PATH", f"{home / 'bin'}:{system / 'bin'}")
    assert CodexBackend("gpt-6-luna").command(tmp_path)[0] == str((system / "bin" / "codex").resolve())
    assert CodexBackend("gpt-6-luna", tools=False).command(tmp_path)[0] == "codex"
    monkeypatch.setenv("PATH", str(home / "bin"))
    with pytest.raises(backend_module.PolicyError, match="outside"):
        CodexBackend("gpt-6-luna").generate("task", "evidence", Answer)
    monkeypatch.setattr(backend_module.sys, "platform", "darwin")
    assert CodexBackend("gpt-6-luna").command(tmp_path)[0] == "codex"


def test_cli_version_is_provenance_not_part_of_the_backend_identity(monkeypatch):
    from reviscope import backend as backend_module

    monkeypatch.setattr(backend_module, "cli_version", lambda binary: "codex-cli 1.0.0")
    before = CodexBackend("gpt-6-luna", effort="high")
    identity, version = before.identity, before.version
    monkeypatch.setattr(backend_module, "cli_version", lambda binary: "codex-cli 2.0.0")
    after = CodexBackend("gpt-6-luna", effort="high")
    assert after.identity == identity and (version, after.version) == ("codex-cli 1.0.0", "codex-cli 2.0.0")
    assert CodexBackend("gpt-6.1-sol", effort="high").identity != identity


def _detached_child(marker: Path) -> str:
    """Shell snippet starting a child in a session of its own, as Claude Code does for its sandboxed shell."""
    import sys

    code = f"import os, time; os.setsid(); time.sleep(3); open({str(marker)!r}, 'w')"
    return f"{sys.executable} -c \"{code}\" &"


def test_timeout_also_kills_children_that_left_the_process_group(tmp_path):
    marker = tmp_path / "detached-alive"
    backend = ScriptBackend(f"{_detached_child(marker)} sleep 30", timeout=1)
    with pytest.raises(TimeoutError):
        backend.generate("task", "evidence", Answer)
    time.sleep(3.5)
    assert not marker.exists()


def test_interrupt_during_parallel_stages_stops_every_running_cli(tmp_path):
    import os
    import signal
    import threading

    markers = [tmp_path / f"alive-{i}" for i in range(3)]
    backends = [ScriptBackend(f"{_detached_child(marker)} sleep 30") for marker in markers]
    jobs = [(f"stage-{i}", {"i": i}, Answer, (lambda b=b: b.generate("task", "evidence", Answer)), b) for i, b in enumerate(backends)]
    pipeline = ReviewPipeline(FixtureBackend(), parallel=3)
    threading.Timer(1, os.kill, (os.getpid(), signal.SIGINT)).start()
    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        pipeline._prefetch(tmp_path, jobs)
    assert time.monotonic() - started < 10  # does not wait for the 30-second calls
    time.sleep(3.5)
    assert not any(marker.exists() for marker in markers)


def test_managed_policy_drop_ins_and_codex_home_are_checked(tmp_path, monkeypatch):
    from reviscope import backend as backend_module

    drop_ins = tmp_path / "managed-settings.d"
    drop_ins.mkdir()
    monkeypatch.setattr(backend_module, "MANAGED_POLICY", {"claude": (drop_ins,), "codex": ()})
    before = backend_module.policy_hash("claude")
    (drop_ins / "10-team.json").write_text(json.dumps({"sandbox": {"excludedCommands": ["python3"]}}))
    assert backend_module.policy_hash("claude") != before
    with pytest.raises(backend_module.PolicyError, match="10-team.json"):
        backend_module.check_managed_policy("claude")
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "requirements.toml").write_text('sandbox_mode = "danger-full-access"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    with pytest.raises(backend_module.PolicyError, match="requirements.toml"):
        backend_module.check_managed_policy("codex")


def test_config_directories_outside_home_are_hidden_and_credentials_go_only_to_their_cli(tmp_path, monkeypatch):
    for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY", "HTTPS_PROXY"):
        monkeypatch.delenv(name, raising=False)
    baseline_codex, baseline_claude = CodexBackend("gpt-6-luna").command(tmp_path), ClaudeBackend().command(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(Path.home() / ".codex-alt"))  # inside home: already hidden
    assert CodexBackend("gpt-6-luna").command(tmp_path) == baseline_codex
    monkeypatch.setenv("CODEX_HOME", "/srv/codex")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/srv/claude")
    profile = next(part for part in CodexBackend("gpt-6-luna").command(tmp_path) if part.startswith("permissions.reviscope="))
    assert '"/srv/codex"="deny"' in profile
    claude = ClaudeBackend().command(tmp_path)
    settings = json.loads(claude[claude.index("--settings") + 1])
    assert "/srv/claude" in settings["sandbox"]["filesystem"]["denyRead"] and "Read(//srv/claude/**)" in settings["permissions"]["deny"]
    assert claude != baseline_claude
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    codex_env, claude_env = CodexBackend("gpt-6-luna").environment(tmp_path), ClaudeBackend().environment(tmp_path)
    assert "ANTHROPIC_API_KEY" not in codex_env and "CLAUDE_CONFIG_DIR" not in codex_env and codex_env["CODEX_HOME"] == "/srv/codex"
    assert claude_env["ANTHROPIC_API_KEY"] == "test-key" and "CODEX_HOME" not in claude_env
    assert codex_env["HTTPS_PROXY"] == claude_env["HTTPS_PROXY"] == "http://proxy.example:3128"


def test_a_missing_cli_stops_the_run_before_any_stage(tmp_path, monkeypatch):
    from reviscope.cli import main

    monkeypatch.setenv("PATH", str(tmp_path))  # no claude or codex here
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("# Paper\n\nParticipants were recruited from the university pool.\n")
    with pytest.raises(FileNotFoundError, match="claude CLI"):
        ReviewPipeline(FixtureBackend(), verifier_backend=ClaudeBackend()).run(manuscript, output_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert main(["review", str(manuscript), "--backend", "claude", "--out", str(tmp_path / "cli-out"), "--no-metacheck"]) == 1
