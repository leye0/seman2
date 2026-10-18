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

## Larger real-novel quote-bearing audit (2026-10-18)

[Run 39136905334](https://github.com/leye0/seman2/actions/runs/39136905334)
succeeded: 17 bounded dialogue-unit tests, 16 canonical regression tests and
both corpus checks. The new deterministic length-stratified research cohort has
40 sentence spans per checked-in novel (160 total), drawn from 4–32 token
sentences containing balanced explicit **double** quotation boundaries.
This is **not** a human-validated corpus of 160 true direct-speech utterances.
Not every quoted span is dialogue (quoted titles, words, verse, etc.); some
selected sentence spans still have truncated surrounding speech punctuation.

- 74/160 (46.25%) yielded a completed dialogue-scoped parse.
- 13/160 yielded a completed **ordinary-grammar fallback**, which does not
  establish that the quotation or speaker was represented.
- 73/160 yielded no completed parse. There were **zero runtime exceptions**.
- Per book (scoped/fallback/unparsed): Dickens **11/8/21**; Austen **16/0/24**;
  Shelley **19/5/16**; Stevenson **28/0/12**.
- Per sentence length: 4–8 tokens **25/36**, 9–16 **22/41**,
  17–24 **15/41**, 25–32 **12/42** dialogue-scoped.
- By visible punctuation layout (not a linguistic label):
  * quote alone **16/36**;
  * narration after quoted span **33/54**;
  * narration before quoted span **6/18**;
  * narration both before and after quoted span **5/21**;
  * multiple quoted spans **14/31**.

The original 20-item smoke still runs separately, unchanged. Its 12/20 and
this audit's 74/160 **cannot be interpreted as a before/after regression**
because the samples and length distribution differ.

Representative failures include authentic interrogatives (e.g.
`“Can you come to-morrow?”`), subordinate-only speech fragments, interleaved
narrative, embedded direct quotations and multi-clause utterances; some long
items hit the 20,000-item forest ceiling. Other failures are not necessarily
grammar bugs: a Dickens example `‘And, “pretty.”’` uses nested typographic
single and double quotations, while individual extracted sentence boundaries
can have unpaired outer single quotes. Distinguish corpus segmentation,
quotation recognition, grammatical completeness, and correct semantic roles
before changing production rules.

Next research priorities:
1. Manually label a small held-out cross-book sample with **true dialogue vs
   quoted mention**, original paragraph boundaries, exact quote spans,
   speaker, reporting predicate and expected semantic links.
2. Fix residual dialogue-aware sentence segmentation where original paragraph
   context shows a mistaken cut. Do not normalize away literary punctuation.
3. Repair independently confirmed syntactic constructions (interrogative,
   vocative, multi-clause, split quoted utterance), with negative controls to
   reject false dialogue and preserve ordinary prose analyses.
4. Re-run **the same frozen samples** to measure coverage and semantic
   correctness, rather than comparing unrelated smoke samples.

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
