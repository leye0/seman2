# Novel-900 / Novel-1000 grammar repair batch 2

This batch is cumulative with [the first repair batch](NOVEL1000_REPAIR_BATCH1.md).
It adds six source-backed constructions without changing the frozen source
inputs, initial diagnostics, WordNet 3.0, or the 50k/500k/10s budgets.
The 175 previously complete tree and graph signatures are kept.

| Cohort | Initial complete | Batch 1 | Batch 2 |
| --- | ---: | ---: | ---: |
| N801–N900 | 84/100 | 89/100 | 91/100 |
| N901–N1000 | 76/100 | 86/100 | 90/100 |
| Total | 160/200 | 175/200 | 181/200 |

| Source | Selected attachments under test |
| --- | --- |
| N890 | Duration belongs to the first locative perfect. The second perfect is a question, and `never` takes scope over the event of happening to see, with a separate subject and location for `see`. |
| N898 | Meryton is the goal of `returned` and the source of `set out`. The `from whence` relative links back to Meryton without reversing the motion roles. |
| N919 | The dismissal and emphatic declaration are separate from the fronted negative modal. `Never` modifies `create`, while the comparison is a modifier of `another`. |
| N961 | `Went on` is continuative in this context. `Without` scopes over the second gerund, whose agent is shared with the first one. |
| N981 | `None of you` is a negative partitive, not a possessive. Both the quantifier and its set are overt and separately attached. |
| N993 | The conditional copula is elliptical. The second sentence contrasts two times and keeps the antecedent of `better` distinct from its comparison standard. |

The independent controls, negative contrasts and exact-source graph checks
are in `superparser/tests/test_novel1000_grammar_repairs.py`. These are
construction-level regression assertions, not full-cohort semantic verdicts.

## Remaining source IDs

- N801–N900: N815, N820, N830, N837, N839, N845, N869, N899, N900.
- N901–N1000: N907, N918, N943, N944, N946, N952, N962, N964, N974, N1000.

N952 remains a provenance defect documented in batch 1. The current unit
does not represent the complete source speech. Its boundary should not
be repaired by inserting synthetic punctuation or changing this cohort's
immutable identity during a grammar-only replay.
