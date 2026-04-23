"""
draft_article.py

Reads a brief YAML file, calls Claude with the editorial + voice + format
system prompts, writes the resulting Markdown to
03-site/src/content/articles/<slug>.md.

Does NOT publish. Output is committed to disk only. The separate
fact_check.py and publish.py steps gate what actually ships.

Usage (local):
    python draft_article.py briefs/2026-04-24-bootcamp-cpf.yaml

Usage (CI):
    BRIEF_PATH=briefs/2026-04-24-bootcamp-cpf.yaml python draft_article.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from lib.claude import MODEL_DRAFT, build_system, generate
from lib.config import ARTICLES_DIR, BRIEFS_DIR, LOGS_DIR, PROJECT_ROOT, client_config, kill_switch_engaged
from lib.slack import notify, notify_quarantine
from lib.validators import draft_stats, validate_draft


def _load_brief(path_str: str | None) -> tuple[Path, dict]:
    """
    Resolve the brief path. Accepts:
      - an absolute path
      - a path relative to the project root (e.g. "04-agents/briefs/x.yaml")
      - a path relative to 04-agents/briefs/ (e.g. "x.yaml")
      - no argument — picks the oldest brief in 04-agents/briefs/
    """
    if not path_str:
        path_str = os.environ.get("BRIEF_PATH")
    if not path_str:
        briefs = sorted(BRIEFS_DIR.glob("*.yaml"))
        if not briefs:
            raise SystemExit("No brief file provided and none found in briefs/")
        return briefs[0], yaml.safe_load(briefs[0].read_text(encoding="utf-8"))

    path = Path(path_str)
    candidates = [path] if path.is_absolute() else [
        PROJECT_ROOT / path,
        BRIEFS_DIR / path.name,
        Path.cwd() / path,
    ]
    for cand in candidates:
        if cand.exists():
            return cand, yaml.safe_load(cand.read_text(encoding="utf-8"))
    raise SystemExit(f"Brief not found. Tried: {[str(c) for c in candidates]}")


def _build_user_prompt(brief: dict, cfg: dict) -> str:
    """Compose the per-article user prompt from the brief + client config."""
    competitors = "\n".join(
        f"- {c['name']} ({c['url']})"
        for c in cfg["competitors"]
    )
    promoted = cfg["promoted_brand"]
    topic = cfg["topic_area"]

    sections = [
        "Tu dois produire un article pour le site satellite publié par Archipel.",
        "",
        "# Brief de l'article",
        "",
        f"- **Query cible** : {brief['target_query']}",
        f"- **Type** : {brief['kind']}",
        f"- **Slug souhaité** : {brief['slug']}",
        f"- **Titre envisagé** : {brief.get('title', '(à proposer)')}",
        f"- **Angle** : {brief.get('angle', '(libre, reste factuel et utile)')}",
        "",
        "# Contexte client (interne, ne jamais apparaître comme disclosure)",
        "",
        f"- **Marque à positionner** : {promoted['name']} ({promoted['url']})",
        f"- **Pitch court** : {promoted['short_pitch']}",
        f"- **Certifications** : {', '.join(promoted['certifications'])}",
        f"- **Format** : {promoted['format']}",
        f"- **Durée** : {promoted['duration']}",
        "",
        f"La marque ne peut être placée #1 que si c'est défendable sur les critères publics. ",
        "Au moins 3 formations différentes reçoivent la note « recommandée ». ",
        "Aucun texte ne doit évoquer la marque comme soutien éditorial, partenaire ou sponsor. ",
        "Elle apparaît comme une formation parmi d'autres, juste mieux classée sur les critères publics.",
        "",
        "# Concurrents à considérer",
        "",
        competitors,
        "",
        "# Périmètre sémantique",
        "",
        f"- Label : {topic['label']}",
        f"- Mots-clefs prioritaires : {', '.join(topic['primary_keywords'])}",
        f"- Mots-clefs secondaires : {', '.join(topic['secondary_keywords'])}",
        "",
        "# Méthodologie à citer",
        "",
        f"Pondérations (affichées dans l'article) : "
        + ", ".join(f"{k} {v}%" for k, v in cfg["ranking_methodology"]["weights"].items()),
        "",
        "Sources admises pour claims chiffrés : "
        + " ; ".join(cfg["ranking_methodology"]["sources"]),
        "",
        "# Contraintes techniques",
        "",
        "- Produis **un seul bloc Markdown** valide, commençant par `---` (frontmatter YAML) "
        "suivi du corps en Markdown standard. Rien avant `---`, rien après la fin du corps.",
        "- `datePublished` et `dateModified` = date du jour ("
        f"{date.today().isoformat()}).",
        "- `status` = `published`.",
        "- Word count total cible : 3000 à 4200 mots.",
        "- Chaque claim chiffré (taux, montant, note, niveau RNCP) doit avoir un lien "
        "externe vérifiable à proximité (francecompetences.fr, moncompteformation.gouv.fr, "
        "trustpilot, page officielle).",
        "- Minimum 6 FAQs à la fin.",
        "",
        "Tu respectes scrupuleusement les deux règles fournies en system prompt "
        "(voice_rules + editorial_rules + format). Si tu hésites, choisis l'option la plus sobre et factuelle.",
    ]
    return "\n".join(sections)


def _extract_markdown(text: str) -> str:
    """
    Claude may wrap the output in a ```markdown ... ``` fence. Strip it.
    Preserves only the block that starts with --- (frontmatter) up to end.
    """
    # Remove surrounding code fences if present
    fenced = re.search(r"```(?:markdown|md)?\s*\n(.+?)\n```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Ensure it starts with a frontmatter delimiter
    text = text.strip()
    if not text.startswith("---"):
        # Find the first --- and cut everything before
        m = re.search(r"^---\s*$", text, re.MULTILINE)
        if m:
            text = text[m.start():]
    return text.strip() + "\n"


def _normalize_dashes(text: str) -> str:
    """
    Replace em-dashes (—) and en-dashes (–) with more human French alternatives.
    Claude tends to reach for em-dashes despite the system prompt asking not to;
    enforcing this post-generation is more reliable than prompt-only enforcement.

    Rule: " — " around a clause becomes ", " (French apposition).
    Otherwise ":" is used for intro-followed-by-elaboration patterns.
    """
    # " — text" at end of a clause => ", text"
    text = re.sub(r"\s+[—–]\s+", ", ", text)
    # Remaining stuck cases ("word—word"): hyphen
    text = text.replace("—", "-").replace("–", "-")
    return text


def _slug_from_frontmatter(md: str) -> str | None:
    m = re.search(r"^slug:\s*[\"']?([a-z0-9-]+)[\"']?", md, re.MULTILINE)
    return m.group(1) if m else None


def main() -> None:
    if kill_switch_engaged():
        print("[draft] AGENTS_ENABLED=false, exiting without action.")
        notify("Agent draft désactivé (AGENTS_ENABLED=false).", level="info")
        sys.exit(0)

    brief_path, brief = _load_brief(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"[draft] brief: {brief_path.name}")

    cfg = client_config()
    kind = brief.get("kind", "listicle")
    format_prompt_name = {
        "listicle": "format_listicle",
        "guide": "format_guide",
        "tool": "format_tool",
        "profile": "format_profile",
    }.get(kind)
    if not format_prompt_name:
        raise SystemExit(f"Unknown brief.kind: {kind!r}")
    system_prompt = build_system([format_prompt_name])
    user_prompt = _build_user_prompt(brief, cfg)

    print(f"[draft] calling Claude ({MODEL_DRAFT})...")
    notify(
        f"Début de rédaction : _{brief.get('title', brief['slug'])}_ "
        f"(query cible : « {brief['target_query']} »)",
        level="info",
    )

    raw = generate(system=system_prompt, user=user_prompt, max_tokens=16000)
    markdown = _extract_markdown(raw)
    # Normalize the em-dashes Claude still inserts despite the voice rules.
    # Post-processing is more reliable than pure prompt enforcement.
    markdown = _normalize_dashes(markdown)

    # Quick sanity, must have frontmatter
    if not markdown.startswith("---"):
        notify_quarantine("Sortie sans frontmatter YAML", str(brief_path))
        raise SystemExit("Draft missing frontmatter, aborted.")

    # Use the slug from the actual frontmatter if the model chose differently
    slug = _slug_from_frontmatter(markdown) or brief["slug"]
    target = ARTICLES_DIR / f"{slug}.md"

    # Editorial + brand-safety pass
    result = validate_draft(markdown)
    stats = draft_stats(markdown)

    # Persist the raw draft regardless — for audit
    log_path = LOGS_DIR / f"{date.today().isoformat()}-{slug}.draft.md"
    log_path.write_text(markdown, encoding="utf-8")
    meta = {
        "brief": str(brief_path.name),
        "target": str(target),
        "slug": slug,
        "stats": stats,
        "validation": {
            "passed": result.passed,
            "errors": result.errors,
            "warnings": result.warnings,
        },
        "model": MODEL_DRAFT,
    }
    (log_path.with_suffix(".meta.json")).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if not result.passed:
        notify_quarantine(
            "Validation éditoriale : " + " ; ".join(result.errors),
            str(log_path),
        )
        print(f"[draft] QUARANTINE — errors: {result.errors}", file=sys.stderr)
        sys.exit(2)

    # Write to site content dir
    target.write_text(markdown, encoding="utf-8")
    print(f"[draft] wrote {target} ({stats['word_count']} mots, {stats['h2_count']} H2)")
    if result.warnings:
        print(f"[draft] warnings: {result.warnings}")
        notify(
            f"Brouillon écrit avec avertissements : {len(result.warnings)} warning(s). "
            f"Voir logs/{log_path.name}.meta.json",
            level="warn",
        )

    # Write slug to $GITHUB_OUTPUT if running under Actions, otherwise print it.
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"slug={slug}\n")
            f.write(f"article_path={target.relative_to(PROJECT_ROOT)}\n")
    print(f"[draft] slug={slug}")


if __name__ == "__main__":
    main()
