# Canonical Layer 1 research utilities

The directory name `verbnet_lr` is **historical**, not the name of the current parser. The compiled left-to-right VerbNet reader, template snapping, partial witness and hybrid C alternatives were explicitly retired from the active tree during cleanup. Their code is recoverable from Git history at `e8322eb7fdb6ab1213c1a44f9b3d032f29d4d7a8`; their research findings remain summarized in [docs/RESEARCH_HISTORY_AND_DECISIONS.md](../../../docs/RESEARCH_HISTORY_AND_DECISIONS.md). Do not import removed modules or treat a template hit as a grammatical analysis.

The **retained executable helpers** are:

- `clean_novel_corpus.py`: manifest-based integrity and loading of the **four checked-in cleaned public-domain novels** in `corpora/`. Their punctuation and quote evidence must remain untouched.
- `gutenberg_novels.py`: reproducible Gutenberg extraction and sentence-band selection (dependent on the canonical sentence segmenter).
- `continuation_probe.py`: a read-only grammar-prefix risk analyzer compiled from the same rules as the authoritative vector parser. It does **not** alter parsing, remove lexical alternatives or certify grammatical correctness.

The actual Layer 1 parser remains `superparser/seman_parser/engine.py` + `vector_chart.py`, with `segmentation.py` and the declarative grammar in `superparser/data/`.

## Tests

```bash
PYTHONPATH=superparser python -m research.verbnet_lr.clean_novel_corpus --check
PYTHONPATH=superparser python -m unittest -v superparser.tests.test_continuation_probe superparser.tests.test_structural_prefix_risk
```

For the architecture, output contract, limitations and future Layer 2 interface, see the [root README](../../../README.md) and [Layer 1 architecture](../../../docs/ARCHITECTURE_LAYER1.md).
