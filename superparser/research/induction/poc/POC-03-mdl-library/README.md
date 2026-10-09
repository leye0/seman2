# POC-03 — Bibliothèque de composants et compression mesurée

## État

`GO` pour une bibliothèque plate et un codec MDL sans perte v0.1 — voir
`verdict.md`.

## Hypothèse

Des motifs structuraux récurrents peuvent payer une seule fois leur modèle,
encoder chaque occurrence par ses substitutions et réduire le coût total d'un
corpus. Un corpus non compressible ne doit pas provoquer une promotion forcée.

## Périmètre v0.1

- découverte gloutonne bornée par signatures structurelles ;
- canonicalisation des nœuds et variables sous renommage ;
- support, coût du modèle, coût des instances et gain enregistrés ;
- promotion conditionnée par support, gain et ratio de variables ;
- encodage brut automatique des exceptions ;
- décodage exact, sérialisation, rechargement, gel et retrait ;
- évaluation `B0/B1/B2/B3` avec le même code logique ;
- réutilisation d'une bibliothèque gelée sur données tenues à l'écart.

## Hors périmètre

- composants imbriqués ou récursifs — POC-04 ;
- recherche d'alignements approximatifs — POC-05 ;
- valeur sémantique ou gain d'inférence ;
- résolution référentielle ;
- optimisation globale de l'ensemble de composants ;
- validation à grande échelle sur un corpus naturel.

## Exécution ciblée

```bash
PYTHONPATH=superparser pytest -q superparser/tests/test_component_library.py
```

Benchmark dédié :

```bash
PYTHONPATH=superparser python \
  superparser/research/induction/poc/POC-03-mdl-library/implementation/benchmark.py
```
