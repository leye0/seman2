# LEX-03 — NLTK PropBank et Treebank

Cette POC établit les données réellement accessibles dans PropBank 1.0 via
NLTK : inventaire de rolesets, descriptions des arguments, exemples lexicaux,
instances annotées et pointeurs vers les constituants du Treebank.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-03/run.sh
```

Le script régénère :

- `output/results.json`, les rolesets et instances structurés ;
- `output/resource-vs-annotation.json`, la frontière entre consultation de la
  ressource, annotation existante et analyse d'une nouvelle phrase ;
- `output/raw/annotation-lines.json`, les lignes natives de `prop.txt` ;
- `output/raw/frame-xml.json`, les fichiers de frames natifs concernés ;
- `output/raw/parse-trees.json`, les arbres Penn Treebank des fixtures ;
- `output/summary.json` et `output/versions-and-parameters.json`.

## Résultat

**PARTIEL comme lecteur de corpus, avec inventaire lexical exploitable.** NLTK
expose les rolesets, leurs arguments, leurs correspondances VerbNet et les
112 917 annotations PropBank. Les six fixtures démontrent des arguments
`ARG0`–`ARG2`, des modificateurs `ARGM-*` ainsi que des pointeurs simples,
scindés et chaînés résolus en positions d'arbre et terminaux.

Le Treebank installé avec NLTK ne contient toutefois que 199 fichiers : les
arbres sont disponibles pour 9 353 des 112 917 annotations PropBank. Le paquet
NLTK `ptb` est également installé ; il fournit le catalogue `allcats.txt` de
2 504 fichiers, mais aucun arbre `.MRG`. Les lignes d'annotation restantes
restent lisibles, mais `instance.tree` vaut `None` sans une copie licenciée du
Penn Treebank complet ajoutée à ce paquet.

PropBank n'est pas un analyseur automatique. Un lookup par lemme énumère les
rolesets possibles ; le roleset d'une fixture vient de l'annotation existante
dans `prop.txt`, et non d'une décision prise sur une phrase nouvelle.

Voir `verdict.md` pour les exemples, les limites et l'impact architectural.
