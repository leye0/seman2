# NLP-03 — Ambiguïtés et analyses concurrentes

Cette POC vérifie que toutes les analyses ACE/ERG sont récupérées jusqu'à une
limite configurable, restent des candidats séparés et peuvent être comparées
sans sélection prématurée. Elle distingue explicitement une analyse de parsing
d'une lecture de portée résolue.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/nlp-03/run.sh
./poc/nlp-03/run.sh --max-results 50
./poc/nlp-03/run.sh --max-scope-results 10
```

La limite des analyses ACE est au minimum 3 et vaut 25 par défaut. La limite
des solutions de portée vaut 100. Le script produit :

- `output/raw/ace-tsdb.stdout` et `ace-tsdb.stderr`, la sortie ACE brute ;
- `output/raw/candidates.json`, les MRS, arbres et dérivations bruts associés à
  chaque candidat ;
- `output/results.json`, les candidats, diagnostics et différences par rapport
  à l'analyse classée première ;
- `output/summary.json`, le bilan agrégé ;
- `output/versions-and-parameters.json`, les versions, paramètres et la règle
  de construction des identifiants.

## Identité et comparaison

Le rang ACE est conservé, mais n'est pas utilisé comme identité. Le
`candidate_id` est une empreinte du texte, de la MRS, de l'arbre syntaxique et
de la dérivation privée de ses IDs d'arêtes et scores transitoires. Il est
reproductible avec les mêmes versions d'ACE et d'ERG ; il ne prétend pas être
stable entre deux versions de grammaire.

Chaque candidat est comparé au rang 1, et toutes les paires de candidats sont
également comparées, par isomorphisme MRS, égalité de l'arbre, égalité de
dérivation, prédicats ajoutés/retirés et règles de dérivation
ajoutées/retirées. Pour l'ambiguïté d'attachement, la cible sémantique de
`_with_p` est également explicitée.

## Résultat

**GO pour le périmètre contrôlé de NLP-03.** La pile rend et permet de conserver
les analyses concurrentes d'attachement et de structure. ACE/ERG/PyDelphin
fournit une MRS sous-spécifiée ; l'adaptateur Z3 de la POC énumère ensuite ses
solutions sans les classer.

Pour l'analyse canonique de **“Every dog chased a cat”**, il produit exactement
les deux ordres `_every_q > _a_q` et `_a_q > _every_q`. Chaque solution possède
ses bindings, son graphe de dominance, la preuve des `qeq` satisfaits, son
ensemble d'alternatives incompatibles et sa provenance jusqu'au candidat ACE.

Une seconde fixture, **“Every student gave a teacher a book”**, vérifie que le
solveur n'est pas spécialisé pour deux quantificateurs : les six permutations
des trois quantificateurs sont produites pour l'analyse canonique. Les deux
indéfinis sont distingués par leur prédicat restrictif (`teacher` ou `book`).

Le solveur accepte les topologies arborescentes avec contraintes `qeq` et
liaisons quantificateur `RSTR`/`BODY`. Toute MRS malformée ou topologie non
prise en charge reçoit un statut explicite plutôt qu'une solution inventée.

Z3 était déjà présent dans `requirements-cognitive.txt`; aucune dépendance n'a
été ajoutée.

Voir `verdict.md` pour les résultats observés et la décision de tooling.
