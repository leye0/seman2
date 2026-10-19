# Seman2

**Canonical linguistic parser:** a token-preserving symbolic **Layer 1** that produces structured grammatical analyses for future semantic, referential and memory layers. The research focus is **high coverage and low latency on real-world text**, especially long, ambiguous, quoted and dialogue-heavy sentences.

Start here:

- [Layer 1 architecture, output contract and boundaries](docs/ARCHITECTURE_LAYER1.md)
- [Current limitations and measured roadmap](docs/KNOWN_LIMITS_AND_ROADMAP.md)
- [Why this architecture: research history and abandoned approaches](docs/RESEARCH_HISTORY_AND_DECISIONS.md)
- [Corpus preservation policy](docs/CORPORA_AND_DATA.md)
- [Lossless shared-prefix storage prototype](docs/SHARED_PREFIX_STORAGE_PROTOTYPE.md)
- [Prediction-first adaptive complexity routing and its research limits](docs/ADAPTIVE_COMPLEXITY_ROUTING.md)
- [Category-prefix trie recognition: proof, measured potential and remaining work](docs/CATEGORY_PREFIX_TRIE_FINDINGS.md)
- [Observed subtree signature cache: cross-book benchmark and limits](docs/SUBTREE_SIGNATURE_CACHE_FINDINGS.md)
- [Current ChatGPT research handoff and exact next steps](docs/CURRENT_RESEARCH_HANDOFF.md)

## The active execution path

`ParserResources.from_dir(superparser/data)` → lexical candidates and a lattice (`seman_parser/segmentation.py`) → **canonical** packed vector grammar (`seman_parser/vector_chart.py`, `engine.py`) → a `ParseResult` containing the lattice, original analyzed text, shared forest, derivation alternatives and complete syntax trees (when available). The selected tree can later be interpreted into semantic relations (`semantics.py`). This separation is deliberate.

Quotation handling uses a separate quote-aware grammar and careful sentence segmentation. The structural-continuation predictor (`research/verbnet_lr/continuation_probe.py`) is **read-only and off the hot path** until independently validated.

We are **not claiming Layer 2 is implemented**. The interface exposes syntax and lexical evidence that Layer 2 can consume; referential/discourse utilities already exist, but a complete understanding/learning/memory layer remains future work.

## Validation

The focused regression workflow `.github/workflows/core-seman2-validation.yml` checks grammatical completion, semantics, quotation and the structural diagnostics with WordNet 3.0. Research benchmarks are documented and reproducible as separate experiments rather than continuous heavy CI jobs.

The past experimental readers, template-snapping and C/hybrid approaches are not the canonical parser; see the historical decision record before reviving them.
