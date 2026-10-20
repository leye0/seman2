# Contrat d'analyse du corpus littéraire (Seman2)

La séparation des phrases et des points-virgules est **déjà** associée à
un transfert volontaire des guillemets. Le contrat logiciel interdit
désormais l'oubli de ce transfert dans les diagnostics.

### Entrée unique

`research.verbnet_lr.corpus_pipeline.parse_corpus_case(parser, case)`
est l'entrée recommandée et utilise **par défaut** l'unité contenant les
guillemets rééquilibrés. La structure `PreparedCorpusInput` documente
le texte original, celui du témoin historique, le texte soumis au parseur
et les signes synthétiques. Si un cas ne contient pas ces métadonnées, une
erreur est levée **avant** de parser : pas de repli silencieux vers le texte brut.

Le témoin historique des 500 phrases peut toujours être évalué, mais il
requiert un argument explicite
`mode=CorpusParseMode.HISTORICAL_REFERENCE`. Cette distinction conserve le
SHA-256 immuable du `cohort.jsonl` et permet la comparaison appariée.

### Barrières anti-régression

Le diagnostic appelle `parse_corpus_case` pour **les deux** modes, sans
appeler `parser.parse_grammar_lattice` directement. Des tests unitaires
vérifient le mode par défaut, l'immuabilité du `source_text`, les guillemets
transférés, l'échec sur provenance absente et, via AST, l'absence de bypass
du chemin standard. Le workflow GitHub exécute ces tests lors des changements
de la préparation du corpus et de son API.

Le découpage et le suivi de la pile de guillemets demeurent uniquement dans
`seman_parser.sentence_boundaries`. **Aucune seconde logique de réparation
des guillemets n'est introduite.**

### Exemple reproductible

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case, CorpusParseMode

prepared, lattice, parsed = parse_corpus_case(parser, case)
assert prepared.mode == CorpusParseMode.QUOTE_BALANCED

reference, old_lattice, old_result = parse_corpus_case(
    parser, case, mode=CorpusParseMode.HISTORICAL_REFERENCE,
)
assert prepared.source_text == reference.source_text
```
