# Shared-prefix storage: lossless physical prototype

Date: 18 October 2026. This research is on main but NOT on the live parser execution path. The canonical parser, grammar, corpora and downstream semantic rules are unchanged.

## Representation and exact contract

The canonical packed forest maintains a partial for each (rule_index, dot, start, end), containing edges (previous partial ID, child node ID). Even if grammar variants share a consumed prefix, the rule and its interpretation must remain separate.

The new `superparser/research/verbnet_lr/packed_prefix_projection.py` makes a SECOND, read-only representation after parsing. It groups (start, end, dot, exact consumed RHS symbols including category/features/requires/exports). It interns each (previous shared group, child node) edge, then retains ordered per-rule edge references and sorted group/rule membership, so every original predecessor partial ID can be reconstructed exactly. The rule's future suffix, LHS, scoring, valence and semantic actions are NOT combined.

- The first object-based implementation shares edges but allocates many Python objects and is wasteful.
- The flat version stores predecessor IDs, child IDs, edge/group offsets, rule membership and per-variant order in contiguous signed/unsigned integer arrays.
- The DIRECT flat builder creates those arrays from the original forest using temporary indexes, avoiding the expensive intermediate Python PrefixGroup representation.
- Every partial and its edges are reconstructed and verified in their original order, including on truncated forests. Tests cover distinct morphological features, spans, ambiguous reading order and invalid ancestry.

## Four novels: 64 real sentences, 4–32 tokens

Shared setup: four checked-in cleaned Gutenberg novels, WordNet 3.0, 20,000 forest items, 100,000 k-best units. Original forest is retained as the source of truth.

| Quantity | Measured total |
| --- | ---: |
| Canonical partial states | 577,545 |
| Shared-prefix groups | 220,715 |
| Original partial derivation edges | 625,555 |
| Unique interned edges | 260,443 |
| Redundant edge occurrences shared | 365,112 = 58.4% |
| Shallow Python original edge-lists + edge-objects storage | 80.9 MB |
| Initial object-based projection | 173.3 MB (WORSE) |
| Flat indirect projection, all owned vectors | 18.36 MB |
| Flat DIRECT projection, all owned vectors | 18.43 MB |
| Direct packing + full validation time | 1.17 s |
| Indirect object grouping + flat packing + full validation | 3.74 s |
| Input forests saturated but recovered without missing edges | 14/14 |
| Differences across reconstructed ordered derivations | 0 |

The direct flat format occupies 22.77% of the **edge-related list/object comparison**, approximately **77.23% less**. This is NOT total parser RSS reduction and includes no claim that runtime allocations decreased. It excludes mutable online interning indexes, source grammar storage, original forest nodes and interpreter structures. Array overallocation causes minor size differences even between equivalent encodings. Direct conversion still happens AFTER a canonical forest has been constructed; it incurs time instead of saving live recognition time.

Independent evidence:
- [First object-based experiment](https://github.com/leye0/seman2/actions/runs/39170861491)
- [First flat-array audit](https://github.com/leye0/seman2/actions/runs/39171074547)
- [Direct-vs-indirect audit](https://github.com/leye0/seman2/actions/runs/39171365147)
- [Individual 64-row diagnostics](https://github.com/leye0/seman2/actions/runs/39171365147/artifacts/12152891286)

## Remaining engineering problems before production

1. Compile consumed-prefix identities ONCE into integers; avoid per-partial JSON signatures.
2. Insert into shared edge arrays **while recognizing** the sentence. Temporary interning tables must not outweigh the memory saved, and live budget accounting must remain honest.
3. Preserve exact (rule index, binding environment, child lexical alternative) histories and original edge enumeration order. The lazy k-best materializer must see every valid path, even under cycles and budget exhaustion.
4. Validate both gold structural/semantic correctness and identical canonical outputs (all available top-k, syntax anchors, lexical features and provenance). Also test negative controls and dialogue punctuation.
5. Measure live peak RSS, p50/p95/p99, fast sentence latency and author-held-out corpora against an A/A reference. Do not credit compressed group count against the 20,000-item forest budget without a sound equivalence proof.

**Decision:** the edge DAG can be compressed without losing derivation evidence. This is a proof of storage representation, NOT YET an acceleration or live memory improvement.
