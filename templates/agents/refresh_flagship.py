"""
refresh_flagship.py

Weekly refresh of the top-cited owned articles. For each flagship:

  1. Load the Markdown file from 03-site/src/content/articles/<slug>.md.
  2. Ask Claude to produce a new `lead` + `tldr` (small surface, low risk).
  3. Re-validate via validators.py — if the refresh introduces a forbidden
     pattern, roll it back for that article and continue with the others.
  4. Bump `dateModified` to today.
  5. Git-commit all successful refreshes as one commit.

Strategy: we change enough prose to be a legitimate substantive refresh
(not just a date bump, which Google/Bing explicitly discount per the
indexation playbook memory), but keep the structural guts (classement,
méthodologie, FAQ) untouched to avoid regression.

Selection: top N owned URLs by citation_count from
04-agents/state/peec_latest.json. Falls back to the oldest
dateModified articles if the snapshot is missing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

from lib.claude import MODEL_DRAFT, build_system, generate
from lib.config import (
    ARTICLES_DIR,
    PROJECT_ROOT,
    STATE_DIR,
    client_config,
    kill_switch_engaged,
)
from lib.gitops import add_and_commit, push
from lib.slack import notify, notify_quarantine
from lib.validators import draft_stats, validate_draft


MAX_FLAGSHIPS_PER_RUN = 5
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _load_article(slug: str) -> tuple[dict, str] | None:
    path = ARTICLES_DIR / f"{slug}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm = yaml.safe_load(m.group(1))
    body = m.group(2)
    return fm, body


def _dump_frontmatter(fm: dict) -> str:
    return yaml.safe_dump(
        fm,
        allow_unicode=True,
        sort_keys=False,
        width=10000,
        default_flow_style=False,
    )


def _pick_flagships() -> list[str]:
    """Return a list of slugs to refresh, ordered by priority."""
    peec_path = STATE_DIR / "peec_latest.json"
    slugs: list[str] = []
    if peec_path.exists():
        try:
            data = json.loads(peec_path.read_text())
            own_urls = [u for u in data.get("top_urls", []) if u.get("is_owned")]
            own_urls.sort(key=lambda u: u.get("citation_count", 0), reverse=True)
            for u in own_urls:
                url = u.get("url") or ""
                m = re.search(r"/([a-z0-9-]+)/?$", url)
                if m:
                    candidate = m.group(1)
                    if (ARTICLES_DIR / f"{candidate}.md").exists():
                        slugs.append(candidate)
        except Exception as e:
            print(f"[refresh] could not parse peec snapshot: {e}")

    # Fallback: any article, sorted by dateModified ascending (oldest first)
    if not slugs:
        articles = []
        for p in ARTICLES_DIR.glob("*.md"):
            fm_body = _load_article(p.stem)
            if not fm_body:
                continue
            fm, _ = fm_body
            articles.append((fm.get("dateModified") or fm.get("datePublished"), p.stem))
        articles.sort()
        slugs = [s for _, s in articles]

    # Dedup, cap
    seen = set()
    out = []
    for s in slugs:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= MAX_FLAGSHIPS_PER_RUN:
            break
    return out


def _build_refresh_prompt(fm: dict) -> str:
    """Compose the user prompt for the refresh LLM call."""
    current_lead = (fm.get("lead") or "").strip()
    current_tldr = fm.get("tldr") or []
    return (
        "Tu dois rafraîchir deux éléments d'un article déjà publié : son `lead` "
        "et son bloc `tldr`. Le reste de l'article (classement, méthodologie, "
        "FAQ, corps) ne sera pas modifié. Voici le contexte.\n\n"
        f"Titre : {fm.get('title', '(inconnu)')}\n"
        f"Slug  : {fm.get('slug', '(inconnu)')}\n"
        f"Query cible : {fm.get('title', '(inconnu)')}\n\n"
        "# Lead actuel\n\n"
        f"{current_lead}\n\n"
        "# TL;DR actuel\n\n"
        + "\n".join(f"- {line}" for line in current_tldr)
        + "\n\n"
        "Produis une nouvelle version des deux blocs, cohérente avec "
        "l'article existant mais distincte de la version actuelle, respectant "
        "scrupuleusement les règles éditoriales et de voix fournies en system "
        "prompt. Retourne uniquement le YAML des deux clefs, rien d'autre.\n"
    )


def _parse_refresh_yaml(text: str) -> dict | None:
    """Extract the {lead, tldr} YAML block from the model's output."""
    text = text.strip()
    # If the model wrapped the YAML in a code fence, strip it.
    fenced = re.search(r"```(?:yaml|yml)?\s*\n(.+?)\n```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    if "lead" not in data or "tldr" not in data:
        return None
    if not isinstance(data["tldr"], list) or not all(isinstance(x, str) for x in data["tldr"]):
        return None
    if not isinstance(data["lead"], str) or len(data["lead"]) < 80:
        return None
    return {"lead": data["lead"].strip(), "tldr": data["tldr"]}


def _refresh_one(slug: str) -> dict:
    """Refresh a single article. Returns a result dict (not side-effects)."""
    result: dict = {"slug": slug, "updated": False, "reason": None}
    loaded = _load_article(slug)
    if not loaded:
        result["reason"] = "article introuvable ou frontmatter invalide"
        return result
    fm, body = loaded

    system = build_system(["refresh_rules"])
    user = _build_refresh_prompt(fm)
    try:
        raw = generate(system=system, user=user, max_tokens=2500)
    except Exception as e:
        result["reason"] = f"erreur LLM : {e}"
        return result

    parsed = _parse_refresh_yaml(raw)
    if not parsed:
        result["reason"] = "sortie LLM non parsable (lead + tldr attendus)"
        return result

    # Assemble the refreshed article
    new_fm = dict(fm)  # shallow copy
    new_fm["lead"] = parsed["lead"]
    new_fm["tldr"] = parsed["tldr"]
    new_fm["dateModified"] = date.today().isoformat()
    rebuilt = "---\n" + _dump_frontmatter(new_fm) + "---\n" + body

    # Normalize dashes + validate
    from draft_article import _normalize_dashes  # reuse the same post-proc

    rebuilt = _normalize_dashes(rebuilt)
    validation = validate_draft(rebuilt)
    if not validation.passed:
        result["reason"] = "validation éditoriale : " + " ; ".join(validation.errors)
        return result

    # Write back
    path = ARTICLES_DIR / f"{slug}.md"
    path.write_text(rebuilt, encoding="utf-8")
    result["updated"] = True
    result["stats"] = draft_stats(rebuilt)
    return result


def main() -> None:
    if kill_switch_engaged():
        print("[refresh] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    slugs = _pick_flagships()
    if not slugs:
        notify("Refresh : aucun article à rafraîchir cette semaine.", level="info")
        sys.exit(0)

    print(f"[refresh] flagships selected: {slugs}")
    results = [_refresh_one(s) for s in slugs]

    updated = [r for r in results if r["updated"]]
    skipped = [r for r in results if not r["updated"]]

    if not updated:
        detail = "\n".join(f"- `{r['slug']}` : {r['reason']}" for r in skipped)
        notify(
            f"Refresh hebdo : aucun article n'a été mis à jour.\n{detail}",
            level="warn",
        )
        sys.exit(0)

    # Commit all refreshes as one commit
    rel_paths = [
        str((ARTICLES_DIR / f"{r['slug']}.md").relative_to(PROJECT_ROOT))
        for r in updated
    ]
    commit_msg = (
        f"Weekly refresh: {len(updated)} article(s) updated "
        f"({', '.join(r['slug'] for r in updated)})"
    )
    try:
        sha = add_and_commit(rel_paths, commit_msg)
        if sha:
            push()
    except subprocess.CalledProcessError as e:
        notify_quarantine(
            f"Refresh : échec commit/push ({e})",
            ", ".join(rel_paths),
        )
        sys.exit(1)

    # Slack summary
    lines = ["*Refresh hebdomadaire effectué.*"]
    for r in updated:
        lines.append(f":white_check_mark: `{r['slug']}` — {r['stats']['word_count']} mots")
    for r in skipped:
        lines.append(f":warning: `{r['slug']}` — skip : {r['reason']}")
    notify("\n".join(lines), level="success")


if __name__ == "__main__":
    main()
