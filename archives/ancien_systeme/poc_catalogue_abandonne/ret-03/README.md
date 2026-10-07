# RET-03 — Requête structurelle séquentielle

Stocke six épisodes en Parquet, les présélectionne avec DuckDB, puis recherche
`G1 → T → C`. NetworkX fournit les bindings structurels et Z3 valide le sens,
l'outcome et les identités partagées entre étapes.

Une seconde séquence provient directement de SEM-06 : épisode support →
relation sémiotique apprise → prédiction heldout. Elle est relue depuis Parquet
par DuckDB, ses références inter-étapes doivent être identiques et Z3 confirme
que l'effet prédit correspond à l'effet observé.

```bash
./poc/ret-03/run.sh
```
