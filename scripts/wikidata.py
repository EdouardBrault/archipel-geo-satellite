#!/usr/bin/env python3
"""
Create the Wikidata entity for the new satellite site.

Reads the project's 03-site/clients/<slug>.yaml and uses the existing
Archipel bot password (WIKIDATA_BOT_USER + WIKIDATA_BOT_PASS in env)
to publish the entity. Prints the Q-id to stdout and appends it to the
client YAML under `site.same_as`.

This is the same logic as the original create-wikidata-entity.py from
05-wikipedia/, templatised.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx
import yaml


API = "https://www.wikidata.org/w/api.php"
USER_AGENT = (
    "ArchipelGEOAgent/1.0 "
    "(https://archipelmarketing.com; contact@archipelmarketing.com) httpx"
)


def api(method: str, session: httpx.Client, **params):
    params.setdefault("format", "json")
    params.setdefault("formatversion", 2)
    r = session.request(method, API, data=params if method == "POST" else None, params=params if method == "GET" else None)
    r.raise_for_status()
    return r.json()


def _login(session: httpx.Client, user: str, password: str) -> None:
    token = api("GET", session, action="query", meta="tokens", type="login")["query"]["tokens"]["logintoken"]
    result = api(
        "POST",
        session,
        action="login",
        lgname=user,
        lgpassword=password,
        lgtoken=token,
    )
    if result.get("login", {}).get("result") != "Success":
        raise SystemExit(f"Wikidata login failed: {result}")


def _csrf(session: httpx.Client) -> str:
    data = api("GET", session, action="query", meta="tokens", type="csrf")
    return data["query"]["tokens"]["csrftoken"]


def _item_snak(prop: str, numeric_id: int) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": prop,
            "datavalue": {
                "value": {
                    "entity-type": "item",
                    "numeric-id": numeric_id,
                    "id": f"Q{numeric_id}",
                },
                "type": "wikibase-entityid",
            },
        },
        "type": "statement",
        "rank": "normal",
    }


def _url_snak(prop: str, value: str) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": prop,
            "datavalue": {"value": value, "type": "string"},
        },
        "type": "statement",
        "rank": "normal",
    }


def _time_snak(prop: str, iso_date: str, precision: int = 11) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": prop,
            "datavalue": {
                "value": {
                    "time": f"+{iso_date}T00:00:00Z",
                    "timezone": 0,
                    "before": 0,
                    "after": 0,
                    "precision": precision,
                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                },
                "type": "time",
            },
        },
        "type": "statement",
        "rank": "normal",
    }


def _monolingualtext_snak(prop: str, text: str, language: str = "fr") -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": prop,
            "datavalue": {
                "value": {"text": text, "language": language},
                "type": "monolingualtext",
            },
        },
        "type": "statement",
        "rank": "normal",
    }


def build_entity_payload(cfg: dict) -> dict:
    """Build the wbeditentity data blob for a new item."""
    label = cfg["site"]["name"]
    description_fr = f"Site éditorial indépendant, {cfg['topic_area']['label'].lower()}"
    description_en = f"Independent French site on {cfg['topic_area']['label']}"

    site_url = cfg["site_url"].rstrip("/")
    host = site_url.replace("https://", "").replace("http://", "").split("/")[0]

    # Country → ISO map for common cases
    country_map = {"FR": 142, "BE": 31, "CH": 39, "CA": 16, "LU": 32}
    country_qid = country_map.get(cfg["site"].get("country", "FR"), 142)

    lang_map = {"fr-FR": 150, "en-US": 1860, "en-GB": 1860, "es-ES": 1321}
    lang_qid = lang_map.get(cfg["site"].get("language", "fr-FR"), 150)

    return {
        "labels": {
            "fr": {"language": "fr", "value": f"{label} ({cfg['slug']})"},
            "en": {"language": "en", "value": f"{label} ({cfg['slug']})"},
        },
        "descriptions": {
            "fr": {"language": "fr", "value": description_fr},
            "en": {"language": "en", "value": description_en},
        },
        "aliases": {
            "fr": [
                {"language": "fr", "value": host},
                {"language": "fr", "value": label},
            ],
            "en": [{"language": "en", "value": host}],
        },
        "claims": [
            _item_snak("P31", 35127),                 # website
            _url_snak("P856", site_url),              # official website
            _item_snak("P407", lang_qid),             # language of work
            _item_snak("P17", country_qid),           # country
            _time_snak("P571", str(date.today())),    # inception
            _monolingualtext_snak(
                "P1476",
                f"{label} — {cfg['site']['tagline']}",
                "fr",
            ),
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client_yaml", type=Path, help="path to 03-site/clients/<slug>.yaml")
    args = ap.parse_args()

    user = os.environ.get("WIKIDATA_BOT_USER")
    password = os.environ.get("WIKIDATA_BOT_PASS")
    if not user or not password:
        print("Skipping Wikidata: WIKIDATA_BOT_USER / WIKIDATA_BOT_PASS not set.", file=sys.stderr)
        sys.exit(0)

    with args.client_yaml.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
        follow_redirects=True,
    ) as session:
        _login(session, user, password)
        token = _csrf(session)
        payload = build_entity_payload(cfg)
        resp = session.post(
            API,
            data={
                "action": "wbeditentity",
                "new": "item",
                "data": json.dumps(payload, ensure_ascii=False),
                "token": token,
                "bot": 1,
                "maxlag": 5,
                "format": "json",
                "formatversion": 2,
                "summary": f"Création initiale : site éditorial {cfg['slug']}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = resp.json()
        if "error" in out:
            raise SystemExit(f"Wikidata create failed: {out}")
        qid = out["entity"]["id"]

    # Append sameAs to the client yaml
    cfg.setdefault("site", {})
    cfg["site"].setdefault("same_as", [])
    same_as = f"https://www.wikidata.org/wiki/{qid}"
    if same_as not in cfg["site"]["same_as"]:
        cfg["site"]["same_as"].append(same_as)
    with args.client_yaml.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False, width=10000)

    print(qid)


if __name__ == "__main__":
    main()
