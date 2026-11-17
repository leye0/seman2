# Novel-800 — 100/100 exploratory completions, 15 rank-one attachments reviewed

Novel-800 is an **exploratory candidate**, not an officially accepted ladder
rung. The source selection, grammar work and regression evidence below are
reproducible without bypassing the production `novel_ladder.freeze` acceptance
gate. Novel-700 has **100/100 complete**, but only **24/100 individually
reviewed**; its 76 remaining source/attachment reviews are still mandatory
before an official Novel-800 acceptance.

## Source and experimental method

- N701–N800 source cohort SHA-256:
  `73e1e51a152d3d60cbf94b0b11d4a607ed6f605648bdeb7652714d857581cfaf`
- Four original cleaned Gutenberg editions, 25 independent paragraphs from
  each, 25 samples in each length band, without reusing any paragraph or
  normalized text from Novel-500–700
- Frozen manifests in
  `superparser/research/novel_800_exploration/novel-800-candidate-cohort.json`
  and `novel-800-candidate-initial.json`; the latter still records **85/100**
- Same WordNet 3.0, original complete source units, `parse_corpus_case`,
  50,000 chart item / 500,000 k-best work / 10 seconds per case budgets

## Measured improvement

| Measurement | Frozen initial | Current |
| --- | ---: | ---: |
| Complete rank-one tree **and selected semantic graph** | **85** | **100** |
| Recognized structural roots without valid analysis | 10 | 0 |
| No structural root | 4 | 0 |
| Forest budget exceeded as status | 1 | 0 |
| Individually verified selected trees and graph attachments | 0 | **15** |

The initial 85 completed signatures were preserved throughout. At the
89/100 step the preceding 85 were identical; at 97/100 the preceding 89
were identical; at 100/100 the preceding **97** were identical.
The correct full-replay results are pinned in
`novel-800-candidate-current.json`. These measurements are **not a
claim that the 85 preexisting complete trees have individually verified
semantic correctness**.

### All fifteen recovered source constructions

| Source | Selected interpretation and attachment |
| --- | --- |
| **N702** | Fronted `From thence` denotes motion source; a full finite `we proceeded to Oxford` clause is independently proven |
| **N704** | Past-perfect yes/no inversion; `my eyes` has an actual plural head, `me` is the accusative patient |
| **N705** | Copular `very unlike` with explicit `his colleague` comparison standard |
| **N708** | A letter's nonfinite closing and following proper-name signature, preserving actual quotation marks |
| **N713** | A documentary dateline preserving the incomplete literal year `17--`, not inventing its missing digits |
| **N718** | Infinitival resolution, overt colon, independent command, vocative and purpose infinitive |
| **N721** | Storm-location construction with `which lies between...` attached to the correct lake-part NP |
| **N730** | `So with the second.` as genuine anaphoric minor utterance, without invented finite predicate |
| **N732** | Interrupted `I thought perhaps Dr. Livesey--` and separate overt `I began` reporting clause |
| **N735** | Temporal frame `In the meantime`, parenthetical `as I supposed` and final `before me` locative |
| **N749** | Inverted counterfactual, shared-modal consequent, mutineers relative, and source-bound directional ellipsis with no fictitious `gone` |
| **N763** | Two source quotation spans and an intercalated reporter; passive `will be seated` and `allow me to do this` share the modal but keep their correct patient/control roles |
| **N791** | Equative comparison with possessive ellipsis `Jane's`, retaining the literal surface and not inventing `husband` after it |
| **N795** | Fronted `Vain indeed must be...` predicative inversion, parallel elliptical properties, finite `if`-condition |
| **N797** | Two speech quotes with `said Lydia`, causal `if you did` and ordered conditional consequences |

All 15 corrected cases have individual source/positive/negative tests,
selected tree spans and semantic relation assertions in
`superparser/tests/test_novel800_residual.py`. Their rank-one and graph
SHA-256 digests and review evidence live in
`novel-800-candidate-review.json`.

## Hosted complete replay

**[Green final full replay and predecessor protection](https://github.com/leye0/seman2/actions/runs/44173694683)**:
- 100/100 Novel-800 complete with no unresolved status or raised budgets
- 97 previously complete Novel-800 tree/graph signatures **unchanged**
- 100/100 Novel-600 **identical** to the accepted result
- 100/100 Novel-700 **identical** to the frozen current result
- **33 tests passed**, covering individual repairs, ladder constraints and
  source-preanalysis behavior

The first [85→89](https://github.com/leye0/seman2/actions/runs/44171105578)
and later [89→97](https://github.com/leye0/seman2/actions/runs/44172915133)
validation runs are preserved for transparent intermediate evidence.

## Remaining quality obligation

The 85 old Novel-800 syntax+graph pairs are complete, but do not yet have
per-tree semantic attachment review. As with Novel-700, syntactic coverage is
not itself semantic accuracy. Keep **PR #99 as draft**, keep the candidate
outside the official ladder, and do **not** create an official
`novel-800-accepted.json` nor waive the 76 outstanding Novel-700 reviews.
