# GRAPH-01 — Représentation de toutes les sorties

Le POC inventorie automatiquement chaque `poc/*/output/results.json` disponible
et conserve la racine JSON complète de chacun — jamais un seul représentant —
dans un `MultiDiGraph` et trois tables Parquet (`nodes`, `edges`, `payloads`).

Les payloads récursifs restent du JSON canonique référencé et vérifié par
SHA-256. Les fixtures destinées aux POC ultérieures sont explicitement marquées
`contract_fixture`; elles testent états temporels, candidats ISU, plans,
relations sémiotiques, spans chevauchants et liens cross-représentation sans se
faire passer pour des sorties mesurées.

`planned_coverage` distingue systématiquement `measured_output`,
`contract_fixture_only` et `uncovered`. Les fixtures nommées restent des cas
adversariaux du contrat (multi-arêtes, spans chevauchants, états), jamais des
substituts aux POC : la couverture planifiée actuelle provient entièrement de
sorties mesurées. NetworkX et rustworkx reconstruisent indépendamment la même
topologie avant le roundtrip Parquet.

```bash
./poc/graph-01/run.sh
```
