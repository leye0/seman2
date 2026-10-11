# SuperParser syntax/semantics boundary

## Contracts

- `segmentation.py` tokenizes and projects lexical resources into grammatical
  candidates. A candidate exposes form, span, lemma, category, features,
  grammatical constraints, score, provenance and stable sense ids. It does
  not expose semantic types in its public serialization.
- `grammar.py` loads only syntactic rules. `data/grammar.jsonl` has no semantic
  recipes.
- `chart.py` and `vector_chart.py` recognize, pack and lazily materialize
  syntax. Parser-produced `ChartItem.semantic` is always `None` (deprecated
  compatibility slot); `ChartItem.syntax` contains occurrence anchors and
  direct structural exports.
- `semantic_rules.py` loads `data/semantic_rules.jsonl`, keyed by syntax rule
  id. It is imported only when interpretation is explicitly requested.
- `semantics.SemanticInterpreter` consumes one selected tree and reconstructs
  the former graph/actions. `ParseReport.interpret(tree)` is the public entry
  point; `sense_selection={anchor: sense_id}` can select a retained lexical
  interpretation.
- `mentions.py`, `refdetect.py` and discourse reference detection consume the
  syntax tree and morphosyntactic features without requiring a graph. The
  optional `semantic=` argument enriches mention types/node ids when a caller
  has requested interpretation. `reader.py` does this only after parsing, then
  merges the separate result into discourse state.

## Syntactic lexical equivalence

`LexicalCandidate.syntactic_signature()` includes span, category, complete
feature structure, normalized lexical identity, syntactic subcategorization
constraints and an optional segment-interface identity. Candidates are merged
only when this signature is equal. Their sense ids and provenance remain in
`interpretations`; sense count and sense frequency do not create extra parser
paths. Distinct POS, morphology, particles, frames or interfaces stay distinct.

## Public syntax result

`ParseResult` retains the original text, tokens/lattice, shared forest,
alternatives, scores and statistics. Every selected tree retains spans,
features, rules, resolved bindings, lexical occurrence references, structural
anchors/links and recursive provenance. `ParseResult.as_dict()` serializes this
syntax without triggering semantic imports or graph construction.

## Compatibility

The old `best.semantic.graph` contract is intentionally replaced by
`report.interpret(best).graph`. `ParseReport.best_semantic_graph()` remains a
convenience facade. `ChartItem.semantic` remains only so older code can build
synthetic fixtures; the parser never writes it.

## Dependency audit

- `semantic_type` remains in the source lexicon catalog and WordNet importer,
  but is resolved only by `SemanticInterpreter`; it is absent from lattice
  serialization, recognition, scoring and materialization. The ontology in
  `types.py` is exposed through a lazy compatibility proxy and is not loaded
  by `Parser.parse()`.
- WordNet `sense_id` values survive only as lexical references. Multiple ids
  share a candidate when their full syntactic signature is equal.
- WordNet frames contribute their syntactic slots/features to the equivalence
  signature. Their semantic role labels do not. `bind_frame_roles()` remains
  available to semantic clients; it was not invoked by the historical active
  parser path either.
- Semantic graphs/packages/actions are created or consulted only in
  `semantics.py`, `semantic_rules.py`, and discourse state. Neither chart
  implementation imports those modules.
- `mentions.py` identifies NP and event mentions from categories, features,
  lexical occurrences and syntax anchors. `refdetect.py` primarily consumes
  these structures; its optional `semantic_type == EVENT` fallback is not
  required because event mentions carry `kind == event`.
