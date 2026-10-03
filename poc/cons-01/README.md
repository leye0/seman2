# CONS-01 — Contrat de résultat Z3

Quatre cas isolent les sorties nécessaires au moteur : SAT avec modèle et
bindings, UNSAT avec assertions suivies et cœur, problème sous-spécifié avec
énumération exhaustive et modèle alternatif, puis UNKNOWN obtenu sous une
limite de ressources déterministe. Les problèmes SMT-LIB sont conservés dans
`output/` pour reproduction.

```bash
./poc/cons-01/run.sh
```
