# TIME-02 — Duckling

Cette POC interroge le service HTTP Duckling local sur des temps, nombres,
ordinaux, quantités, monnaies, mesures, températures, durées et intervalles en
anglais et en français. Le service est lancé sur un port éphémère pendant le
test.

## Exécution

```bash
./poc/time-02/run.sh
```

Le script régénère `output/results.json`, la matrice
`dimension-locale-matrix.json`, les réponses natives sous `output/raw/`, le
résumé et les versions/paramètres.

## Résultat

**GO avec couverture et ambiguïtés propres aux locales.** Les 28 fixtures
produisent 36 entités : 19 `time`, 4 `amount-of-money`, 3 `quantity`, et 2 pour
chacune des dimensions `duration`, `number`, `ordinal`, `distance` et
`temperature`. Toutes ces dimensions sont observées dans les deux langues.

La POC conserve unité, grain, intervalle, latent et tableau natif `values`.
Sept analyses sont latentes et 19 analyses temporelles portent des
alternatives. Aucun chevauchement n'est éliminé : le nombre nu `42` reçoit par
exemple plusieurs lectures lorsque les analyses latentes sont demandées.

Voir `verdict.md` pour les implications.
