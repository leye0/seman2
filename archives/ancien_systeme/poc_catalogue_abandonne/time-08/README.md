# TIME-08 — Analyseurs temporels de surface en quarantaine

Cette POC conserve sous `legacy/` les expériences HeidelTime, Duckling et leur
ancien adaptateur commun. Elle réinjecte leurs résultats comme annotations
externes seulement, puis vérifie que le sous-graphe temporel cognitif ne change
ni lors de leur ajout ni lors de leur retrait.

```bash
./poc/time-08/run.sh
```

Les outils externes restent utiles pour les spans, durées, grains et valeurs
normalisées. Le rapport `surface-capability-gaps.json` documente ce qu'ils ne
remplacent pas dans TIME-03 à TIME-07.
