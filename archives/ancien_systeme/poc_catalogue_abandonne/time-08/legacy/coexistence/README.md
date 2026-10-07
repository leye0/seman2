# TIME-03 — Coexistence HeidelTime / Duckling

Cette POC exécute TIME-01 et TIME-02, projette leurs sorties dans un petit
schéma commun et compare les analyses sur les mêmes sources. Elle ne fusionne
jamais leurs identités et ne sélectionne aucune vérité.

## Exécution

```bash
./poc/time-03/run.sh
```

Le script régénère d'abord les sorties sources, puis écrit :

- `output/results.json`, occurrences et analyses attribuées ;
- `output/comparison-matrix.json`, accords, divergences et sorties propres à
  un outil ;
- `output/common-adapter-contract.json`, le contrat minimal de l'adaptateur ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**GO, ADAPTATEUR COMMUN À DÉVELOPPER.** Sur 18 occurrences communes, 18
analyses HeidelTime et 20 Duckling restent distinctes. Les comparaisons donnent
9 accords exacts, 4 divergences exactes, 2 accords sur spans chevauchants, 4
divergences sur chevauchement et 2 analyses Duckling seules.

Le schéma commun suffit à aligner producteur, occurrence, span, type natif,
valeur native et projection comparable. La projection ne remplace jamais la
valeur native. `selected_analysis_id` reste nul partout.

Voir `verdict.md`.
