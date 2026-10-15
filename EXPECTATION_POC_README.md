# SuperParser — POC *active expectations* (v0)

**Statut : prototype expérimental isolé ; ne modifie pas le moteur de production.**

Une implémentation réellement différente du prédictif V1/V2 : **l'état de base est une attente grammaticale ouverte**, et non une pile d'actions SHIFT/REDUCE à essayer. Dès que `CLAUSE` réclame un `NP`, le moteur ouvre seulement les productions capables de fabriquer ce `NP`; quand `NP` attend `DET`, il ne consulte que les candidats lexicaux `DET` présents à cette position. Les constructions peuvent se prolonger grâce aux règles existantes de la grammaire (`NP → NP PP`, relatives, etc.).

## Intégration au dépôt

Extraire l'archive à la racine de `leye0/seman2` :

```bash
unzip -o seman2_expectation_poc.zip
cd superparser
PYTHONPATH=. pytest -q tests/test_expectation_parser.py
python scripts/bench_expectations_300.py --limit 30 --trace-first \
  --output expectation_30.json
python scripts/bench_expectations_300.py --limit 300 --baseline \
  --output expectation_300.json
```

Les seuls fichiers ajoutés sont :

- `superparser/seman_parser/expectation_parser.py` — nouveau moteur.
- `superparser/scripts/bench_expectations_300.py` — benchmark et diagnostic, 300 phrases existantes.
- `superparser/tests/test_expectation_parser.py` — tests d'intégration à lancer dans le dépôt.

Les fichiers de production, la grammaire et les ressources lexicales ne sont **pas modifiés**. Le benchmark utilise `data/seman2_reference_300_compact.json` déjà présent dans le dépôt, ainsi que les données WordNet configurées par le projet. Le modèle statistique V2 existant est réutilisé en lecture seule via `TransitionModel`.

## Nouvelle interface

```python
from seman_parser.expectation_parser import ExpectationParser
from seman_parser.predictive import TransitionModel

parser = ExpectationParser.from_dir(
    'data',
    model=TransitionModel.load('data/predictive_transitions.json'),
    max_states=60_000,
)
result = parser.parse('I saw the man with a telescope.')
print(result.completed, result.stats)
if result.completed:
    print(result.item)       # ChartItem, même type que SuperParser
    if result.ambiguities:
        alternative = parser.expand(result, 0)
        print(alternative.item if alternative.completed else 'aucune autre dérivation trouvée')
```

`expand` reprend la recherche d'attentes et le lattice de la même session. Les variantes partageant catégorie/span/traits sont conservées jusqu'à `alternatives_per_node=2` par défaut. Elles sont **plausibles selon la grammaire**, sans garantie d'être idiomatiques ; le moteur n'affirme pas les avoir toutes trouvées.

## Algorithme

1. Compile une seule fois les index de `PredictiveGrammar` et un index `LHS → règles`.
2. Initialise les **attentes** du but `CLAUSE` au début de la phrase.
3. À chaque point de la lecture, ouvre seulement les productions demandées par les attentes et compatibles avec les catégories FIRST disponibles au prochain mot.
4. Compare les catégories lexicales réelles aux catégories explicitement attendues ; chaque lecture lexicale n'est activée qu'à la demande.
5. Quand un enfant est reconnu, reprend uniquement les constructions qui l'attendaient (`waiting[(position, category)]`).
6. Réutilise l'unification, les `requires`, les preuves de traits, les règles et la matérialisation native existantes (`PredictiveParser._reduce` et `_materialize`).
7. Réutilise `TransitionModel` pour pondérer **l'ordre** d'exploration, sans changer les contraintes grammaticales.
8. Arrête au **premier `CLAUSE` complet couvrant l'entrée** ; les alternatives connues restent différables via `expand`.

Aucun appel caché à `Parser.parse`, `VectorGrammar`, `HybridPredictiveParser` ou à un fallback de production. Les statistiques `fallback` indiquent toujours `False`.

## Comparaison équitable

Le script `bench_expectations_300.py --baseline` mesure dans un même processus la production et la POC avec le même `ParserResources`, après un amorçage WordNet, sans cache de phrase pour la production. Il rapporte :

- Couverture *native* et causes d'échec pour chaque phrase.
- p50/p95/p99/max sur **toutes** les phrases, y compris les échecs.
- Nombre de demandes et d'activations d'attentes, scans lexicaux, unifications, partages de nœuds et transitions.
- Correspondance exacte **normalisée à titre diagnostique**, sans confondre un arbre différent avec une erreur syntaxique.
- JSON détaillé, une entrée par phrase, avec les catégories attendues à chaque position.

L'échantillon de 300 phrases a déjà servi au développement du projet et au modèle `predictive_transitions.json` : la mesure **ne constitue pas un holdout de généralisation**.

## Ce qui reste à établir

- **La vitesse et la couverture réelles sur les 300 phrases ne sont PAS encore mesurées.** Le code a passé la vérification de syntaxe Python et un test isolé avec une grammaire miniature injectée ; pas d'exécution end-to-end sur le dépôt privé dans cet environnement.
- La recherche dirigée par les attentes risque encore d'exploser sur certaines ambiguïtés longues. Elle réduit les prédictions inutiles, mais ne garantit pas une complexité linéaire.
- Le partage limité à 2 dérivations par état grammatical est un compromis expérimental, potentiellement incomplet. Pour mesurer un mode plus léger, construire `ExpectationParser(..., alternatives_per_node=1)` ; pour examiner davantage d'ambiguïtés, 3 est accepté. Une analyse rare peut être perdue dans les deux cas.
- Les contraintes sémantiques n'ont **pas** été ajoutées. Les analyses générées par une grammaire trop permissive nécessitent un audit.
- Le filtrage FOLLOW est désactivé par défaut pour préserver la couverture ; `--follow` permet son ablation, avec risque de faux négatifs.
- Le moteur utilise un chart d'attentes partagées : c'est une POC de **prédiction conditionnée par la construction ouverte**, pas une preuve que le calcul humain réel suit cet algorithme.

**Le benchmark doit décider si cette direction mérite d'être poursuivie.** Ne pas intégrer au runtime de production avant validation sur 300 phrases, audit de plausibilité et holdout indépendant.
