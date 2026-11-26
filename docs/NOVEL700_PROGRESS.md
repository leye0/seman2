# Novel-700 — source-grounded 100/100 and attachment review status

> **Semantic accuracy not certified.** The recorded 100/100 means complete selected syntax trees and generated graphs, **not correct selected roles or attachments**. The full source-and-graph audit in [the semantic defect register](NOVEL700800_SEMANTIC_DEFECTS.md), [second pass](NOVEL700800_SEMANTIC_SECOND_PASS.md), [third pass](NOVEL700800_SEMANTIC_THIRD_PASS.md), and [final pass](NOVEL700800_SEMANTIC_FINAL_PASS.md) documents 158 selected semantic shortcomings across Novel-700/800, including a contradiction of a previous positive review. The semantic acceptance gate is intentionally blocked. Do not use 100/100 as an accuracy claim.


The frozen Novel-700 source SHA-256 remains
`92076729dc1ee5763c9981831b02af84e394f4d0daa7ebe05ad8a1c014660687`.
The immutable **77/100 initial baseline** is unchanged. The initial correction pass
achieved **88/100**. The residual correction pass has now recovered exactly the
remaining 12, reaching **100/100 complete selected rank-one trees with semantic
graphs** at unchanged budgets and WordNet 3.0.

The 12 recovered source IDs are **N624, N625, N639, N643, N647, N648, N649,
N660, N661, N669, N672 and N691**. Each has independent positive, negative,
source-span and selected semantic attachment checks in
`superparser/tests/test_novel_700_residual.py`. The supplementary
`docs/NOVEL700_RESIDUAL_REPAIRS.md` documents their construction and meaning
reviews. Notably, N624's relative contains a real quantified object and
genitive constituent, and N647's `make her count` is correctly selected as
a verbal bare causative, **not** a possessive noun phrase.

## Exact hosted validation

[Final frozen full-cohort and Layer-1 validation](https://github.com/leye0/seman2/actions/runs/44167834185)
completed successfully:

- **Novel-600**: 100/100 complete; all 100 sealed selected-tree and selected-graph
  signatures unchanged.
- **Novel-700**: 100/100 complete; the earlier **88** completed records are exactly
  unchanged, including N612's already-reviewed `saw` sense. Exactly the 12
  previously incomplete cases became complete. No new forest/k-best saturation
  or raised resource limits.
- **Novel-500**: 500/500 complete, with its original source fingerprint, all 500
  selected rank-one signatures, statuses and saturation flags identical.
- **30 anchored real-dialogue cases**: 30/30 complete, with no changed identities.
- **Direct syntax**: 120/120 structural positive annotations; 24/24 positive
  grammatical contrasts. Existing negative acceptance tolerance unchanged.
- **Source-specific review**: all 12 additional rank-one trees and selected graphs
  are checked against original source and independent positive/negative controls.

The current selected signatures are pinned in
`superparser/research/novel_ladder/novel-700-current.json`; the 12 review
verdicts are recorded alongside the 12 pre-existing verified entries in
`novel-700-review.json`.

## Important remaining quality boundary

**24/100** Novel-700 selected trees have individual source-grounded attachment
reviews. The other **76** are complete, not individually certified. Do not
equate this coverage of full-span analyses with independent accuracy for
every attachment; keep PR #98 in draft, do **not** create
`novel-700-accepted.json`, and do **not** sample Novel-800 until all
100 individual source-grounded attachment reviews are finished.
