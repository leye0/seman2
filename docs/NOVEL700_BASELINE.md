# Novel-700 — immutable source and first parsing baseline

This new rung starts from the **sealed Novel-600** selected analyses at commit `6323206fc12c2224c16219fdff0bc05be69b4a54`, not from a changed parser. The source sampler, WordNet 3.0, corpus gateway and parse limits are unchanged. Novel-600 remains in its original stacked PR and is not rewritten here.

## Frozen selection

- IDs: **N601–N700**, 100 distinct cleaned-source passages.
- Four original Gutenberg source editions, 25 per book and length band; one source paragraph and normalized text identity per case, no overlaps with Novel-500 or Novel-600.
- The sampler chose these **before running the grammar**.
- Frozen cohort SHA-256: `92076729dc1ee5763c9981831b02af84e394f4d0daa7ebe05ad8a1c014660687`.
- Anchors: [novel-700-cohort.json](../superparser/research/novel_ladder/novel-700-cohort.json).

## Initial measurement

Source workflow: [Novel-700 frozen-source baseline](https://github.com/leye0/seman2/actions/runs/44144433179). It ran on unchanged parser code and preserved a complete per-case parse artifact.

| Outcome | Initial count |
| --- | ---: |
| Complete rank-one trees | **77** |
| Roots with no valid unified analysis | 15 |
| No structural root | 5 |
| Forest saturation without complete tree | 3 |
| **Total** | **100** |

Seven cases had the forest-budget flag: N622, N625, N646, N648, N672, N675, and N699. Four of these still returned a complete rank-one tree.

The **23 currently incomplete** cases are:
N603, N615, N619, N623, N624, N625, N639, N641, N643, N647, N648,
N649, N652, N654, N660, N661, N665, N666, N669, N672, N685, N691, N700.

The result files [novel-700-initial.json](../superparser/research/novel_ladder/novel-700-initial.json) and [novel-700-current.json](../superparser/research/novel_ladder/novel-700-current.json) deliberately begin identical. **77 complete trees is not a claim that 77 trees have correct attachments.** A source-grounded review and selected semantic graph examination must precede any `verified` verdict. Do not rewrite initial results or substitute inputs to manufacture coverage.

## Rules for corrections

Use the one public `parse_corpus_case` route and original source paragraphs. Keep 50,000 chart items, 500,000 k-best work units, and 10 seconds per sentence. Include an independent grammatical positive, a near-miss negative, and exact constituent/semantic attachment assertions for each repair. Replay the same 100 IDs and protect all 600 earlier signatures. Commit a `novel-700-accepted.json` pin only after **100 independently verified selected trees and graphs**, not merely 100 completed parses. Do not draw Novel-800 yet.
