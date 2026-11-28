# Contextual WSD (GlossBERT)

Seman2 now has an optional independent contextual WSD provider, using the
published `glossbert==1.0.6` wrapper and `kanishka/GlossBERT` weights.
The original model was fine-tuned on SemCor 3.0 for context/gloss matching
(Huang et al., EMNLP 2019, https://aclanthology.org/D19-1355/).
Upstream performs retrieval, marking, neural scoring and ordering. The
adapter passes exact character offsets and lemma/POS, then serializes all
returned synsets, original scores, definitions and sense keys. It neither
rewrites MRS nor makes new grammatical decisions. The standard UPOS to
WordNet POS translation is only an interface mapping. Scores are not
calibrated probabilities across senses. A missing sense is not an engine error.

Install CPU torch separately using the official PyTorch index, then
`pip install -r requirements-wsd.txt -r requirements-knowledge.txt`
and install the existing spaCy model and corpora (see EXTERNAL_KNOWLEDGE.md).
The model snapshot is resolved to a full commit in the report. Inference is
local; downloading weights and corpora requires network on first setup.
Use `--wsd` on the existing CLI to attach contextual predictions for all
NOUN/VERB/ADJ/ADV tokens exposed by the external provider. This leaves
ERG outputs and native ranks unchanged. Direct API:
```python
from seman_parser.wsd import WSD
wsd=WSD()
result=wsd.target("They sat on the river bank.",22,26,"bank","n")
```

The diagnostic CI compares the model with WordNet first-sense selection on
28 controlled target instances, including rare literary uses and polysemy
controls. Gold lemma and POS are supplied equally; report exact and broad
lexname results separately. The code detects invalid gold labels and does
not silently count them as misses. The set is exploratory, not a standard
independent benchmark; no WSD result is promoted into the production MRS.
