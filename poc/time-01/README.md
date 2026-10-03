# TIME-01 — Ordre observable et ancres externes séparées

Cette POC valide le premier niveau de la couche temporelle formelle : un ordre
partiel issu de relations observables, indépendant des coordonnées d'horloge ou
de calendrier. Les timestamps sont conservés comme nœuds de provenance et ne
créent jamais implicitement une relation temporelle cognitive.

## Exécution

```bash
./poc/time-01/run.sh
```

Les fixtures couvrent ordre linéaire, ordre partiel, messages liés par
`reply_to`, événements incomparables, timestamps égaux, timestamp contredisant
l'ordre observé et cycle explicite.

Le POC vérifie par oracle l'ordre transitif, les paires incomparables, les
cycles et les conflits d'ancres. Il recalcule une signature du sous-graphe
relationnel après retrait de toutes les ancres : elle doit rester identique.
