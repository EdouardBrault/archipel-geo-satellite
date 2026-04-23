"""Minimal Slack webhook poster. Never raises, logs failures instead."""
from __future__ import annotations

import json
import os
import sys
import time

import httpx


def notify(text: str, *, level: str = "info") -> None:
    """
    Post a message to #{{SLACK_CHANNEL_NAME}}.
    level: info | success | warn | alert — prepends the corresponding emoji.
    """
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return  # silent: no webhook, don't block the agent
    emoji = {
        "info": ":information_source:",
        "success": ":white_check_mark:",
        "warn": ":warning:",
        "alert": ":rotating_light:",
    }.get(level, ":information_source:")
    payload = {"text": f"{emoji}  {text}"}
    try:
        httpx.post(webhook, json=payload, timeout=10.0)
    except Exception as e:
        # fallback to stderr so the GH Actions log still shows it
        sys.stderr.write(f"[slack notify failed] {e}\n")


def notify_quarantine(reason: str, draft_path: str) -> None:
    notify(
        f"Brouillon quarantaine : {reason}\n"
        f"Fichier : `{draft_path}`\n"
        f"Aucune publication n'a eu lieu. Run ID : `{os.environ.get('GITHUB_RUN_ID', 'local')}`",
        level="alert",
    )


def notify_published(title: str, slug: str, stats: dict) -> None:
    words = stats.get("word_count", "?")
    h2 = stats.get("h2_count", "?")
    refs = stats.get("external_links", "?")
    notify(
        f"*Article publié* : {title}\n"
        f"URL : https://{{FQDN}}/{slug}/\n"
        f"Stats : {words} mots, {h2} H2, {refs} liens sources",
        level="success",
    )
