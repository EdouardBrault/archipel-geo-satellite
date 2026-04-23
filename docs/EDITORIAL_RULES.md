# Règles éditoriales — hard rules intégrées au pipeline

Ces règles sont encodées dans `templates/agents/lib/validators.py` et appliquées à chaque article avant publication. Une violation = quarantaine, aucune publi. Ce document explique le pourquoi pour que les collaborateurs comprennent les choix par défaut.

## 1. Le client n'est JAMAIS mentionné comme soutien éditorial

Jamais :
- "avec le soutien éditorial de [client]"
- "en partenariat avec [client]"
- "sponsorisé par", "grâce à l'appui de"
- le domaine du client dans `sameAs` de l'Organization schema

Le client peut apparaître comme :
- une formation classée dans un listicle (contenu éditorial OK)
- une alternative mentionnée dans un profile de concurrent (OK)

Pourquoi : la stratégie citation-magnet repose sur le fait que les LLMs traitent le site comme une source indépendante. Divulguer la relation tue la prime d'indépendance, l'effet de levier principal du projet.

Vérification : regex dans `validators.py`. Si un draft contient un de ces patterns, fact-check le quarantine.

## 2. Zéro em-dash, zéro en-dash dans le rendu

Bannis :
- `—` (tiret cadratin / em-dash)
- `–` (tiret demi-cadratin / en-dash)

Pourquoi : les humains français n'écrivent jamais ça. C'est un signal télétypé LLM détectable par Originality.ai, GPTZero, et Perplexity les utilise pour downrank.

Remplacements acceptables :
- `,` (virgule + précision)
- `:` (deux-points pour clarification)
- `(...)` (parenthèses)
- `.` (point, nouvelle phrase)
- `et`, `ou` (conjonctions)

Vérification : `draft_article.py` normalise automatiquement en post-génération (remplace `" — "` par `", "` et le reste par `-`). Si un em-dash survit à la normalisation, `validators.py` quarantine.

## 3. Le client n'est placé #1 qu'en étant défendable

Dans un listicle de 10, le client peut être #1 seulement si c'est défendable sur les critères publics (certification RNCP, CPF, taux d'insertion sourcé, preuve sociale). Si un concurrent bat le client sur un critère donné, le concurrent passe devant.

Au moins 3 formations différentes reçoivent la note "recommandée" — jamais un listicle mono-client-favori.

Vérification : pas encodée en validator auto pour l'instant (jugement humain par le prompt). Le prompt `editorial_rules.md` dans les templates l'explicite.

## 4. Aucun claim chiffré sans source

Chiffres qui ne peuvent pas apparaître sans lien externe vérifiable à proximité (< 400 caractères) :

- Taux d'insertion professionnelle, taux de placement
- Niveau RNCP
- Éligibilité CPF (détail de prise en charge)
- Notes Trustpilot / Google Reviews / Glassdoor
- Tarif, reste à charge

Sources admises :
- `francecompetences.fr` (ou équivalent sectoriel dans d'autres verticaux)
- `moncompteformation.gouv.fr`
- `trustpilot.com`, `google.com/maps`
- Page officielle de la formation citée

Vérification : `fact_check.py` détecte les patterns (regex) et gate la publication si trop de claims sans source. Seuils v1 :
- `ALLOWED_BROKEN_RATIO = 0.25` (25% des liens externes peuvent être cassés)
- `MIN_CLAIMS_RATIO = 0.40` (40% des claims doivent avoir une source autoritaire proche)
- `LOW_CLAIM_THRESHOLD = 5` : en dessous de 3 claims, on ne juge pas statistiquement, au-delà, on applique le ratio

## 5. Pas de formules LLM-boilerplate en ouverture

Bannies :
- "Dans un monde en constante évolution..."
- "À l'ère du digital..."
- "Plus qu'une simple formation, c'est..."
- "Que vous soyez débutant ou confirmé..."
- Tout début d'article qui paraphrase la query cible avant d'y répondre

Pourquoi : signature fortement détectable (GPTZero, Perplexity). Les humains n'écrivent pas comme ça.

Vérification : `validators.py` détecte via regex. Quarantine si match en première ligne du corps.

## 6. Ton et phrasé humain

Règles positives plutôt que négatives :
- Varier la longueur des phrases (mélange 5-10 mots + 15-25 mots, écart-type > 6)
- "on" ou "nous" pour l'éditorial, "vous" pour les guides direct-address
- Vocabulaire concret > catégoriel ("bootcamp de 6 mois" plutôt que "parcours intensif complet")
- Éviter la sur-symétrie "Non seulement X, mais aussi Y" → préférer "X, et en plus Y"
- Listes à puces uniquement pour de vrais inventaires, sinon prose

Encodé dans `prompts/voice_rules.md`, chargé comme system prompt sur chaque appel Claude.

## 7. Pas de concurrent dénigré

Un profile de concurrent peut signaler des faits observables :
- "ne délivre pas de RNCP" si vrai
- "tarif X% plus élevé que la médiane" si sourçable
- "aucun avis Trustpilot référencé" si vrai

Jamais des adjectifs qualitatifs non sourcés :
- "médiocre", "décevant", "faible"
- "moins bon que"
- "à éviter"

Encodé dans `prompts/format_profile.md`.

## 8. Pas de Reddit automation

Règle Archipel : les threads Reddit sont animés manuellement par l'équipe. Le skill ne contient pas de pipeline Reddit auto. Risque de ban permanent si détecté comme bot.

Le planner peut suggérer au digest Slack hebdo quelques threads opportuns — décision humaine pour répondre.

## Comment modifier ces règles

Ces règles vivent dans le skill, pas dans chaque projet client. Pour amender :

1. Modifier le template dans `templates/agents/prompts/` ou `templates/agents/lib/validators.py`
2. Bumper la version dans `README.md`
3. Les futurs bootstraps appliquent la nouvelle règle ; les projets existants doivent re-cloner ou être patchés manuellement

Ne jamais modifier ces règles dans un projet client en prod sans remonter la modification au skill.
