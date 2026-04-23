"""
replenish_queue.py

Tops up the editorial queue when it's running low. The planner consumes
one entry per publish cycle (2x/week). When fewer than MIN_BUFFER entries
remain uncovered, this agent proposes 8-12 new priority entries via Claude
and appends them to 04-agents/planner_priorities.yaml.

Runs weekly (Sunday). Idempotent: if the queue is deep enough, it exits
without changes.
"""
from __future__ import annotations

import re
import sys
from datetime import date

import yaml

from lib.claude import MODEL_DRAFT, build_system, generate
from lib.config import (
    AGENTS_DIR,
    ARTICLES_DIR,
    STATE_DIR,
    client_config,
    kill_switch_engaged,
)
from lib.gitops import add_and_commit, push
from lib.slack import notify

PRIORITIES_FILE = AGENTS_DIR / "planner_priorities.yaml"
PEEC_SNAPSHOT = STATE_DIR / "peec_latest.json"

MIN_BUFFER_WEEKS = 4       # stop when buffer >= 4 weeks of publishing
ARTICLES_PER_WEEK = 2      # cadence
TARGET_NEW_ENTRIES = 10    # how many Claude should propose per run


def _covered_slugs() -> set[str]:
    return {p.stem for p in ARTICLES_DIR.glob("*.md")}


def _queue_depth(priorities: list[dict], covered: set[str]) -> int:
    return sum(1 for p in priorities if p["slug"] not in covered)


def _build_user_prompt(
    priorities: list[dict],
    covered: set[str],
    cfg: dict,
) -> str:
    existing_queue = "\n".join(
        f"- {p['slug']} ({p['kind']}) — {p['target_query']}"
        for p in priorities if p["slug"] not in covered
    ) or "(file vide)"
    published = "\n".join(f"- {s}" for s in sorted(covered)) or "(aucun article publié)"

    topic = cfg["topic_area"]
    return (
        "Tu dois proposer de nouveaux sujets pour la file de priorités éditoriales.\n\n"
        "# Contexte du site\n\n"
        f"- Périmètre thématique : {topic['label']}\n"
        f"- Mots-clefs primaires : {', '.join(topic['primary_keywords'])}\n"
        f"- Mots-clefs secondaires : {', '.join(topic['secondary_keywords'])}\n"
        f"- Mots-clefs exclus : {', '.join(topic['excluded_keywords'])}\n\n"
        "# Articles déjà publiés (slugs)\n\n"
        f"{published}\n\n"
        "# File de priorités actuelle (slugs non encore publiés)\n\n"
        f"{existing_queue}\n\n"
        "# Ta tâche\n\n"
        f"Propose {TARGET_NEW_ENTRIES} nouvelles entrées distinctes. Elles doivent :\n"
        "- Ne dupliquer ni un article publié ni une entrée en file\n"
        "- Couvrir des intentions de recherche réelles sur le périmètre\n"
        "- Varier les formats entre `listicle`, `guide` et `tool`\n"
        "- Suivre strictement le format YAML demandé dans le system prompt\n"
        "\n"
        "Retourne uniquement le bloc YAML, rien d'autre.\n"
    )


def _parse_entries(raw: str) -> list[dict]:
    """Parse Claude output, be tolerant to fences or leading commentary."""
    text = raw.strip()
    fenced = re.search(r"```(?:yaml|yml)?\s*\n(.+?)\n```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Find first "- slug:" bullet and start from there
    m = re.search(r"^-\s+slug:", text, re.MULTILINE)
    if m:
        text = text[m.start():]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"[replenish] YAML parse error: {e}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        return []
    clean: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        required = {"slug", "kind", "target_query", "title", "angle"}
        if not required.issubset(item.keys()):
            continue
        if item["kind"] not in {"listicle", "guide", "tool"}:
            continue
        # sanitize slug
        slug = str(item["slug"]).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        if not slug or len(slug) > 80:
            continue
        item["slug"] = slug
        clean.append({
            "slug": item["slug"],
            "kind": item["kind"],
            "target_query": str(item["target_query"]).strip(),
            "title": str(item["title"]).strip(),
            "angle": str(item["angle"]).strip(),
        })
    return clean


def _append_to_yaml(new_entries: list[dict]) -> int:
    """Append to priorities file. Returns number of entries actually added."""
    with PRIORITIES_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {"priorities": []}
    existing = {p["slug"] for p in data.get("priorities", [])}
    covered = _covered_slugs()
    added = 0
    for entry in new_entries:
        if entry["slug"] in existing or entry["slug"] in covered:
            continue
        data.setdefault("priorities", []).append(entry)
        existing.add(entry["slug"])
        added += 1
    if added:
        with PRIORITIES_FILE.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                data, f, allow_unicode=True, sort_keys=False, width=10000
            )
    return added


def main() -> None:
    if kill_switch_engaged():
        print("[replenish] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    with PRIORITIES_FILE.open(encoding="utf-8") as f:
        priorities = yaml.safe_load(f)["priorities"]
    covered = _covered_slugs()
    depth = _queue_depth(priorities, covered)
    buffer_weeks = depth / ARTICLES_PER_WEEK
    print(f"[replenish] queue depth = {depth} entries, ~{buffer_weeks:.1f} weeks")

    if buffer_weeks >= MIN_BUFFER_WEEKS:
        print(f"[replenish] buffer sufficient (>= {MIN_BUFFER_WEEKS} weeks), skipping")
        notify(
            f"Queue OK ({depth} sujets restants, ~{buffer_weeks:.1f} semaines de cadence). Rien à faire.",
            level="info",
        )
        sys.exit(0)

    print("[replenish] calling Claude for new entries")
    cfg = client_config()
    system = build_system(["replenish_rules"])
    user = _build_user_prompt(priorities, covered, cfg)

    raw = generate(system=system, user=user, max_tokens=4000, model=MODEL_DRAFT)
    entries = _parse_entries(raw)
    if not entries:
        notify(
            "Replenish : sortie Claude non parsable, aucune entrée ajoutée. "
            "Logs GitHub Actions à vérifier.",
            level="alert",
        )
        print(f"[replenish] could not parse entries, raw output:\n{raw[:500]}", file=sys.stderr)
        sys.exit(1)

    added = _append_to_yaml(entries)
    if added == 0:
        notify(
            "Replenish : toutes les entrées proposées par Claude étaient déjà couvertes "
            "ou dupliquées. File inchangée.",
            level="warn",
        )
        sys.exit(0)

    # Commit the updated priorities file
    rel = "04-agents/planner_priorities.yaml"
    commit_msg = f"Replenish queue: +{added} new priority topics ({date.today().isoformat()})"
    sha = add_and_commit([rel], commit_msg)
    if sha:
        push()
        preview = "\n".join(
            f":white_small_square: `{e['slug']}` ({e['kind']}) — {e['target_query']}"
            for e in entries[:added]
        )
        notify(
            f"*Queue rechargée* : {added} nouveaux sujets ajoutés à la file.\n{preview}",
            level="success",
        )
    else:
        print("[replenish] no-op commit (unexpected), nothing pushed")


if __name__ == "__main__":
    main()
