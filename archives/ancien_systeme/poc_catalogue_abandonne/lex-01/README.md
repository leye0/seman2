# LEX-01 — NLTK WordNet

Cette POC établit les données lexicales réellement accessibles depuis une forme
ou un lemme avec NLTK WordNet : synsets candidats, identifiants, lemmes,
définitions, exemples et relations lexicales/sémantiques immédiates.

## Exécution

Depuis la racine du dépôt :

```bash
./poc/lex-01/run.sh
```

Le script régénère :

- `output/results.json`, tous les synsets candidats et leurs relations ;
- `output/context-independence.json`, démonstration que le lookup n'effectue
  pas de désambiguïsation contextuelle ;
- `output/raw/lookups.json`, appels et résultats natifs de lookup ;
- `output/summary.json`, bilan quantitatif ;
- `output/versions-and-parameters.json`, versions et paramètres.

## Résultat

**GO comme ressource de candidats lexicaux.** Les sept fixtures produisent 64
synsets, 162 lemmes et toutes les familles relationnelles demandées :
hyperonymes, hyponymes, méronymes, holonymes, antonymes et formes dérivées.

WordNet ne choisit aucun sens. Pour deux phrases où `bank` signifie
respectivement une rive et une institution financière, le même lookup renvoie
les mêmes 18 candidats et `selected_synset_id` reste nul.

Le composé `credit card` illustre aussi une obligation d'adaptation : la clé de
surface avec espace ne retourne rien, tandis que la clé WordNet explicite
`credit_card` retourne `credit_card.n.01`. La transformation demeure tracée.

NLTK et WordNet sont déjà installés par l'environnement du projet. Aucune
bibliothèque supplémentaire n'est requise.

Voir `verdict.md` pour les exemples en langage humain et les limites.
