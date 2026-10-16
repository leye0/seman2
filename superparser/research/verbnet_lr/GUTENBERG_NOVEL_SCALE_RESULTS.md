# 60,000-observation Project Gutenberg full-structure snapping result

**Measured, not an estimate.** GitHub Actions SUCCESS:
https://github.com/leye0/seman2/actions/runs/38982466564
Artifact report (download may expire):
https://github.com/leye0/seman2/actions/runs/38982466564/artifacts/12082290453

Execution used the public-domain novel loader, 12 Gutenberg training books,
2 heldout books by other authors, seed DEV grammar witnesses, and 1-in-10
bounded Earley sampling. The actual run processed 60,000 distinct observations
from the novels, despite the later safety-default of 50,000 in workflow.
To rerun the measured horizon explicitly, supply --max-train 60000
--checkpoints 0,5000,20000,60000. The audited eligible train pool was
60,183 after text overlap exclusions, so a reproducibility rerun depends
on the exact downloaded Gutenberg edition versions (SHA256 in artifact).

Corpus audit SUCCESS:
https://github.com/leye0/seman2/actions/runs/38982829153
14 Gutenberg works, 109,702 raw segments, 90,719 eligible candidate
sentences (4-45 tokens), 60,349 train candidate sentences of 4-32 tokens
before inter-book deduplication, 18,184 eligible candidates in Jane Eyre
and Middlemarch. These are heuristic sentences, NOT manually annotated gold.

## Actual 60k sampling results

| Train observations | Earley attempts | Earley FOUND | Total whole-tree patterns | Novel holdout snapped / 600 | Novel holdout completed / 600 | Seman2 positive explicit-gold passes / 70 | Grammatical negative false accepts / 24 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 41 | 1 | 12 | 31 | 7 |
| 5,000 | 500 | 33 | 73 | 3 | 14 | 31 | 7 |
| 20,000 | 2,000 | 188 | 219 | 5 | 15 | 31 | 8 |
| 60,000 | 6,000 | 529 | **514** | **7** | **16** | **31** | **8** |

At completion, 5,471 of 6,000 bounded Earley attempts produced
UNKNOWN/CATEGORY_REJECTED rather than usable proof. Never count these
as ungrammatical. 529 are teacher *witnesses*, not gold or unique trees;
some whole-tree templates are duplicates across sentences. The 514
total patterns include 503 witness-tagged patterns and 11 candidate-only
patterns from DEV (0 independent manually verified gold patterns).

## Held-out novel length-stratified recognition

Stratified sample from two separate novels (Jane Eyre 300 sentences,
Middlemarch 300 sentences), **not** the entire 18,184 held-out pool:

| Token length | Snapped / tested | Completed / tested |
|---|---:|---:|
| 4-12 | 7 / 150 | 16 / 150 |
| 13-24 | **0 / 150** | 0 / 150 |
| 25-40 | **0 / 150** | 0 / 150 |
| 41-45 | **0 / 150** | 0 / 150 |

Jane Eyre: 4 / 300 snapped, 11 / 300 completed.
Middlemarch: 3 / 300 snapped, 5 / 300 completed.
Median hybrid end-to-end on 600 heldout novel examples: **6.674 ms**,
p95 **14.675 ms**. These are timing measurements on the CI runner,
and neither result meets a hard 5-ms target.

On the Seman2 70 partially annotated syntax checks, the cache gained
1 additional snap (24 to 26) but **no additional annotated syntax
passes** (31 at both ends). The independent negative suite accepted
**one more known-incorrect sentence** after the novel training (7 to 8).
Do not promote newly learned novel patterns to a default production
configuration.

## Interpretation and next scientific test

The experiment supports a narrow but strong finding: exact whole-tree
structure recognition from this highly bounded teacher learns a few
hundred patterns after 60,000 input observations, and these transfer
very poorly across different fiction authors, especially beyond 12
tokens. This does **not** disprove the utility of large whole-tree
caches when populated by substantially better grammatical teachers.

Important confounds to measure separately:
- Earley grammar's sentence-level coverage and timeout sensitivity.
- Lexical lattice missing required senses/valence for period prose.
- Exact full-tree signature reuse vs compositional/generalized templates.
- Text heuristics splitting chapters and quoted speech incorrectly.
- Differences in source style and authors (the holdout is intentionally
  author-disjoint).

Source code:
- research/verbnet_lr/gutenberg_novels.py (14 book IDs, parsing, hashes)
- scripts/benchmark_snap_novels.py (learning + evaluations)
- research/verbnet_lr/sampled_teacher.py (10% budgeted teacher)
- .github/workflows/snap-gutenberg-novels.yml (reproducible CI)

Production main was not changed. No novel text was shipped in the report.
