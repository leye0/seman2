# TIME-01 — HeidelTime

Cette POC mesure l'extraction et la normalisation temporelles de HeidelTime
2.2.1 avec le TreeTagger local, en anglais et en français. Les fixtures couvrent
dates absolues et relatives, heures, durées, fréquences, intervalles,
expressions ambiguës et deux dates de document par expression relative.

## Exécution

```bash
./poc/time-01/run.sh
```

Le script régénère `output/results.json`, `coverage-matrix.json`,
`dct-dependency.json`, les documents TimeML bruts sous `output/raw/`, ainsi que
le résumé et les versions/paramètres.

## Résultat

**GO avec limites explicites de couverture.** Les 18 fixtures produisent 18
TIMEX3 : 12 `DATE`, 2 `TIME`, 2 `DURATION` et 2 `SET`. Les deux fixtures
monétaires de contrôle ne produisent aucune annotation, comme attendu. Tous les
spans reconstruisent la source et la dépendance à la date du document est
démontrée pour `tomorrow` et `demain`.

Dans les deux phrases d'intervalle, cette configuration rend deux dates
terminales plutôt qu'un objet intervalle unique. La sortie ne doit donc pas être
enrichie d'une relation absente. Voir `verdict.md`.
