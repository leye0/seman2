# SOAR-02 — Buts, impasses, opérateurs et préférences

Le POC propose réellement deux opérateurs concurrents dans Soar 9.6.5. Leur
égalité crée un sous-état d'impasse `operator tie`. Une production du sous-état
émet ensuite une préférence `require` pour l'opérateur temporel. Les états,
items de l'impasse, préférences avant/après, opérateur sélectionné et compteurs
de décision sont tous relus via SML.

```bash
./poc/soar-02/run.sh
```

Les preuves natives (`print --stack`, `print S1/S2`, `preferences` et `stats`)
sont conservées dans `output/results.json`.

Le checkpoint cognitif RUN-01 fournit en plus les vraies transformations
`retain-episode` et `defer-consolidation`, leurs épisodes, références culturelles
et préconditions. La POC vérifie que toutes ces références ont réellement été
projetées dans la WM du worker Soar, que la sélection porte sur un candidat
parent et qu'elle reste une décision opérationnelle sans engagement de vérité.
