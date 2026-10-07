# RET-02 — Correspondance partielle et similarité structurelle

DuckDB présélectionne cinq graphes contrôlés, puis un matcher partiel classe
forme complète, forme amputée, variante et distracteur. Chaque résultat expose
bindings, nœuds/arêtes manquants, composantes du score et validation Z3.

Le même mécanisme classe ensuite les 40 candidats mesurés de GRAPH-03 à partir
du résultat exact RET-01. DuckDB présélectionne les candidats possédant groupe
et support; la relation de conflit est optionnelle et apparaît explicitement
comme manquante pour les groupes compatibles ou unitaires.

```bash
./poc/ret-02/run.sh
```
