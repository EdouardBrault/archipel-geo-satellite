"""
planner.py

Picks the next editorial topic to cover and writes a brief YAML file to
04-agents/briefs/ that draft_article.py will consume.

Strategy (v1, rule-based):
  1. Load 04-agents/planner_priorities.yaml (human-curated priority queue).
  2. Drop priorities whose slug already exists in 03-site/src/content/articles/.
  3. If the Peec snapshot is available (04-agents/state/peec_latest.json),
     re-rank remaining priorities using the gap signal:
       - prompts where Uncode loses big get promoted in the queue
  4. Pick the first remaining priority and emit a brief file.

Output:
  - writes 04-agents/briefs/<today>-<slug>.yaml
  - prints the relative path (consumed by the write-and-publish workflow)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

from lib.config import (
    AGENTS_DIR,
    ARTICLES_DIR,
    BRIEFS_DIR,
    STATE_DIR,
    kill_switch_engaged,
)
from lib.slack import notify


PRIORITIES_FILE = AGENTS_DIR / "planner_priorities.yaml"
PEEC_SNAPSHOT = STATE_DIR / "peec_latest.json"


def _covered_slugs() -> set[str]:
    """Slugs we've already published (by article filename)."""
    if not ARTICLES_DIR.exists():
        return set()
    return {p.stem for p in ARTICLES_DIR.glob("*.md")}


def _load_priorities() -> list[dict]:
    with PRIORITIES_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["priorities"]


def _peec_gap_score(target_query: str) -> float:
    """
    Use the Peec snapshot (if present) to score priorities by the gap signal.
    Returns a multiplier (higher = more urgent) based on whether any cited
    URL mentions the brand on that query topic. Very rough for v1.
    """
    if not PEEC_SNAPSHOT.exists():
        return 1.0
    try:
        data = json.loads(PEEC_SNAPSHOT.read_text())
    except Exception:
        return 1.0
    q = target_query.lower()
    # Boost if any of the top 30 cited domains has a title/URL matching a keyword
    # from the target query. Very approximate but good enough for v1 re-ranking.
    keywords = [w for w in q.split() if len(w) > 3]
    matches = 0
    for u in data.get("top_urls", []):
        hay = ((u.get("title") or "") + " " + (u.get("url") or "")).lower()
        if any(k in hay for k in keywords):
            matches += 1
    # Fewer matches = bigger gap = higher priority
    return max(0.5, 1.5 - (matches / 50.0))


def _pick_next(priorities: list[dict], covered: set[str]) -> dict | None:
    candidates = [p for p in priorities if p["slug"] not in covered]
    if not candidates:
        return None
    # Apply gap re-ranking
    for p in candidates:
        p["_score"] = _peec_gap_score(p["target_query"])
    candidates.sort(key=lambda p: p.get("_score", 1.0), reverse=True)
    return candidates[0]


def _emit_brief(priority: dict) -> Path:
    today = date.today().isoformat()
    filename = f"{today}-{priority['slug']}.yaml"
    out = BRIEFS_DIR / filename
    brief = {
        "slug": priority["slug"],
        "kind": priority["kind"],
        "target_query": priority["target_query"],
        "title": priority["title"],
        "angle": priority["angle"].strip(),
    }
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(brief, f, allow_unicode=True, sort_keys=False, width=1000)
    return out


def main() -> None:
    if kill_switch_engaged():
        print("[planner] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    priorities = _load_priorities()
    covered = _covered_slugs()
    pick = _pick_next(priorities, covered)

    if pick is None:
        notify(
            "Planner : file de priorités vide. Tous les sujets listés dans "
            "`planner_priorities.yaml` sont déjà couverts. Ajoute de nouvelles entrées.",
            level="warn",
        )
        print("[planner] queue empty — nothing to do")
        # Exit 78 is the "neutral skip" code for GitHub Actions jobs.
        sys.exit(78)

    brief_path = _emit_brief(pick)
    rel = brief_path.relative_to(AGENTS_DIR.parent)
    print(f"[planner] next brief: {rel}")

    # Expose the path to the caller (GitHub Actions consumes $GITHUB_OUTPUT)
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"brief_path={rel}\n")

    notify(
        f"Planner : sujet suivant sélectionné — *{pick['title']}* "
        f"(query `{pick['target_query']}`). Brief : `{rel}`",
        level="info",
    )


if __name__ == "__main__":
    main()
