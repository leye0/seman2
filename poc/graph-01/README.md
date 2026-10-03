# GRAPH-01 — Représentation de toutes les sorties

Le POC inventorie automatiquement chaque `poc/*/output/results.json` disponible
(ainsi que la matrice d'audit DISC-02), en prend l'élément mesuré le plus riche
par taille JSON canonique plutôt que le premier arbitrairement, puis le porte dans un
`MultiDiGraph` et trois tables Parquet (`nodes`, `edges`, `payloads`).

Les payloads récursifs restent du JSON canonique référencé et vérifié par
SHA-256. Les fixtures destinées aux POC ultérieures sont explicitement marquées
`contract_fixture`; elles testent états temporels, candidats ISU, plans,
relations sémiotiques, spans chevauchants et liens cross-représentation sans se
faire passer pour des sorties mesurées.

`planned_coverage` distingue systématiquement `measured_output`,
`contract_fixture_only` et `uncovered`. Les contrats SEM-05 et DLG-06 à DLG-14
sont exercés par des fixtures nommées, mais devront être remplacés puis rejoués
sur leurs sorties mesurées quand ces POC auront été réalisées.

```bash
./poc/graph-01/run.sh
```
