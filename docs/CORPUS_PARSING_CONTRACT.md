# Point d'entrée unique de Seman2 — corpus et moteur

**Un seul moteur public : `Parser.parse(text, ...)`.** Le diagnostic
des 500 phrases, les tests d'intégration et les usages normaux doivent
tous passer par cet appel. Les paramètres de budget
(`max_items`, `kbest_work_limit`, `diagnostic_k`) sont des options
du **même** moteur ; ils ne sélectionnent jamais un second chemin.

Pour les enregistrements littéraires, la préparation du texte est
une responsabilité séparée, sans moteur concurrent :

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case

prepared, lattice, result = parse_corpus_case(parser, case)
# parse_corpus_case appelle Parser.parse(prepared.analysis_text).
# lattice est la vue lexicale du même Parser et de ses mêmes paramètres.
```

`prepare_corpus_input` valide que le contexte des guillemets est
transféré par `gutenberg_novels.extract()` via
`seman_parser.sentence_boundaries`. Aucun script ne répare ou ne
reconstruit indépendamment ces guillemets. Toute provenance absente
provoque une erreur.

Le **découpage actif est unique** : `analysis_units()` et `extract()`
n'exposent pas de paramètre v1/v2. Tous les échantillons sont reconstruits
avec les mêmes règles de frontières, y compris les propositions dépendantes
et les citations imbriquées. Le benchmark courant de 500 unités porte
la **signature figée de sa version actuelle** dans
[`CURRENT_COHORT.json`](CURRENT_COHORT.json), et analyse exclusivement
le texte équilibré via `Parser.parse`. Quand la segmentation change,
on crée une **nouvelle référence** : nouveau SHA, nouveau score, nouveaux
indices de file. On ne revendique aucune progression en comparant les
totaux de cohortes différentes. Les anciennes cohortes appartiennent à
l'historique Git, pas au chemin d'exécution.

Pour une recherche de compatibilité historique seulement :

```python
from research.verbnet_lr.corpus_pipeline import CorpusParseMode
prepared, lattice, result = parse_corpus_case(
    parser, case, mode=CorpusParseMode.HISTORICAL_REFERENCE,
)
```

Cette option explicite ne change pas l'entrée du moteur. Elle
change exclusivement les données soumises à celui-ci.

**Tests anti-contournement :**
`superparser/tests/test_novel_parse_diagnostics.py` vérifie
que le script passe par `parse_corpus_case`, que celui-ci
appelle `Parser.parse` et qu'aucune autre entrée cachée ou autre
préparation lexicale n'est invoquée. Les tests d'intégration
exercent le même point d'entrée public.
