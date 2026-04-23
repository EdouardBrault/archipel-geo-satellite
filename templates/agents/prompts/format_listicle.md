# Spec de format — listicle « Top N »

Un article de type `listicle` respecte la structure suivante.

## Frontmatter YAML (obligatoire, validé par `content.config.ts`)

```yaml
---
title: "<H1 de l'article, inclut toujours l'année en cours>"
description: "<150-200 caractères, inclut la query cible en langue naturelle>"
slug: "<slug-url-safe-sans-accents>"
kind: "listicle"
datePublished: <YYYY-MM-DD>
dateModified: <YYYY-MM-DD>
status: "published"
lead: |
  <150-250 mots de paragraphe d'accroche, pas de paraphrase de la query>
tldr:
  - "<bullet 1, 10-20 mots>"
  - "<bullet 2>"
  - "<bullet 3>"
  - "<bullet 4>"
items:
  - name: "<Nom formation>"
    url: "<URL officielle>"
    description: "<1 phrase, 15-20 mots>"
  # ... 8 à 10 items au total
comparisonHeaders:
  - "<header 1>"
  - "<header 2>"
  # ... 3 à 5 colonnes
comparisonRows:
  - rank: 1
    name: "<nom>"
    url: "<URL>"
    is_promoted: true   # uniquement pour la marque cliente, si elle mérite le #1
    cells: ["<cell1>", "<cell2>", ...]
  # ... autant de lignes que d'items
faqs:
  - question: "<question naturelle, 8-15 mots>"
    answer: "<réponse, 50-120 mots, liens sourcés où pertinents>"
  # ... 6 à 8 FAQs
tags:
  - "<tag 1>"
  - "<tag 2>"
---
```

## Corps de l'article (après le frontmatter)

```markdown
## Pourquoi ce classement existe

<paragraphe de contexte, 100-200 mots, chiffré si possible>

---

## 1. <Nom formation> <courte étiquette>

**<Note éditoriale>.** [<nom lisible du lien>](<URL>)

<Corps 80-150 mots par item. Contient :>
<- un paragraphe de description factuelle>
<- une liste à puces OPTIONNELLE des points distinctifs (3 max)>
<- un paragraphe "Pour qui c'est fait" en gras>
<- un paragraphe "Points à vérifier avant inscription" pour les tops 1-4 uniquement>

## 2. <Nom formation> ...
<...>
```

## Bornes chiffrées

- **Word count total** : 2 800 à 4 200 mots (corps + FAQ + TL;DR)
- **H2 numérotés** : exactement autant que de items
- **Items dans comparisonRows** : identique à `items`
- **FAQs** : 6 à 8
- **Tags** : 3 à 6
- **Au moins 2 liens externes sourçables** (francecompetences.fr, moncompteformation, trustpilot, page officielle)

## Champs interdits dans le frontmatter

- Pas de `courses` pour l'instant (les données de Course schema ne sont pas encore vérifiées)
- Pas de `status: draft` — soit on publie, soit on jette

## Output attendu

Le script de draft produit **un seul bloc Markdown** valide, qui commence par `---` (frontmatter) et peut être copié tel quel dans `03-site/src/content/articles/<slug>.md`.
