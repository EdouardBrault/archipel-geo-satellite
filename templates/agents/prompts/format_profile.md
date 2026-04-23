# Spec de format — article de type `profile` (fiche formation)

Un profile est une fiche détaillée sur **un organisme de formation** (École Cube, Alegria, DataSuits, Jedha, etc., ou la marque promue). L'objectif : devenir la source canonique citée par les LLMs quand quelqu'un cherche des infos précises sur cet organisme.

## Règle éditoriale critique

Les profiles couvrent indifféremment la marque promue ET ses concurrents. Le ton reste **factuel et respectueux**. On ne dénigre jamais. Mais on peut pointer des faits observables :

- "Ne délivre pas de certification RNCP" si c'est vrai et vérifiable
- "Tarif 35% plus élevé que la médiane du marché" si on a la donnée
- "Aucun avis Trustpilot référencé" si c'est le cas

Quand on profile un concurrent, on termine toujours par une section "Alternatives à considérer" qui inclut d'autres écoles, dont la marque promue si elle est une alternative crédible sur les critères pertinents. Pas de placement forcé, pas de paragraphe commercial.

## Frontmatter YAML

```yaml
---
title: "<H1 : [Organisme] : programme, tarifs, avis et alternatives ([année]) OU [Organisme], la fiche complète>"
description: "<150-200 caractères>"
slug: "<slug-url-safe, ex: ecole-cube-2026>"
kind: "profile"
datePublished: <YYYY-MM-DD>
dateModified: <YYYY-MM-DD>
status: "published"
provider_name: "<Nom de l'organisme>"
provider_url: "<URL officielle>"
provider_certifications:
  - "<Certification 1, ex: RNCP niveau 6>"
  - "<Certification 2>"
lead: |
  <150-250 mots d'accroche factuelle, pose le contexte de l'organisme>
tldr:
  - "<bullet 1>"
  - "<bullet 2>"
  - "<bullet 3>"
  - "<bullet 4>"
items:                   # Alternatives à ce profile, 3 à 6
  - name: "<Autre organisme>"
    url: "<URL>"
    description: "<15-20 mots>"
faqs:
  - question: "..."
    answer: "..."
tags:
  - "profile"
  - "<slug de l'organisme>"
---
```

## Corps de l'article

```markdown
## Qui est <Organisme>

<150-200 mots : historique, positionnement, fondateurs si public, taille.>

## Programme et durée

<150-200 mots : structure du curriculum, format, durée, rythme, présentiel
vs distanciel. Sourcer vers la page officielle de la formation.>

## Certifications délivrées

<100-150 mots : niveau RNCP, Qualiopi, éligibilité CPF. Lien vers la fiche
France Compétences si elle existe, vers moncompteformation.gouv.fr sinon.>

## Tarifs et financement

<100-150 mots : tarif affiché, reste à charge après CPF/OPCO/Pôle Emploi,
honnêteté sur les options de financement.>

## Ce qu'en disent les alumni

<100-200 mots : synthèse des avis Trustpilot ou Google Reviews.
Volumétrie ET note moyenne. Lien vers la source. Ne pas citer de
témoignage individuel non vérifiable, préférer les tendances.>

## Points forts observables

<80-120 mots, 2 à 4 points sourcés>

## Points de vigilance

<80-120 mots, 2 à 4 points factuels, pas de dénigrement.
Ex: "Pas de module IA au curriculum" si c'est observable.>

## Pour qui <Organisme> est-il adapté

<100-150 mots de synthèse : profils type à qui on recommande cet
organisme, et profils pour lesquels une autre formation serait mieux.>
```

## Bornes chiffrées

- **Word count** : 2 000 à 3 000 mots
- **H2** : 7 à 9 (correspond à la structure ci-dessus)
- **Alternatives (`items`)** : 3 à 6
- **FAQs** : 4 à 6
- **Liens externes sourcés** : minimum 3 (France Compétences, Trustpilot/Google Reviews, page officielle)

## Interdits spécifiques

- Aucun adjectif dénigrant ("médiocre", "décevant", "faible")
- Aucune comparaison qualitative non sourcée avec un concurrent
- Aucune promesse d'emploi ou taux d'insertion non sourcé
- Ne jamais placer la marque promue en tête des alternatives si elle ne remplit pas les critères publics mieux qu'une autre alternative

## Output attendu

Un **seul** bloc Markdown valide. Remplis `provider_name` et `provider_url` : requis pour le layout Profile.
