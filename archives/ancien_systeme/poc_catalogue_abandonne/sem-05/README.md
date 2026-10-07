# SEM-05 — Retrieval cross-représentation sans collapse

Construit un index Parquet/DuckDB à cinq plans depuis les sorties SEM-01 à
SEM-03, le contrat RET-02 et des occurrences contrôlées. La distance
phonologique n'est plus postulée : elle est mesurée avec Epitran/PanPhon selon
SEM-02. NetworkX exécute les chemins et rustworkx les recalcule indépendamment.

La requête `io` traverse aussi
`Source → Observation → cross-representation-retrieval-bundle`. Les recherches
forme, phonologie, symbolique, graphe et contexte restent simultanément dans ce
bundle, sans score global ni sélection.

```bash
./poc/sem-05/run.sh
```
