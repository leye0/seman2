# Seman2 repository instructions — mandatory corpus parsing contract

**CRITICAL:** This project already has an intentional, tested algorithm for
transferring quotation marks when novel text is split at semicolons and between
sentences: `seman_parser.sentence_boundaries.split_prose_analysis_units`.
It preserves the source spans and records synthetic prefixes/suffixes. It is
**not** a repair heuristic or a defect. Do not reimplement this algorithm or
discard/ignore its provenance.

There is only ONE public syntactic parsing entry point:
`seman_parser.engine.Parser.parse(text, ...)`. Do not introduce another
public recognizer or route a benchmark directly into an internal forest.
Options for search budgets belong on that same entry point.

When parsing Gutenberg/novel case records from `gutenberg_novels.extract()`,
**ALWAYS** call:

```python
from research.verbnet_lr.corpus_pipeline import parse_corpus_case

prepared, lattice, result = parse_corpus_case(parser, case)
# The DEFAULT parse uses case["balanced_analysis_text"].
# prepared.source_text remains exactly the original passage.
```

The canonical 500-case score uses the **balanced analysis text** through
`Parser.parse` directly; the historical raw control must NEVER be the
headline score or an implicit alternate engine.

The frozen historical **500-case** corpus is special. Its original
`case["text"]` and `cohort.jsonl` are SHA-256-pinned for longitudinal
comparisons. To explicitly reproduce the historical *unbalanced* control,
and only for that purpose:

```python
from research.verbnet_lr.corpus_pipeline import CorpusParseMode
prepared, lattice, result = parse_corpus_case(
    parser, case, mode=CorpusParseMode.HISTORICAL_REFERENCE
)
```

The legacy corpus result is a **control**, not the new recommended way to
analyze a novel. New experiments always start with the default
`QUOTE_BALANCED` mode. Never claim a grammar regression solely because the
original historical text lacks context that the quote-transfer system provides.

Prose segmentation v2 conservatively retains dependent semicolon continuations.
`split_prose_analysis_units` uses that improvement by default, but
`gutenberg_novels.analysis_units` and `extract` default to the **original v1
segmentation** to protect the SHA-pinned 500-case cohort. Use
`extract(..., segmentation_version=2)` for a separately measured prospective
corpus; see `docs/SEGMENTATION_V2_DEPENDENT_CLAUSES.md`. Do not conflate
better segmentation with evidence of a correctly attached grammar tree.

The `superparser/tests/test_novel_parse_diagnostics.py` CI tests enforce
the gateway, provenance, and the absence of direct parser calls in the
500-case diagnostic. Modify these tests and this contract together when
changing the architecture. The existing cohort checksum remains immutable
unless the benchmark itself is deliberately versioned.

**For every individual grammar/corpus sentence fix**, first read and follow
[`docs/GRAMMAR_CASE_FIX_PROTOCOL.md`](docs/GRAMMAR_CASE_FIX_PROTOCOL.md).
It defines the acceptance criteria for a correct selected tree, exact
attachments, independent positive/negative tests, no regressions, unchanged
budgets, and efficient staged validation. A completed parse alone is not
proof of a grammatical correction.
