# Structural continuation prediction: read-only POC and measured audit

Date 2026-10-18. Branch: research/verbnet-left-to-right-poc.
No changes to main, canonical parser, grammar rules, or production routing.

## What was actually built

- continuation_probe.py builds an optimistic FIRST-category closure and
  indexes the first two grammar RHS slots. This produces rule fan-out,
  approximate adjacent-token continuation counts and counts of rule
  variants with a common category skeleton.
- The measured compiled grammar contains 383 effective ordinary rules
  (the two hierarchical-only clause list rules are not included in the
  ordinary vector forest), forming 320 distinct category skeletons.
- The basic diagnostic optionally tests direct lexical feature unification.
  A much cheaper second implementation compiles category-to-rule bitsets.
  It keeps one bit **per rule variant** and separate compressed-skeleton
  bits, so it does NOT discard category distinctions or morphosyntactic
  alternatives. This representation is an approximate upper-bound
  **risk signal**, NOT a second grammar or a valid reason to prune.
- Neighboring tokens may lie inside the same mult-token constituent.
  Matching the first and second RHS slots to adjacent tokens is an
  optimistic heuristic, not proof that the complete rule applies.
  Indirect FIRST-category paths also do not prove feature unifiability.

Source:
[continuation_probe.py](continuation_probe.py)
[research audit](../../scripts/audit_structural_prefix_risk.py)
[10 unit tests](../../tests/test_continuation_probe.py)
[exact-length AUC tests](../../tests/test_structural_prefix_risk.py)

## Successful experimental execution

[CI run 39155480717](https://github.com/leye0/seman2/actions/runs/39155480717);
[individual 256-row artifact](https://github.com/leye0/seman2/actions/runs/39155480717/artifacts/12146617004).

The existing four checked-in cleaned novels, four equal token-length bands,
16 deterministic samples/book/band = 256 sentences. Exactly one
quote-aware canonical lattice parse per sentence, forest cap 20,000 and
k-best cap 100,000. The probe runs before the parse. There are 68
forest-saturated sentences; 41 exceeded 150 ms in this particular run.

Pooled ROC-AUC for predicting forest saturation:

| Preparse measure | Pooled AUC | AUC over **exactly equal-length** positive/negative pairs |
| --- | ---: | ---: |
| Tokens | 0.975 | 0.500 (constant by construction) |
| Lexical category log-product | 0.940 | 0.647 |
| Syntactic feature/subtype log-product | 0.960 | 0.716 |
| Feature-compatible rule-start count | 0.986 | 0.836 |
| Feature-compatible duplicated-skeleton pressure | 0.986 | 0.862 |
| **Fast bitset rule-start count** | **0.985** | **0.841** |
| Fast bitset rule-pair count | 0.975 | 0.819 |
| Fast bitset duplicated-skeleton pressure | 0.985 | 0.823 |

Only **116** opposite-label pairs shared exactly the same token count.
These are within-corpus ranking comparisons, NOT an independently validated
predictive model, statistical proof, or causal analysis.

For detecting total parse latency >=150 ms, the equal-length ranking was
less discriminative: lexical category log-product 0.673 vs fast rule-start
0.624. That distinction matters: **forest saturation**, k-best exhaustion
and wall-clock tail latency are different targets. The predictor's strong
saturation AUC does not mean it can optimize k-best work.

## Critical overhead: fast path is about 100x cheaper

Measured in the final **same run**, warm precompiled index:

| Probe path | p50 | p95 | max | Total over 256 |
| --- | ---: | ---: | ---: | ---: |
| Feature-compatible version | 3.333 ms | 7.001 ms | 11.13 ms | 932.1 ms |
| **Category-rule bitset version** | **0.03391 ms** | **0.05612 ms** | **0.09828 ms** | **8.72 ms** |

The canonical 256 parses cost 28,209 ms summed; fast probing is
approximately **0.031%** of their total wall time, excluding shared
lexical lattice construction and a **10.26-ms one-time index compile**.
On 4–8 token sentences alone, median probe time was **0.0158 ms**
versus median canonical parse of **3.79 ms**. 10 tests passed.

Timings are CI-run observations, not deterministic latency guarantees;
they should be remeasured across repeat runs/cold starts and workloads.

## Exploratory author-held-out threshold, no new parser runs

Using only the per-sentence artifact from the same CI run, for the 128
sentences of length >=17, we tried one transparent threshold each for
length and the fast rule-start count:

- For each held-out book, learn from the other three books the **lowest
  threshold** keeping training false-positive rate <=20% among nonsaturated
  sentences (including threshold ties). Then apply it to the held-out book.
- Pooled out-of-book recall of saturated cases:
  **89.7%** with length alone versus **95.6%** with fast rule-start sum.
- Both had **16.7% false-positive rate** on the pooled held-out
  nonsaturated examples.

This is a tiny four-fold exploration using 68 positives, not evidence
of robust generalization or an approved production threshold. Scores
and threshold rules were investigated after seeing the initial benchmark;
they need a separate untouched author/corpus holdout before deployment.

## Decision and next research

- The hypothesis that grammar-rule interaction helps predict saturation
  **survives** the matched-length and speed checks of this pilot.
- No automatic routing, early rule deletion or change to parsing behavior
  has been activated; the prototype is a **read-only** diagnostic.
- Next: freeze the feature set, acquire untouched novels by other authors,
  and compare a calibrated cheap risk classifier against token length
  and lexical option products. Evaluate false triggers, p50/p95 overhead
  and stability on the fast path separately from forest-saturated cases.
- Only after independent validation may the signal choose experimental
  *safe* optimizations (structural state sharing or bounded hierarchical
  clause analysis), with canonical reference, full-tree and role
  equivalence checks, and no loss of lexical subtypes or semantic rules.
- Do not interpret high risk as a license to skip grammatical candidates.
