# NLP-02 — MRS, EDS et DMRS

Cette POC vérifie que l'analyse ACE/ERG peut être décodée en MRS par
PyDelphin, puis projetée en EDS et DMRS. Elle observe aussi, sans les masquer,
les pertes propres aux deux projections.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-02/run.sh
```

La limite de lectures est configurable (10 par défaut) :

```bash
./poc/nlp-02/run.sh --max-results 20
```

Toutes les lectures rendues jusqu'à cette limite sont conservées et converties.
`NLP-03` devra aller plus loin sur la comparaison systématique et la stabilité
des analyses concurrentes. Le script régénère :

- `output/raw/ace-tsdb.stdout` et `ace-tsdb.stderr`, sortie ACE brute ;
- `output/raw/semantic-representations.txt`, sérialisations canoniques MRS,
  EDS, EDS JSON et DMRS JSON de PyDelphin ;
- `output/results.json`, les trois structures décomposées et les observations
  de conversion pour chaque fixture ;
- `output/loss-matrix.json`, la matrice explicite des pertes MRS → EDS/DMRS ;
- `output/summary.json`, les diagnostics agrégés de qualité et de fidélité ;
- `output/versions-and-parameters.json`, les versions, paramètres et
  l'empreinte de l'image ERG.

Les assertions échouent si une fixture n'est pas analysée, si EDS/DMRS perd un
prédicat ou son ancre textuelle, si une ancre sort du texte source, si une
lecture classée première n'est pas une MRS bien formée, si les cas
quantification/négation/portée ne produisent plus les structures attendues, ou
si aucune analyse concurrente n'est conservée. Les candidats secondaires
malformés ou de repli sont conservés, mais explicitement diagnostiqués.

## Couverture

Les sept fixtures couvrent : prédicats multiples, quantificateurs, négation,
portée ambiguë, pronoms, relative et coordination. La portée dite ambiguë est
la portée sous-spécifiée de la MRS (`HCONS`/`qeq`) ; la POC ne force aucune
résolution arbitraire de cette portée.

## Résultat observé

**Verdict : GO pour produire MRS, EDS et DMRS ; PARTIEL pour préserver toute
l'information MRS dans les projections.**

Les trois formes conservent les occurrences de prédicats et leurs charspans.
MRS est la forme la plus riche : variables typées et propriétés, rôles,
labels/handles, contraintes `HCONS`, quantificateurs et `TOP`/`INDEX`. EDS
fournit le graphe de dépendances le plus direct. DMRS conserve un graphe typé
et projette une partie de l'information de portée dans `post=H|HEQ`.

Avec les sorties observées, 18 MRS sur 21 sont bien formées, 8 candidats
contiennent le prédicat de repli `unknown`, 4 contiennent des `ICONS`, et
seulement 5 reconstructions DMRS → MRS sur 21 sont isomorphes à leur source.
Ces diagnostics interdisent de confondre « mêmes prédicats et mêmes ancres »
avec « conversion sans perte ».

La pile installée fournit ici une MRS sous-spécifiée et PyDelphin vérifie que sa
portée est plausible. NLP-02 n'a pas à énumérer les lectures résolues : cette
exigence appartient à NLP-03. L'absence de solutions explicites dans cette POC
n'est donc pas un échec de NLP-02.

Chaque candidat possède un identifiant déterministe dérivé de la fixture, de
son rang et de sa MRS, ainsi qu'un `semantic_id` fondé sur la MRS seule. Deux
lectures distinctes ayant la même projection sémantique restent donc deux
candidats, mais leur équivalence MRS est observable. Rang, score éventuel,
support dans l'observation source et attribution distincte pour MRS, EDS et
DMRS sont conservés. Une analyse reste une observation externe : rien dans la
sortie ne la promeut en vérité interne. Le détail des pertes est dans
`verdict.md`; les comptages et preuves par phrase sont dans
`output/results.json`.
