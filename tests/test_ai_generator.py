"""Claude CLI generator: prompt assembly, code extraction, and subprocess wiring.

The actual `claude` CLI is never invoked here — we monkeypatch subprocess.run so
the tests are hermetic and do not depend on a signed-in CLI.
"""
import subprocess

import pytest

from bhav.ai import claude_generator
from bhav.ai.claude_generator import (
    ClaudeNotFoundError,
    GenerationError,
    _extract_code,
    generate_strategy,
)
from bhav.ai.prompt import build_prompt

VALID_CODE = """\
from bhav.engine.strategy import Context, Strategy


class Gen(Strategy):
    name = "gen_v1"

    def on_bar(self, ctx: Context) -> None:
        ctx.buy_option(option_type="CE")


strategy = Gen()
"""


def test_build_prompt_includes_description():
    p = build_prompt("sell an ATM straddle at 09:20")
    assert "sell an ATM straddle at 09:20" in p
    assert "=== CONTRACT ===" in p


def test_build_prompt_rejects_empty():
    with pytest.raises(ValueError):
        build_prompt("   ")


def test_extract_code_from_python_fence():
    out = "Here you go:\n```python\n" + VALID_CODE + "```\nDone."
    assert _extract_code(out).startswith("from bhav.engine.strategy")


def test_extract_code_from_bare_fence():
    out = "```\n" + VALID_CODE + "```"
    assert "strategy = Gen()" in _extract_code(out)


def test_extract_code_from_raw_with_prose_prefix():
    out = "Sure, here is the file:\n" + VALID_CODE
    assert _extract_code(out).startswith("from bhav.engine.strategy")


def _fake_run(stdout="", returncode=0, stderr=""):
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return _run


def test_generate_success(monkeypatch):
    monkeypatch.setattr(claude_generator, "claude_binary", lambda: "/usr/bin/claude")
    monkeypatch.setattr(
        claude_generator.subprocess,
        "run",
        _fake_run(stdout="```python\n" + VALID_CODE + "```"),
    )
    result = generate_strategy("buy an ATM call at 09:30")
    assert result.ok
    assert result.name == "gen_v1"
    assert "strategy = Gen()" in result.code


def test_generate_flags_unsafe_code(monkeypatch):
    unsafe = "import os\nstrategy = os\n"
    monkeypatch.setattr(claude_generator, "claude_binary", lambda: "/usr/bin/claude")
    monkeypatch.setattr(
        claude_generator.subprocess, "run", _fake_run(stdout=unsafe)
    )
    result = generate_strategy("do something sketchy")
    assert not result.ok
    assert result.violations


def test_generate_raises_when_cli_missing(monkeypatch):
    monkeypatch.setattr(claude_generator, "claude_binary", lambda: None)
    with pytest.raises(ClaudeNotFoundError):
        generate_strategy("anything")


def test_generate_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(claude_generator, "claude_binary", lambda: "/usr/bin/claude")
    monkeypatch.setattr(
        claude_generator.subprocess,
        "run",
        _fake_run(returncode=1, stderr="not signed in"),
    )
    with pytest.raises(GenerationError, match="not signed in"):
        generate_strategy("anything")


def test_generate_raises_on_empty_output(monkeypatch):
    monkeypatch.setattr(claude_generator, "claude_binary", lambda: "/usr/bin/claude")
    monkeypatch.setattr(claude_generator.subprocess, "run", _fake_run(stdout="   "))
    with pytest.raises(GenerationError):
        generate_strategy("anything")
