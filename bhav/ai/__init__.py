"""AI-assisted strategy generation.

Turns plain-English descriptions into Bhav strategy files by shelling out to the
locally installed `claude` CLI (no API key required). Every generated file is run
through the same AST validator (`bhav.ai.validate`) that guards uploaded strategies.
"""
from bhav.ai.claude_generator import (
    ClaudeNotFoundError,
    GenerationError,
    GenerationResult,
    claude_available,
    generate_strategy,
)
from bhav.ai.prompt import build_prompt
from bhav.ai.validate import ValidationError, validate_strategy_source

__all__ = [
    "ClaudeNotFoundError",
    "GenerationError",
    "GenerationResult",
    "ValidationError",
    "build_prompt",
    "claude_available",
    "generate_strategy",
    "validate_strategy_source",
]
