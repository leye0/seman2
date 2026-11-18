# Novel-700 / 800 — first semantic repair pass

See the [second pass](NOVEL700800_SEMANTIC_BATCH2.md) for the current count.

Starting point: `a40c4054c0c2b412ed584a5255c35787929b2a3f` and the
[full audit](NOVEL700800_SEMANTIC_FULL_AUDIT.md). The selected source units,
their quoted spans and their immediately preceding context were checked
before changing the grammar. No source, paragraph selection or WordNet
entry changed.

| Cohort | Complete selected trees and graphs | Verified | Needs fix |
| --- | ---: | ---: | ---: |
| Novel-700 | 100 | 28 (+3) | 72 (−3) |
| Exploratory Novel-800 | 100 | 16 | 84 |
| Total | 200 | **44 (+3)** | **156 (−3)** |

## Revalidated cases

- **N601 — Frankenstein, “I could not answer.”** The original rank-one
  tree already placed `not[8:11]` in `vp_neg_bare` with
  `answer[12:18]`, below the ability modal. The semantic recipe omitted
  the relation. It now emits `NEGATION(answer, not)` on the selected
  predicate, with the existing modal and subject edges unchanged. This
  records the predicate domain and does not claim to formalize the
  scope order of all auxiliary and negation operators.
- **N660 — David Copperfield, “Not I! my dear Daisy...”** The previous
  speech supplies an antecedent concerning Steerforth taking a degree.
  The selected standalone turn treats `Not I!` as a subject-focus
  negative reprise, with an explicit focus and scoped overt negator,
  without inventing the omitted predicate. The vocative has adjectival
  `dear[11:15]` modifying its referential head `Daisy[16:21]`.
  The addressee links to the question predicate `mind`, not its modal
  `will`. The possessed gerund and its predication remain separate.
- **N680 — Pride and Prejudice, “I hope not.”** In context this responds
  to the preceding question about being blinded by prejudice. Clause-final
  `not[8:11]` fills propositional content rather than negating the
  attitude. The selected clause now uses the existing negative-proform
  construction without an overt `No,` preface, emitting
  `EXPERIENCER(hope,I)` and `CONTENT_PROFORM(hope,not)`. It does not
  invent or link to an unparsed cross-turn proposition.

The associated source, independent positives and contrasting constructions
are asserted on the selected tree and graph by
`test_semantic_ladder_review_candidates.py`. The contrasts distinguish
affirmative modal predicates, non-negative/incorrectly terminated reprises,
attitude negation and infinitival negation.

## Improved, still blocked

The general semantic recipes for verbal and do-supported negation use
the NEG child selected by each rule, not word proximity or a sweep over
unattached graph nodes. They add a correct local negation relation in six
other passages. Rechecking their actual selected outputs exposed unresolved
attachments, so none was promoted.

| Case | Added edge | Still wrong |
| --- | --- | --- |
| N671 | `NEGATION(be,not)` | Nearness and the without-regrets condition are split incorrectly |
| N692 | `NEGATION(follow,not)` | Expletive and predicand treated as agents, report manner and emphasis omitted |
| N698 | `NEGATION(been,not)` | `had` is a noun-phrase modifier and the temporal clause is misattached |
| N725 | `NEGATION(prepossess,not)` | Misread honorific, lost second-clause subject and spurious imperative |
| N782 | `NEGATION(be,not)` | Duration adverb and predicative nominal misanalysed |
| N798 | `NEGATION(remind,not)` | Possessive gerund and degree/frequency attachment still wrong |

## Replays

- Same WordNet 3.0 and 50k items / 500k k-best work / 10 s per sentence,
  through `parse_corpus_case`.
- Novel-500 retains the original source and selected-tree/status/budget
  fingerprint. Novel-600 retains every accepted selected tree and graph
  signature and budget flag.
- All 200 Novel-700/800 rows retained their status and budget flags. Only
  the nine individually reviewed outputs above changed. Other signatures
  and all prior verified verdicts were preserved. The original audit
  evidence is preserved at the starting commit.
- The complete semantic audit reports 17 automatically flagged cases
  (previously 26), with unscoped negation flagged in 9 (previously 18).
  This is diagnostics, not the verdict count. Acceptance is deliberately
  blocked on 156 individually outstanding cases.
- The Layer 1 smoke checks pass. Direct grammar quality retains 120/120
  annotated positives and 24/24 grammatical contrasts, with 9 known
  false accepts among the 24 negative controls.

Next: use the selected subject and predicate roles to resolve cases such
as N629, whose visible negator coexists with a false subject, instead of
fixing only the missing edge.
