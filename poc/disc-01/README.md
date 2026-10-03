# DISC-01 — Sortie IsaNLP RST

Inspecte la sortie réelle du modèle `gumrrg` sur textes anglais/français,
courts, longs, ambigus et multi-tours, plus une entrée vide adversariale.

```bash
./poc/disc-01/run.sh
```

Le POC conserve l'arbre natif sérialisé, EDUs, spans, relations, nuclearités,
scores lorsqu'émis, latences et échecs.

Le modèle accepte l'entrée vide comme une EDU élémentaire vide. Ce comportement
est conservé comme limite de validation d'entrée, et non requalifié en succès.
