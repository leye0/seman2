# IND-06 — Induction récursive et compression hiérarchique

Deux patterns de niveau 1 deviennent les nœuds d’un pattern de niveau 2 dans
dix graphes ; deux graphes aléatoires servent de témoins négatifs. Les tables
Parquet/DuckDB conservent dépendances, occurrences enfants et bindings originaux.
Chaque support est reconstruit, puis les gains descriptifs des deux niveaux sont
comptés avec dictionnaires, références, liens résiduels et témoins.

Le trajet intégré combine le concept FCA/ILP IND-01/02 et le motif structurel
IND-03. Leur intersection forme un candidat de niveau 2 sur H1 et H3, avec
références aux deux occurrences de niveau 1 et aux artefacts cognitifs
originaux; H2/H4 restent témoins négatifs. La structure est exacte, mais deux
occurrences n'amortissent pas le dictionnaire de niveau 2 : le gain récursif
mesuré est négatif et le candidat n'est donc pas promu.

```bash
./poc/ind-06/run.sh
```
