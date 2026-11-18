# Novel-1500 repair batch 1

The source and initial replay pins from [the exploratory baseline](NOVEL1500_EXPLORATION.md)
remain unchanged. The comparison is against `ac1a462a213b457c0bab300ae962f9d0054ea764`,
using identical editions, text, source offsets, WordNet 3.0 and the original
limits of 50,000 chart items, 500,000 k-best work units and 10 seconds per case.

**Coverage is now 1,401/1,500, up from 1,391.** Novel-1100 is 87/100, up from
77/100. The other four new rungs are unchanged at 79, 77, 77 and 81.
Two previously complete Novel-1100 results had their incorrect attachments
repaired independently of the ten coverage gains. There are 99 outstanding
coverage failures, starting at N1043. The remaining complete results are
not certified by this batch.

| Case | Before | Evidence in the selected repair |
| --- | --- | --- |
| N1006 | Complete with incorrect subject relative | *All* is the overt shared subject of *felt* and *feel*. Both verbs take *sorrow* through the object gaps. |
| N1010 | Roots, no valid derivation | The `-ing` property coordinates with *long*. The relative qualifies *journey*, which has *Ingolstadt* as its destination. The reflection topics belong to *leisure*. |
| N1012 | Complete with two bad PP attachments | *My face* is where determination is visible, not the recipient of *saw*. *In the impotence of anger* modifies *gnashed*, whose subject is still *the monster*. |
| N1013 | Roots, no valid derivation | Independent declaratives with emphatic `do`, an appositive vocative, and both consequences coordinated under *devote*. |
| N1014 | No root | The movement and report share their subject. The vocative and temporal imperative are inside the real quotation. The before-clause governs the command, whose certainty predicate takes *that you are yourself safe*. |
| N1015 | Roots, no valid derivation | *Health* is the antecedent of the recovery relative. *Shock* is the object of *sustained* in the nested zero relative. Negation and degree stay scoped to *recovered*. |
| N1021 | Roots, no valid derivation | *Margaret* is addressed by the reader clause. *Your blood* is the subject of *congeal*, *horror* its cause, and *mine* uses the overt nominal type *blood* without inserting words. |
| N1024 | Roots, no valid derivation | The creation has the matrix subject, while *barbarity*, possessed by the *fiend*, causes both effects. *It* refers to *heart*. |
| N1025 | Roots, no valid derivation | *Father* takes both the affective state and perception. *Diffidence* is perceived within the niece's melancholy, and preparation provides the context for recognition. |
| N1037 | No root | Both original quote spans are attributed to *Morgan*. The overt dialectal gerund is the cause and *Bibles* its patient. No gerund controller is invented. |
| N1039 | No root | Both the negative response and finite negative auxiliary are reported by *Livesey*. The omitted predicate remains unresolved, not reconstructed. |
| N1041 | Roots, no valid derivation | *Dance* dismounts and controls *taking*, but is the patient of *admitted*. *Word* is the enabling cue and *house* the destination. |

Each case is checked through `parse_corpus_case` with its genuine source span.
The tests assert the critical selected constituent and its exact source offsets,
the overt relation endpoints, an independent grammatical control and a
negative contrast. All 12 targeted results finish without resource flags.
No grammar is added to accept an orphaned source or fabricate punctuation.

The [verified deltas](../superparser/research/novel_1500_exploration/verified-repairs.json)
bind the previous and selected tree/graph signatures to the initial manifest.
Replay still checks all unmodified results, not just total coverage. The initial
repair queue stays immutable. To see remaining cases or the next passage in
context, run:

```sh
PYTHONPATH=superparser python -m scripts.novel1500_exploratory queue
PYTHONPATH=superparser python -m scripts.novel1500_exploratory inspect
```
