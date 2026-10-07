# STAT-01 — Signaux statistiques pour l'induction

Le POC génère 120 sessions structurées et calcule fréquence, probabilité
conditionnelle, transitions, cooccurrence, support, contre-exemples,
distribution contextuelle, stabilité temporelle et corrélation d'outcome.
DuckDB produit les agrégats principaux ; Polars et NumPy les contre-vérifient,
et SciPy calcule la corrélation point-bisériale.

Ce corpus contrôlé sert d'oracle numérique. Un second trajet consomme les
épisodes réellement produits par SEM-06, recalcule le support, les
contre-exemples et la probabilité conditionnelle de sa relation apprise, puis
vérifie dans RET-03 que cette relation mène bien, avec les mêmes références,
à une prédiction réservée dont les contraintes finales sont satisfaites. Les
deux fichiers amont sont liés par chemin et SHA-256.

```bash
./poc/stat-01/run.sh
```
