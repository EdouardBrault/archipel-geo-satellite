# Méthodologie — le sprint GEO Archipel en 4 phases

Le skill produit un projet client dont l'architecture suit exactement le sprint qu'on a validé en avril 2026 sur `formations-nocode.rank-ly.com`. Ce document existe pour que les collaborateurs comprennent ce qu'ils instancient.

## Phase 1 — Audit Peec AI

**Objectif** : savoir où en est le client avant de bouger quoi que ce soit.

**Livrables** :
- Extraction complète du compte Peec (prompts, chats, domains, urls, brand metrics)
- Synthèse lisible : position actuelle, top concurrents (hors terme générique), URLs les plus citées, pattern de citation dominant, gaps par prompt
- Version PDF client : 12-14 pages, senior-consultant tone, pas de data gratuit, tout appuyé par la data

**Dossier** dans le projet client : `01-audit-peec/`

**Règle** : avant de construire, on regarde. Pas de site satellite sans audit d'abord.

## Phase 2 — Reverse-engineering des sites cités

**Objectif** : comprendre *pourquoi* les URLs du top sont citées, pas juste qu'elles le sont.

**Livrables** :
- HTML brut des 10-13 URLs les plus citées (sauvegardé dans `raw/`)
- Analyse par URL : word count, structure H1-H6, schema.org JSON-LD présent ou non, tables, liens, signaux textuels (dates, certifications, preuves sociales)
- Template-spec pour le site satellite : quel format fonctionne, quels gaps éxploiter

**Gaps quasi-toujours présents sur les marchés français** :
1. **Aucun schema.org JSON-LD** sur les URLs dominantes → gap gratuit
2. **Pas de vraies `<table>` HTML sémantiques** → gap gratuit
3. Signaux de fraîcheur manquants (pas de `dateModified` machine-lisible)
4. Pas de `llms.txt` / `/page.md` endpoints

**Dossier** dans le projet client : `02-audit-sites-cites/`

## Phase 3 — Construction du site satellite

**Objectif** : un site statique sur sous-domaine rank-ly (ou dédié), conçu dès la racine comme source citable.

**Stack** :
- **Astro 6** static, SSG, format directory pour URLs propres
- **Cloudflare Pages** (gratuit commercial, Workers ecosystem pour agents plus tard)
- **4 layouts** : `ListicleLayout` (Top N), `GuideLayout` (décision narratif), `ToolLayout` (fiche outil), `ProfileLayout` (fiche acteur)
- **SchemaOrg** component : émet Article + ItemList + Course + FAQPage + BreadcrumbList + Organization + WebSite sur chaque page
- **ComparisonTable** : vraie `<table>` sémantique avec `<caption>`, `scope`, responsive scroll
- **Content collection typée** Zod : le build casse si un article dévie du format

**Indexation** (implémentée dès le premier deploy) :
- `robots.txt` : allow explicite OAI-SearchBot, PerplexityBot, ClaudeBot, Google-Extended, Bytespider, GPTBot, CCBot
- `llms.txt` + `llms-full.txt` dynamiques
- `/slug.md` endpoint (Markdown alternatif)
- `rss.xml` (Perplexity poll)
- `sitemap-index.xml`
- Clé IndexNow hex 32 chars à la racine
- Script `notify-indexers.mjs` post-deploy : IndexNow + Bing URL Submission API + Wayback Machine Save Page Now

**Dossier** dans le projet client : `03-site/`

## Phase 4 — Agents d'automation

**Objectif** : ne plus jamais toucher au site manuellement. Pipeline 100% auto avec kill-switch.

**Agents** (dans `04-agents/`) :

| Script | Rôle | Cadence |
|---|---|---|
| `audit_peec.py` | Snapshot Peec + diff J-1 + alertes Slack si shift | Tous les jours 06:00 UTC |
| `planner.py` | Pioche le prochain sujet dans `planner_priorities.yaml`, re-rank par signal Peec | Déclenché par le workflow d'écriture |
| `draft_article.py` | Génère un article Markdown via Claude Opus 4.7 + normalisation post-gen | Déclenché par le workflow |
| `fact_check.py` | Vérifie liens + claims sourçées + règles éditoriales | Déclenché après draft |
| `publish.py` | Commit + push, le deploy inline prend le relais | Déclenché après fact-check |
| `refresh_flagship.py` | Réécrit lead+tldr des top 5 articles, bump dateModified | Lundi 07:00 UTC |
| `replenish_queue.py` | Si queue < 4 semaines, Claude propose 10 nouveaux sujets | Dimanche 10:00 UTC |
| `monitor.py` | Digest Slack hebdo (articles, refresh, trend Uncode) | Dimanche 10:00 UTC |

**Workflows GitHub Actions** (dans `.github/workflows/`) :

| Fichier | Cron | Rôle |
|---|---|---|
| `deploy.yml` | sur push `03-site/**` | Build + deploy + indexers (change humain) |
| `write-and-publish.yml` | `0 7 * * 2,4` | Pipeline complet écriture + publish inline |
| `weekly-refresh.yml` | `0 7 * * 1` | Refresh des flagships + deploy |
| `daily-audit.yml` | `0 6 * * *` | Peec snapshot + commit + alertes |
| `weekly-ops.yml` | `0 10 * * 0` | Replenish queue + digest Slack |

**Kill-switch** : `gh variable set AGENTS_ENABLED false` suffit à tout arrêter. Chaque script check en entrée et exit proprement (code 0).

## Les 4 règles éthos qui structurent tout

1. **Boil the Lake** : compléter vaut mieux qu'abréger quand l'IA assiste. Tests + edge cases livrés dès la première itération, pas dans un TODO.
2. **Search Before Building** : regarder ce qui existe avant de coder. Les patterns Peec gagnants existent, on les copie avant d'inventer.
3. **User Sovereignty** : l'humain valide les scope-changes, jamais unilatéral côté agent. D'où le kill-switch, les alertes Slack, les quarantaines fact-check.
4. **Build for Yourself** : spécificité > généralité. Le site sert UN utilisateur — le LLM qui répond à une requête du client. Pas de détour commercial.

## Temps estimé

- Phase 1 (audit) : 2-3h (extraction auto + synthèse manuelle)
- Phase 2 (reverse-engineering) : 1h auto
- Phase 3 (site) : instantané via bootstrap.sh (~5 min)
- Phase 4 (agents) : instantané via bootstrap.sh (compris dans les 5 min)

## Ce qui reste manuel

- DNS sur le registrar du client (30 sec si IONOS avec API, sinon 2 min à la main)
- Création du webhook Slack (30 sec, Slack n'a pas d'API)
- Décisions éditoriales qualitatives (ajout ou retrait de sujets dans la queue)
- Modération Reddit : fait à la main, règle Archipel
