---
name: archipel-geo-satellite
description: End-to-end onboarding for an Archipel GEO client: scaffolds the Astro satellite site, agents, cron workflows and deploys to Cloudflare Pages from a single client.yaml. Invoke on new client projects.
---

# Archipel GEO Satellite — skill de provisioning client

Ce skill industrialise la création de sites satellites citation-magnet que l'agence Archipel Marketing déploie pour ses clients. Il réplique à l'identique la stack prouvée sur `formations-nocode.rank-ly.com` (Astro + Cloudflare Pages + agents quotidiens + audit Peec + indexation IndexNow/Bing/Wayback), paramétrée pour le business du nouveau client.

## Quand invoquer ce skill

Un collaborateur Archipel :
- démarre un nouveau projet client GEO (positionnement citations LLM)
- a besoin d'un site satellite indépendant sur un sous-domaine de `rank-ly.com` ou sur un domaine dédié
- veut la même chaîne automatique (2 articles/semaine, refresh hebdo, audit Peec quotidien, digest Slack)

Ne pas invoquer pour :
- modifier un site existant (utiliser directement les scripts dans le repo du client)
- onboarder plusieurs clients en batch (une prochaine itération couvrira ce cas)

## Pré-requis locaux (le script les vérifie et échoue vite sinon)

- `gh` CLI authentifié (`gh auth status` doit retourner OK)
- `wrangler` authentifié (`wrangler whoami`)
- `python3` ≥ 3.11, `node` ≥ 22, `npm`
- `yq` (parser YAML) : `brew install yq` ou binaire équivalent
- Accès au compte Peec AI du client + clé API projet-scoped
- Webhook Slack créé dans `#rank-ly-<slug>` (Slack n'a pas d'API de création, se reporter à `docs/SLACK_WEBHOOK.md`)

## Comment Claude doit exécuter ce skill

Étape par étape, sans interrompre l'utilisateur sauf si une info manque :

1. **Trouver ou construire le `client.yaml`**
   - Si l'utilisateur indique un chemin (`--config`), lire ce fichier
   - Sinon, lire `client.example.yaml`, demander les valeurs manquantes en une seule passe (ne pas enchaîner 10 questions), puis écrire le résultat dans le cwd sous le nom `client.yaml`

2. **Vérifier les pré-requis**
   - Exécuter `./scripts/check-prereqs.sh` et lire son output
   - Si échec, afficher clairement le binaire manquant et stopper

3. **Lancer le bootstrap**
   - `./scripts/bootstrap.sh client.yaml` fait tout le reste sans question
   - Le script log chaque étape (scaffolding, git, Cloudflare, secrets, Wikidata, premier article)

4. **Passer la main pour les deux étapes inhérentes**
   - DNS : afficher les valeurs CNAME à poser chez le registrar (le script tente IONOS automatiquement si `IONOS_API_KEY` est dans l'env)
   - Vérification HTTPS après 5-10 min (Cloudflare émet le certif)

5. **Annoncer le succès**
   - URL finale live
   - Lien vers le repo GitHub
   - Lien vers le dashboard Cloudflare Pages
   - Rappel : crédentials à rotater (Wikidata bot password notamment)

## Structure du skill

```
archipel-geo-satellite/
├── SKILL.md                    # ce fichier
├── README.md                   # présentation GitHub
├── LICENSE                     # proprietary, all rights reserved
├── client.example.yaml         # template des inputs attendus
├── templates/
│   ├── site/                   # Astro site (layouts, components, pages)
│   ├── agents/                 # 04-agents/ (draft, fact-check, publish, etc.)
│   ├── workflows/              # .github/workflows/*
│   └── root/                   # CLAUDE.md, .gitignore, .env.example, README
├── scripts/
│   ├── bootstrap.sh            # orchestration end-to-end
│   ├── check-prereqs.sh        # vérif binaires + auth
│   ├── instantiate.py          # copie des templates + substitutions
│   ├── wikidata.py             # création de l'entité Wikidata
│   └── post-gh-secrets.sh      # pose tous les secrets GH via gh CLI
└── docs/
    ├── GETTING_STARTED.md      # walkthrough collaborateur
    ├── METHODOLOGY.md          # phases 1-4 en transférable
    ├── EDITORIAL_RULES.md      # no-client, no-em-dash, voice
    ├── INDEXATION_PLAYBOOK.md  # GEO indexation 2026
    ├── DNS_IONOS.md            # config CNAME IONOS (et génériques)
    └── SLACK_WEBHOOK.md        # création webhook (étape UI inévitable)
```

## Sécurité

- Aucun secret n'est stocké dans le skill. Tous transitent par l'environnement local (`.env.onboarding`) ou par `gh secret set`
- Les templates ne contiennent **jamais** de slug client (pas d'`uncode`, pas de `formations-nocode.rank-ly.com` en dur). Tout est paramétré depuis `client.yaml`
- Le repo GitHub créé pour un client est **privé par défaut**
- Le bootstrap n'écrit jamais de `.env` réel dans le repo client ; il positionne uniquement les secrets GH via API
- Les identifiants agence (bot Wikidata, token Cloudflare, clé Anthropic) sont fournis via env vars à l'invocation, jamais persistés sur disque autrement que dans `~/.config/` ou Keychain

## Ce que le skill ne fait pas

- Ne crée pas de compte Cloudflare/GitHub/Slack pour toi (prérequis)
- Ne gère pas la facturation Anthropic/Peec du client (hors scope)
- N'automatise pas le post Reddit (règle Archipel : humain dans la boucle)
- Ne touche pas aux sites de clients existants (scaffolding seulement)
