# LEX-07 — Alignement lexical d'une nouvelle occurrence

Cette POC part d'occurrences polysémiques ancrées par ACE/ERG, puis énumère
les candidats disponibles dans WordNet, VerbNet, PropBank et FrameNet. Elle
matérialise ensuite les liens fournis par les membres VerbNet, SemLink et les
mappings WordNet–SUMO sans transformer ces liens en décision de sens.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-07/run.sh
```

Le script régénère :

- `output/results.json`, les occurrences, analyses ERG, candidats et arêtes ;
- `output/contrast-report.json`, les comparaisons des deux sens de `run` et
  `bank` ;
- `output/lookup-vs-mapping-vs-decision.json`, la frontière méthodologique ;
- `output/raw/erg-analyses.json`, les structures MRS attribuées ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**GO pour générer et attribuer des candidats ; pas de GO pour sélectionner un
sens en contexte.** Les deux occurrences de `run` reçoivent le même prédicat
ERG `_run_v_1` et les mêmes inventaires de 41 synsets WordNet, 4 classes
VerbNet, 9 rôles PropBank et 8 frames FrameNet. ERG distingue néanmoins la
structure intransitive `ARG1` de la structure transitive `ARG1+ARG2`.

Les deux occurrences de `bank` reçoivent `_bank_n_of`, 10 synsets WordNet et
2 frames FrameNet. VerbNet et PropBank restent vides pour cette cible nominale
au lieu d'être étendus artificiellement.

Aucun candidat n'est sélectionné. Les exemples attendus (`run.v.01` contre
`operate.v.01`, `bank.n.01` contre
`depository_financial_institution.n.01`) servent uniquement de contrôles de
présence dans l'ensemble des candidats.

Voir `verdict.md` pour les limites d'intégration et de version.
