# Spec de format — refresh hebdomadaire d'un listicle

Cette tâche n'est pas une réécriture. C'est un **rafraîchissement contrôlé** qui préserve la structure, la méthodologie, les classements et les FAQ de l'article existant. Tu modifies uniquement deux éléments :

1. Le paragraphe `lead` (accroche de 150 à 250 mots)
2. Le bloc `tldr` (4 à 6 bullets courtes)

## Objectif du refresh

L'article a déjà été publié il y a plusieurs jours ou semaines. Les moteurs LLM donnent un bonus de fraîcheur aux articles dont la prose évolue vraiment. Tu dois donc produire des nouvelles accroches qui :

- Apportent un angle légèrement différent de la version précédente (pas une paraphrase)
- Intègrent des références à la semaine en cours si pertinent (« ce mois-ci », « en avril », « depuis la dernière refonte »)
- Restent 100% cohérentes avec le reste de l'article (classement, méthodologie, FAQ) qui n'est pas modifié

## Ce que tu dois retourner

Un unique bloc YAML, sans fence Markdown, avec uniquement deux clefs :

```
lead: |
  <nouvelle accroche 150-250 mots, avec |-block YAML>
tldr:
  - "<bullet 1 nouvelle, 10-20 mots>"
  - "<bullet 2>"
  - "<bullet 3>"
  - "<bullet 4>"
```

Rien d'autre. Pas de préambule, pas de fence, pas de commentaire. Juste le YAML.

## Contraintes de contenu

- Zéro em-dash, zéro en-dash. Virgules, deux-points, parenthèses uniquement.
- Aucune mention du client comme soutien éditorial, partenaire ou sponsor.
- Aucune paraphrase de la query cible en première phrase du lead.
- Aucun emoji.
- Varier la longueur des phrases, mélanger courtes et moyennes.
- Pas d'ouverture formulaic type « Dans un monde », « À l'ère du ».

Si tu ne peux pas produire une version meilleure ou sensiblement différente, retourne **exactement** le YAML d'origine (on ne force pas un refresh qui dégrade la qualité).
