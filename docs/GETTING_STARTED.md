# Getting started — collaborator walkthrough

Tu es un collaborateur Archipel qui vient de signer un nouveau client GEO. Ce document te fait passer de zéro à un site satellite en production, en ~30 minutes de ton temps effectif (le reste, c'est le bootstrap qui tourne et la propagation DNS).

## Étape 1 : pré-requis locaux (à faire une seule fois)

```bash
# Binaries
brew install gh yq jq            # ou équivalent sur ton OS
# Node ≥ 22 : https://nodejs.org/
# Python ≥ 3.11 : https://www.python.org/downloads/

# Auth
gh auth login                    # choisir GitHub.com, HTTPS, OAuth web
npm i -g wrangler && wrangler login
```

## Étape 2 : installe le skill

```bash
git clone https://github.com/EdouardBrault/archipel-geo-satellite \
  ~/.claude/skills/archipel-geo-satellite
```

Claude Code va automatiquement le détecter. Tu peux vérifier avec :

```bash
ls ~/.claude/skills/
```

## Étape 3 : prépare le `client.yaml`

```bash
cp ~/.claude/skills/archipel-geo-satellite/client.example.yaml ./acme-client.yaml
# édite le fichier avec les données du client
```

Les champs obligatoires, dans l'ordre de ce qui bloque si absent :

| Champ | Exemple | Où le trouver |
|---|---|---|
| `slug` | `acme` | inventer, court, kebab-case |
| `integrations.github.owner` / `repo` | `EdouardBrault / acme-rank-ly` | `gh` authenticated user, nom du repo à créer |
| `integrations.cloudflare.pages_project` | `acme-rank-ly` | souvent identique au nom du repo |
| `integrations.slack.channel` | `#rank-ly-acme` | crée le canal + le webhook avant le bootstrap, cf. `SLACK_WEBHOOK.md` |
| `domain.subdomain` (si mode rankly) | `acme` | le sous-domaine final sera `acme.rank-ly.com` |
| `promoted_brand.name` + `url` | `ACME School` / `https://…` | nom officiel du client + URL principale |
| `topic_area.*` | mots-clefs du business du client | brief client |
| `competitors` | 8-12 entrées avec `name`, `url`, `domains` | audit Peec du client |

Laisse les valeurs par défaut pour : `ranking_methodology.weights`, `voice`, `cadence`.

## Étape 4 : prépare les variables d'environnement

Crée un fichier `.env.onboarding` local (jamais commit) :

```bash
# Clés agence (réutilisables entre clients)
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export CLOUDFLARE_ACCOUNT_ID="0dac96ca277df1196e98a5ee12e46f0d"
export CLOUDFLARE_API_TOKEN="cfut_..."
export BING_API_KEY="..."                                # optionnel mais recommandé
export WIKIDATA_BOT_USER="Archipel-editorial@archipel-agent"
export WIKIDATA_BOT_PASS="..."

# Clés spécifiques client (à collecter pour chaque nouveau client)
export PEEC_AI_API_KEY="skp-..."                         # clé project-scoped du client dans Peec
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."

# Optionnel : automatisation DNS IONOS si le parent est rank-ly.com
export IONOS_API_KEY="prefix.secret"
```

Puis `source ./.env.onboarding`.

## Étape 5 : lance Claude

Ouvre Claude Code dans un shell où les vars sont chargées, et tape :

> Onboard a new Archipel GEO client, config at `./acme-client.yaml`.

Claude va :

1. Détecter le skill `archipel-geo-satellite`
2. Lire `client.yaml`, vérifier les pré-requis
3. Lancer `scripts/bootstrap.sh`
4. Te rapporter l'état à chaque étape

Le bootstrap lui-même prend ~5 min. Les étapes qui restent manuelles :

- **DNS** : si `IONOS_API_KEY` n'est pas dans ton env, le script t'affiche le CNAME exact à coller dans le registrar du client. 30 sec.
- **Propagation + SSL** : 5 à 15 minutes. Le site est servi sur `<cf-project>.pages.dev` pendant ce temps.

## Étape 6 : vérifie en prod

Une fois le DNS propagé :

```bash
curl -sI https://$FQDN/ | head -3
```

Attendu : `HTTP/2 200`. Le site est live, le premier article est en cours de génération par le workflow `write-and-publish.yml`.

## Étape 7 : handover au client (optionnel)

- Slack : invite le client dans `#rank-ly-<slug>` (en lecture seule si tu ne veux pas qu'il modifie)
- Dashboard : partage-lui l'URL du site, pas le repo GitHub
- Rapport hebdo : il tombe dans Slack le dimanche (digest `monitor.py`)

## Troubleshooting

| Erreur | Cause | Fix |
|---|---|---|
| `gh auth status` refuse | pas logué ou scope insuffisant | `gh auth login` puis `gh auth refresh -s workflow` |
| `wrangler whoami` refuse | pas logué sur Cloudflare | `wrangler login` |
| `Creating Github Deployment failed` | warning non bloquant | ignorer, le deploy CF a réussi |
| workflow `write-and-publish` échoue au fact-check | article généré avec trop de claims non sourcées | normal en v1, le gate se détend, re-trigger manuel |
| CNAME invalide dans GSC | cache Google négatif | soumettre l'URL complète `https://<fqdn>/sitemap-index.xml`, retry 24h |

## Quand faire une session manuelle

- Modifier la file `planner_priorities.yaml` si la couverture sémantique doit pivoter (ex: le client change son positionnement).
- Revoir le contenu du seed article initial si le premier draft est insuffisant.
- Ajuster les seuils `fact_check.py` (`ALLOWED_BROKEN_RATIO`, `MIN_CLAIMS_RATIO`) après quelques semaines de data.

Toute autre modification (ajouter un nouveau type d'article, changer la méthodologie de notation…) doit remonter dans le skill, pas rester locale au repo du client.
