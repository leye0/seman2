# VerbNet / Seman2 — experimental L→R lexical hint adapter

This prototype parses locally supplied VerbNet 3.4 XML and optionally joins VerbNet WordNet sense keys to WordNet `dict/index.sense`. It exposes ordered post-verb slot expectations to the existing Seman2 lexical candidates without changing morphology, grammar, runtime, or packed forests. Missing data always yields **UNKNOWN, not grammatical rejection**.

Use from `superparser`:

```python
from research.verbnet_lr import compile_xml, Index, predict_candidate
frames = compile_xml("/path/to/verbnet3.4", "/path/to/WordNet-3.0/dict/index.sense")
index = Index(frames)
hint = predict_candidate(index, lexical_candidate, ("NP", "PREP:to"))
```

The `observed` argument consists of structural events such as `NP`, `PREP:to`, `TO_INF`, not raw words. The caller owns recognition and handles ambiguity. This is a positive-evidence interface, **not an exhaustive valency grammar**. XML features not supported are excluded rather than promoted into false syntax. Subclasses inherit parent frames, but parents do not inherit child frames.

Known limitations: ambiguous WordNet sense coverage; no strong rejection; this initial prefix matcher scans candidate frames (upgrade to indexed prefix trie after benchmarking); no integration into the L→R hot path yet. The fuller local prototype includes a trie, export format, unit tests and provenance.
