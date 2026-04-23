"""
Git operations for the publish step.

In GitHub Actions the runner is already authenticated via GITHUB_TOKEN.
Locally we rely on the gh CLI credential helper that we set up earlier.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import PROJECT_ROOT


def run(cmd: list[str], *, cwd: Path | None = None) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def configure_identity_if_missing() -> None:
    """CI runners need a git identity before committing."""
    try:
        run(["git", "config", "user.email"])
    except subprocess.CalledProcessError:
        run(["git", "config", "user.email", "agents@archipelmarketing.com"])
        run(["git", "config", "user.name", "Archipel Agent"])


def add_and_commit(paths: list[str], message: str) -> str:
    """Stage the given paths and create a commit. Returns the new commit sha."""
    configure_identity_if_missing()
    run(["git", "add", *paths])
    # If nothing changed, don't fail loudly.
    status = run(["git", "status", "--porcelain"])
    if not status:
        return ""
    run(["git", "commit", "-m", message])
    return run(["git", "rev-parse", "HEAD"])


def push(remote: str = "origin", branch: str = "main") -> None:
    run(["git", "push", remote, branch])
