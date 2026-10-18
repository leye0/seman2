# Seman2 — Layer 1: canonical grammatical parser

**Status:** current architecture (18 October 2026). **Goal:** deliver grammatically meaningful sentence structures to a future Layer 2, *fast*, without discarding the original words or lexical ambiguity.

## 1. Contract between layers

Layer 1 receives a text span and produces one `ParseReport` containing a `ParseResult`. It is not a single part-of-speech guess and does not turn lexical categories alone into meaning. A successful full parse supplies a complete `CLAUSE` derivation with embedded NP/VP/PP/etc., syntax-bearing trees, links, features, spans and provenance. Unsuccessful analyses must be identified as **incomplete/unknown**, never as evidence of ungrammaticality.

**The words are carried forward**, not replaced by abstract categories:

- `ParseResult.text` holds the string *as analyzed*; `ParseResult.lattice` holds the original lexical alternatives, token positions and candidate spans. `LexicalCandidate` holds its `surface`, `lemma`, grammatical category, morphosyntactic features and sense IDs.
- In a materialized derivation, leaves are `ChartItem` values retaining `lexical_candidate`; `ChartItem.start/end` and the leaf candidate's `span_start/span_end` tie analysis to the text. Tree nodes carry `category`, `features`, `rule_id`, `children`, `syntax`, `score` and `provenance`.
- `ParseResult.shared_forest` represents packed alternatives; `result.best()` and `result.alternatives(limit=N)` are *views*, not the only possible linguistic readings. `result.completed` describes whether a complete analysis could be materialized within the configured budgets.
- `SyntacticPackage` contains syntax-local lexical occurrence anchors and links (`SyntacticLink`). These are **not yet** stable world-individual IDs or semantic graph nodes.
- `ParseReport.interpret(tree)` is an *optional later operation*, using `semantic_rules.jsonl` (plus dialogue rules) to create a semantic graph from a selected tree. No semantic graph construction is required to recognize syntax.

**Serialization caveat:** `ChartItem.as_dict()` does not copy full lexical candidates into each leaf; the surface evidence is in `ParseResult.text`, `ParseResult.lattice` and the live leaf objects. Consumers must transport the full `ParseResult`, or serialize both the lattice and tree with common span references. The current quote-stripping fallback in `Parser.parse()` can change the analyzed text/span origin when the quote-aware parse fails; reliable original-offset mapping for this fallback remains an explicit outstanding task.

## 2. Execution pipeline (present, not speculative)

```text
input text / sentence boundaries
       |
       v
segmentation.py: tokens, full lexical lattice
      - WordNet + supplemental function/syntax lexicons
      - ALL relevant word categories, subtypes and traits
      - contractions and multiword edges; character spans
       |
       +--- if quoted ---> dialogue.py + dialogue_grammar.jsonl
       |
       v
engine.Parser + declarative grammar.jsonl
      - rule constraints / feature unification
      - vector_chart.VectorGrammar: compact shared forest
      - bounded search; lazy k-best materialization
      - clause-list hierarchical assembly only when justified
       |
       v
ParseReport / ParseResult / ChartItem / SyntacticPackage
       |
       +--- optional interpretation ---> semantic_rules.py, semantics.py
       |
       +--- future Layer 2 --> entities, events, temporality, reference,
                               persistent episodes and induction
```

Entry points: `superparser/seman_parser/engine.py`; data sources: `superparser/data/`; output structures: `chart.py`, `syntax.py`. The old `Chart` class is not the active vector recognizer; do not confuse coexistence of compatibility code with a second production parser.

## 3. Why a packed forest is fundamental

Homographs, lexical sense variants, agreement, valency, attachment ambiguity, coordinations, ellipsis and quotation all interact. The program must **not** silently drop alternative lexical hypotheses or accept a mere pattern hit as a valid sentence. We compact shared substructures and extract expensive candidate derivations lazily rather than enumerating all possibilities up front. We need both grammatical coverage *and* exact traceability back to the words.

The 385 raw rules (383 directly relevant to ordinary vector recognition in the last prefix-probe run) are **not interchangeable** because their category skeleton is identical. Morphosyntactic features, required evidence, grammatical roles, scores and semantic actions remain distinct. Future structural factoring may share computations but must retain these distinctions.

## 4. Fast Layer 1: current experimental adviser

`superparser/research/verbnet_lr/continuation_probe.py` compiles the *same* grammar into a read-only FIRST-category/rule-prefix index. The fast variant uses bitsets over category-to-rule transitions and calculates approximate structural risk before building a parse forest. It takes no action on the canonical parser and does **not** assert grammatical truth, determine completion, delete readings, or supply semantic analyses.

Pilot on 256 real sentences: bitset probe median **0.0339 ms**, p95 **0.0561 ms**; saturation ranking AUC **0.841** when comparing only equal-token-length positive/negative pairs (116 pairs). The observation is small-sample and not a validated routing rule. Cost figures exclude pre-existing lexical lattice construction and one-time compilation. See [the research note](../superparser/research/verbnet_lr/STRUCTURAL_CONTINUATION_PROBE_FINDINGS.md).

**Conditional routing is now implemented in the Layer 1 Parser, with explicit opt-in thresholds.** `seman_parser/complexity_routing.py` computes a preparse rule-start score only for eligible nonquoted sentences; short snippets bypass scoring and use the canonical recognizer unchanged. Only high-risk cases enter a separately compiled shared-prefix grammar; lower-risk sentences stay canonical, and speech retains its specialized canonical grammar. Both paths preserve all original rule variants, word/feature alternatives and parsing budgets. See [the adaptive-routing audit](ADAPTIVE_COMPLEXITY_ROUTING.md). **The routing mechanism is validated for parity**, but the specialized hard-path algorithm has not demonstrated a repeatable overall latency improvement. Production remains off by default.

**Latest forest experiment (18 Oct):** 64 real-novel examples contain many states with exactly matched consumed grammar prefixes, but the packed derivation structure still distinguishes individual rules. Research-only `VectorGrammar(cache_boundaries=True)` avoids recomputing the same inter-token whitespace/quote scan, yet shows unstable timing relative to A/A controls and is disabled by default. See [prefix-sharing audit](FOREST_PREFIX_SHARING_FINDINGS.md).

## 5. Layer 2: what is intentionally out of scope

Layer 1's responsibility is syntactic analyses **plus lexical evidence**, not deciding that two mentions refer to the same real-world person or that a remembered event is true. Downstream work should resolve entities/individuals, events and temporal/modality relations, build persistent episodes and apply memory/induction and learning while retaining provenance to original tokens and grammatical choices.

The repository has semantic interpretation and discourse/corereference utilities; these do **not** mean a fully integrated persistent Layer 2 already exists. Proposed future designs must consume structured alternatives and anchor-to-token traceability rather than regenerate missing surface forms from guesses.

## 6. Required invariants

1. All lexical categories/subtypes/traits remain available in the lattice; no lossy single POS projection.
2. Full syntax must cover the actual analyzed text according to the specified punctuation contract; no silent fragment-as-CLAUSE.
3. The grammatical features, rule variants, agreement, valence and negative constraints must be preserved.
4. Complete parses have usable `ChartItem` trees and anchors; semantic roles are generated only from selected derivations.
5. Saturation, time budget and exhausted k-best are reported honestly; `completed` is not gold accuracy.
6. Performance comparisons use the **same** texts, lexicon, budgets and software revision with fast-path p50/p95/p99 and semantic/tree parity.
7. Corpus text (including quotation, original punctuation, metadata and offsets) is never silently rewritten merely to improve a benchmark.
