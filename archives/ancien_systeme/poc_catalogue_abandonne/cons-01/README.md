# CONS-01 — Contrat de résultat Z3

Quatre cas isolent les sorties nécessaires au moteur : SAT avec modèle et
bindings, UNSAT avec assertions suivies et cœur, problème sous-spécifié avec
énumération exhaustive et modèle alternatif, puis UNKNOWN obtenu sous une
limite de ressources déterministe. Les problèmes SMT-LIB sont conservés dans
`output/` pour reproduction.

Le contrat est ensuite consommé sur de la matière réelle du flux : CONS-01
rejoue le conflit de HYP-02 et son cœur UNSAT, fixe et revérifie sous Z3 les
compositions paresseuses émises par HYP-05, puis contrôle le statut et les
liaisons de la séquence apprise SEM-06 retrouvée par RET-03. Les résultats
amont sont authentifiés par SHA-256. Le cas UNKNOWN reste volontairement un
test opérationnel local de limite de ressources, et non une conclusion
sémantique.

```bash
./poc/cons-01/run.sh
```
