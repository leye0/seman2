# Novel-700 / 800 — third semantic repair pass

Starting point: `57562b4434844c339cf25ccb7a36345ead45738a`
([previous pass](NOVEL700800_SEMANTIC_BATCH2.md)).

| Cohort | Complete selected outputs | Verified before → after | Still open |
| --- | ---: | ---: | ---: |
| Novel-700 | 100 | 42 → 54 | 46 |
| Exploratory Novel-800 | 100 | 30 → 44 | 56 |
| Total | 200 | **72 → 98** | **102** |

## Twenty-six newly verified analyses

| Group | Verified source cases |
| --- | --- |
| Nominal roles, control, direction and degree | N607, N610, N613, N627, N631, N656, N683, N731, N733, N755, N781, N783, N784 |
| Reported questions, vocatives and replies | N630, N637, N659, N662, N736, N738, N761 |
| Exclamation, ellipsis, negation and discourse continuation | N682, N701, N707, N751, N752, N756 |

Representative differences on the selected tree and graph:

- **N607:** the PP is inside the hand noun phrase, not an argument of
  taking. The selected graph has `POSSESSOR(hand,Elizabeth)` and
  `AFFECTED(took,hand)` instead of a recipient.
- **N613 and N783:** the reciprocal prepositional object and the verb
  selected by *unable* have distinct roles. In object control, the overt
  object of *called* controls the lower *look* predicate, which has its
  own oblique complement.
- **N659 and N662:** *Master* is the address title, rather than a verb
  or a second speaker. The overt postposed reporting subject is a single
  noun phrase. The interjection and nominal exclamation share the
  reporting construction without sharing their internal grammar.
- **N733:** the previously repaired comparison now also has ordinal
  *fifth*, scalar *quite* and a predicand instead of a false agent.
- **N752:** the fused spelling *cannot* is preserved. Its two components
  use adjacent, original character spans, with negation and modality
  on *answer*. *Others* is the object of *for*, not a second predicate.
- **N761:** the nominal speech act comes before the perfect question.
  *Woman* is not topicalized as a modifier of *forgot*. The original
  historical participle and punctuation remain intact.

Semantic recipes can now classify an already-grounded graph node under
an explicit selected construction, without rewriting the candidate,
replacing its sense identifiers, or moving its span. Examples include
literal *hands* as a body part in the reciprocal greeting, the literary
*volume* as a book volume, and *best shot* as a person in the identifying
question. No global replacement of the competing lexical readings was made.

## Still open

Fourteen other selected outputs changed but retain documented defects:
N667, N674, N688, N694, N722, N725, N737, N747, N750, N758, N764,
N794, N796 and N799. For instance, N794 now identifies the arrival as
the cause of the passive, but the opening reduced relative still
misanalyses *week* as the agent of *spent*. A corrected edge does not
verify the full utterance.

## Verification

- Source, independent positive and contrast tests inspect the selected
  constituent rules, original anchors and graph edges for all 26 cases.
  The test also checks the disjoint spans of the repeated degree replies,
  the contiguous modal/negator spans, and the contextually classified nodes.
- Novel-500 retains its pinned syntax, status and budget fingerprint,
  including the 30 anchored dialogues. Novel-600 retains all its
  protected selected syntax and graph signatures.
- Replayed all 200 Novel-700/800 cases with unchanged source identity,
  completion and budget flags. Forty selected outputs changed, none of
  the 72 previously verified outputs changed, and 102 blockers remain.
- WordNet 3.0 and the 50k item, 500k k-best and 10-second limits were
  unchanged. Layer 1 smoke and the direct grammar controls passed.
  The automatic quality report flags 11 cases, but does not replace
  the 102 case-level open reviews.

The acceptance gate remains intentionally closed.
