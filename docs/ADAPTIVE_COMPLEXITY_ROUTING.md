# Adaptive complexity routing — Layer 1 decision before the forest

**18 October 2026. Branch: main. Status: opt-in research only. Default OFF.**

## Architectural contract (implemented)

The fast preparse **must decide whether to invoke costly recognition**. We never run a second expensive parser on a sentence that is already cheap just because an experimental storage algorithm exists.

1. Construct the same lexical lattice with original words, character spans, grammatical subtypes, traits and alternatives.
2. Without an explicit `ComplexityPolicy`, execute the unchanged canonical `VectorGrammar` — no predictor, no alternate grammar on the hot path.
3. With a policy, return directly to the canonical grammar for all snippets shorter than `min_tokens` (17 in these pilots), **without even computing a complexity score**. Dialogue/quotes retain the canonical quote-aware parser with zero score computation.
4. Otherwise, calculate the grammar-derived `fast_start_sum`: sum over lexical token spans of the count of original rule starts reachable from candidate POS categories, using integer masks compiled once at parser initialization. It matches the historical `ContinuationIndex.fast_signal` metric.
5. Compare with a required, explicit risk threshold. Optional nonoverlapping thresholds by token-length band prevent an overall long-sentence bias. A low score goes **canonical**. A high score routes to a separately precompiled opt-in `flat` or `online` shared-prefix variant.
6. Both paths retain all original rules, lexical readings, syntactic features, scores, derivations and semantics. Forest size/budget are counted identically. `ParseResult.stats` reports `complexity_route`, `complexity_reason`, `complexity_score`, `complexity_probe_ms` and `complexity_tokens` for audits. Neither complexity score nor a full tree implies grammatical correctness.

Sources: `superparser/seman_parser/complexity_routing.py`, `engine.py`, `vector_chart.py`. Tests: `superparser/tests/test_complexity_routing.py`. Both `Parser.parse` and `Parser.parse_grammar_lattice` route eligible ordinary prose; diagnostic-mode parsing stays canonical.

### Opt-in developer interface (numbers are examples, not validated cutoffs)

```python
from seman_parser.engine import Parser, ParserResources
from seman_parser.complexity_routing import ComplexityPolicy

parser = Parser(
    ParserResources.from_dir("superparser/data"),
    complexity_policy=ComplexityPolicy(
        rule_start_threshold=5000,      # illustrative ONLY
        min_tokens=17,
        difficult_strategy="flat",
        band_thresholds=((17, 24, 2700), (25, 32, 3900)),
    ),
)
```

Production continues to instantiate `Parser(resources)` **without** a policy.

## Experimental evidence and pitfalls

Two A/adaptive/A experiments on 64 identical, length-stratified snippets from four cleaned Gutenberg novels, using one unchanged lexical lattice per sentence and WordNet 3.0. Caps: 20,000 forest items and 100,000 k-best work units. We compare complete/incomplete outcomes, recognition budgets, best and top-two trees and every rule-specific partial derivation for the routed cohort.

### Single threshold: selection overly driven by length

[CI 39173698608](https://github.com/leye0/seman2/actions/runs/39173698608), [64 individual records](https://github.com/leye0/seman2/actions/runs/39173698608/artifacts/12152659396).

- 8 routed sentences **all in the 25–32 band**; all 8 already saturated and none became complete. Other 56 used the canonical code path.
- Predictor computation across all 64 cost **1.33 ms**.
- Reference A 4.19 s; adaptive B 3.45 s; reference A repeat 4.12 s. But the 56 **unrouted** sentences appeared 19% faster under B despite using the same algorithm. Treat that difference as runner noise, not a routing speedup.

### Per-length threshold trained on other books' *preparse* scores

[CI 39173986933](https://github.com/leye0/seman2/actions/runs/39173986933). Each book is held out in turn; thresholds for 17–24 and 25–32 use only the other three books' lexical-rule-start scores, never their parse outcomes or times. All four books have been used in previous research, so this is **not an untouched external test**.

- **10/64 routed**, 5 in 17–24 and 5 in 25–32. The remaining **54/64 canonical**, including 23 quote-bearing, 16 nonquoted below 17 tokens and 15 longer below risk threshold.
- The 32 snippets shorter than 17 tokens had **zero score computation and zero alternate parser work**. Predictor time on the entire sample: **1.08 ms**.
- **22 complete** in all arms; **14** forest saturations in all arms; **193,983** ordered partial edges from selected parses checked with exact equality.
- Reference A 3.55 s; adaptive 3.16 s; repeated reference A **6.44 s**, revealing severe runner drift. For 20/64 sentences the two reference passes differed by over 20%. Bracketed geometric comparison is ~1.00 adaptive/base, but is also too noisy for rollout.
- The 10 selected parses took 1.39 s adapted, versus reference A 0.41 s and A repeat 1.72 s. The alternative cannot yet claim any consistent hard-path speedup.

Earlier unconditional shared-prefix experiments showed **+27.6% overhead on 4–8 tokens** and **+42.3% on 9–16**, despite sampled memory savings on some short sentences. This justifies gating, but **does not prove the current alternate engine is useful even on hard sentences**.

## Acceptance gates before production

1. Preserve short-circuit bypass of predictor and specialized recognizer for short/low-risk cases, and canonical quoted/dialogue parsing.
2. Freeze scores and bands and validate on **new authors**; calibrate without test labels or time leakage.
3. Replace noisy CI timing comparisons with repeated A/A and A/B on controlled/isolated hardware, capturing CPU, wall, p50/p95/p99, per-sentence traces, and peak RSS.
4. Rework the specialized algorithm so **shared prefix transitions avoid duplicated recognition work**, not just deduplicate derivative objects after independent rule-specific recognition.
5. Verify grammar trees, complete top-k, categories, morphological constraints, quotation spans, original words and future Layer 2 semantic action identity. Budget exhaustion is never proof of ungrammaticality.
6. Keep `complexity_policy=None` as the production default until **independent** evidence shows real total latency wins without losing accuracy or slowing easy sentences.

**Decision:** the original prediction-first conditional architecture now exists and has parity tests. The routing mechanism works. The current specialized algorithm has not yet demonstrated a stable net speedup.


## Follow-up, 18 October: the failed indexed-transition shortcut

A separate *discarded* strategy, named `indexed`, tried to avoid duplicate
category-mask checks already guaranteed by the recognition agenda and to
encode four-part partial-state lookup keys as collision-free integers.
It preserved all grammatical rule variants and all ordered derivations,
but it **did not share the underlying rule-prefix recognition work**.

- Initial [128-case audit](https://github.com/leye0/seman2/actions/runs/39175285966):
  11 selected and **176,573 redundant mask checks removed**; apparent
  overall **+8.5%** time, with large canonical A/A and nonrouted outliers.
  Cannot infer causation from this noisy run.
- Controlled [128-case repeat](https://github.com/leye0/seman2/actions/runs/39175507714),
  [individual result artifact](https://github.com/leye0/seman2/actions/runs/39175507714/artifacts/12154087888):
  when cyclic garbage collection was excluded from each A/B/A timed
  window, reference A total **7.0809 s**, conditional indexed **7.0771 s**,
  reference A repeat **7.0707 s**. On the 11 routed cases specifically:
  **739.2 ms** reference A, **757.3 ms** indexed, **743.0 ms** repeat.
  Thus routed performance was **2.45% worse**, despite eliminating the
  176,573 checks. The 64 short cases had no predictor work and practically
  identical median runtime. Completion, forest budgets and all rule-specific
  derivations remained equal.
- The audit deliberately performed explicit full garbage collections
  **outside** the timed arms (their total setup cost was substantial).
  Those timings measure isolated parse work, **not fully inclusive
  production throughput**; this distinction matters.

**Decision: reject and remove `indexed` from the current runtime and policy.**
Historical source remains recoverable in Git history, before this cleanup.
Do not resurrect it merely to count avoided cheap tests.

A genuine next attempt must compile a shared **category-prefix automaton**
for the grammar, advance one common prefix state for multiple rule variants
*before* duplicating rule-specific state creation, and only project matched
rule variants and their feature/semantic constraints when evidence requires
them. Compare recognition CPU, materializer work, peak RSS and all original
rule-specific derivations, especially under the fixed forest budget.
