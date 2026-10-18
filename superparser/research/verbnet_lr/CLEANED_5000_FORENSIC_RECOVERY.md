# Cleaned four-novel 5,000-sentence forensics — recovered baseline

**Source:** GitHub Actions [run 39093939018](https://github.com/leye0/seman2/actions/runs/39093939018), artifact `cleaned-four-novels-5000-forensic-corpus` (artifact id 12124411615). Extracted from the **fully saved** `cleaned_5000_every_sentence.jsonl` (5,000 rows) and `cleaned_problematic_sentences.jsonl` (2,266 rows). No corpus or parse recomputation was required to recover these results.

## First-pass counts (1,250 cleaned sentences per novel)

| Outcome | Count |
|---|---:|
| Complete syntactic tree | 3,013 |
| No full-sentence structural root, without forest truncation | 894 |
| Full structural root but no certified grammatical witness | 477 |
| Forest budget hit with a root present | 334 |
| Forest budget hit with no root | 226 |
| K-best work budget hit | 56 |
| **Total** | **5,000** |

The forest budget was reached on **1,077** sentences in total, including successful parses; categories above are mutually exclusive *outcome labels*, so the cap and completion counters overlap.

**First-pass profiling median:** 36.9127 ms. The >5x-median threshold was 184.5635 ms; **527 sentences** exceeded it, including **279 successful** parses. Union of the **1,987 incomplete** plus **279 expensive-complete** = **2,266** problematic sentences. Dominant phase among the 527: **429 recognition / 88 k-best / 10 lexical**. This median belongs to the profiling run and need not equal the earlier separate benchmark's timing.

## Per-book coverage

| Book | Completed / 1,250 | Forest cap hit |
|---|---:|---:|
| David Copperfield | 602 | 207 |
| Pride and Prejudice | 811 | 252 |
| Frankenstein | 793 | 370 |
| Treasure Island | 807 | 248 |

## Why the CI job incorrectly failed

All 5,000 sentences were profiled and saved, as were all 2,266 problematic records. An **optional counterfactual sample preparation** re-lexed and re-parsed some sentences and observed five reproducibility differences at indices `0, 1, 4, 126, 2440`. An ill-placed `raise RuntimeError` then turned an auxiliary warning into a CI failure **after the expensive baseline had finished**. This was a benchmark implementation defect, not failure of the 5,000 parses.

### Safeguards added afterwards

- The baseline summary is written **atomically immediately after collection**, *before* any optional probing.
- Sample reparse differences are logged and excluded from strict identical-lattice comparisons; never fatal to the completed baseline.
- Optional counterfactual exceptions are captured, tagged `failed_nonfatal`, and persisted rather than bringing down the run.
- Per-sentence files continue to be streamed incrementally and uploaded even when a later stage fails.
- The **expensive 5k workflow is now manual-only**; a push to the research branch must not automatically rerun the entire job.

**Limit:** No counterfactual ablations were completed in the failed original run. The saved baseline supports detailed forensic comparisons of grammar rule partials, expensive phases, and individual sentences. No gold-tree validation and no grammar changes were made.
