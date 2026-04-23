#!/usr/bin/env python3
"""
Sanitize the templates/ tree: replace every client-specific string
inherited from the Uncode project with {{PLACEHOLDER}} tokens.

Run once when the templates are first copied from a seed project.
Not invoked at bootstrap time (bootstrap uses instantiate.py which does
the reverse substitution).

This script is idempotent: running it twice is a no-op.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"

# Order matters: longer strings first so we don't corrupt partial matches
REPLACEMENTS: list[tuple[str, str]] = [
    # URLs first (longer tokens)
    ("https://www.uncodeschool.com", "{{PROMOTED_BRAND_URL}}"),
    ("https://formations-nocode.rank-ly.com", "https://{{FQDN}}"),
    ("formations-nocode.rank-ly.com", "{{FQDN}}"),
    ("www.uncodeschool.com", "{{PROMOTED_BRAND_DOMAIN}}"),
    ("uncodeschool.com", "{{PROMOTED_BRAND_DOMAIN}}"),
    # GitHub + Cloudflare project names
    ("formations-nocode-rank-ly", "{{GH_REPO}}"),
    ("EdouardBrault/formations-nocode-rank-ly", "{{GH_OWNER}}/{{GH_REPO}}"),
    ("EdouardBrault", "{{GH_OWNER}}"),
    # Wikidata + IndexNow
    ("Q139503864", "{{WIKIDATA_QID}}"),
    ("b9d8c6ee959771898c405f9caa05462c", "{{INDEXNOW_KEY}}"),
    # Slack channel
    ("#rank-ly-uncode", "#{{SLACK_CHANNEL_NAME}}"),
    ("rank-ly-uncode", "{{SLACK_CHANNEL_NAME}}"),
    # Display strings
    ("Uncode School", "{{PROMOTED_BRAND_NAME}}"),
    ("Cartesia", "{{CLIENT_DISPLAY_NAME}}"),
    ("Formations No-Code", "{{SITE_NAME}}"),
    # Contact
    ("edouard@archipelmarketing.com", "{{CONTACT_EMAIL}}"),
    # Generic slug (careful: 'uncode' can match substrings — we apply
    # word-boundary sensitive handling below)
]

# Extensions to process (text files only)
TEXT_EXTS = {
    ".md", ".astro", ".ts", ".tsx", ".js", ".mjs", ".cjs",
    ".yaml", ".yml", ".json", ".html", ".css", ".txt",
    ".py", ".sh", ".toml", ".env", ".template",
}


def should_process(path: Path) -> bool:
    if path.name.startswith("."):
        # Skip dotfiles except a few we care about
        if path.name not in (".gitignore.template", ".env.example"):
            return False
    if path.is_dir():
        return False
    if path.suffix in TEXT_EXTS:
        return True
    # Extension-less files that are known text? Only robots.txt etc., covered.
    return False


def sanitize_file(path: Path) -> int:
    content = path.read_text(encoding="utf-8", errors="replace")
    original = content
    changed = 0
    # Simple substring replacements first
    for orig, token in REPLACEMENTS:
        new = content.replace(orig, token)
        if new != content:
            changed += content.count(orig)
            content = new

    # Handle the bare "uncode" slug with word boundaries ONLY.
    # We don't want to replace substrings like "uncodedvalue" etc.
    # The slug appears in: filenames, YAML slug fields, import paths.
    def replace_slug(match: re.Match[str]) -> str:
        return "{{SLUG}}"

    # Pattern: 'uncode' bordered by non-word chars or start/end of file
    pattern = re.compile(r"\buncode\b")
    new = pattern.sub(replace_slug, content)
    if new != content:
        changed += len(pattern.findall(content))
        content = new

    if content != original:
        path.write_text(content, encoding="utf-8")
    return changed


def rename_slug_filenames(root: Path) -> int:
    """If a filename contains 'uncode', rename it to use {{SLUG}}."""
    renamed = 0
    for p in list(root.rglob("*")):
        if p.is_dir():
            continue
        if "uncode" in p.name:
            new_name = p.name.replace("uncode", "{{SLUG}}")
            p.rename(p.with_name(new_name))
            renamed += 1
    return renamed


def main() -> None:
    if not TEMPLATES.exists():
        raise SystemExit(f"Templates dir not found: {TEMPLATES}")

    total = 0
    processed = 0
    for path in TEMPLATES.rglob("*"):
        if not should_process(path):
            continue
        processed += 1
        changes = sanitize_file(path)
        if changes:
            total += changes
            print(f"  edited: {path.relative_to(TEMPLATES)} ({changes} replacement{'s' if changes > 1 else ''})")

    renamed = rename_slug_filenames(TEMPLATES)
    if renamed:
        print(f"\n  renamed {renamed} file(s) containing the slug")

    print(f"\nDone. {processed} files scanned, {total} client-specific strings tokenised.")


if __name__ == "__main__":
    main()
