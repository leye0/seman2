# RET-04 — Récupération disk-backed

Génère 5 000 graphes dans deux Parquet séparés : statistiques et fragments.
DuckDB sélectionne d'abord les IDs sur les seules statistiques, puis charge et
vérifie avec rustworkx uniquement les JSON candidats. Trois tailles mesurent
latence, allocations Python et fraction chargée.

Une seconde passe utilise directement les statistiques et payloads candidats
de GRAPH-03, avec la famille demandée par RET-02. DuckDB choisit les IDs dans un
Parquet étroit avant de lire les payloads. Les checkpoints `VmRSS` et le
`ru_maxrss` global complètent `tracemalloc` en incluant les allocations natives.

```bash
./poc/ret-04/run.sh
```
