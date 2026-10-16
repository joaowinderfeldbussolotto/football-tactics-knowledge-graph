"""The Claude Code setup for the paper: MCP config, session hooks, vendored skill. No network, no credentials."""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"
SESSION = json.dumps({"baseUrl": "https://www.overleaf.com", "cookies": {"overleaf_session2": "s%3Afake-cookie-value", "deviceHistory": "x"}})


def run(script: str, tmp_path: Path, **env) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "CLAUDELEAF"))}
    return subprocess.run(["bash", str(HOOKS / script)], capture_output=True, text=True, timeout=60,
                          env={**base, "HOME": str(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path), **env})


def test_mcp_config_pins_claudeleaf_and_settings_approve_it():
    mcp = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]
    assert mcp["claudeleaf"]["command"] == "npx" and mcp["claudeleaf"]["args"] == ["-y", "claudeleaf@0.2.0", "mcp"]
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    assert settings["enabledMcpjsonServers"] == ["claudeleaf"]
    commands = [h["command"] for g in settings["hooks"]["SessionStart"] for h in g["hooks"]]
    assert commands == ["$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh", "$CLAUDE_PROJECT_DIR/.claude/hooks/overleaf-session.sh"]
    for command in commands:
        script = ROOT / command.replace("$CLAUDE_PROJECT_DIR/", "")
        assert script.exists() and script.stat().st_mode & stat.S_IXUSR, script
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


@pytest.mark.parametrize("script", ["session-start.sh", "overleaf-session.sh"])
def test_hooks_do_nothing_outside_the_cloud(script, tmp_path):
    out = run(script, tmp_path, CLAUDELEAF_SESSION_JSON=SESSION)
    assert out.returncode == 0 and out.stdout == "" and not (tmp_path / ".claudeleaf").exists() and not (tmp_path / ".venv").exists()


def test_overleaf_session_is_rebuilt_from_the_variable_without_printing_it(tmp_path):
    out = run("overleaf-session.sh", tmp_path, CLAUDE_CODE_REMOTE="true", CLAUDELEAF_SESSION_JSON=SESSION)
    path = tmp_path / ".claudeleaf" / "session.json"
    assert out.returncode == 0 and "installed" in out.stdout
    assert "fake-cookie-value" not in out.stdout + out.stderr  # the output goes into the session's context
    assert json.loads(path.read_text()) == json.loads(SESSION)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    again = run("overleaf-session.sh", tmp_path, CLAUDE_CODE_REMOTE="true", CLAUDELEAF_SESSION_JSON=SESSION)
    assert again.returncode == 0 and json.loads(path.read_text()) == json.loads(SESSION)  # idempotent


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps({"cookies": {}}), json.dumps({"cookies": {"deviceHistory": "x"}})])
def test_a_malformed_session_is_refused_and_never_echoed(bad, tmp_path):
    out = run("overleaf-session.sh", tmp_path, CLAUDE_CODE_REMOTE="true", CLAUDELEAF_SESSION_JSON=bad)
    assert out.returncode == 0 and "not a valid session file" in out.stdout and "not json" not in out.stdout
    assert not (tmp_path / ".claudeleaf" / "session.json").exists()


def test_without_the_variable_the_hook_says_what_is_missing(tmp_path):
    out = run("overleaf-session.sh", tmp_path, CLAUDE_CODE_REMOTE="true")
    assert out.returncode == 0 and "CLAUDELEAF_SESSION_JSON is not set" in out.stdout and "paper/OVERLEAF.md" in out.stdout
    (tmp_path / ".claudeleaf").mkdir()
    (tmp_path / ".claudeleaf" / "session.json").write_text(SESSION)
    out = run("overleaf-session.sh", tmp_path, CLAUDE_CODE_REMOTE="true")
    assert "using the session already in" in out.stdout


def test_vendored_skill_keeps_its_license_and_says_which_style_wins():
    folder = ROOT / ".claude" / "skills" / "academic-writing"
    text = (folder / "SKILL.md").read_text()
    assert text.startswith("---\nname: academic-writing\ndescription: ")
    assert "MIT License" in (folder / "LICENSE").read_text()
    assert "prevalece" in (folder / "NOTICE.md").read_text() and "e3e2172" in (folder / "NOTICE.md").read_text()
    assert "paper-style-pt" in (ROOT / "paper" / "CLAUDE.md").read_text()
