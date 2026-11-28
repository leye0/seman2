# Seman2 — source-first ERG analysis

One grammatical engine: **ERG 2025 + ACE 0.9.34**, via PyDelphin. Seman2 retains its original paragraph/quote extraction, exact source offsets and provisional dialogue/discourse graph. It exposes full native MRS and derivations in native rank order, plus separate exact speech/reporting spans. A partial success never certifies a whole utterance.

## Use

Install Python 3.12+, `pip install -e .`, and the native ACE binary and compatible ERG grammar image (see [CI](.github/workflows/native-erg-novel1000.yml) for pinned releases).

```sh
PYTHONPATH=superparser python -m seman_parser --ace /path/to/ace --grammar /path/to/erg.dat --text '"Come here," said John, "and sit down."'
```

```python
from seman_parser import Parser
with Parser("/path/to/erg.dat", executable="/path/to/ace") as parser:
    report = parser.parse_paragraph('"Come here," said John.')
```

`parse(text)` handles a single exact utterance. `parse_paragraph(text)` retains spans relative to the original paragraph; component spans are relative to their unit, MRS offsets relative to the corresponding input. `research.verbnet_lr.gutenberg_novels.analysis_units` exposes source units from cleaned books, including original book offsets. The name of this historical package is kept for source compatibility, not to imply VerbNet supplies grammar. Source hypotheses are not validated semantic edges.

## Validation

```sh
PYTHONPATH=superparser python -m unittest discover -s superparser/tests
PYTHONPATH=superparser python -m scripts.benchmark_native_erg --ace /path/to/ace --grammar /path/to/erg.dat --out-dir /tmp/native-erg
```

The exact Novel-1000 v3 source anchors and original cleaned editions are retained. See [migration audit](docs/ERG_MIGRATION.md) and [paired historical evaluation](docs/NATIVE_ERG_COMPARATIVE_AUDIT.md). The old parser, rules, recipes and obsolete experiments are recoverable at [pre-migration commit](https://github.com/leye0/seman2/tree/99595036d49d3756d080b9e798d94640d73aae4c), not active code. Future work is independent validation, robust discourse exposure and semantic enrichment, not rebuilding grammar rules.

## Dialogue graph

See [the source-linked MRS dialogue graph](docs/DIALOGUE_GRAPH.md). The default paragraph API exposes alternative native analyses, exact source maps, reporting and resumption links and additional ERG views of interrupted speech.
