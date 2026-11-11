# Seman2 — mandatory source-first corpus and parsing contract

**One active prose segmentation algorithm:** `seman_parser.sentence_boundaries`
and `research.verbnet_lr.gutenberg_novels.analysis_units/extract` always
preserve dependent semicolon clauses, nested reported speech and source
quotation context. There is **no v1/v2 extraction switch or historical
segmentation fallback** in current code. Historical commits and diagnostics
are retained in Git, not as a second production path.

**One public syntactic parsing entry point:** `seman_parser.engine.Parser.parse`.
For every Gutenberg case, ALWAYS use:

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
prepared, lattice, result = parse_corpus_case(parser, case)
```

The extractor supplies the *same source-unit boundaries* for raw and
quote-balanced views, together with precise provenance
(`source_text`, synthetic prefixes/suffixes, and source spans). Do not
manually repair quotation marks, drop alternatives, invent a second parser
or bypass `parse_corpus_case` to inspect novel examples.

**Current benchmark:** `scripts.diagnose_novel_parses.select_cases(500)`
samples the cleaned novels with the current single segmenter. Its SHA-256
is pinned in `docs/CURRENT_COHORT.json`. The pinned corpus must not change
during a normal grammar fix. A deliberate segmentation change requires
re-sampling, a newly validated SHA, a newly generated grammar-case queue,
and a separately reported baseline. **Never compare scores from different
cohort SHAs or carry over old case indices.** The old 475/500 and its
case-numbered research remain historical evidence only.

**Before diagnosing any grammar failure**, read the contiguous source
paragraph and neighboring original units. Confirm that the single active
splitter has not isolated a dependent clause, a shared-subject predicate,
a multi-sentence nested quote or a causal narrative aside. If the split is
wrong, repair `sentence_boundaries.py` and its general positive/negative
regression tests FIRST; do not invent a grammar rule to parse an orphan.
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
