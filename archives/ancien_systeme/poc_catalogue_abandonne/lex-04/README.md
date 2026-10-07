# LEX-04 — NLTK FrameNet 1.7

Cette POC établit les structures réellement accessibles dans Berkeley FrameNet
1.7 via NLTK : définitions de frames, unités lexicales, éléments de frame,
ensembles d'éléments coréférents, relations entre frames, mappings d'éléments,
tables de valence et exemples annotés.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-04/run.sh
```

Le script régénère :

- `output/results.json`, les trois frames, unités lexicales, valences et quatre
  exemples structurés ;
- `output/resource-vs-detection.json`, la frontière entre consultation de la
  ressource, lecture d'annotations existantes et analyse d'un nouveau texte ;
- `output/corpus-inventory.json`, l'inventaire des types d'éléments, parties du
  discours, statuts d'unités lexicales et types de relations ;
- `output/raw/frame-xml.json` et `output/raw/lexical-unit-xml.json`, les XML
  FrameNet natifs concernés ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**GO comme ressource lexicale et corpus annoté, pas comme détecteur de
frames.** L'API NLTK expose 1 221 frames, 13 572 unités lexicales, 11 428
éléments de frame et 2 070 relations typées. Les fixtures démontrent les
relations d'héritage et leurs mappings d'éléments, les core sets, les cibles et
éléments annotés, leur alignement avec les couches GF/PT, ainsi qu'une
instanciation nulle `CNI`.

La section de valence requiert une nuance d'intégration : elle est présente
dans les fichiers LU de FrameNet 1.7, mais le lecteur NLTK 3.10.3 la saute
explicitement. L'adaptateur la lit donc dans le XML installé et rattache chaque
pattern à ses annotation sets ; toutes les autres structures de la POC passent
par l'API NLTK.

Un lookup de frame ou d'unité lexicale consulte un inventaire et les exemples
retournés sont des annotations humaines déjà existantes. Rien dans cette POC
ne détecte automatiquement la cible, la frame ou ses éléments dans une phrase
nouvelle.

Voir `verdict.md` pour les exemples, limites et conséquences architecturales.
