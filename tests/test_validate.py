"""AST validator: it must let clean strategies through and block escape hatches."""
import pytest

from bhav.ai.validate import ValidationError, check_strategy_source, validate_strategy_source

CLEAN = """\
from bhav.engine.strategy import Context, Strategy


class MyStrat(Strategy):
    name = "clean"

    def on_bar(self, ctx: Context) -> None:
        ctx.buy_option(option_type="CE")


strategy = MyStrat()
"""


def test_clean_strategy_passes():
    assert check_strategy_source(CLEAN) == []
    validate_strategy_source(CLEAN)  # does not raise


@pytest.mark.parametrize(
    "snippet",
    [
        "import os",
        "import subprocess",
        "import socket",
        "from os import system",
        "import requests",
        "import httpx",
        "from pathlib import Path",
    ],
)
def test_forbidden_imports_flagged(snippet):
    src = snippet + "\nstrategy = 1\n"
    assert check_strategy_source(src), f"{snippet!r} should be rejected"


@pytest.mark.parametrize(
    "snippet",
    [
        "eval('1')",
        "exec('x=1')",
        "open('/etc/passwd')",
        "__import__('os')",
        "compile('1', '<s>', 'eval')",
    ],
)
def test_forbidden_calls_flagged(snippet):
    src = "strategy = 1\n" + snippet + "\n"
    assert check_strategy_source(src), f"{snippet!r} should be rejected"


def test_dunder_escape_flagged():
    src = "strategy = 1\nx = ().__class__.__bases__\n"
    violations = check_strategy_source(src)
    assert any("__class__" in v or "__bases__" in v for v in violations)


def test_missing_strategy_variable_flagged():
    src = "from bhav.engine.strategy import Strategy\nclass S(Strategy):\n    pass\n"
    violations = check_strategy_source(src)
    assert any("strategy" in v for v in violations)


def test_syntax_error_reported():
    violations = check_strategy_source("def broken(:\n")
    assert len(violations) == 1
    assert "syntax error" in violations[0]


def test_validate_raises_with_all_violations():
    with pytest.raises(ValidationError) as exc:
        validate_strategy_source("import os\nimport socket\n")
    assert len(exc.value.violations) >= 2
