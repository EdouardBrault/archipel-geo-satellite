"""
audit_peec.py

Daily pull of Peec AI metrics. Produces two files:
  state/peec_latest.json  — snapshot consumed by the planner
  state/peec_daily.jsonl  — one JSON line per day, long-term trend

Alerts Slack when a significant shift occurs day-over-day:
  - Uncode visibility drops > 2 pts in 24h
  - A competitor gains > 5 pts in 24h
  - An owned URL that was cited yesterday is no longer in the top-cited list
  - A new domain enters the top 30 cited (could be a new competitor site)

The script is fast (≈30s at steady state) and side-effect-only on disk;
no content is ever modified by this agent.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from lib.config import STATE_DIR, client_config, kill_switch_engaged, require
from lib.slack import notify


PEEC_BASE = "https://api.peec.ai/customer/v1"
REQUEST_DELAY_S = 0.35  # Peec rate-limits around ~10 req/s


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError))


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1.5, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _request(method: str, client: httpx.Client, path: str, **kwargs: Any) -> httpx.Response:
    time.sleep(REQUEST_DELAY_S)
    r = client.request(method, path, **kwargs)
    if r.status_code in (429, 500, 502, 503, 504):
        ra = r.headers.get("Retry-After")
        if ra and ra.isdigit():
            time.sleep(min(int(ra), 30))
        r.raise_for_status()
    return r


def fetch_snapshot() -> dict:
    """Pull the subset of Peec data the planner + alerting need."""
    api_key = require("PEEC_AI_API_KEY")
    cfg = client_config()
    own_domains = {d.lower() for c in [cfg["promoted_brand"]] for d in [c["url"]]}
    own_domain_host = (
        cfg["promoted_brand"]["url"]
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )

    end = date.today()
    start = end - timedelta(days=90)
    window = {"start_date": start.isoformat(), "end_date": end.isoformat()}

    with httpx.Client(
        base_url=PEEC_BASE,
        headers={"x-api-key": api_key, "accept": "application/json"},
        timeout=60,
    ) as client:
        # Overall brand metrics (includes Uncode + all competitors)
        r = _request(
            "POST",
            client,
            "/reports/brands",
            json={**window, "dimensions": [], "limit": 100, "offset": 0},
        )
        brands = r.json().get("data", [])

        # Top cited URLs, slice to top 50 by citation_count
        all_urls = []
        offset = 0
        while True:
            r = _request(
                "POST",
                client,
                "/reports/urls",
                json={**window, "dimensions": [], "limit": 100, "offset": offset},
            )
            batch = r.json().get("data", [])
            if not batch:
                break
            all_urls.extend(batch)
            if len(batch) < 100:
                break
            offset += 100
            if offset >= 500:  # cap at 500 URLs to keep the run fast
                break
        top_urls = sorted(
            all_urls, key=lambda u: u.get("citation_count", 0), reverse=True
        )[:50]

        # Top cited domains, same treatment
        all_domains = []
        offset = 0
        while True:
            r = _request(
                "POST",
                client,
                "/reports/domains",
                json={**window, "dimensions": [], "limit": 100, "offset": offset},
            )
            batch = r.json().get("data", [])
            if not batch:
                break
            all_domains.extend(batch)
            if len(batch) < 100:
                break
            offset += 100
            if offset >= 500:
                break
        top_domains = sorted(
            all_domains, key=lambda d: d.get("citation_rate", 0), reverse=True
        )[:30]

    # Build a compact snapshot
    snapshot = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "window_days": 90,
        "brand_metrics": [
            {
                "name": b["brand"].get("name"),
                "id": b["brand"].get("id"),
                "visibility": b.get("visibility"),
                "share_of_voice": b.get("share_of_voice"),
                "mention_count": b.get("mention_count"),
                "sentiment": b.get("sentiment"),
                "position": b.get("position"),
            }
            for b in brands
        ],
        "top_domains": [
            {
                "domain": d["domain"],
                "classification": d.get("classification"),
                "citation_rate": d.get("citation_rate"),
                "usage_rate": d.get("usage_rate"),
            }
            for d in top_domains
        ],
        "top_urls": [
            {
                "url": u["url"],
                "title": u.get("title"),
                "classification": u.get("classification"),
                "citation_count": u.get("citation_count"),
                "is_owned": own_domain_host.lower() in (u.get("url") or "").lower(),
            }
            for u in top_urls
        ],
        "own_domain_host": own_domain_host,
    }
    return snapshot


# -------- day-over-day comparison + alerts -----------------------------

def _index_by_name(brands: list[dict]) -> dict[str, dict]:
    return {b["name"]: b for b in brands if b.get("name")}


def compare_and_alert(previous: dict | None, current: dict) -> list[str]:
    """
    Returns a list of human-readable alert strings. Also posts to Slack
    if at least one alert is triggered.
    """
    if not previous:
        return []

    alerts: list[str] = []
    cfg = client_config()
    own_name = cfg["promoted_brand"]["name"].lower()

    prev_brands = _index_by_name(previous.get("brand_metrics", []))
    curr_brands = _index_by_name(current.get("brand_metrics", []))

    # Uncode / own-brand visibility drop
    own_prev = next(
        (b for n, b in prev_brands.items() if n.strip().lower() == own_name),
        None,
    )
    own_curr = next(
        (b for n, b in curr_brands.items() if n.strip().lower() == own_name),
        None,
    )
    if own_prev and own_curr:
        delta = (own_curr.get("visibility") or 0) - (own_prev.get("visibility") or 0)
        if delta < -0.02:
            alerts.append(
                f":rotating_light: Visibilité {own_curr['name']} baisse de "
                f"{delta*100:+.1f} pts en 24h "
                f"({own_prev['visibility']*100:.1f}% -> {own_curr['visibility']*100:.1f}%)"
            )

    # Competitor surges
    for name, curr in curr_brands.items():
        if name.strip().lower() == own_name:
            continue
        prev = prev_brands.get(name)
        if not prev:
            continue
        delta = (curr.get("visibility") or 0) - (prev.get("visibility") or 0)
        if delta > 0.05:
            alerts.append(
                f":chart_with_upwards_trend: {name} gagne {delta*100:+.1f} pts de visibilité en 24h "
                f"({prev['visibility']*100:.1f}% -> {curr['visibility']*100:.1f}%)"
            )

    # New domain enters top 30
    prev_domains = {d["domain"] for d in previous.get("top_domains", [])}
    curr_domains = {d["domain"] for d in current.get("top_domains", [])}
    new_in_top = curr_domains - prev_domains
    if new_in_top:
        alerts.append(
            f":mag: Nouveaux domaines dans le top 30 cités : {', '.join(sorted(new_in_top)[:5])}"
        )

    # Owned URL dropped out of top 50
    prev_owned = {u["url"] for u in previous.get("top_urls", []) if u.get("is_owned")}
    curr_urls = {u["url"] for u in current.get("top_urls", [])}
    dropped = prev_owned - curr_urls
    if dropped:
        alerts.append(
            ":warning: URL éditeur sortie du top 50 des URLs citées : "
            + ", ".join(sorted(dropped)[:3])
        )

    return alerts


def main() -> None:
    if kill_switch_engaged():
        print("[audit] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    print(f"[audit] fetching Peec snapshot ({date.today().isoformat()})")
    snapshot = fetch_snapshot()

    latest_path = STATE_DIR / "peec_latest.json"
    previous = None
    if latest_path.exists():
        try:
            previous = json.loads(latest_path.read_text())
        except Exception as e:
            print(f"[audit] could not load previous snapshot: {e}")

    alerts = compare_and_alert(previous, snapshot)
    if alerts:
        notify(
            "*Audit Peec quotidien — signaux détectés*\n" + "\n".join(alerts),
            level="alert",
        )
        print(f"[audit] alerts: {len(alerts)}")
    else:
        # Quiet info ping on successful run so we know the cron is alive.
        brand_count = len(snapshot["brand_metrics"])
        url_count = len(snapshot["top_urls"])
        notify(
            f"Audit Peec OK ({brand_count} marques, {url_count} URLs top) — rien d'anormal détecté.",
            level="info",
        )

    # Persist the snapshot (replaces previous, log-appends the daily line)
    latest_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    daily_path = STATE_DIR / "peec_daily.jsonl"
    with daily_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": date.today().isoformat(), **snapshot}) + "\n")

    print(f"[audit] snapshot saved -> {latest_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify(f"Audit Peec — erreur d'exécution : `{e}`", level="alert")
        print(f"[audit] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
