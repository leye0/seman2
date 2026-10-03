# RET-03 — Requête structurelle séquentielle

Stocke six épisodes en Parquet, les présélectionne avec DuckDB, puis recherche
`G1 → T → C`. NetworkX fournit les bindings structurels et Z3 valide le sens,
l'outcome et les identités partagées entre étapes.

```bash
./poc/ret-03/run.sh
```
