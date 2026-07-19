"""Generate strategy files by shelling out to the local `claude` CLI.

This is the "no API key" path: instead of calling the Anthropic API with a key,
we drive the Claude Code CLI that the user already has authenticated on their
machine. We run it in headless print mode (`claude -p`), feed it the Bhav strategy
contract plus the user's plain-English idea over stdin, and parse a single Python
file back out.

    from bhav.ai import generate_strategy
    result = generate_strategy("sell an ATM straddle at 09:20, 30% SL on premium")
    print(result.code)

The returned code is passed through `bhav.ai.validate` so a hallucinated `import
os` is caught before anything is written to disk or executed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from bhav.ai.prompt import build_prompt
from bhav.ai.validate import check_strategy_source

DEFAULT_TIMEOUT = 180  # seconds; a cold CLI call can take a while
_CLI_CANDIDATES = ("claude",)

_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)
_NAME_RE = re.compile(r"""^\s*name\s*=\s*["']([^"']+)["']""", re.MULTILINE)
_CODE_START_RE = re.compile(
    r"^(from\s+bhav|import\s+|from\s+__future__|class\s+|\"\"\")", re.MULTILINE
)


class GenerationError(RuntimeError):
    """The CLI ran but did not yield a usable strategy (empty/garbled output)."""


class ClaudeNotFoundError(GenerationError):
    """The `claude` CLI is not installed or not on PATH."""


@dataclass
class GenerationResult:
    code: str
    name: str | None = None
    violations: list[str] = field(default_factory=list)
    raw: str = ""
    model: str | None = None

    @property
    def ok(self) -> bool:
        """True when the generated code passed the AST validator."""
        return not self.violations


def claude_binary() -> str | None:
    """Absolute path to the `claude` CLI, or None if it is not on PATH.

    `shutil.which` honours PATHEXT on Windows, so this also finds `claude.cmd`.
    """
    for name in _CLI_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def claude_available() -> bool:
    return claude_binary() is not None


def _extract_code(output: str) -> str:
    """Pull the Python file out of the CLI's response.

    Handles three shapes the model tends to return: a ```python fenced block,
    a bare fenced block, or raw code with a stray line of prose in front.
    """
    text = output.strip()
    if not text:
        return ""
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()
    # No fence: drop any leading prose before the first real line of Python.
    start = _CODE_START_RE.search(text)
    if start:
        return text[start.start() :].strip()
    return text


def generate_strategy(
    description: str,
    *,
    model: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    binary: str | None = None,
) -> GenerationResult:
    """Turn a plain-English `description` into a validated strategy file.

    Raises ClaudeNotFoundError if the CLI is missing, GenerationError if the CLI
    fails or returns nothing parseable. A result whose `.violations` is non-empty
    means the code came back but failed static validation — inspect before running.
    """
    prompt = build_prompt(description)  # raises ValueError on empty description

    exe = binary or claude_binary()
    if exe is None:
        raise ClaudeNotFoundError(
            "the `claude` CLI was not found on PATH. Install Claude Code "
            "(https://claude.com/claude-code) and run `claude` once to sign in, "
            "then retry. No ANTHROPIC_API_KEY is required."
        )

    cmd = [exe, "-p"]
    if model:
        cmd += ["--model", model]

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired as e:
        raise GenerationError(
            f"claude CLI timed out after {timeout}s. Try a simpler description "
            f"or raise the timeout."
        ) from e
    except OSError as e:
        raise GenerationError(f"failed to launch claude CLI: {e}") from e

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise GenerationError(
            f"claude CLI exited with code {proc.returncode}: {detail[:500]}"
        )

    code = _extract_code(proc.stdout)
    if not code:
        raise GenerationError(
            "claude CLI returned no code. Raw output:\n" + proc.stdout[:500]
        )

    name_match = _NAME_RE.search(code)
    return GenerationResult(
        code=code,
        name=name_match.group(1) if name_match else None,
        violations=check_strategy_source(code),
        raw=proc.stdout,
        model=model,
    )
