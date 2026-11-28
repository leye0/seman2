# Independent neural SRL

Default model: HanLP English ModernBERT Large, official checkpoint dated
2025-01-07. Its upstream documentation reports predicate detection F1 98.91
and end-to-end SRL F1 95.86; these are publisher metrics, not Seman2 results.
The English ModernBERT Base checkpoint is also available (reported end-to-end
F1 92.57). See https://hanlp.hankcs.com/docs/api/hanlp/pretrained/mtl.html
and https://hanlp.hankcs.com/docs/data_format.html.

The provider uses the model's native tokenization and joint predicate/span
role detection. It keeps every native frame, every argument (including
adjuncts and reference/continuation labels if returned), original token
offsets, exact source character offsets when alignable, and original output.
Unalignable tokens are explicitly marked; no invented offsets. No grammar,
predicate selection rules or changes to ERG. Numbered roles are predicate
dependent: ARG0 is not universally agent and ARG1 is not universally patient.
This model does not itself return PropBank roleset sense IDs or promise full
nominal/adjectival predicate coverage, implicit arguments or cross-sentence
coreference. GlossBERT remains separate. Models are generally CC BY-NC-SA 4.0
unless otherwise specified by HanLP; verify licensing before commercial use.

Install CPU torch from its official index, then
`pip install -r requirements-srl.txt`. Model downloaded by HanLP on first use;
inference local. CLI add `--srl`. Python:
```python
from seman_parser.srl import SRL
srl=SRL()
report=srl.inspect("Nora gave Felix a book yesterday.")
```

The independent audit uses 30 source-annotated diagnostic sentences and all
327 frozen dialogue passages. It reports partial-target recall at exact and
overlap boundaries, native predicate availability, coverage and role inventory.
No F1 is claimed for partially annotated targets. Native MRS regression remains
separate. None of the target annotations enter the model.
