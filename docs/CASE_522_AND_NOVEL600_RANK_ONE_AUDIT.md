# Novel-600 selected-tree audit

Base PR #97 SHA `80ae06186d4670f832d5ceccf063df4999a0a017`.
The evaluated source manifest is still
`47b72e48a85bb6e04ff179b3a5cbcdd9284d1ea6c596cbbfb8fb2773f21987e7`.
Each selected tree was inspected for its source-faithful construction,
constituents, arguments and attachments, and for missing or false exported
roles. The per-case review ledger records the judgment and both digests.
It does not claim word-sense disambiguation, recovered cross-sentence
antecedents, or independent expert agreement.

## N522 — two distinct sledges

> It was, in fact, a sledge, like that we had seen before, which had drifted towards us in the night on a large fragment of ice.

The contiguous Frankenstein paragraph describes finding a different sledge
beside the vessel. The same paragraph and surrounding account establish the
previously seen sledge as the comparison standard, not the one that drifted
towards the ship. The frozen source span `[17667, 17793)` is one complete
utterance. No source or segmentation change is needed.

Before, `clause_comma` selected lexical `was` in an intransitive VP, then an
imperative `like` whose NP incorrectly held both relatives. The final three
PPs were swallowed in an NP below `towards`, giving `us` its own time and
support modifiers. This shape passed the structural completion count.

The verified source composition preserves `It` `[0,2)`, copula `was`
`[3,6)`, and stance `in fact` `[8,15)`. The predicative nominal begins at
`[17,25)` and governs the following comparison and supplementary relative.
The two clauses have independently licensed perfect auxiliaries and
participles. `That` `[32,36)` is the missing object of the seeing in the
first relative `[32,55)`. `Which` `[57,62)` refers to the newly introduced
sledge and is the sole subject of drifting. The direction `[75,85)`, time
`[86,98)` and support `[99,125)` belong to drifting, not to `us`. The
independent boat example and the malformed perfect contrast exercise the
same construction and are part of the attachment test suite.

## Other selected-tree repairs

| Case | Former error | Verified construction |
| --- | --- | --- |
| N501 | Adverb without a predicate | Exclamation attributed by an inverted speech tag |
| N503 | Missing relative object relation despite a gap | The same object belongs to matrix gaining and relative desiring |
| N504 | Generic adjunct leaves the sobs relation unspecified | Suppressed voice is the passive theme and the sobs its cause |
| N505 | Standalone answer becomes a topic, with negation not exported | Separate refusal, copular attribution and scoped degree and negation |
| N507 | Two nominal names | An interjection with a vocative and an inverted speech tag |
| N511 | The onset rather than the fever is the antecedent; duration is a recipient | Relative inside the embedded NP; `for several months` measures confinement |
| N530 | `won` is a verbal modifier of the subject | Negative `will`, an overt question, and the reporter’s own manner |
| N543 | Modal becomes adjective and perfect auxiliary becomes noun | Fronted predicative concessive, separate possessed capacity and controlled infinitive |
| N566 | Copula prematurely ends the matrix and temporal nouns become a subject | An incised copular proposition containing a negated modal perfect existential |
| N576 | Negative reply is a nominal apposition | An answer and a separate degree-modified negative reprise |
| N577 | Manner modifies the embedded copula | Reporting manner is on replied; the missing copular predicate remains unresolved |
| N578 | `ma’am` splits into nominal `ma` and verbal `am` | Affirmation, respectful vocative and elliptical totality |
| N579 | `not` is an ordinary adverb | Negative propositional proform under belief, with an independent negative answer |
| N588 | Clause-level disjunction and a spurious title | Local frequency coordination, adversative second clause, and retained subject Charlotte |
| N599 | Object of received absorbs the second action and purpose | Shared subject, high depictive attachment and purpose on taking refuge |

Each repair has the source witness, an independent positive example, and a
negative test that must not select the same composition. Negative controls
are not a claim that existing fallback grammar rejects every ungrammatical
input. Source plans specify span constraints; the normal lexical evidence
and grammar license the spans. No exact-citation switch or changed parse
budget is used. The two existing forest flags are N547 and N575.

## Audit outcome

44 verified, 56 require further work. The 16 newly repaired trees are
included among the 44. Of the other 84 current trees, all are unchanged
from PR #97's previous result. Novel-700 remains unopened. Next is N502,
where the structure is plausible but the exported adverb is a topic and
`of rain` is assigned a partitive role.

## Follow-up — N502

In the contiguous Frankenstein paragraph, the rising wind, moving clouds and
waves precede the sudden onset of a rainstorm. The complete source utterance
is “Suddenly a heavy storm of rain descended.” The clause-initial adverb
modifies the onset of descending. The subject is “a heavy storm of rain”.
“Heavy” describes “storm”, while “of rain” specifies its precipitation and
does not make the storm a subset of a larger whole.

The source-scoped grammar preserves the terminal full stop and separates the
finite event, its subject, and the precipitation PP under the subject. The
selected graph exports TIME, THEME, MODIFIER and MATERIAL for these links.
An independent shower-of-hail example exercises the same structure, and an
actual portion-of-hail construction must not select it. The 99 other
Novel-600 signatures, source anchors, original baselines and budget flags
are unchanged. The ledger now records 45 verified trees and 55 open cases.
