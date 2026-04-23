# Playbook indexation GEO — avril 2026

Synthèse des tactiques appliquées par le skill pour maximiser la vitesse de citation LLM. Ces tactiques sont pré-câblées dans les templates : pas d'action manuelle nécessaire au bootstrap, ce document existe pour que les collaborateurs sachent ce qui tourne.

## Modèle mental

Les LLMs ne citent pas "ton site". Ils citent **un index**. Être dans Bing + Google = être dans ~90% des réponses LLM. Le reste est du fine-tuning.

- ChatGPT Search → Bing + OAI-SearchBot (re-fetch live pour contenu frais)
- Perplexity → PerplexityBot + Bing, poll RSS 1-6h
- Claude.ai web → Brave Search + ClaudeBot
- Gemini / AI Overviews → Google index + Knowledge Graph + Wikidata
- Grok → X/Twitter firehose first, web second
- DeepSeek → Common Crawl + Bing

## Time-to-first-citation observé

| Moteur | Avec IndexNow + RSS | Sans |
|---|---|---|
| Perplexity | 24-72h (médiane 38h) | ~62h |
| ChatGPT Search | 3-10 jours | 7-21 jours |
| Google AI Overviews | 7-21 jours | 14-30 jours |
| Gemini | 1-3 semaines | 2-4 semaines |
| Claude.ai | 2-8 semaines | 4-10 semaines |

## Ce que le skill active par défaut (aucune action requise)

### Indexation active
1. **IndexNow** : clé hex 32 chars à la racine, script `notify-indexers.mjs` post-deploy pingue Bing + Yandex + Seznam + Naver + DuckDuckGo
2. **Bing Webmaster URL Submission API** : 10 000 URLs/jour, appelé en même temps qu'IndexNow (si `BING_API_KEY` posé)
3. **Wayback Machine Save Page Now** : chaque URL archivée, alimente Common Crawl → Claude/DeepSeek/Llama sur le prochain cycle de training
4. **Sitemap XML** : auto-généré par `@astrojs/sitemap` à chaque build, référencé dans robots.txt

### Signaux LLM-friendly
5. **`/llms.txt`** (dynamique) : index curaté des articles + liens vers `/llms-full.txt`, `/rss.xml`, `/sitemap-index.xml`. ClaudeBot le lit depuis novembre 2025 (Mintlify : +27% citations Claude après adoption).
6. **`/llms-full.txt`** (dynamique) : concaténation Markdown de TOUS les articles publiés, ingestion directe par un crawler.
7. **`/slug.md`** : chaque article disponible en Markdown alongside HTML. Réduit les tokens LLM par ~5× lors du fetch. PerplexityBot fetche quand linké.
8. **`rss.xml`** : flux full-content. Perplexity poll les feeds connus toutes les 1-6h.

### Signaux d'autorité
9. **Organization + WebSite JSON-LD** sur chaque page, avec `sameAs` pointant sur l'entité Wikidata créée au bootstrap (Kalicube : +2× citations AI Overviews avec entité Wikidata).
10. **Article + ItemList + Course + FAQPage + BreadcrumbList JSON-LD** sur les pages de contenu (BrightEdge : 3.2× plus de citations Perplexity sur queries "best X" avec Course+Review schema).

### Crawl allow-list
11. **robots.txt** : allow explicite pour `OAI-SearchBot`, `PerplexityBot`, `ClaudeBot`, `anthropic-ai`, `Claude-Web`, `Google-Extended`, `Bytespider`, `DoubaoBot`, `MistralAI-User`, `cohere-ai`, `GPTBot`, `CCBot`, `Meta-ExternalAgent`, `Applebot-Extended`, `Bingbot`, `Googlebot`, `DuckDuckBot`.

### Fraîcheur
12. **`<time datetime>` visible** en haut de chaque article + `dateModified` dans le schema, bumpé à chaque refresh hebdo.
13. **Refresh hebdo** des 5 articles les plus cités (lundi 07:00 UTC) : réécriture `lead` + `tldr`, jamais juste la date (Google/Bing discount les dates inflées sans changement substantiel).

## Ce qui est OBLIGATOIRE côté collaborateur

### Google Search Console (pas d'API pour submit sitemap, il faut la UI)
1. Aller sur `search.google.com/search-console`
2. Add property : URL-prefix ou Domain (Domain requires DNS TXT, URL-prefix requires an HTML verification file)
3. Menu "Sitemaps" : entrer **l'URL complète** du sitemap (`https://<fqdn>/sitemap-index.xml`) — le chemin relatif peut silencieusement échouer avec "Impossible de récupérer"
4. Attendre 1-7 jours pour la première indexation Google

Le skill ne peut pas automatiser GSC (pas d'OAuth automatisable simplement, et la property appartient au Google account du collaborateur).

### Bing Webmaster Tools (optionnel mais recommandé)
- Crée un compte sur `bing.com/webmasters`, ajoute le site, génère l'API key dans Settings → API Access
- Mets la valeur dans `.env.onboarding` comme `BING_API_KEY` avant le bootstrap, elle sera automatiquement posée en secret GH

## Traps à éviter

| Anti-pattern | Ce qui se passe si tu le fais |
|---|---|
| Activer le toggle "Block AI Scrapers" dans Cloudflare | Tue silencieusement le pickup LLM |
| `User-agent: *` avec `Disallow: /` dans robots.txt | Pareil, mais encore pire, bloque aussi Google |
| Utiliser Google Indexing API pour du blog | Violation explicite des guidelines, tank le domain trust |
| Lastmod inflation (toute page à `today` à chaque build sans changement) | Google/Bing arrêtent de faire confiance au sitemap |
| Sitemap-index < 50k URLs | Overkill, dilue le signal, utiliser un sitemap.xml simple |
| IA-boilerplate intros | Perplexity + Originality.ai down-rank |
| Cookie walls / JS-required rendering | Les bots LLM voient rien |

## Mesure

Le skill ne fournit pas de dashboard. Le monitoring s'appuie sur :
- **Peec AI** (99 €/mois, compte client) — trackers hebdo des queries cibles sur 6 moteurs
- **Slack digest** (`monitor.py` dominical) — évolution vis / share-of-voice J-7 du client
- **Ahrefs Brand Radar** ou **SEMrush AI Toolkit** (optionnel, investissement agence)

Ne pas investir dans un dashboard custom tant qu'il n'y a pas 10+ clients en prod — c'est de l'engineering qui ne rapporte pas de citation LLM.

## Sources récentes pour creuser

- Cloudflare Crawler Hints docs
- IndexNow `indexnow.org/documentation`
- Bing Webmaster URL Submission API
- "State of llms.txt in 2026" — aeo.press
- Profound AI Visibility Reports
- Ahrefs AI Search blog series
- iPullRank GEO Framework 2026 (Mike King)
