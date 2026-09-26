# NLP-05 — Linkages syntaxiques Link Grammar

Cette POC établit les données réellement émises par Link Grammar 5.13.0 et ses
bindings Python : tokens ancrés, disjoncteurs, liens typés, alternatives,
coûts, constituants et états d'échec. Chaque linkage reste une analyse externe
attribuée et reliée à l'observation source.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-05/run.sh
```

La limite et le temps maximal sont configurables :

```bash
./poc/nlp-05/run.sh --max-linkages 200 --timeout-seconds 20
```

Le script régénère :

- `output/results.json`, représentation structurée de chaque fixture, linkage,
  token, lien, coût et arbre de constituants ;
- `output/raw/native-linkages.json`, valeurs natives, diagrammes et arbres
  rendus par les bindings ;
- `output/summary.json`, bilan quantitatif ;
- `output/versions-and-parameters.json`, versions, dictionnaire et paramètres.

## Résultat

**GO.** Les quatre entrées grammaticales produisent 25 linkages stricts, tous
avec tokens, liens typés, coûts et constituants. L'ambiguïté d'attachement
prépositionnel produit 16 alternatives. L'entrée non grammaticale produit zéro
linkage strict ; une passe séparée et explicitement étiquetée récupère deux
analyses partielles avec deux mots inutilisés.

La bibliothèque et ses bindings étaient déjà installés par
`scripts/install_tools.sh`. Aucune dépendance supplémentaire n'est requise.

Voir `verdict.md` pour l'interprétation linguistique et les limites.
