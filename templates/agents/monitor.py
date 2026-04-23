"""
monitor.py

Sunday weekly digest. Reads git log + planner queue + Peec snapshot
and posts a summary to #{{SLACK_CHANNEL_NAME}}.

No dashboard, no extra infra. Slack is the single surface Edouard
already watches, so the monitoring lives there.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from lib.config import (
    AGENTS_DIR,
    ARTICLES_DIR,
    PROJECT_ROOT,
    STATE_DIR,
    client_config,
    kill_switch_engaged,
)
from lib.slack import notify


PRIORITIES_FILE = AGENTS_DIR / "planner_priorities.yaml"
PEEC_SNAPSHOT = STATE_DIR / "peec_latest.json"
PEEC_DAILY = STATE_DIR / "peec_daily.jsonl"

ARTICLES_PER_WEEK = 2


def _covered_slugs() -> set[str]:
    return {p.stem for p in ARTICLES_DIR.glob("*.md")}


def _since_iso(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def _count_commits_matching(since: str, pattern: str) -> int:
    """Count commits since `since` whose subject matches `pattern`."""
    out = _git("log", f"--since={since}", "--format=%s")
    return sum(1 for line in out.splitlines() if pattern in line)


def _recent_published_articles(since: str) -> list[dict]:
    """Return articles committed in the last week, with title + slug."""
    out = _git(
        "log",
        f"--since={since}",
        "--name-only",
        "--format=%H|%s|%ci",
        "--",
        "03-site/src/content/articles/",
    )
    entries: list[dict] = []
    block: list[str] = []
    for line in out.splitlines() + [""]:
        if not line.strip():
            if block:
                header = block[0]
                files = [f for f in block[1:] if f.endswith(".md")]
                if "|" in header and files:
                    sha, subject, commit_date = header.split("|", 2)
                    for f in files:
                        slug = Path(f).stem
                        entries.append(
                            {
                                "slug": slug,
                                "subject": subject,
                                "sha": sha[:7],
                                "date": commit_date,
                            }
                        )
            block = []
        else:
            block.append(line)
    return entries


def _queue_summary() -> tuple[int, int, float]:
    """Return (covered, remaining, weeks_of_cadence_remaining)."""
    with PRIORITIES_FILE.open(encoding="utf-8") as f:
        priorities = yaml.safe_load(f).get("priorities", [])
    covered = _covered_slugs()
    remaining = sum(1 for p in priorities if p["slug"] not in covered)
    return len(covered), remaining, remaining / ARTICLES_PER_WEEK


def _own_brand_trend(days: int = 7) -> dict | None:
    """Read peec_daily.jsonl, find today's + N-days-ago entries for own brand."""
    if not PEEC_DAILY.exists():
        return None
    cfg = client_config()
    own_name = cfg["promoted_brand"]["name"].strip().lower()

    lines = PEEC_DAILY.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None

    def _own_metrics(line: str) -> dict | None:
        try:
            data = json.loads(line)
        except Exception:
            return None
        for b in data.get("brand_metrics", []):
            if (b.get("name") or "").strip().lower() == own_name:
                return {
                    "date": data.get("date") or data.get("fetched_at", "")[:10],
                    "visibility": b.get("visibility"),
                    "share_of_voice": b.get("share_of_voice"),
                    "position": b.get("position"),
                }
        return None

    latest = _own_metrics(lines[-1])
    if not latest:
        return None

    # Find a line from ~days ago
    target_date = (date.today() - timedelta(days=days)).isoformat()
    earlier = None
    for line in lines:
        entry = _own_metrics(line)
        if entry and entry["date"] and entry["date"] <= target_date:
            earlier = entry
    if not earlier:
        earlier = _own_metrics(lines[0])  # fallback to first recorded

    return {"latest": latest, "earlier": earlier}


def _fmt_pct(x: float | None) -> str:
    return f"{x*100:.1f}%" if isinstance(x, (int, float)) else "n/c"


def main() -> None:
    if kill_switch_engaged():
        print("[monitor] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    since = _since_iso(7)

    published = _recent_published_articles(since)
    refresh_count = _count_commits_matching(since, "Weekly refresh:")
    audit_count = _count_commits_matching(since, "Daily Peec snapshot")

    covered, remaining, weeks_left = _queue_summary()
    trend = _own_brand_trend(7)

    week_num = datetime.utcnow().isocalendar().week
    year = datetime.utcnow().year

    lines: list[str] = [
        f"*Digest hebdo — semaine {week_num} ({year})*",
        "",
        "_Activité du site satellite_",
    ]
    if published:
        lines.append(f":newspaper: *{len(published)} article(s) publié(s)* :")
        for p in published:
            lines.append(
                f":white_small_square: <https://{{FQDN}}/{p['slug']}/|{p['slug']}>"
            )
    else:
        lines.append(":x: Aucun article publié cette semaine.")

    lines.append("")
    lines.append(f":arrows_counterclockwise: {refresh_count} refresh(s) commit(s)")
    lines.append(f":mag: {audit_count} snapshot(s) Peec quotidien(s)")

    lines.append("")
    lines.append("_File éditoriale_")
    lines.append(
        f":clipboard: Publiés : *{covered}* · Restants : *{remaining}* "
        f"(~{weeks_left:.1f} semaines de cadence)"
    )
    if weeks_left < 2:
        lines.append(
            ":warning: File basse, l'agent replenish devrait se déclencher dimanche prochain."
        )

    if trend and trend["earlier"]:
        lines.append("")
        lines.append("_Signal Peec (marque promue)_")
        d_vis = (trend["latest"]["visibility"] or 0) - (trend["earlier"]["visibility"] or 0)
        d_sov = (trend["latest"]["share_of_voice"] or 0) - (trend["earlier"]["share_of_voice"] or 0)
        lines.append(
            f":chart_with_upwards_trend: Visibilité : {_fmt_pct(trend['latest']['visibility'])} "
            f"(Δ 7j {d_vis*100:+.1f} pt)"
        )
        lines.append(
            f":loudspeaker: Share of Voice : {_fmt_pct(trend['latest']['share_of_voice'])} "
            f"(Δ 7j {d_sov*100:+.2f} pt)"
        )
    else:
        lines.append("")
        lines.append(":grey_question: Pas encore assez de snapshots Peec pour un delta 7j.")

    notify("\n".join(lines), level="info")
    print("[monitor] digest posted")


if __name__ == "__main__":
    main()
