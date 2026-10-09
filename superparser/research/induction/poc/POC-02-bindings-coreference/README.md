# POC-02 — Variables de sous-graphes, liaison et coréférence

## État

`GO` borné pour les ports de sous-graphe et la préservation des candidats
référentiels v0.1 — voir `verdict.md`.

## Hypothèse

Une anti-unification peut absorber des constituants de tailles différentes
derrière un port typé sans perdre leur reconstruction, et généraliser les
arêtes référentielles observées sans transformer une possibilité en identité
résolue.

## Périmètre v0.1

- ports de sous-graphe nommés par variable et typés par catégorie ;
- NP, VP, proposition, PP, NOM, ADJP et ADVP admissibles ;
- liaison répétée : deux occurrences du même port doivent matcher le même
  nœud et le même sous-graphe ;
- traits grammaticaux protégés contrôlés avant toute abstraction ;
- ports référentiels nommés `REF_SOURCE` et `REF_TARGET` ;
- conservation de chaque arête `MAYBE_REF` comme alternative ouverte ;
- reconstruction exacte des deux observations et matching tenu à l'écart.

## Hors périmètre

- résolution du meilleur antécédent ou probabilités de coréférence ;
- représentation d'un ensemble d'alternatives mutuellement exclusives ;
- choix appris de la frontière optimale d'un port ;
- port vers un composant promu en bibliothèque ;
- compression MDL et alignement approximatif.

Ces points relèvent des POC-03 et POC-05, ou d'une extension référentielle
ultérieure si les inférences en ont besoin.

## Exécution ciblée

```bash
PYTHONPATH=superparser pytest -q superparser/tests/test_subgraph_bindings.py
```

Benchmark dédié :

```bash
PYTHONPATH=superparser python \
  superparser/research/induction/poc/POC-02-bindings-coreference/implementation/benchmark.py
```
