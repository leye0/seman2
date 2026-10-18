# Scoped dialogue parsing in Seman2

## Scope and isolation

The canonical general-purpose vector grammar remains unchanged for unquoted
prose. A second `VectorGrammar` is instantiated **only when double quotation
marks are explicit and balanced**; it loads `data/dialogue_grammar.jsonl`
in addition to the ordinary grammar. All normal grammar rule scores, lexical
analyses, and the user's cleaned novel source files remain unchanged.

The dialogue-specific lexical lattice overlays `OPEN-QUOTE`,
`CLOSE-QUOTE` and `SPEECH-STOP` terminals at their actual character spans.
It does not rewrite the corpus, lose quote boundaries, or reclassify
apostrophes in contractions and possessives as quotations.

Supported constructions include:
- Quote-only clauses and some non-clausal fragments (e.g. "Hello!").
- Postposed reporting: `"John walks," said Mary.`.
- Subject-before-verb reporting: `"John walks," Mary said.`.
- Preposed reporting: `Mary said, "John walks."`.
- Quoted interruptions: `"John walks," said Mary, "John listens."`.
- Reporting tags with a PP/adverbial or an additional NP argument.
- Semantic `AGENT` links for reporting verbs, `REPORTED_CONTENT` for
  quoted content, and `CONTINUED_SPEECH` for split quotes.

Public entry points:
- `Parser.parse()`: retains original marked text in a successful dialogue tree;
  dialogue successes are cached.
- `Parser.parse_diagnostic()`: retains quotes and semantic roles in audits.
- `Parser.parse_grammar_lattice(lattice, ...)`: explicitly opt-in parser entry
  point for **future** per-sentence corpus research with quotation support.

Older experiments that deliberately call `parser._vector_grammar.parse_lattice`
directly still run the prior canonical grammar. **Old benchmark numbers are not
retroactively modified.** In particular, reuse/indexing support for the new
structural quote terminals has not yet been audited; no <1ms claim is made
for spoken-text snap hits.

## Validation

- 15 bounded dialogue-specific syntax/semantics tests: quote normalization,
  fragments, both reporting orders, PP reporting tags, interrupted speech,
  semantic identity, diagnostic parsing, caching, and unquoted baseline.
- 16 canonical compiled-structure replay regression tests.
- [GitHub Actions: scoped dialogue tests](https://github.com/leye0/seman2/actions/workflows/dialogue-grammar-regressions.yml).
- **Real cleaned novels smoke** [run 39098797681](https://github.com/leye0/seman2/actions/runs/39098797681):
  20 balanced-quotation excerpts sampled across four separate books (5/book),
  with the same WordNet dictionary setup as research runs:
  - Dickens: 4/5 dialogue-scoped success.
  - Austen: 5/5.
  - Shelley: 2/5.
  - Stevenson: 1/5.
  - **Total: 12/20**. Zero runtime exceptions. These are deliberately a
    tiny smoke cohort, **not** a population coverage estimate.

## Confirmed remaining cases

- Direct-speech spans containing subordinate-only fragments (`"because ..."`),
  compound vocatives, and non-CLAUSE material need additional, carefully
  constrained constructions.
- Long discourse turns with several clauses/semicolons, narrator interjections,
  and narration before the dialogue often fail. These should be understood
  as distinct grammatical/discourse constructions, not erased by sentence cleaning.
- Single apostrophe quote marks are ambiguous with contractions; the first
  implementation supports only balanced double quotation marks, both straight
  and typographic.
- The generic finite-`V` reporting tag is scoped by real quotations but has
  not yet been restricted to independently verified reporting predicates.
- Scoring and speaker/reference correctness on real novel text still require
  human tree validation. A recognized parse is not an independently certified
  linguistic analysis.

Next: label a representative held-out set of true literary dialogue patterns
with expected quote span, speaker, report predicate and quoted content; add
minimal productions and cross-book regression tests rather than broad
rule relaxation or stripping the utterance punctuation.
