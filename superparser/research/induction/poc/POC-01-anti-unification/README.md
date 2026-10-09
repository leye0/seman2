# POC-01 — Anti-unification et première abstraction

## État

`GO` pour l'anti-unification exacte de DAG v0.1 — voir `verdict.md`.

## Hypothèse

Deux graphes grammaticaux de même topologie peuvent produire un composant
paramétrique qui conserve leurs invariants, rend explicites leurs différences
et permet de reconstruire exactement les deux observations.

## Périmètre v0.1

- alignement de DAG enracinés de nœuds `CONSTITUENT` ;
- catégories, règles, arêtes `CHILD` ordonnées et réentrances préservées ;
- anti-unification récursive des propriétés JSON ;
- réemploi d'une variable quand la même paire de valeurs se répète ;
- spans traités comme substitutions résiduelles, jamais comme contraintes ;
- rejet des différences de polarité, modalité, voix, interrogation et portée
  grammaticale protégée ;
- reconstruction et matching sur de nouvelles substitutions ;
- génération/ranking à partir de l'unique analyse sélectionnée de chaque observation.

## Hors périmètre

- insertions, suppressions et sous-graphes de tailles différentes ;
- alignement approximatif ou actif/passif ;
- variables remplaçant un sous-graphe entier ;
- promotion en bibliothèque et véritable score MDL multi-occurrences.

Ces points sont destinés aux POC-02, POC-03 et POC-05.

## Exécution ciblée

```bash
PYTHONPATH=superparser pytest -q superparser/tests/test_anti_unification.py
```

Benchmark dédié :

```bash
PYTHONPATH=superparser python \
  superparser/research/induction/poc/POC-01-anti-unification/implementation/benchmark.py
```

