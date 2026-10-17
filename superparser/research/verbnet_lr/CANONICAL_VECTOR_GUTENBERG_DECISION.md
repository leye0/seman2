# Seman2: decision gate after correcting the parser baseline (2026-10-17)

Branch: `research/verbnet-left-to-right-poc`. The production `main` parser was not modified.

## Why the earlier 4.2% figure was misleading

The previous 3,000-sentence identical-corpus memorization test used
`SemanCompiledReader`: a deliberately single-continuation, research-only
left-to-right reader, **not** the canonical `VectorGrammar` parser.

On those 3,000 sentences it completely parsed 126, stored 124 full trees
and recovered 120 of those via a structural template matcher (96.77%).
It achieved 2.55% second-pass time savings and 1.03% across both passes
including initial parsing. However, five template hits did not have a
complete reference tree, and one candidate tree differed, so it is NOT an
accuracy guarantee.

Evidence: [GitHub CI #39049817517](https://github.com/leye0/seman2/actions/runs/39049817517).

## Same-candidate Gutenberg engine audit — measured

[GitHub Actions, successful, 150 samples](https://github.com/leye0/seman2/actions/runs/39052574394).
`superparser/scripts/audit_vector_vs_lr_timed_gutenberg.py`

- Twelve source novels, 50 sentences each in length bands 4–12, 13–18,
  and 19–24 tokens, sampled deterministically and without cross-book duplicates.
- **Exactly the same `build_lattice(..., multiword_max=1)`** is fed into
  the canonical vector engine and the compiled L-R reader. That removes
  lexical-inventory differences from this architecture comparison.
- 1.5-second **per-sentence** deadline. Timeouts are neither parse
  completions nor proof of grammatical impossibility.
- Vector: **98/150 complete (65.33%)**, 46 incomplete, 6 timed out.
- Compiled L-R: **10/150 complete (6.67%)**, 140 incomplete.
- Vector by length: 38/50, 29/50, 31/50 complete.
- L-R by length: 7/50, 2/50, 1/50 complete.
- Latency (including same lexical lattice precomputation in neither arm):
  - Vector p50 **40.701 ms**, p75 **102.140 ms**, p90 **437.385 ms**,
    p95 **623.793 ms**.
  - L-R p50 **4.007 ms**, p75 **8.389 ms**, p90 **13.587 ms**,
    p95 **16.586 ms**.

**Conclusion:** The old L-R reader cannot be the candidate-tree teacher for
this project. The full packed vector grammar achieves nearly ten times the
completion rate at the price of significantly higher and heavy-tailed
latency. 98 complete parses are not 98 independently verified gold trees.
The vector still misses or times out on 52/150, so its grammar and search
remain research priorities.

## Canonical-vector replay control — measured pilot

[Canonical-vector two-pass workflow](https://github.com/leye0/seman2/actions/runs/39051968763),
`superparser/scripts/benchmark_vector_replay_gutenberg.py`.

For the 30-phrase initial matrix job:
- Canonical full vector: **21/30 complete**.
- Stored `ParseResult` retrieved by the ordinary exact-text cache:
  **30/30**, including **21/21** complete grammars.
- The exact cache performs **no grammatical generalization**. Its 99.994%
  pass-two timing gain is a deliberately cheating **positive control only**;
  it is not to be presented as evidence for learned C.
- Trained C + full vector, with its matching cost included: **1** local
  witness actually reused, 30/30 agreement in full completed/failed
  parse outcome and best trees relative to a separate fresh baseline run.
- C has **worse p50** (44.18 vs 29.47 ms), worse p75 (55.99 vs
  40.37 ms), and worse p90 (95.29 vs 71.97 ms). Its total time on this
  small, noisy sample happened to be ~10% lower because of a few expensive
  canonical cases. This is *not* robust evidence of acceleration.
- The initial cached parse and separately executed fresh canonical
  baseline were identical in 28/30 cases. This possible nondeterministic
  tie or contextual difference deserves focused debugging, even though
  both C and fresh canonical agree 30/30 on this pilot.

The larger 160-sentence matrix is configured and may still be processing
when this note is read. **Do not invent its results.**

## Architectural decisions

1. Keep `VectorGrammar` as the authoritative recognizer/analysis forest.
   Never use compiled L-R completion rate as Seman2's overall accuracy.
2. Retain exact caching as a separate POSITIVE CONTROL with 100% recoverability
   of stored ParseResults, not as statistical structural learning.
3. Leave prepacked C structural replay off by default until p50/p75/p90,
   cumulative runtime, and complete-forest/alternative parity improve
   **including** match/indexing/learning overhead.
4. Keep WordNet alternatives and the grammar's complete derivations;
   branch-only experiments must not fabricate verified gold from a
   grammar-produced candidate tree.
5. Next optimize heavy-tailed vector recognition and improve independently
   scored syntactic correctness. Compare p50/p75/p90 and timeouts on the same
   realistic Gutenberg corpus, not hand-selected simple sentences. Avoid
   treating a 1.5s timeout as linguistic impossibility.
6. For long learning curves, use multi-run/multiple-order or cross-author
   replication before statistical confidence claims, and distinguish
   memorization recall, generalization, grammar accuracy, and runtime speed.

Charts and machine-readable CI artifacts are stored in the workflow runs.
