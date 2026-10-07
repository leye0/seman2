# LEX-02 — NLTK VerbNet

Cette POC établit les données réellement accessibles pour un lemme verbal avec
NLTK VerbNet : classes candidates, hiérarchie, membres, rôles thématiques,
restrictions, cadres syntaxiques et prédicats sémantiques.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-02/run.sh
```

Le script régénère :

- `output/results.json`, classes et cadres structurés ;
- `output/context-independence.json`, preuve que le lookup ne classe pas une
  occurrence en contexte ;
- `output/raw/lookups.json` et `raw/class-xml.json`, sorties et XML natifs ;
- `output/summary.json`, bilan quantitatif ;
- `output/versions-and-parameters.json`, versions et paramètres.

## Résultat

**GO comme ressource de classes verbales candidates.** Les cinq fixtures
produisent 15 classes, 66 cadres locaux et 72 cadres distincts lorsqu'on inclut
les définitions disponibles le long des hiérarchies. La POC expose 42
déclarations de rôles, 294 éléments syntaxiques, 26 restrictions de sélection,
7 restrictions syntaxiques et 221 prédicats sémantiques.

Les restrictions sont conservées sous deux formes : la vue pratique aplatie de
NLTK et l'arbre logique natif du XML VerbNet. Les cadres et rôles de chaque
niveau parent restent également attribués à leur classe d'origine.

Le lookup ne choisit aucune classe pour une occurrence. Deux phrases employant
`break` différemment reçoivent les mêmes cinq classes candidates et
`selected_class_id` reste nul.

NLTK et VerbNet sont déjà installés. Aucune bibliothèque supplémentaire n'est
requise.

Voir `verdict.md` pour les exemples et les limites.
