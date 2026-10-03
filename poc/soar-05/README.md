# SOAR-05 — Bridge mémoire globale / Soar

Le POC implémente le bridge de bout en bout : une production Soar émet une
commande de récupération sur l'output-link; l'adaptateur la lit par SML,
interroge un Parquet par DuckDB, puis injecte seulement le top-k avec identités
et provenance. Soar consomme le rang 1, les WME temporaires sont détruits, et
une requête ultérieure réactive une hypothèse restée hors beam.

```bash
./poc/soar-05/run.sh
```

Le store est relié cryptographiquement aux artefacts RET-03. Les dumps SML
avant/après retrait et les deux accusés de consommation sont archivés dans
`output/results.json`.
