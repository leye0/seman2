# Novel-700 / 800 — fourth semantic repair pass

Starting point: `4164d228f5975196bf1c4941a907d8aec81a4d29`
([previous pass](NOVEL700800_SEMANTIC_BATCH3.md)).

| Cohort | Complete selected outputs | Verified before → after | Still open |
| --- | ---: | ---: | ---: |
| Novel-700 | 100 | 54 → 83 | 17 |
| Exploratory Novel-800 | 100 | 44 → 74 | 26 |
| Total | 200 | **98 → 157** | **43** |

Exactly 59 selected outputs changed and all 59 have case-level evidence.
The 98 already verified outputs and the 43 unresolved outputs kept their
selected syntax and graph signatures. The acceptance gate remains closed.

## What changed

The new source gates delimit independently proved attachment domains.
They check original quotation or semicolon boundaries, then let the existing
lexical lattice, phrase parser and structural grammar prove the candidates.
They use grammatical constructions and bounded lexical classes, not cohort
IDs or whole-source literals. Semantic recipes project relations from
selected constituents. No extraction rule, corpus text, or parser work
limit was changed.

- **N617, N616, N684, N690 and N714:** a relative's antecedent is distinct
  from its internal subject, location or passive theme. In N714 the inn
  is both the orientation landmark and the location of the vehicle stops.
  The literary *diligences* means stagecoaches here.
- **N635, N636, N638, N742 and N757:** speech content, addressees, reporting
  clauses, echo tags and reporting gestures are separate selected structures.
  The source spellings `ain't`, `a-going`, `cap'n` and `won't` survive.
  In the tag *won't you* the modal and negator use adjacent spans of one
  printed token; there is no lexical event of winning.
- **N621, N642, N657, N668, N723, N764, N766 and N800:** a participant may
  control one complement without taking over an adjacent clause. In N800
  *him* controls *stand up*, but *she* controls *introduce* under *offer*.
- **N632, N689, N744, N762, N767 and N769:** distinct edges represent the
  time, location, manner or circumstance of the event they actually modify.
- **N614, N688, N692, N782 and N793:** persistence, aspect, modality,
  negation and the declared conditions bind to their own predicates.
  In N692 dummy *it* does not become the actor of *follow*. A separate
  node represents the first reply's unresolved predicate.
- **N667, N645, N758, N787, N790, N794 and N796:** both halves of a
  comparison or coordinated complex keep their own local attachments.
  In N794 *week* is the theme of reduced passive *spent*, and arrival of
  Saturday is the cause of *called*. N796 grounds the topic of the
  curiosity and removes the spurious self-cause.

The [fixture](../superparser/tests/data/semantic_batch4_controls.json)
lists every verified case, one independent positive, an independent
near-miss, selected tree requirements, and the graph relations used in
review. Additional checks distinguish the two *have … lost* clauses by
their original spans, require a genuinely shared comparison standard,
check lexical classifications in context, and reject incongruent
agreement in the new passive, perfect and interrogative analyses.

## Regression scope

- Novel-500 matches its pinned ordered rank-one, completion and budget
  fingerprint. Its 30 original anchored dialogues complete.
- Novel-600 matches all 100 accepted syntax and graph signatures.
- Novel-700 and Novel-800 both replayed 100 complete selected outputs
  under the same 50,000 chart item, 500,000 k-best and 10-second caps,
  using WordNet 3.0. Their original case and source identities are unchanged.
- The direct grammar gold keeps 120/120 annotations and 24/24 grammatical
  contrasts. The same nine known false accepts are still reported.
- The focused regression suite passed 56 tests. The full semantic audit
  reports five automatic issue cases, with zero stale or conflicting
  reviews. The deliberately failing final gate still requires all 43
  open cases to be individually corrected and verified.
- A passed replay or automatic flag scan does not certify the remaining
  43 cases. For example N655 still needs a *general* solution for the bare
  finite-form agreement contrast; a correct graph for the original sentence
  is not enough to close it.
