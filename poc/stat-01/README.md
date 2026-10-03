# STAT-01 — Signaux statistiques pour l'induction

Le POC génère 120 sessions structurées et calcule fréquence, probabilité
conditionnelle, transitions, cooccurrence, support, contre-exemples,
distribution contextuelle, stabilité temporelle et corrélation d'outcome.
DuckDB produit les agrégats principaux ; Polars et NumPy les contre-vérifient,
et SciPy calcule la corrélation point-bisériale.

```bash
./poc/stat-01/run.sh
```
