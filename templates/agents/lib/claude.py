"""
Thin wrapper around the Anthropic SDK used by every agent.

Rationale: every agent loads the same two mandatory system-prompt
fragments (editorial + voice) and adds a role-specific one. We centralise
that here so a model/temperature/change propagates everywhere.
"""
from __future__ import annotations

import os
from typing import Iterable

from anthropic import Anthropic

from .config import read_prompt, require


# Default models. Override via env vars if needed.
MODEL_DRAFT = os.environ.get("CLAUDE_MODEL_DRAFT", "claude-opus-4-7")
MODEL_FACTCHECK = os.environ.get("CLAUDE_MODEL_FACTCHECK", "claude-sonnet-4-6")


def _client() -> Anthropic:
    return Anthropic(api_key=require("ANTHROPIC_API_KEY"))


def build_system(role_prompt_names: Iterable[str]) -> str:
    """
    Concatenate the editorial + voice rules + one or more role-specific
    prompt fragments into a single system prompt.
    """
    parts: list[str] = []
    parts.append(read_prompt("editorial_rules"))
    parts.append("---")
    parts.append(read_prompt("voice_rules"))
    for name in role_prompt_names:
        parts.append("---")
        parts.append(read_prompt(name))
    return "\n\n".join(parts)


def generate(
    *,
    system: str,
    user: str,
    max_tokens: int = 8000,
    model: str = MODEL_DRAFT,
) -> str:
    """Single-turn text generation. Returns the model's text output.

    Temperature is intentionally not passed. Opus 4.7 deprecates the
    parameter; using defaults gives consistent output without trade-offs.
    """
    resp = _client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    blocks = [b for b in resp.content if getattr(b, "type", None) == "text"]
    if not blocks:
        raise RuntimeError(f"Claude returned no text blocks: {resp}")
    return "\n".join(b.text for b in blocks)
