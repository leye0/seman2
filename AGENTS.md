# Seman2 — mandatory source-first corpus and parsing contract

**One active corpus-extraction path:** normalized Gutenberg paragraphs →
seman_parser.structural_preanalysis.analyze_paragraph → typed complete
utterance + source-core spans → research.verbnet_lr.gutenberg_novels.extract →
research.verbnet_lr.corpus_pipeline.parse_corpus_case → Parser.parse.
Semicolons are NEVER independent extraction boundaries. They are preserved as
intra-utterance typed source constituents with governor references. Short,
multi-sentence quotation blocks stay intact. Unmatched speech quotation marks
are NOT synthetically closed. Such source units are documented as requiring
context and excluded from the active parse benchmark, not falsely "completed".

The older sentence_boundaries module remains a lower-level typographic
heuristic/test utility; its split_analysis_units is NOT the production
Gutenberg corpus extractor. Historical rule fixtures are frozen as test data,
not resurrected as a second production segmentation mode.

**One public syntactic parsing entry point:** `seman_parser.engine.Parser.parse`.
For every Gutenberg case, ALWAYS use:

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
prepared, lattice, result = parse_corpus_case(parser, case)
```

The extractor supplies exactly the same *source-complete* utterance for
both compatibility views. Each corpus case includes source paragraph index,
paragraph-relative offsets, original cleaned-book offsets, provisional typed
constituents, governor references, and quotation status. New corpus cases
carry NO synthetic quote or terminal punctuation. Never drop alternatives,
invent a second grammar engine or bypass `parse_corpus_case`.

**Current benchmark:** `scripts.diagnose_novel_parses.select_cases(500)`
samples the cleaned novels with the current single segmenter. Its SHA-256
is pinned in `docs/CURRENT_COHORT.json`. The pinned corpus must not change
during a normal grammar fix. A deliberate segmentation change requires
re-sampling, a newly validated SHA, a newly generated grammar-case queue,
and a separately reported baseline. **Never compare scores from different
cohort SHAs or carry over old case indices.** The old 475/500 and its
case-numbered research remain historical evidence only.

**Active paragraph-level grammatical preanalysis:**
`seman_parser.structural_preanalysis.analyze_paragraph` produces full utterance
boundaries from contiguous paragraphs (no semicolon splitting or fabricated
quotation marks), original paragraph offsets and typed constituents with
source spans, governor IDs and explicit descriptive relations. Its functions
(`matrix_clause`, `coordinate_clause`, `nonfinite_clause`, `direct_speech`,
`reporting_clause`, `adverbial_subordinate_clause`, etc.) are **provisional**
and do not assert a correct complete parse. The corpus gateway validates these
references and exposes them as `PreparedCorpusInput.structural_constituents`.
Quotes unmatched within the source paragraph are flagged `requires_source_context`
and **excluded from parse sampling**. Conservative discourse triage also
separates source-dependent afterthoughts (e.g. `Only upon us two.`),
quoted in-medias-res clause continuations, documentary map bearings and
postscript wrappers from independent matrix clauses. Formulaic replies and
salutations are valid **minor utterances**, not automatically bad segments.
All decisions have an explicit evidence label; dependent discourse links
point to the prior source-book span (a candidate, not asserted syntactic
coreference). The evidence classifier never treats lowercase starts alone
as proof of incompleteness. They are not made valid by synthetic
punctuation. The full engine still accepts one text input at a time; the
source-span graph does not yet rewrite its grammar search.

**Semicolon cohesion heuristic (supporting component evidence, not
independent production slicing):**
`seman_parser.structural_units.review_semicolon_boundaries` is consulted
by `structural_preanalysis.constituency` to type intra-utterance edges
**before full `Parser.parse`**.
It records a reason for each proposed semicolon boundary; it may join only
on explicit surface dependency evidence (e.g. shared subject, PP series,
causal conjunction, omitted matrix or parallel nominal ellipsis). It is
**not a second parser** and does not certify grammatical completeness.
Keep independent-clause negative controls and exact source provenance.

**Grammar rule-risk audit:** `python -m scripts.audit_fragment_grammar_rules`
compares current rule IDs against an October 11 snapshot and lists high-risk
elliptical/root productions for review. No removal is permitted without
selected-tree evidence, source-context justification, and successful
independent positive/negative contrasts. Never equate a heuristic flag with
proof of an invalid rule.

**Before diagnosing any grammar failure**, inspect the typed constituents,
source quote context and the original contiguous paragraph. If the unit is
incomplete or a governor reference is unsupported, fix
`structural_preanalysis.py` and its general positive/negative controls
BEFORE touching grammar.jsonl. Do not invent a grammar rule to parse an orphan.
The graph records provisional functions but the full parser still receives
an entire text unit; no claim is made that the full grammar already uses
these constituent edges to prune its search.
Verify lossless round-trips, transferred quote provenance, independent
sentence controls, and changes in sampled case identity.

The `docs/GRAMMAR_CASE_FIX_PROTOCOL.md` specifies all further
requirements: correct selected rank-one tree and exact attachments,
WordNet 3.0, unchanged parse budgets, positive/negative controls,
full-cohort comparison on an identical SHA, and green CI. A parsed
root alone is not a successful grammatical correction.

**CI hygiene:** use the active Layer 1 and current 500-case workflows.
Old case-index-specific research or 26-residual studies may be consulted
historically but MUST NOT enter the current cohort gate. Merge only
validated changes; close abandoned research PRs.
