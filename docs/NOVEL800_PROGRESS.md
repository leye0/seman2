# Novel-800 exploratory cohort — 89/100, with protected predecessors

Novel-800 is a **candidate research cohort**, not an accepted ladder rung.
The production `scripts.novel_ladder.freeze` gate is unchanged: Novel-700's
100 selected trees must each receive individual source-backed syntax and
semantic review before advancing the official ladder. At this branch point,
Novel-700 has **100/100 completed, 24/100 individually reviewed**.

## Source cohort

- **N701–N800**: fixed SHA-256
  `73e1e51a152d3d60cbf94b0b11d4a607ed6f605648bdeb7652714d857581cfaf`.
- Same four cleaned Gutenberg editions as the accepted 500, 600 and
  frozen 700; 25 distinct paragraphs per book and 25 per length band.
- No paragraph or normalized text identity re-used from the first 700 cases.
- Sampling uses the identical deterministic `novel_ladder.pick` and
  `novel_ladder.resolve` functions, but stages in
  `research/novel_800_exploration/` so the acceptance gate remains intact.
- Frozen `novel-800-candidate-cohort.json` and initial results never change.
- **Same limits**: 50,000 chart items, 500,000 k-best operations,
  10 seconds per case; WordNet 3.0; all original source spans via
  `parse_corpus_case`.

## Baseline and first correction

| Metric | Frozen initial | Current |
| --- | ---: | ---: |
| Full rank-one parse and semantic graph | 85 | **89** |
| Root candidates without valid selected analysis | 10 | 7 |
| No structural root | 4 | 3 |
| Chart budget exceeded | 1 | 1 |
| Individually verified source/attachment reviews | 0 | **4** |

The completed but not independently reviewed 85 trees have **byte-identical
selected tree and graph fingerprints** across the first correction. No
baseline success was traded for another success.

### Corrected cases

- **N702** `From thence we proceeded to Oxford.`: a source-marked deictic
  origin and an independently proven finite movement clause, no illicit
  projection of the adverb `thence` into a nominal object.
- **N704** `Had my eyes deceived me?`: subject–auxiliary inversion with
  overt past participle and accusative object, plus a genuine **plural**
  possessive subject `my eyes` (the misleading singular homograph is rejected).
  Its semantics encode perfect aspect, agent, patient and possessor.
- **N705** `This professor was very unlike his colleague.`: predicative
  adjective `unlike` with a full NP comparison standard, scoped under
  `very`, and an independently proven demonstrative subject.
- **N730** `So with the second.`: overt elliptical, anaphoric minor
  utterance; no fictitious finite verb. The PP remains a complete source
  constituent.

Each repaired selected tree and selected semantic graph has an independently
sampled grammatical positive, a matched negative and exact source offsets
asserted in `superparser/tests/test_novel800_residual.py`; the case review
digests are recorded in `novel-800-candidate-review.json`.

[First full validation](https://github.com/leye0/seman2/actions/runs/44171105578)
confirmed **89/100**, **85 unchanged rank-one signatures**, and **100/100
unchanged signatures for both Novel-600 and Novel-700**. Grammar, corpus
and budget contracts stay unchanged.

## Remaining 11 source-specific failures

| Status | IDs | Need |
| --- | --- | --- |
| No structural root | N708, N713, N791 | Investigate original contiguous paragraph and quote/document context before adding syntax |
| Structural roots without valid analysis | N718, N721, N732, N735, N763, N795, N797 | Diagnose selected source constituents and genuinely missing attachment/valency |
| Chart saturation | N749 | Constrain conditional-inversion and coordination proof; do not raise 50k budget |

These are genuine open cases, **not** marked expected failures or suppressed
through changed eligibility. Keep the first 85 and four new trees protected
before each subsequent incremental correction.

## Promotion boundary

The initial and current candidate manifests here must not be renamed
`novel-800-accepted.json`. Do not present **89/100 completed** as
**89/100 semantic correctness**: only four novel 800 source trees have
individual review evidence. The eventual official frozen Novel-800 rung
still depends on the completion of the 76 remaining Novel-700 reviews.
