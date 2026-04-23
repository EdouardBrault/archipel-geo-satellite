#!/usr/bin/env python3
"""
Instantiate a new client project from the skill's templates/ tree.

Reads a client.yaml file, substitutes every {{PLACEHOLDER}} in the
templates, writes the result to an OUTPUT_DIR. Does not touch git,
GitHub, Cloudflare — that's bootstrap.sh's job.

Usage:
    python instantiate.py path/to/client.yaml --out /path/to/new-project-dir

The resulting directory structure mirrors the original Uncode project:

    new-project-dir/
    ├── .github/workflows/
    ├── 03-site/
    ├── 04-agents/
    ├── CLAUDE.md
    ├── .gitignore
    ├── .env.example
    └── README.md

Placeholders supported:
    {{SLUG}}                   — short kebab-case id of the client
    {{CLIENT_DISPLAY_NAME}}    — human display name
    {{FQDN}}                   — full domain (e.g. acme.rank-ly.com)
    {{FQDN_REGEX}}             — escaped FQDN for regex use (.→\.)
    {{SITE_NAME}}              — editorial name of the satellite
    {{SITE_TAGLINE}}           — tagline for the hero
    {{PROMOTED_BRAND_NAME}}    — client brand (e.g. Uncode School)
    {{PROMOTED_BRAND_URL}}     — full URL (https://…)
    {{PROMOTED_BRAND_DOMAIN}}  — bare host (no scheme)
    {{GH_OWNER}}               — GitHub account/org
    {{GH_REPO}}                — GitHub repo name
    {{SLACK_CHANNEL}}          — #channel (with hash)
    {{SLACK_CHANNEL_NAME}}     — channel without hash
    {{INDEXNOW_KEY}}           — 32-char hex, generated if not in env
    {{WIKIDATA_QID}}           — Q-id, filled after Wikidata entity is created
    {{CONTACT_EMAIL}}          — editor email address
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_ROOT / "templates"

# Mapping of template subfolders → destination paths inside the new project.
# Keep this in sync with the structure produced by the original project.
LAYOUT = {
    "site":      "03-site",
    "agents":    "04-agents",
    "workflows": ".github/workflows",
    # "root" contents go to project root, handled specially below
}


def _bare_host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0]


def build_substitutions(cfg: dict[str, Any]) -> dict[str, str]:
    """Collect every {{placeholder}} value we need, from the client.yaml."""
    slug = cfg["slug"]

    # Resolve the FQDN
    dmode = cfg["domain"]["mode"]
    if dmode == "subdomain_rankly":
        fqdn = f"{cfg['domain']['subdomain']}.{cfg['domain']['parent']}"
    elif dmode == "standalone":
        fqdn = cfg["domain"]["standalone_fqdn"]
    else:
        raise SystemExit(f"Unknown domain.mode: {dmode!r}")

    promoted_url = cfg["promoted_brand"]["url"]
    slack_channel = cfg.get("integrations", {}).get("slack", {}).get("channel", f"#rank-ly-{slug}")
    slack_channel_name = slack_channel.lstrip("#")

    indexnow_key = os.environ.get("INDEXNOW_KEY") or secrets.token_hex(16)
    wikidata_qid = os.environ.get("WIKIDATA_QID") or ""

    subs = {
        "{{SLUG}}": slug,
        "{{CLIENT_DISPLAY_NAME}}": cfg.get("client_display_name", slug),
        "{{FQDN}}": fqdn,
        "{{FQDN_REGEX}}": fqdn.replace(".", r"\."),
        "{{SITE_NAME}}": cfg["site"]["name"],
        "{{SITE_TAGLINE}}": cfg["site"]["tagline"],
        "{{PROMOTED_BRAND_NAME}}": cfg["promoted_brand"]["name"],
        "{{PROMOTED_BRAND_URL}}": promoted_url,
        "{{PROMOTED_BRAND_DOMAIN}}": _bare_host(promoted_url),
        "{{GH_OWNER}}": cfg["integrations"]["github"]["owner"],
        "{{GH_REPO}}": cfg["integrations"]["github"]["repo"],
        "{{SLACK_CHANNEL}}": slack_channel,
        "{{SLACK_CHANNEL_NAME}}": slack_channel_name,
        "{{INDEXNOW_KEY}}": indexnow_key,
        "{{WIKIDATA_QID}}": wikidata_qid,
        "{{CONTACT_EMAIL}}": os.environ.get(
            "CONTACT_EMAIL", "contact@archipelmarketing.com"
        ),
    }
    return subs


def copy_and_substitute(src: Path, dst: Path, subs: dict[str, str]) -> None:
    """Copy a single file, substituting placeholders in content and filename."""
    # Substitute placeholders in the destination filename
    new_name = dst.name
    for token, value in subs.items():
        new_name = new_name.replace(token, value)
    dst = dst.with_name(new_name)

    dst.parent.mkdir(parents=True, exist_ok=True)

    # Binary passthrough — the skill has none, but future-proof.
    try:
        content = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shutil.copy(src, dst)
        return

    for token, value in subs.items():
        content = content.replace(token, value)

    # Strip any .template suffix on the destination filename
    if dst.name.endswith(".template"):
        dst = dst.with_name(dst.name.removesuffix(".template"))

    dst.write_text(content, encoding="utf-8")
    # Preserve exec bit for scripts
    mode = src.stat().st_mode
    if mode & 0o100:
        os.chmod(dst, mode)


def copy_tree(src_root: Path, dst_root: Path, subs: dict[str, str]) -> int:
    count = 0
    for path in src_root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src_root)
        copy_and_substitute(path, dst_root / rel, subs)
        count += 1
    return count


def write_client_yaml(cfg: dict[str, Any], out_dir: Path) -> None:
    """Produce the 03-site/clients/<slug>.yaml runtime config."""
    slug = cfg["slug"]
    dmode = cfg["domain"]["mode"]
    if dmode == "subdomain_rankly":
        site_url = f"https://{cfg['domain']['subdomain']}.{cfg['domain']['parent']}"
    else:
        site_url = f"https://{cfg['domain']['standalone_fqdn']}"

    runtime_cfg = {
        "slug": slug,
        "site_url": site_url,
        "site": cfg["site"],
        "promoted_brand": cfg["promoted_brand"],
        "topic_area": cfg["topic_area"],
        "competitors": cfg["competitors"],
        "ranking_methodology": cfg["ranking_methodology"],
        "voice": cfg["voice"],
        "cadence": cfg["cadence"],
        "integrations": {
            "peec_ai": {
                "api_key_env": "PEEC_AI_API_KEY",
                "api_base": "https://api.peec.ai/customer/v1",
            },
            "slack": {
                "webhook_env": "SLACK_WEBHOOK_URL",
                "channel": cfg["integrations"]["slack"]["channel"],
            },
            "cloudflare": {
                "account_id_env": "CLOUDFLARE_ACCOUNT_ID",
                "api_token_env": "CLOUDFLARE_API_TOKEN",
                "pages_project": cfg["integrations"]["cloudflare"]["pages_project"],
            },
        },
    }

    # Add site.same_as when WIKIDATA_QID is known
    qid = os.environ.get("WIKIDATA_QID")
    if qid:
        runtime_cfg["site"]["same_as"] = [f"https://www.wikidata.org/wiki/{qid}"]

    dst = out_dir / "03-site" / "clients" / f"{slug}.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml.safe_dump(runtime_cfg, f, allow_unicode=True, sort_keys=False, width=10000)


def write_priorities(cfg: dict[str, Any], out_dir: Path) -> None:
    """Seed 04-agents/planner_priorities.yaml from the initial_priorities field."""
    seed = cfg.get("initial_priorities") or []
    # Normalize multiline strings
    clean = []
    for p in seed:
        clean.append({
            "slug": p["slug"],
            "kind": p["kind"],
            "target_query": p["target_query"],
            "title": p["title"],
            "angle": str(p["angle"]).strip() + "\n",
        })
    dst = out_dir / "04-agents" / "planner_priorities.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"priorities": clean},
            f,
            allow_unicode=True,
            sort_keys=False,
            width=10000,
        )


def write_indexnow_key(subs: dict[str, str], out_dir: Path) -> None:
    """Place the INDEXNOW_KEY_PLACEHOLDER.txt under the real key name."""
    key = subs["{{INDEXNOW_KEY}}"]
    dst = out_dir / "03-site" / "public" / f"{key}.txt"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(key, encoding="utf-8")
    # Remove the placeholder file if it exists
    placeholder = out_dir / "03-site" / "public" / "INDEXNOW_KEY_PLACEHOLDER.txt"
    if placeholder.exists():
        placeholder.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="path to client.yaml")
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="destination directory for the instantiated project",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the destination if it exists",
    )
    args = parser.parse_args()

    if not args.config.exists():
        raise SystemExit(f"client.yaml not found: {args.config}")
    with args.config.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.out.exists():
        if not args.force:
            raise SystemExit(
                f"Destination already exists: {args.out} (use --force to overwrite)"
            )
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True, exist_ok=False)

    subs = build_substitutions(cfg)
    print(f"Instantiating into {args.out}")

    total = 0
    for template_sub, project_sub in LAYOUT.items():
        src = TEMPLATES / template_sub
        if not src.exists():
            continue
        dst = args.out / project_sub
        total += copy_tree(src, dst, subs)

    # Root-level files (flat)
    root_src = TEMPLATES / "root"
    if root_src.exists():
        for path in root_src.iterdir():
            if path.is_file():
                copy_and_substitute(path, args.out / path.name, subs)
                total += 1

    # Handle filenames that still need renaming (e.g. .gitignore.template)
    gi = args.out / ".gitignore.template"
    if gi.exists():
        gi.rename(args.out / ".gitignore")

    # Client runtime config + priorities + IndexNow key
    write_client_yaml(cfg, args.out)
    write_priorities(cfg, args.out)
    write_indexnow_key(subs, args.out)

    print(f"  {total} files instantiated")
    print(f"  INDEXNOW_KEY={subs['{{INDEXNOW_KEY}}']}")
    print("Done.")


if __name__ == "__main__":
    main()
