"""
Project-wide paths and client config loader.

Every agent imports from here so there's a single source of truth for
where things live on disk.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Directory layout
AGENTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = AGENTS_DIR.parent
SITE_DIR = PROJECT_ROOT / "03-site"
ARTICLES_DIR = SITE_DIR / "src" / "content" / "articles"
BRIEFS_DIR = AGENTS_DIR / "briefs"
PROMPTS_DIR = AGENTS_DIR / "prompts"
STATE_DIR = AGENTS_DIR / "state"
LOGS_DIR = AGENTS_DIR / "logs"
CLIENTS_DIR = SITE_DIR / "clients"

for d in (STATE_DIR, LOGS_DIR, BRIEFS_DIR):
    d.mkdir(exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")


def read_prompt(name: str) -> str:
    """Load a system-prompt fragment from prompts/<name>.md."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def client_config(slug: str | None = None) -> dict[str, Any]:
    """Load clients/<slug>.yaml. Slug defaults to the CLIENT_SLUG env var."""
    slug = slug or os.environ.get("CLIENT_SLUG", "{{SLUG}}")
    path = CLIENTS_DIR / f"{slug}.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def kill_switch_engaged() -> bool:
    """
    Returns True if AGENTS_ENABLED is explicitly set to "false".
    Default behaviour (unset) is to RUN — but the GH Actions workflows
    pass the variable explicitly so this only matters locally.
    """
    val = os.environ.get("AGENTS_ENABLED", "true").strip().lower()
    return val in {"false", "0", "no", "off"}


def require(var: str) -> str:
    v = os.environ.get(var)
    if not v:
        raise RuntimeError(f"Missing required env var: {var}")
    return v
