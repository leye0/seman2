# RET-04 — Récupération disk-backed

Génère 5 000 graphes dans deux Parquet séparés : statistiques et fragments.
DuckDB sélectionne d'abord les IDs sur les seules statistiques, puis charge et
vérifie avec rustworkx uniquement les JSON candidats. Trois tailles mesurent
latence, allocations Python et fraction chargée.

```bash
./poc/ret-04/run.sh
```
