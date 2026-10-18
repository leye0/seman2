# Forest prefix sharing — evidence before mutating the recognizer

Date: 18 October 2026. Branch: **main**, not a separate development fork. This is research toward a fast, lossless Layer 1; no change in production parsing or corpus text.

## Question and implementation

The canonical vector forest currently stores a distinct `PackedPartial` for each `(rule_index, dot, start, end)`. This preserves independent feature constraints, valence, rule scoring and semantic provenance, but may repeat recognition of the **same already-consumed grammatical prefix** when several rules lead into different suffixes.

We added two **observational** counters in `superparser/scripts/benchmark_partial_sharing_aab.py`:

1. A coarse, optimistic category-skeleton duplicate count: exact `(start, end, dot, lhs.category, complete_rhs_category_sequence)`.
2. A consumed-prefix count: exact `(start, end, dot, serialized RHS[:dot] symbols)`, including each consumed symbol's category, features, required evidence and lexical handle exports. Different future RHS suffixes, final LHS, rule scores and semantic actions **are NOT joined**. This measures potentially reusable prefix matching, **not** interchangeable complete analyses, nor all binding/context dependencies. Identical prefixes must still retain every rule-variant identity for all later operations.

No changes were made to `PackedPartial`, `_LazyMaterializer`, grammatical constraints, scores or semantic interpretation.

An optional `VectorGrammar(cache_boundaries=True)` stores `_VectorForest._next_start(end)` within one source sentence, separately for quote-preserving and ordinary modes. It is **off by default** and has parity tests, including punctuation and dialogues. Memoizing separator scans does not compress packed states.

## Two matched real-novel experiments

Same four checked-in cleaned novels, WordNet 3.0, 4–32-token strata, `max_items=20,000` and `kbest_work_limit=100,000`, with one lexical lattice shared across canonical A, opt-in cached B and repeated canonical A runs; order is counterbalanced across adjacent samples.

| | [128-sentence run](https://github.com/leye0/seman2/actions/runs/39164335185) | [64-sentence run](https://github.com/leye0/seman2/actions/runs/39164647623) |
|---|---:|---:|
| Total logical partials | 1,230,617 | 577,545 |
| Category-skeleton duplicates | 329,781 (26.8%) | 154,135 (26.7%) |
| Exact-feature consumed-prefix reuse potential | not yet measured | **356,830 (61.8%)** |
| Boundary lookups served from local cache | 1,046,602 | 489,345 |
| Distinct boundary inputs scanned | 2,142 | 1,088 |
| Completion, best tree and forest-count mismatches | **0** | **0** |
| A/A comparison mismatches | **0** | **0** |

The feature-exact consumed-prefix number can exceed category-skeleton duplicates because the former intentionally allows *different remaining suffixes or LHS categories* after the common consumed prefix. It is a count of repeat opportunities, **not an achievable memory reduction**. Partial derivation links and variable binding context have not yet been factored; prefix reuse must preserve those dependencies and all complete rule variants.

The 128-case study ([per-sentence artifact](https://github.com/leye0/seman2/actions/runs/39164335185/artifacts/12149164524)) saw a nominal 18.3% total-time reduction with cached boundaries versus canonical A, but canonical A/A repeat itself varied by 4.9% and the 4–8-token cohort had outliers. The 64-case study ([artifact](https://github.com/leye0/seman2/actions/runs/39164647623/artifacts/12150361595)) showed just 0.75% total-time difference versus canonical A, while repeated canonical A was 28.5% slower. The optimization therefore **has not proven a repeatable speedup**, or stability on fast sentences. We retain it opt-in.

Small explicit tests also ensure matching-prefix counts do not merge different consumed features, word positions or dot depths, and verify canonical forest/tree parity for normal and quoted sentences. The original novel text, punctuation and lexical alternatives are unchanged.

## Next implementation experiment: shared prefix recognition with variant projection

1. Add a **research-only** packed-prefix coordinator indexed by `(start, end, dot, consumed RHS constraint signature)`. It should store shared recognition evidence once, but keep a list of **distinct** `(rule_index, binding context, child derivation path)` variants. Do not erase scored alternatives or semantic recipes.
2. Materializer still operates over exact original rules and all child alternatives. Prove equivalence on **more than the best tree** (top-k, grammar feature bindings, lexical senses and anchors), including negative, dialogue, passive, interrogative and long-coordination controls.
3. Measure *physical* allocated prefix groups, derivation-edge count, memory, forest-budget hits and wall-clock time versus an A/A control, repeated with 4–8-token fast sentences and author-held-out novels. An improved sharing ratio alone does not prove speed.
4. Only after semantic/tree and performance parity is established may a new implementation replace the current partial state index. Avoid simply crediting theoretical duplicates toward the 20,000-state budget.

**Decision:** the repeated-prefix measurements justify experimenting with factored recognition, **not yet activating a new parser architecture**.
