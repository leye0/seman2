# NLP-04 — Ancres et positions textuelles DELPH-IN

Cette POC établit expérimentalement la convention des offsets ACE/ERG et la
couverture des tokens, prédicats, variables, handles, rôles et projections
MRS/EDS/DMRS. Toutes les analyses renvoyées jusqu'à une limite configurable
sont conservées. Chaque analyse reste attribuée à ACE/ERG/PyDelphin et liée à
une observation source distincte ; les supports dérivés ne deviennent pas des
faits internes.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-04/run.sh
```

La limite par phrase vaut 10 par défaut et peut être modifiée :

```bash
./poc/nlp-04/run.sh --max-results 20
```

Le script régénère :

- `output/raw/ace-tsdb.stdout` et `ace-tsdb.stderr`, sortie ACE brute ;
- `output/results.json`, toutes les analyses retenues, tokens
  initiaux/internes, MRS/EDS/DMRS, ancres, supports dérivés et résidus textuels ;
- `output/offset-convention.json`, preuves comparant points de code, octets
  UTF-8, unités UTF-16 et unités d'affichage avec accents combinants ;
- `output/summary.json`, bilan de couverture ;
- `output/versions-and-parameters.json`, versions et paramètres.

## Résultat

**GO.** Sur les fixtures contrôlées, les charspans DELPH-IN sont des offsets en
points de code Unicode, base zéro, début inclus et fin exclue. Ils ne comptent
ni les octets UTF-8, ni les unités UTF-16, ni les graphèmes affichés.

Les formes de tokens peuvent être normalisées : pour l'entrée ASCII `can't`,
le token couvrant exactement la source `n't` porte la forme normalisée `n’t`.
Il faut donc conserver à la fois le charspan, la tranche source et la forme de
l'analyseur.

Avec la limite par défaut, les six fixtures produisent 22 analyses. Les 130
prédications MRS et les 130 nœuds de chacune des projections EDS et DMRS sont
directement ancrés. Les 319 variables/handles et les 291 rôles MRS disposent
d'un support indirect ou dérivé explicite. Chaque partition tokens + résidus
reconstitue exactement la source, espaces multiples compris. Les contrôles de
forme MRS sont aussi exposés : 21 analyses sur 22 sont bien formées selon
PyDelphin ; l'analyse divergente reste conservée et attribuée.

Voir `verdict.md` pour les exemples et limites.
