# SOAR-04 — Chunking

Le POC force un choix par raisonnement dans un sous-état d'impasse, active
l'Explanation-Based Chunking natif et inspecte la production apprise. Le chunk
est ensuite réutilisé directement sur un cas relationnel isomorphe portant une
autre valeur. Un contre-exemple sans candidat compatible doit conserver
l'impasse et ne pas déclencher le chunk.

```bash
./poc/soar-04/run.sh
```

`output/results.json` contient la règle complète, sa formation fournie par
`explain`, ses dépendances et ses compteurs de déclenchement. La règle seule est
aussi exportée dans `output/learned-chunk.soar`.
