# NLP-06 — Complémentarité ERG / Link Grammar

Cette POC donne exactement le même jeu de neuf phrases à ACE/ERG/PyDelphin et
à Link Grammar. Elle compare couverture, segmentation, constituants,
ambiguïtés et structures exclusives sans supposer que leurs nombres de
candidats désignent les mêmes unités linguistiques.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-06/run.sh
```

La limite commune et le temps maximal de Link Grammar sont configurables :

```bash
./poc/nlp-06/run.sh --max-results 200 --timeout-seconds 20
```

Le script régénère :

- `output/results.json`, résultats attribués des deux chaînes ;
- `output/comparison-matrix.json`, comparaison par fixture ;
- `output/capability-matrix.json`, informations communes et exclusives ;
- `output/raw/ace-results.json` et `raw/link-grammar-linkages.json`, sorties
  natives conservées ;
- `output/summary.json` et `versions-and-parameters.json`.

## Résultat

**CONSERVER LINK GRAMMAR COMME ANALYSEUR SECONDAIRE ATTRIBUÉ.**

ERG demeure l'analyseur profond principal : il fournit HPSG, MRS, EDS, DMRS et
les contraintes de portée. Link Grammar ajoute un autre formalisme observable,
notamment des liens typés directement entre mots, les disjoncteurs et une
décomposition propre des coûts. Il couvre aussi une construction acceptable
qu'ERG ne parse pas dans cette expérience.

Cette complémentarité ne justifie pas un fallback automatique. Link Grammar
accepte également une entrée volontairement fautive en réinterprétant ses
catégories lexicales. Toutes ses sorties doivent donc conserver leur provenance
et rester concurrentes des autres observations.

Aucune bibliothèque supplémentaire n'est nécessaire : les deux chaînes et
leurs bindings étaient déjà installés.

Voir `verdict.md` pour la matrice expliquée en langage humain.
