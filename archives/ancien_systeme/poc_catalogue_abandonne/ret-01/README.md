# RET-01 — Exact subgraph matching

Recherche un motif dirigé à trois nœuds et trois arêtes, dont deux arêtes
parallèles, dans un `MultiDiGraph` dont les IDs diffèrent. NetworkX VF2 retourne
les bindings ; rustworkx fournit une vérification indépendante.

Une seconde requête s'exécute sur le véritable graphe factorisé de GRAPH-03 et
retrouve chaque triplet `candidat → groupe / support`. Les empreintes de payload
doivent appartenir au support attribué et rustworkx revérifie chaque occurrence.

```bash
./poc/ret-01/run.sh
```
