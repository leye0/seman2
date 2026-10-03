# HYP-01 — Séparation observation, hypothèse et sélection

Le POC sérialise une première occurrence ambiguë de `io`, quatre hypothèses,
un snapshot d'évidence et la sélection initiale erronée H1 dans quatre tables
Parquet chargées dans DuckDB. Une correction ultérieure ajoute H1 version 2 ;
elle ne modifie aucun objet historique de `t1`.

```bash
./poc/hyp-01/run.sh
```
