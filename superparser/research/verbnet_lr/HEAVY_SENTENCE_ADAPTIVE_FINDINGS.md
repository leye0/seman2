# Seman2 — Expensive sentence parsing: selective, lossless research

Date: 2026-10-18. Branch: research/verbnet-left-to-right-poc.
**No changes to production defaults, the canonical grammar, or main.**

## Motivation and reliable historical baseline

The earlier four-novel 5,000-sentence forensic artifact is still valid as
a **historical, pre-dialogue-fix measurement**, not a statement of current
dialogue coverage. Source:
[run 39093939018](https://github.com/leye0/seman2/actions/runs/39093939018),
artifact 12124411615, original 5,000-row JSONL.
The corpus had sentence-boundary/quotation defects later corrected.

- 3,013/5,000 complete; 1,987 incomplete.
- 1,077 sentences hit the 20,000-item forest cap, including parses that
  nevertheless yielded a complete tree.
- Success by token band: 4–8 **74.7%**; 9–16 **70.4%**;
  17–24 **61.2%**; 25–32 **30.6%**.
- Forest budget hit by band: **0%, 0%, 21.2%, 74.8%**, respectively.
- Historical profiling median 36.9 ms. Among 527 items above 5x that
  median, 429 had recognition as their most expensive reported phase,
  88 had k-best and 10 had lexing.
- Runtime concentration over all 5,000 stored rows: top **1%**
  accounts for **18.27%** of time; top **5%** for **47.64%**;
  top **10%** for **73.07%**. This motivates cheap selective gating
  instead of imposing expensive processing on all sentences.

The 385 canonical grammar rules contain 113 rules in 50 groups with the
same ordered LHS and RHS **category skeleton**. They are **not**
semantically redundant: differences in vform, valence, features,
required evidence, score and semantic actions must be retained.
A shared *structural* dotted state with tagged rule variants is a
possible future optimization, but no runtime gain has yet been measured.

## Paired research A/B: same novel sentences, same lexical lattice

Script: [benchmark_heavy_sentence_ab.py](../../scripts/benchmark_heavy_sentence_ab.py).
CI: [final successful run 39139324790](https://github.com/leye0/seman2/actions/runs/39139324790).
Artifact: [individual rows + summary](https://github.com/leye0/seman2/actions/runs/39139324790/artifacts/12139869985).
Tests: [test_heavy_sentence_ab.py](../../tests/test_heavy_sentence_ab.py).

256 deterministic real samples = four books x four token bands
(4–8, 9–16, 17–24, 25–32) x 16.
All comparisons use one *identical* prebuilt
build_lattice(text, resources.lexicon, multiword_max=1) per sentence.
Dialogue-aware parsing is used for the reference and lexical-filter arms.
The experiment is about **syntactic recognition and resource consumption**;
a completed tree is not human-verified syntax or semantics.

The baseline in the final matched run completed 130/256, with 68 forest
saturations. Four opt-in policies:

1. **Baseline**: current canonical quote-aware Parser grammar.
2. **Early lexical evidence filter**: experimental VectorGrammar feature
   compatibility prefilter, **only for unquoted 17+ token sentences**.
3. **Split-first**: for an unquoted clause-looking coordination, try two
   separately parsed segments and grammar-verified SegmentInterface assembly
   before fallback. Conservatively require a unique split, cap each
   speculative forest at 4,500, beam 4.
4. **Post-budget rescue**: ALWAYS run exactly the ordinary baseline first.
   Only when it fails, a forest/k-best budget was reached, the sentence has
   at least 22 tokens and no quotation, try one potentially ambiguous
   coordinated split. The ordinary success is returned unchanged; failure
   of the rescue returns the original result. The extra recovery attempt
   uses the normal 20,000-item parser budget.

| Final same-run measurement | Baseline | Early filter | Split-first | Post-budget rescue |
| --- | ---: | ---: | ---: | ---: |
| Completed / 256 | 130 | 143 | 130 | 136 |
| Newly completed | — | 14 | 0 | 6 |
| Previously completed lost | — | **1** | 0 | **0** |
| Changed best signatures among prior successes | — | **15** | **5** | **0** |
| Forest budget hits | 68 | 52 | 65 | 62 |
| Paired run p50 (ms) | 30.68 | 25.85 | 30.54 | 30.68 |
| Paired run p95 (ms) | 555.27 | 526.33 | 591.47 | 588.34 |
| Accumulated parse wall time (s) | 28.05 | 25.82 | 34.77 | 30.77 |

The post-budget rescue attempted an extra branch in **17/256** sentences:
11 failures returning the original parse outcome and 6 newly completed
analyses. On the 128 fastest baseline cases it attempted no recovery;
its recorded reference time and tree are identical **by construction**,
apart from small uninstrumented policy-condition checks. It increases
aggregate wall time **9.7%** and p95; do not claim it accelerates parsing.
It is a *coverage recovery mechanism* with isolation from fast successes.

A broader unrestricted split-first test on exactly the same 256 examples
[run 39138523497](https://github.com/leye0/seman2/actions/runs/39138523497)
found 21 successful segment-first compositions and 6 additional
completions, but changed 15 previously successful best-tree signatures;
a speculative attempt is **not** an acceptable drop-in optimization.
Restricting it to a 4,500-item speculative budget and one unique candidate
eliminated those six recoveries while still causing overhead. This
justifies keeping the rescue mode strictly post-failure and off by default.

The initial experiment
[run 39138125373](https://github.com/leye0/seman2/actions/runs/39138125373)
had a comma-only splitting guard that selected zero cases. The binary
coordination test corrected the *experimental selection*, not production
parser behavior.

**Runner variance is large.** The identical 256 baseline sample cost
roughly 24.8 s, 29.7 s and 35.1 s across different workflow runs.
Therefore never compare absolute milliseconds across CI runs as an
optimization gain. Even within a matched run, alternate run order,
baseline drift and context-dependent cache state require repeated A/A
controls before promoting any timing result.

### Why early lexical filtering is not yet safe

Across successful paired runs it consistently found 14 new completed
parses but also lost one previously completed parse and changed 15 other
best-tree signatures. In many rescued cases the forest still reached the
20,000-item ceiling, so altered agenda order near a budget boundary is
a plausible confounder. Do **not** interpret recovery as proof of
grammatical validity. The fast baseline cohort also showed erratic slow
tail outliers under the early-filter experiment. Filter selectivity,
work accounting and tie/budget behavior need separate investigation.

## Exploratory cheap risk predictor (offline only)

A small decision-tree diagnostic was fitted to *the historical 5,000
records*, using exclusively preparse features (token count, candidate
count, ambiguity, punctuation and other lexical flags), and evaluated
by leaving **one of the four books out** for each fold.
With max_depth=3, min_samples_leaf=100, class_weight="balanced", and
threshold 0.65, prediction of **forest-budget hit** gave pooled
held-out ROC-AUC ~0.949, precision ~0.678, recall ~0.918,
flagging 29.2% of sentences. The naive >=25-token threshold
had precision ~0.748 but lower recall ~0.723.
These are exploratory observational scores from older pre-dialogue data,
**not** a validated runtime policy, calibrated probability, or external
novel/general-language generalization. A classifier must not depend
on actual parse time or postparse forest stats at runtime.

## Next experiments: positive proofs and strict safety gates

1. **Correctness first**: hand-label the 14 lexical-filter rescues,
   the one loss, the 15 changed analyses, and six budget-rescued
   cases for clause boundaries, lexical subtypes, agreement, negation,
   valence, speaker/quotation boundaries, semantic roles and tree
   evidence. Retain negative controls and unseen authors.
2. **Predict before exploring**: learn a cheap structural-risk policy from
   preparse lexical ambiguity and length, with a *book/author-level*
   holdout and calibrated false-trigger rate. Repeat on cleaned quote-aware
   corpus because the historic 5k sample has compromised dialogue spans.
3. **True structural compaction**: prototype factoring rules with
   identical category skeletons while **retaining rule identity, feature
   constraints, semantic actions and score**. Compare number of packed
   states and exact best/alternative-tree signatures on every fast control
   *and* expensive sentence, not raw parser coverage alone.
4. **Safer hierarchical clauses**: derive segment boundaries from
   positive evidence for independently parseable clauses, not commas
   alone. Preserve punctuation, original character spans, all lexical
   ambiguity and reporting-incise scope. Score/validate assembled
   trees and negative examples; never accept unverified fragments.
5. **Measurement protocol**: paired fixed sample, counterbalanced order,
   repeated canonical A/A (detect drift/noise), warmed and cold regimes,
   p50/p95/p99, completion, censored forest and k-best, changed
   best trees, lexical and semantic parity, extra recovery CPU, and
   speed on fast controls. Avoid global grammar relaxation and arbitrarily
   larger search budgets until these gates pass.

**Decision:** continue these as research-only options. No current arm
simultaneously demonstrates better gold-verified syntax, lower whole-sample
cost, and zero fast-case impact under repeated, reliable measurements.
