# Preparse lexical ambiguity versus actual forest cost (2026-10-18)

Branch: research/verbnet-left-to-right-poc. **Production untouched.**

An inexpensive proxy for independent lexical assignments is P = product_i max(1, k_i), where k_i is the number of available grammatical categories at token i. Its numerically safe score is A = log2(P) = sum_i log2(max(1, k_i)). This can be computed from the lexical lattice before any syntactic recognition.

A second score preserves **distinct syntactic subtypes and feature sets** (candidate.syntactic_signature), not merely categories. Neither product counts grammatical trees, since syntactic rules constrain combinations and the packed forest shares structures. Lexical edges spanning several tokens are NOT independent word choices; contractions and multiword edges are counted separately. Tokens without an exact-span candidate are flagged and contribute the neutral multiplier 1, not a false grammatical acceptance.

## Measured on 256 real novel sentences

[Successful one-pass CI audit](https://github.com/leye0/seman2/actions/runs/39152368862), sampling 16 phrases per book per length band from four cleaned novels, WordNet 3.0, 20,000 forest items, 100,000 k-best work units. 68/256 sentences saturated the forest and 41/256 exceeded 150 ms.

AUC of ranking forest-budget exhaustion:

| Available before parsing | Overall | 17–24 tokens | 25–32 tokens |
|---|---:|---:|---:|
| Token count | **0.975** | **0.878** | 0.672 |
| Category log-product | 0.940 | 0.738 | 0.658 |
| Syntactic subtype/feature log-product | 0.960 | 0.841 | **0.679** |
| Raw candidate count | 0.925 | 0.745 | 0.536 |

The 4–8 and 9–16 token groups had no forest saturation, so within-band forest AUC was undefined, not chance.

AUC of predicting **latency >= 150 ms**, over all samples:

| Preparse factor | AUC |
|---|---:|
| Token count | 0.750 |
| Category log-product | **0.766** |
| Syntactic subtype log-product | 0.742 |
| Raw candidate count | 0.721 |

Inside the 25–32 band, AUC for >=150 ms was near chance for all factors (roughly 0.46–0.51). The products strongly correlate with length; pooled AUC cannot establish predictive value *beyond token count*. Only four authors were examined. Per-book AUC is descriptive, NOT out-of-sample ML training or a held-out threshold-selection experiment.

## Engineering decision

1. Keep these cheap scores as research-only observations, not an active runtime routing policy. No grammar, production behavior, or original novel data were changed.
2. Investigate structural fan-out at compiled grammar prefixes (number of rule continuations and feature-compatible transitions) and attachment choice, the probable sources of cost not explained by independent lexical option counts.
3. Compare within narrow length bands, with book/author holdout and explicit false-trigger accounting. Preserve all syntactic feature alternatives and test exact best-tree signatures, semantic roles, fast-sentence latency, and negative controls.
4. Distinguish forest saturation from k-best exhaustion and residual cost; they are different targets requiring different remedies.

**Conclusion:** the user-suggested product is efficient and well-defined as a lexical upper-bound proxy. However, even the feature-aware product is not sufficiently discriminative among equally long difficult sentences. We need to characterize the interaction between categories and rule prefixes instead of replacing grammar analysis with the raw product.
