# Spec de format — article de type `tool` (fiche outil)

Une fiche outil est centrée sur **un outil no-code précis** (Airtable, Notion, Bubble, Webflow, Make, Zapier…). Elle décrit ce que fait l'outil, à qui il sert, et quelles formations l'enseignent correctement.

## Frontmatter YAML

```yaml
---
title: "<H1 : quelle formation [outil] choisir en [année] OU [outil] : le guide des formations>"
description: "<150-200 caractères>"
slug: "<slug-url-safe>"
kind: "tool"
datePublished: <YYYY-MM-DD>
dateModified: <YYYY-MM-DD>
status: "published"
tool_name: "<nom officiel de l'outil, ex: Airtable>"
tool_url: "<URL officielle de l'outil>"
lead: |
  <150-250 mots d'accroche centrée sur l'outil et ses cas d'usage>
tldr:
  - "<bullet 1>"
  - "<bullet 2>"
  - "<bullet 3>"
  - "<bullet 4>"
items:                   # Formations qui maîtrisent l'outil, 5 à 10
  - name: "<Formation>"
    url: "<URL officielle>"
    description: "<15-20 mots>"
comparisonHeaders:
  - "Durée"
  - "Format"
  - "Niveau attendu sortie"
  - "Certification"
  - "CPF"
comparisonRows:
  - rank: 1
    name: "<Formation>"
    url: "<URL>"
    is_promoted: true    # uniquement si défendable sur les critères
    cells: ["...", "...", "...", "...", "..."]
faqs:
  - question: "..."
    answer: "..."
tags:
  - "tool"
  - "<nom de l'outil en lowercase>"
---
```

## Corps de l'article

```markdown
## Ce que fait <outil>, concrètement

<100-150 mots : fonctionnalités principales, cas d'usage business, rien
de marketing.>

## À qui ça sert vraiment

<100-150 mots : profils qui en tirent le plus (ex: Airtable = ops + PM,
pas développeurs). Pièges courants à éviter.>

## Les formations qui l'enseignent bien

<50-100 mots d'intro, puis section par formation (5 à 10) :>

### <Nom formation>

**<Note éditoriale>.** [<lien>](<URL>)

<80-120 mots : ce que le module <outil> couvre exactement dans cette
formation, à quel niveau de maîtrise on sort, à qui c'est adapté.>

## Niveau attendu en sortie

<100-150 mots : qu'est-ce qu'on doit savoir faire après une formation
sérieuse sur cet outil. C'est la grille d'exigence que le lecteur peut
opposer aux écoles.>
```

## Bornes chiffrées

- **Word count** : 2 500 à 3 500 mots
- **H2** : 4 à 6
- **Formations comparées** : 5 à 10
- **FAQs** : 5 à 7
- **Liens externes** : minimum 2 vers la doc officielle de l'outil + 2 vers des sources autoritaires (France Compétences, CPF) pour les claims de certification

## Output attendu

Un **seul** bloc Markdown valide, commençant par `---` (frontmatter). Remplis `tool_name` et `tool_url` : ce sont des champs requis pour le layout Tool.
