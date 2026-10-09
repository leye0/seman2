# POC-00 — Graphe universel d’observation

## État

`GO` pour le périmètre structurel compact v0.2 — voir `verdict.md`.

## Hypothèse

La sortie du parseur peut être projetée vers un graphe structurel canonique,
auditable et sérialisable sans exposer à l’inducteur les significations
lexicales importées.

## Périmètre de cette tranche

- texte, tokens, spans et ordre ;
- lexèmes de l'analyse sélectionnée après retrait des champs sémantiques ;
- catégories et traits grammaticaux ;
- un seul arbre final, ses règles et ses enfants ordonnés ;
- mentions et contraintes de référence observées ;
- sérialisation JSON canonique et identifiants adressés par contenu ;
- validation des références, de l’acyclicité et de la non-contamination ;
- reconstruction d’un instantané structurel équivalent.

Le texte source reste dans chaque observation afin de permettre un reparsing
ultérieur. La forêt, les autres racines et les constituants intermédiaires ne
sont pas sérialisés.

## Exclusions actuelles

- modèle persistant de l’`ObservationStore` ;
- graphes de discours multi-phrases ;
- représentation explicite des alternatives de coréférence ;
- portée/modaux au-delà des traits effectivement produits par le parseur ;
- reconstruction des graphes sémantiques, scores ou états internes du chart ;
- optimisation de la taille et du coût de projection.

## Exécution

Depuis la racine du dépôt :

```bash
PYTHONPATH=superparser pytest -q superparser/tests/test_observation_graph.py
```

Benchmark dédié (hors boucle de tests) :

```bash
PYTHONPATH=superparser python \
  superparser/research/induction/poc/POC-00-observation-graph/implementation/benchmark.py
```

Implémentation partagée : `research/induction/observation_graph.py`.
Tests/fixtures exécutables : `tests/test_observation_graph.py`.

La suite complète du parseur n'est pas exécutée dans la boucle de travail du
POC. Elle est réservée aux jalons de non-régression.

