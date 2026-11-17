import json
import time
import os
import shutil
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


def _opencode_events() -> str:
    def tool(name, status, arguments, output="", metadata=None, error=None):
        state = {"status": status, "input": arguments, "output": output, "metadata": metadata or {}, "title": name}
        if error:
            state["error"] = error
        return {"type": "tool_use", "sessionID": "ses_1", "part": {"type": "tool", "tool": name, "callID": "c", "state": state}}
    events = [
        {"type": "step_start", "part": {"type": "step-start"}},
        tool("websearch", "completed", {"query": "Cohen 1992 power primer"}, "Title: A power primer\nURL: https://pubmed.ncbi.nlm.nih.gov/19565683/"),
        tool("bash", "completed", {"command": "python3 -c 'print(1/3)'"}, "0.333\n", {"exit": 0}),
        tool("bash", "completed", {"command": "curl https://example.com"}, "curl: (6) Could not resolve host", {"exit": 6}),
        tool("webfetch", "error", {"url": "https://pubpeer.com/"}, error="denied by pattern *pubpeer.com*"),
        {"type": "text", "part": {"type": "text", "text": "Working on it."}},
        {"type": "text", "part": {"type": "text", "text": '{"value": 3}'}},
    ]
    return "\n".join(json.dumps(event) for event in events) + "\nnot json\n"


def test_opencode_event_stream_yields_tool_calls_and_final_text():
    from reviscope.backend import parse_opencode_events

    calls, final = parse_opencode_events(_opencode_events(), NOW)
    assert [c.kind for c in calls] == ["search", "exec", "exec", "fetch"] and [c.sequence for c in calls] == [0, 1, 2, 3]
    assert calls[0].query == "Cohen 1992 power primer" and calls[0].result_urls == ["https://pubmed.ncbi.nlm.nih.gov/19565683/"]
    assert not calls[1].error and calls[1].output == "0.333\n"
    assert calls[2].error  # non-zero exit status
    assert calls[3].url == "https://pubpeer.com/" and calls[3].error and "denied" in calls[3].output
    assert final == '{"value": 3}'


@pytest.fixture
def opencode_catalogue(monkeypatch):
    """Offline stand-in for OpenCode's model catalogue: one text-only and one image-capable model."""
    from reviscope import backend as backend_module

    models = {"openrouter/deepseek/deepseek-v4-flash": backend_module.OpenCodeModel(("OPENROUTER_API_KEY",), ("none", "high", "xhigh"), False),
              "openrouter/z-ai/glm-5.3-flash": backend_module.OpenCodeModel(("OPENROUTER_API_KEY",), ("low", "high", "max"), True),
              "local/plain": backend_module.OpenCodeModel(("LOCAL_KEY",), (), False)}

    def lookup(model):
        if model not in models:
            raise ValueError(f"OpenCode does not list {model}")
        return models[model]
    monkeypatch.setattr(backend_module, "opencode_model", lookup)
    monkeypatch.setattr(backend_module, "opencode_auth", lambda provider: None)
    return models


def test_opencode_isolates_configuration_and_allows_only_shell_and_web_tools(tmp_path, monkeypatch, opencode_catalogue):
    from reviscope.backend import OPENCODE_STATE, OpenCodeBackend

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "other-key")
    backend = OpenCodeBackend()
    assert backend.model == "openrouter/z-ai/glm-5.3-flash"
    command, env = backend.command(tmp_path), backend.environment(tmp_path)
    assert command[:2] == ["opencode", "run"] and "--pure" in command and command[command.index("--format") + 1] == "json"
    assert command[command.index("--variant") + 1] == "high" and "--title" in command
    state = tmp_path / OPENCODE_STATE
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        assert Path(env[key]).parent == state  # never the user's ~/.config/opencode or auth.json
    assert env["OPENCODE_DISABLE_PROJECT_CONFIG"] == env["OPENCODE_DISABLE_CLAUDE_CODE"] == env["OPENCODE_PURE"] == "1"
    assert env["OPENROUTER_API_KEY"] == "test-key" and "ANTHROPIC_API_KEY" not in env
    config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    permission = config["permission"]
    assert list(permission)[0] == "*" and permission["*"] == "deny"  # read, edit, write, glob, grep, list, task, skill
    assert {key for key, value in permission.items() if value == "allow"} == {"bash", "external_directory", "websearch"}
    assert permission["webfetch*"]["*"] == "allow" and permission["webfetch*"][f"*{REVIEW_DOMAINS[0]}*"] == "deny"
    assert permission["webfetch*"]["*://127.*"] == "deny"
    assert config["shell"] == str(state / "sandbox-shell") and config["mcp"] == {} and config["plugin"] == []
    assert config["small_model"] == config["model"] and config["provider"]["openrouter"]["whitelist"] == ["z-ai/glm-5.3-flash"]
    assert "shell commands" in backend.guard  # the file tools are gone; say how to read files instead
    judge = OpenCodeBackend(tools=False)
    judge_config = json.loads(judge.environment(tmp_path)["OPENCODE_CONFIG_CONTENT"])
    assert judge_config["permission"] == {"*": "deny"} and "shell" not in judge_config
    assert "OPENCODE_ENABLE_EXA" not in judge.environment(tmp_path) and judge.identity != backend.identity
    with pytest.raises(ValueError, match="shell-network"):
        OpenCodeBackend(shell_network=True)
    with pytest.raises(ValueError, match="none, high, xhigh"):
        OpenCodeBackend("openrouter/deepseek/deepseek-v4-flash", effort="low")
    with pytest.raises(ValueError, match="does not list"):
        OpenCodeBackend("openrouter/unknown/model")
    plain = OpenCodeBackend("local/plain", effort="max")  # no reasoning variants: run without one
    assert plain.effort == "default" and "--variant" not in plain.command(tmp_path) and "LOCAL_KEY" in plain.env_keys


def test_opencode_attaches_images_only_for_image_models_and_passes_only_its_providers_login(tmp_path, monkeypatch, opencode_catalogue):
    from reviscope import backend as backend_module

    image = tmp_path / "page-images" / "p1.png"
    command = backend_module.OpenCodeBackend().command(tmp_path)
    backend_module.OpenCodeBackend()._attach(command, [image])
    assert command[2:4] == ["--file", str(image)]
    with pytest.raises(NotImplementedError, match="does not accept images"):
        backend_module.OpenCodeBackend("openrouter/deepseek/deepseek-v4-flash")._attach([], [image])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    (tmp_path / "opencode").mkdir()
    (tmp_path / "opencode" / "auth.json").write_text(json.dumps({"openrouter": {"type": "api", "key": "k1"}, "zai": {"type": "api", "key": "k2"}}))
    monkeypatch.undo()  # restore the real opencode_auth, keep XDG_DATA_HOME below
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert json.loads(backend_module.opencode_auth("openrouter")) == {"openrouter": {"type": "api", "key": "k1"}}
    assert backend_module.opencode_auth("anthropic") is None


def test_opencode_sandbox_hides_home_state_and_temp_and_mounts_staged_files_read_only(tmp_path, monkeypatch):
    from reviscope.backend import OPENCODE_STATE, TOOL_OUTPUT_DIR, opencode_sandbox_args

    monkeypatch.setenv("XDG_DATA_HOME", "/srv/xdg-data")
    args = opencode_sandbox_args(tmp_path)
    tmpfs = {args[i + 1] for i, arg in enumerate(args) if arg == "--tmpfs"}
    assert {str(Path.home().resolve()), "/srv/xdg-data", "/tmp", str(tmp_path / OPENCODE_STATE)} <= tmpfs
    assert "--unshare-all" in args and "--clearenv" in args and "--share-net" not in args
    assert args[args.index("--ro-bind") + 1:args.index("--ro-bind") + 3] == ["/", "/"]
    assert args.index("--tmpfs") > args.index("--ro-bind")  # hidden paths are mounted over the read-only root
    bind = args.index("--bind")
    assert args[bind + 1:bind + 3] == [str(tmp_path)] * 2 and args.index(str(tmp_path / OPENCODE_STATE)) > bind
    assert ["--ro-bind-try", str(tmp_path / "materials"), str(tmp_path / "materials")] == args[-3:]
    truncated = str(tmp_path / OPENCODE_STATE / TOOL_OUTPUT_DIR)  # full text of truncated tool output stays readable
    assert args.index(truncated) > args.index(str(tmp_path / OPENCODE_STATE)) and args[args.index(truncated) - 1] == "--ro-bind-try"


def test_opencode_seccomp_filter_refuses_unix_sockets_and_io_uring():
    import platform
    import struct

    from reviscope.backend import _seccomp_filter

    if platform.machine() not in {"x86_64", "aarch64"}:
        pytest.skip("seccomp filter is built for x86_64 and aarch64")
    program = [struct.unpack("=HBBI", _seccomp_filter()[i:i + 8]) for i in range(0, len(_seccomp_filter()), 8)]

    def run(nr: int, arg0: int = 0, arch: int | None = None) -> int:
        data = {0: nr, 4: arch if arch is not None else program[1][3], 16: arg0}
        pc, accumulator = 0, 0
        while True:
            code, jt, jf, k = program[pc]
            if code == 0x20:
                accumulator = data[k]
            elif code == 0x06:
                return k
            elif code in (0x15, 0x35):
                taken = accumulator == k if code == 0x15 else accumulator >= k
                pc += jt if taken else jf
            pc += 1

    socket_nr = 41 if platform.machine() == "x86_64" else 198
    allow, eperm = 0x7FFF0000, 0x00050001
    assert run(socket_nr, 1) == eperm and run(socket_nr, 2) == allow and run(425) == eperm
    assert run(0x40000000 + 41) == eperm and run(0) == allow and run(0, arch=0x40000003) == 0x80000000


def test_opencode_refuses_managed_configuration(tmp_path, monkeypatch, opencode_catalogue):
    from reviscope import backend as backend_module

    managed = tmp_path / "opencode.json"
    monkeypatch.setattr(backend_module, "MANAGED_POLICY", {"opencode": (managed,)})
    monkeypatch.setattr(backend_module, "bubblewrap_works", lambda: None)
    backend = backend_module.OpenCodeBackend()
    before = backend.identity
    backend.check_policy()
    managed.write_text('{"shell": "/bin/bash"}')
    assert backend.identity != before
    for tools in (True, False):
        with pytest.raises(backend_module.PolicyError, match="managed OpenCode configuration"):
            backend_module.OpenCodeBackend(tools=tools).generate("task", "evidence", Answer)
    monkeypatch.setattr(backend_module, "MANAGED_POLICY", {"opencode": ()})
    monkeypatch.setattr(backend_module, "bubblewrap_works", lambda: "bubblewrap is missing")
    with pytest.raises(backend_module.PolicyError, match="bubblewrap is missing"):
        backend_module.OpenCodeBackend().check_policy()
    backend_module.OpenCodeBackend(tools=False).check_policy()  # tool-free calls run no shell


@pytest.mark.skipif(not shutil.which("bwrap"), reason="needs bubblewrap")
def test_opencode_sandbox_shell_blocks_home_network_sockets_and_outside_writes(tmp_path, opencode_catalogue):
    """Runs the generated sandbox shell exactly as OpenCode does (`<shell> -c COMMAND`); no model call."""
    import socket
    import subprocess
    import tempfile

    from reviscope.backend import OpenCodeBackend, bubblewrap_works

    if bubblewrap_works():
        pytest.skip(bubblewrap_works())
    call = Path(tempfile.mkdtemp(prefix="reviscope-test-", dir="/tmp"))
    try:
        (call / "materials").mkdir()
        (call / "materials" / "data.csv").write_text("a\n1\n")
        backend = OpenCodeBackend()
        backend._prepare(call)
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(call / "host.sock"))
        server.listen()
        secret = Path.home() / ".reviscope-test-secret"
        checks = {
            "home": f"cat {secret}", "key": 'test -n "$OPENROUTER_API_KEY"', "outside": "touch /usr/local/reviscope-test",
            "materials": "touch materials/new", "network": "python3 -c 'import socket; socket.create_connection((\"1.1.1.1\", 443), timeout=3)'",
            "socket": "python3 -c 'import socket; s = socket.socket(socket.AF_UNIX); s.connect(\"host.sock\")'",
            "state": "find .opencode-state -mindepth 1 | grep -v -x -e .opencode-state/data -e .opencode-state/data/opencode -e '.opencode-state/data/opencode/tool-output.*'", "tmp": "test -e " + str(tmp_path)}
        script = "".join(f'if {command} >/dev/null 2>&1; then echo "{name} ALLOWED"; fi\n' for name, command in checks.items())
        (call / ".opencode-state" / "data" / "opencode" / "tool-output" / "tool_1").write_text("saved\n")
        checks["tool-output write"] = "touch .opencode-state/data/opencode/tool-output/new"
        script = "".join(f'if {command} >/dev/null 2>&1; then echo "{name} ALLOWED"; fi\n' for name, command in checks.items())
        script += 'cat .opencode-state/data/opencode/tool-output/tool_1 && echo written > here.txt && cat materials/data.csv'
        secret.write_text("secret")
        try:
            result = subprocess.run([str(call / ".opencode-state" / "sandbox-shell"), "-c", script], cwd=call, capture_output=True, text=True,
                                    env={**backend.environment(call), "OPENROUTER_API_KEY": "test-key"}, timeout=60)
        finally:
            secret.unlink()
            server.close()
        assert "ALLOWED" not in result.stdout, result.stdout + result.stderr
        assert result.stdout.strip() == "saved\na\n1" and (call / "here.txt").read_text() == "written\n"
    finally:
        import shutil

        shutil.rmtree(call, ignore_errors=True)


def test_cli_builds_opencode_backends_and_rejects_its_unsupported_options(tmp_path, capsys, opencode_catalogue):
    from reviscope.cli import _backend, main, parser

    args = parser().parse_args(["review", "paper.md", "--backend", "opencode", "--verifier-backend", "opencode"])
    backend = _backend(args.backend, args.model, args, args.effort)
    assert backend.name == "opencode" and backend.model == "openrouter/z-ai/glm-5.3-flash" and backend.tools
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("# Paper\n")
    assert main(["review", str(manuscript), "--backend", "opencode", "--shell-network", "--out", str(tmp_path / "out")]) == 1
    assert "shell-network" in capsys.readouterr().err and not (tmp_path / "out").exists()


def test_structured_output_skips_bracketed_prose_before_the_answer():
    from pydantic import BaseModel, ValidationError
    from reviscope.backend import _validate

    class Answer(BaseModel):
        decisions: list[str]

    output = 'The interval [0.312, 1.048] excludes zero.\n{"decisions": ["a"]}'
    assert _validate(Answer, output).decisions == ["a"]
    with pytest.raises(ValidationError, match="decisions"):
        _validate(Answer, 'See [1, 2]. {"choices": ["a"]}')  # the error describes the intended object


def test_catalogue_cannot_name_isolation_variables_as_credentials():
    from reviscope.backend import _credential_name

    assert _credential_name("OPENROUTER_API_KEY")
    for key in ("HOME", "PATH", "XDG_CONFIG_HOME", "OPENCODE_CONFIG_CONTENT", "LD_PRELOAD", "HTTPS_PROXY", "lower", 1):
        assert not _credential_name(key)


def test_effort_outside_the_shared_levels_is_left_to_opencode(capsys):
    from reviscope.cli import main

    assert main(["review", "paper.txt", "--backend", "codex", "--effort", "minimal"]) == 1
    assert "supports --effort low" in capsys.readouterr().err


@pytest.mark.parametrize("planted", ["file", "symlink"])
def test_only_codex_answers_through_the_output_file(tmp_path, monkeypatch, opencode_catalogue, planted):
    """The model's shell can write to the call directory, so a planted last-message.json (or a symlink to a
    file the sandbox hides) must not replace the answer that OpenCode printed."""
    from pydantic import BaseModel
    from reviscope import backend as backend_module

    class Answer(BaseModel):
        value: int

    secret = tmp_path / "secret.json"
    secret.write_text('{"value": 666}')
    monkeypatch.setattr(backend_module.OpenCodeBackend, "check_policy", lambda self: None)

    def execute(command, prompt, cwd, env, timeout):
        target = Path(cwd) / "last-message.json"
        target.symlink_to(secret) if planted == "symlink" else target.write_text('{"value": 666}')
        return 0, json.dumps({"type": "text", "part": {"text": '{"value": 1}'}}) + "\n", ""

    monkeypatch.setattr(backend_module, "_execute", execute)
    assert backend_module.OpenCodeBackend(tools=False).generate("Answer.", "", Answer).value == 1


def test_output_file_is_read_only_as_a_regular_file(tmp_path):
    from reviscope.backend import _read_regular_file

    (tmp_path / "secret").write_text("secret")
    (tmp_path / "link").symlink_to(tmp_path / "secret")
    os.mkfifo(tmp_path / "fifo")
    assert _read_regular_file(tmp_path / "secret") == "secret"
    assert _read_regular_file(tmp_path / "link") is None
    assert _read_regular_file(tmp_path / "fifo") is None
    assert _read_regular_file(tmp_path / "missing") is None
