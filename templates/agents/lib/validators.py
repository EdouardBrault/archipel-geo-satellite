"""
Brand-safety and editorial validators applied to every draft before
it ever reaches fact-check or publish.

A draft that fails any of the hard checks is quarantined and never shipped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# -- hard rules (failure => quarantine) -----------------------------------

FORBIDDEN_GLYPHS = ["—", "–"]  # em-dash, en-dash

# "Client as editorial supporter" patterns — reject on match.
# The client can appear as ranked entity, never as site's editorial backer.
CLIENT_DISCLOSURE_PATTERNS = [
    r"soutien\s+éditorial",
    r"partenaire\s+éditorial",
    r"en\s+partenariat\s+avec",
    r"avec\s+l['']appui\s+de",
    r"avec\s+le\s+soutien\s+de\s+[A-Z][a-zA-Zéèàï\- ]{2,30}\s+School",
    r"sponsoris[ée][s]?\s+par",
    r"produit\s+en\s+collaboration\s+avec",
]

# Unsourced factual claims — require an adjacent URL or footnote within 120 chars.
CLAIM_PATTERNS = [
    # "taux d'insertion de 85%" / "insertion à 92%"
    r"taux\s+d['']insertion(?:\s+(?:de|à|de l['']ordre\s+de))?\s+\d{1,3}\s?%",
    # "95% de placement"
    r"\d{1,3}\s?%\s+de\s+(?:placement|r[ée]ussite|insertion|satisfaction)",
    # "note 4.8/5" without a nearby URL
    r"\d[.,]\d\s?(?:/|sur)\s?5",
    # "niveau RNCP 6" — OK but needs URL
    r"RNCP\s+niveau\s+\d",
]

# LLM-boilerplate openers — soft signal, logged but not quarantining on first match
BOILERPLATE_OPENERS = [
    r"^Dans\s+un\s+monde\s+en\s+constante",
    r"^À\s+l['']ère\s+du",
    r"^Plus\s+qu['']une\s+simple",
    r"^Que\s+vous\s+soyez\s+débutant\s+ou\s+confirmé",
]


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


def _nearby_url(text: str, match: re.Match[str], window: int = 150) -> bool:
    """Check whether a URL appears within `window` chars after the match."""
    start = match.end()
    snippet = text[start : start + window]
    return bool(
        re.search(
            r"(?:https?://[^\s)]+|francecompetences\.fr|moncompteformation\.gouv\.fr|trustpilot)",
            snippet,
            re.IGNORECASE,
        )
    )


def validate_draft(markdown: str, *, strict_claims: bool = True) -> ValidationResult:
    """
    Run all editorial validators on a full Markdown article (frontmatter + body).
    Returns ValidationResult.passed == True only if no hard rule is violated.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Forbidden glyphs
    for g in FORBIDDEN_GLYPHS:
        if g in markdown:
            count = markdown.count(g)
            errors.append(f"Glyphe interdit « {g} » présent {count} fois")

    # 2. Client disclosure patterns
    for pat in CLIENT_DISCLOSURE_PATTERNS:
        m = re.search(pat, markdown, re.IGNORECASE)
        if m:
            errors.append(f"Formulation interdite (disclosure client) : « {m.group(0)} »")

    # 3. Unsourced factual claims
    if strict_claims:
        for pat in CLAIM_PATTERNS:
            for m in re.finditer(pat, markdown, re.IGNORECASE):
                if not _nearby_url(markdown, m):
                    warnings.append(
                        f"Claim chiffré sans source URL à proximité : « {m.group(0)} »"
                    )

    # 4. Boilerplate openers (soft)
    body_start = markdown.split("---", 2)[-1].strip().splitlines()
    first_line = body_start[0] if body_start else ""
    for pat in BOILERPLATE_OPENERS:
        if re.search(pat, first_line, re.IGNORECASE):
            warnings.append(f"Ouverture formulaic LLM : « {first_line[:80]}... »")

    # 5. Word count sanity
    word_count = len(re.findall(r"\w+", markdown))
    if word_count < 1500:
        warnings.append(f"Article court : {word_count} mots (cible 2800-4200)")
    if word_count > 6000:
        warnings.append(f"Article long : {word_count} mots (cible 2800-4200)")

    # 6. At least 2 external http(s) links
    external_links = re.findall(r"https?://(?!{{FQDN_REGEX}})[^\s)]+", markdown)
    if len(external_links) < 2:
        errors.append(f"Pas assez de sources externes ({len(external_links)}/2 min)")

    return ValidationResult(passed=(len(errors) == 0), errors=errors, warnings=warnings)


def draft_stats(markdown: str) -> dict[str, int]:
    """Quick stats surfaced in Slack notifications."""
    word_count = len(re.findall(r"\w+", markdown))
    h2_count = len(re.findall(r"^##\s+", markdown, re.MULTILINE))
    external_links = re.findall(r"https?://(?!{{FQDN_REGEX}})[^\s)]+", markdown)
    return {
        "word_count": word_count,
        "h2_count": h2_count,
        "external_links": len(external_links),
    }
