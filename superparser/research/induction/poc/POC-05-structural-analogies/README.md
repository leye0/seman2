# POC-05 — Correspondances partielles et analogies structurelles

## État

`GO` borné pour l'alignement partiel ordonné v0.1.

## Hypothèse

Deux arbres grammaticaux non isomorphes peuvent partager une structure
relationnelle utile sans que leurs branches différentes soient supprimées ou
interprétées sémantiquement.

## Périmètre v0.1

- alignement ordonné de sous-arbres `CONSTITUENT` ;
- insertions et suppressions tarifées par taille de sous-arbre ;
- substitutions lexicales et structurelles explicites ;
- résidus gauche/droite conservés dans le patron ;
- reconstruction exacte des deux observations ;
- comparaison de plusieurs frontières constituantes ;
- protection de la négation, modalité, voix, interrogation et portée ;
- classement déterministe par structure partagée, couverture et coût.

## Hors périmètre

- permutation libre des dépendances ;
- alignement actif/passif validé linguistiquement ;
- réentrances de DAG dans la vue imbriquée ;
- promotion automatique dans la bibliothèque MDL ;
- interprétation sémantique des correspondances.

## Exécution ciblée

```bash
PYTHONPATH=superparser /usr/bin/python3 -m pytest -q \
  superparser/tests/test_graph_analogy.py
```

Implémentation : `research/induction/graph_analogy.py`.

