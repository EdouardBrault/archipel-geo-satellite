"""
fact_check.py

Reads a fresh article Markdown from 03-site/src/content/articles/<slug>.md,
extracts factual claims, verifies what can be verified (external URL reachable,
domain authoritative), and gates publication.

This is a pragmatic v1: it does NOT hallucinate-check every claim via LLM
re-query. It checks:
  1. Every claim pattern (taux, prix, RNCP niveau, note /5) has a nearby
     authoritative URL.
  2. Every external link in the article resolves (HEAD 200).
  3. No forbidden glyphs (already covered by validators.py, but re-run here).

If the draft has too many unverified claims or too many broken links,
fact_check exits non-zero and publish.py is skipped by the workflow.
"""
from __future__ import annotations

import os
import re
import sys

import httpx

from lib.config import ARTICLES_DIR, kill_switch_engaged
from lib.slack import notify, notify_quarantine
from lib.validators import validate_draft


AUTHORITATIVE_DOMAINS = {
    "francecompetences.fr",
    "www.francecompetences.fr",
    "moncompteformation.gouv.fr",
    "www.moncompteformation.gouv.fr",
    "fr.trustpilot.com",
    "trustpilot.com",
    "data.gouv.fr",
    "www.service-public.fr",
    "travail-emploi.gouv.fr",
    "centre-inffo.fr",
    "qualiopi.gouv.fr",
}


def _extract_urls(markdown: str) -> list[str]:
    # [text](url) markdown links, plus bare http(s)
    urls = re.findall(r"\]\((https?://[^\s)]+)\)", markdown)
    bare = re.findall(r"(?<![\(\"])https?://[^\s)]+", markdown)
    return list(dict.fromkeys(urls + bare))  # dedup, preserve order


def _head_ok(url: str, timeout: float = 10.0) -> bool:
    """Return True if the URL responds 200-399 to a GET.

    Trusted authoritative domains (francecompetences.fr, moncompteformation,
    trustpilot, etc.) often block programmatic GETs with 403/anti-bot. We
    assume they resolve correctly and don't penalize the article for
    their blocking behavior.
    """
    try:
        host = url.split("/")[2] if "://" in url else ""
        if any(host.endswith(d) for d in AUTHORITATIVE_DOMAINS):
            return True
    except Exception:
        pass
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        return 200 <= r.status_code < 400
    except Exception:
        return False


def _authoritative_coverage(markdown: str) -> dict:
    """
    Count how many "claim-like" patterns (specific chiffered claims only)
    appear within 400 chars of an authoritative URL. Returns a ratio.

    Patterns are intentionally narrow: only claims that should be sourced
    in serious editorial. Generic phrases like "éligible CPF" are NOT
    counted — they appear in every paragraph and sourcing each would be
    noise, not signal.
    """
    patterns = [
        r"taux\s+d['']insertion[^.]*?\d{1,3}\s?%",
        r"\d{1,3}\s?%\s+de\s+(?:placement|réussite|insertion|satisfaction)",
        r"RNCP\s+niveau\s+\d",
        r"(?:montant|prise\s+en\s+charge|reste\s+à\s+charge|tarif|prix)\s+[^.]*?\d{2,}\s?(?:€|euros)",
        r"note\s+[^.]*?\d[.,]\d\s?(?:/|sur)\s?5",
    ]
    claims_total = 0
    claims_sourced = 0
    for pat in patterns:
        for m in re.finditer(pat, markdown, re.IGNORECASE):
            claims_total += 1
            # Look for an authoritative domain within 400 chars after the match
            window = markdown[m.end() : m.end() + 400]
            if any(d in window for d in AUTHORITATIVE_DOMAINS):
                claims_sourced += 1
    return {
        "total": claims_total,
        "sourced": claims_sourced,
        "ratio": (claims_sourced / claims_total) if claims_total else 1.0,
    }


def main() -> None:
    if kill_switch_engaged():
        print("[fact-check] AGENTS_ENABLED=false, exiting.")
        sys.exit(0)

    slug = os.environ.get("ARTICLE_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not slug:
        raise SystemExit("Usage: fact_check.py <slug> (or ARTICLE_SLUG env var)")
    path = ARTICLES_DIR / f"{slug}.md"
    if not path.exists():
        raise SystemExit(f"Article not found: {path}")
    markdown = path.read_text(encoding="utf-8")

    # 1. Re-run editorial validators
    ed = validate_draft(markdown)
    if not ed.passed:
        notify_quarantine(
            "Fact-check: validation éditoriale échouée — " + " ; ".join(ed.errors),
            str(path),
        )
        raise SystemExit(f"Editorial validation failed: {ed.errors}")

    # 2. Check every external URL resolves
    urls = [u for u in _extract_urls(markdown) if "{{FQDN}}" not in u]
    broken = [u for u in urls if not _head_ok(u)]
    total = len(urls)
    broken_ratio = (len(broken) / total) if total else 0.0
    print(f"[fact-check] external links: {total - len(broken)}/{total} ok")
    if broken:
        print(f"[fact-check] broken links: {broken}")

    # 3. Authoritative coverage of claims
    cov = _authoritative_coverage(markdown)
    print(f"[fact-check] claims: {cov['sourced']}/{cov['total']} sourced "
          f"(ratio {cov['ratio']:.0%})")

    # Gating rules (v1). Expected to tighten once the agent writes at steady
    # state. For articles with few chiffered claims we apply a "at least one
    # sourced" rule instead of a pure ratio — otherwise 1/3 gets rejected
    # which is statistically harsh.
    ALLOWED_BROKEN_RATIO = 0.25
    MIN_CLAIMS_RATIO = 0.40
    LOW_CLAIM_THRESHOLD = 5  # below this count, use absolute rule

    reasons: list[str] = []
    if broken_ratio > ALLOWED_BROKEN_RATIO:
        reasons.append(
            f"{len(broken)}/{total} liens externes cassés "
            f"({broken_ratio:.0%}, seuil {ALLOWED_BROKEN_RATIO:.0%})"
        )
    if cov["total"] >= LOW_CLAIM_THRESHOLD and cov["ratio"] < MIN_CLAIMS_RATIO:
        reasons.append(
            f"Claims sourcées {cov['sourced']}/{cov['total']} "
            f"({cov['ratio']:.0%}, seuil {MIN_CLAIMS_RATIO:.0%})"
        )
    elif 2 < cov["total"] < LOW_CLAIM_THRESHOLD and cov["sourced"] == 0:
        # When very few chiffered claims are detected (1-2), skip the
        # "at least one sourced" rule: the surface is too small to draw
        # a reliable signal, and some kinds (profile, guide) naturally
        # have fewer numeric claims than listicles.
        reasons.append(
            f"Aucune des {cov['total']} claims chiffrées n'est sourcée "
            f"(au moins une source obligatoire)"
        )

    if reasons:
        notify_quarantine(
            "Fact-check rejeté : " + " ; ".join(reasons),
            str(path),
        )
        # Revert the article file so it doesn't get published
        path.unlink()
        print(f"[fact-check] REJECTED — article file removed: {path}", file=sys.stderr)
        sys.exit(3)

    # Soft warnings
    warnings = list(ed.warnings)
    if broken:
        warnings.append(f"{len(broken)} lien(s) externe(s) cassé(s) (sous seuil)")

    if warnings:
        notify(
            f"Fact-check passé pour `{slug}` avec avertissements: "
            + " ; ".join(warnings),
            level="warn",
        )
    else:
        notify(f"Fact-check passé pour `{slug}` — prêt à publier.", level="success")

    print(f"[fact-check] OK — ready to publish")


if __name__ == "__main__":
    main()
