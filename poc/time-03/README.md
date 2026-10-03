# TIME-03 — Temps d'événement, de référence et d'énonciation

Cette POC représente séparément E (événement), R (référence) et S
(énonciation) selon Reichenbach. Les structures sont des analyses formelles
attribuées et scopées, compatibles avec une adaptation Temporal DRT.

## Exécution

```bash
./poc/time-03/run.sh
```

Les fixtures couvrent présent, passé, plus-que-parfait, futur, futur antérieur,
discours rapporté et analyse cyclique contradictoire. Aucune date n'est
inventée. Le rapport `normalization-information-loss.json` montre les relations
perdues si le discours rapporté était réduit aux seules valeurs de `hier` et
`demain`.
