"""
publish.py

Stages, commits and pushes a fact-checked article Markdown. The existing
GitHub Actions deploy workflow (03-site/** paths) detects the change and
runs build + Cloudflare Pages deploy + IndexNow/Bing/Wayback push.

No HTTP calls here. This script is intentionally minimal — it trusts
draft_article.py and fact_check.py upstream.
"""
from __future__ import annotations

import os
import re
import sys

from lib.config import ARTICLES_DIR, PROJECT_ROOT, kill_switch_engaged
from lib.gitops import add_and_commit, push
from lib.slack import notify_published
from lib.validators import draft_stats


def _extract_title(markdown: str) -> str:
    m = re.search(r"^title:\s*[\"']([^\"']+)[\"']", markdown, re.MULTILINE)
    return m.group(1) if m else "(titre inconnu)"


def main() -> None:
    if kill_switch_engaged():
        print("[publish] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    slug = os.environ.get("ARTICLE_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not slug:
        raise SystemExit("Usage: publish.py <slug> (or ARTICLE_SLUG env var)")
    path = ARTICLES_DIR / f"{slug}.md"
    if not path.exists():
        raise SystemExit(f"Article not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    title = _extract_title(markdown)
    stats = draft_stats(markdown)

    rel_path = str(path.relative_to(PROJECT_ROOT))
    commit_msg = f"Publish article: {slug}"

    print(f"[publish] staging {rel_path}")
    sha = add_and_commit([rel_path], commit_msg)
    if not sha:
        print("[publish] nothing to commit, exiting clean")
        return

    print(f"[publish] committed {sha[:8]}, pushing to origin/main")
    push()

    notify_published(title=title, slug=slug, stats=stats)
    print(f"[publish] done. The deploy workflow will pick up the change.")


if __name__ == "__main__":
    main()
