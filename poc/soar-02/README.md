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
