# Novel-600 — selected attachment pass

This pass starts from the completed replay of PR #97 at
[3ca9ae9](https://github.com/leye0/seman2/commit/3ca9ae9f8443363d1ac280f856c70da9d00b9448).
The [source checklist](NOVEL600_OPEN_TREE_REVIEW.md) describes the 55 open
cases at that point. The [current signatures](../superparser/research/novel_ladder/novel-600-current.json)
and [review ledger](../superparser/research/novel_ladder/novel-600-review.json)
are the machine-readable results.

| Frozen Novel-600 slice | Before | After |
| --- | ---: | ---: |
| Complete selected trees | 100 | 100 |
| Linguistically verified trees and graphs | 45 | 95 |
| Open attachment reviews | 55 | 5 |
| Forest budget flags | 2 | 2 |

Exactly 49 selected trees and semantic graphs changed. N570 was verified
without changing either signature. The old tree already preserves the four
spoken attempts, the three source dash spans, the final amount, the waiter
as payee, and the question-level politeness supplement. No previously
verified entry changed and no new forest or k-best budget flag was added.

## What the changed trees fix

- **Adjunct scope and argument structure.** N510 now selects a prepositional
  phrase and anchors MANNER to all of *on horseback*. N514 dates the start
  of the journey, not the decision. N519 attaches *the next day* to the
  projected beginning and the availability relative to that day.
- **Coordination, control and gaps.** N517 and N562 retain the shared
  subject through the coordinated predicates. N537 binds the focused
  group to the cleft gap without negating the perception. In N539 the
  relative takes the death event rather than *that evening*.
- **Speech and quotation boundaries.** N540 keeps the condition within
  the quote and both spatial complements in the later narrated placement.
  N542 keeps the two distinct negations and the local deictic clause.
  N554 distinguishes a bare reporting use of *interposed* from a
  transitive narration, preserving the original speech and vocative.
  N590 preserves two independent questions and a modal perfect passive.
- **Exact semantic spans.** The new anchored semantic action is opt-in.
  It is used where a node must refer to the full syntactic constituent,
  such as the horseback PP, the full title and name in N589, or the
  dislocated nominal antecedent in N593. N589 also exports the perfect
  auxiliary at its original span.

The scoped planners only propose spans. Lexical candidates and independently
parsed phrases still have to satisfy the declarative rules, and nonmatching
analyses keep the existing parser route. Every corrected construction has
its original-source attachment test, an independent positive and a contrast.

## Regression checks

The local replay uses the same frozen anchors, `parse_corpus_case`,
WordNet 3.0 and 50,000 chart items / 500,000 k-best work units / 10 seconds
per case. All 500 legacy signatures and all 30 anchored dialogues pass.
The 120 positive direct grammar annotations also pass. This does not claim
that the direct negative set has been solved, or that the hosted workflow
has finished.

The five remaining cases are **N547, N573, N575, N592 and N596**. N547 and
N575 preserve their existing forest flags. N573 still needs a decision on
the retrospective versus higher stance attachment and an explicit perfect
aspect link. N592 and N596 involve a free-relative exception and a split
reported gerund construction, respectively. The rung is not sealed.

## Closing the rung

The final pass starts from [a77320b](https://github.com/leye0/seman2/commit/a77320b95a2aab7443931b35c92fffc86daec42a).
It changes exactly the five remaining trees and their exported graphs. The
95 earlier verified signatures stay identical. The count reaches **100/100
verified**, with no chart or k-best budget flag in Novel-600. The initial
78/100 replay, source anchors and per-case budgets are unchanged.

| Case | Selected structure and regression witness |
| --- | --- |
| N547 | The hearing times *felt*, the perceived person supplies the subject of *addressing*, and the full same-words phrase modifies the addressing. The comparison standard retains the perfect auxiliary and local recipient. |
| N573 | *Have done* exports perfect aspect. The selected reading attaches *in my fatuity* to the prior actions, which the surrounding confession supports. An alternative attaches it to *know*, and preposing the PP selects that higher reading. The complete named attribution and gesture are outside the quote. |
| N575 | *Made* controls the bare saying clause through *him*. *I knew* comments on the causation. The purpose belongs to the causer's action, and the final *when* clause modifies *night* within the description of the light. |
| N592 | The fronted PP gives the domain of a perfect passive, and the free relative is an exception to what was known. The public-knowledge context favors emphatic *himself*. The self-recipient reading remains available at lower rank. |
| N596 | The fronted nursing activity is inside the certainty's content as the domain of the addressee's pleasure. The original tag attributes both speech parts. A modal passive increase is hoped for, with *her quite well* as a depictive inside the means. |

The [accepted pin](../superparser/research/novel_ladder/novel-600-accepted.json)
preserves the selected tree and graph fingerprints for future runs. Novel-500
keeps all 500 protected entries and passes all 30 anchored dialogues. No
Novel-700 source was sampled in this pass.
