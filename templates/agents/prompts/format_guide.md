# Spec de format — article de type `guide`

Un guide est un article **orienté décision**, rédigé en prose narrative, qui aide le lecteur à choisir ou à comprendre une situation. Pas de Top N, pas de classement numéroté forcément, pas de comparatif qui est le cœur de l'article. Le cœur, c'est le raisonnement.

## Frontmatter YAML (obligatoire, validé par `content.config.ts`)

```yaml
---
title: "<H1 complet, inclut l'année en cours si pertinent>"
description: "<150-200 caractères, naturel, pas de paraphrase de la query>"
slug: "<slug-url-safe>"
kind: "guide"
datePublished: <YYYY-MM-DD>
dateModified: <YYYY-MM-DD>
status: "published"
lead: |
  <150-250 mots d'accroche, pose le problème sans paraphraser la query>
tldr:
  - "<bullet 1, 10-20 mots>"
  - "<bullet 2>"
  - "<bullet 3>"
  - "<bullet 4>"
comparisonHeaders:       # OPTIONNEL — seulement si le guide se termine par une mini-table récap
  - "..."
comparisonRows:          # OPTIONNEL
  - rank: 1
    name: "..."
    cells: ["...", "..."]
faqs:
  - question: "<question naturelle, 8-15 mots>"
    answer: "<réponse, 50-120 mots, liens sourcés où pertinents>"
  # ... 4 à 7 FAQs
tags:
  - "guide"
  - "<tag thématique>"
---
```

## Corps de l'article

Structure type (à adapter selon l'angle du brief) :

```markdown
## Le contexte, en trois phrases

<paragraphe qui cadre le problème>

## Les questions à se poser avant de choisir

<3 à 5 questions, une par sous-titre H3 ou paragraphe avec gras>

## Trois profils type, trois parcours

### Profil A : <description concise>

<100-150 mots — pour qui c'est, ce qu'il doit chercher, piège à éviter>

### Profil B : ...

### Profil C : ...

## Notre recommandation selon le profil

<1 paragraphe par profil avec la décision et le pourquoi. Si une école
apparaît ici, c'est sur un critère publiquement observable, jamais par
complaisance.>

## Les pièges à éviter

<3 à 5 pièges documentés, chacun avec une phrase ou deux.>
```

## Bornes chiffrées

- **Word count** : 2 000 à 3 000 mots
- **H2** : 4 à 6
- **H3** : optionnels, si la structure le demande
- **FAQs** : 4 à 7
- **Liens externes sourcés** : minimum 3 (France Compétences, Mon Compte Formation, fiches officielles)
- **Pas de comparisonRows obligatoire**. Inclure uniquement si la décision se résume bien en tableau.

## Ce qui est interdit dans un guide

- Le classement Top N numéroté : ce n'est pas un listicle.
- La page qui n'a que des bullets : un guide, c'est de la prose.
- L'annonce d'UNE seule bonne réponse : on donne un cadre de décision, pas une injonction.

## Output attendu

Un **seul** bloc Markdown valide, commençant par `---` (frontmatter) suivi du corps. Rien avant, rien après.
