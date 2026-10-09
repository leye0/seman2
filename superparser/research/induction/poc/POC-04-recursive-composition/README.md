# POC-04 — Composition récursive et concepts de concepts

## État

`GO` borné pour la composition structurelle récursive v0.1 — voir
`verdict.md`.

## Hypothèse

Un composant récurrent peut être référencé depuis des composants de niveau
supérieur, réduire la duplication du modèle et conserver exactement les
variables qui traversent ses interfaces.

## Périmètre v0.1

- coquilles structurelles contenant des ports de composant ;
- appels par identifiant canonique et mappings explicites inner/outer ;
- égalités de variables conservées à travers plusieurs appels ;
- découverte d'une sous-structure déjà connue dans un gabarit plat ;
- composition récursive, matching et expansion sans perte ;
- détection statique et dynamique des cycles ;
- canonicalisation sous renommage et ordre des appels ;
- sérialisation/rechargement avec partage des définitions ;
- coût logique du graphe de dépendances payé une seule fois.

## Hors périmètre

- recherche globale de la meilleure hiérarchie ;
- frontières approximatives ou actif/passif — POC-05 ;
- récursion cyclique productive ;
- inférence relationnelle ou preuve de valeur sémantique ;
- gain marginal held-out lorsque le modèle plat est déjà payé.

## Exécution ciblée

```bash
PYTHONPATH=superparser pytest -q superparser/tests/test_component_composition.py
```

Benchmark dédié :

```bash
PYTHONPATH=superparser python \
  superparser/research/induction/poc/POC-04-recursive-composition/implementation/benchmark.py
```
