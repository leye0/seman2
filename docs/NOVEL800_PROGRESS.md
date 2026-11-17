# Novel-800 — 100/100 exploratory coverage, with source-verified residual trees

Novel-800 is a **reproducible candidate cohort**, not an accepted ladder
rung. The production `scripts.novel_ladder.freeze` review gate is unchanged.
Novel-700's 100 full-span analyses still have only **24/100 individual
source-backed syntax/semantic reviews**, so Novel-800 remains on a separate
research branch until that predecessor is accepted.

## Source selection and immutable baseline

- **N701–N800** frozen cohort SHA-256:
  `73e1e51a152d3d60cbf94b0b11d4a607ed6f605648bdeb7652714d857581cfaf`.
- Four fixed cleaned Gutenberg novels, **25 distinct paragraphs per book**
  and **25 cases per length band**. Neither paragraphs nor normalized sentence
  identities are reused from the preceding 700 cases.
- The same deterministic `novel_ladder.pick` and `resolve` are used, but the
  frozen 800 candidate lives in `research/novel_800_exploration` and does not
  bypass the actual acceptance gate.
- **No changed budget:** WordNet 3.0, 50,000 chart items, 500,000 k-best
  work units, 10 seconds per case; every original source passes through
  `parse_corpus_case`. No sentence text or source span is rewritten.

| Metric | Frozen initial N800 | Final explored N800 |
| --- | ---: | ---: |
| Complete rank-one syntax tree and selected semantic graph | 85/100 | **100/100** |
| No structural root | 4 | **0** |
| Roots without valid selected analysis | 10 | **0** |
| Forest budget exceeded | 1 | **0** |
| Individual source-backed syntax/semantic reviews | 0/100 | **15/100** |

The immutable 85/100 baseline remains `novel-800-candidate-initial.json`.
The final 100/100 signatures are pinned in
`novel-800-candidate-current.json`. The **85 originally complete cases
remain bit-for-bit unchanged**, together with the 12 intermediate recovered
cases; the final stage added only N763, N791 and N797.

## Reviewed fixes (N800 original failures)

| Case | Verified rank-one construction and relationships |
| --- | --- |
| N702 | `From thence` is an attested source PREP+ADV deictic and modifies independently proven finite `we proceeded to Oxford`; it is not a counterfeit nominal PP |
| N704 | `Had my eyes deceived me?` has perfect subject–auxiliary inversion, an actual **plural** possessive subject, transitive participle and accusative object |
| N705 | Predicative `unlike` retains its degree `very` and complete NP comparison standard `his colleague`, with `This professor` as singular subject |
| N708 | Source **letter subscription** is a nonfinite documentary NP with the real quotation delimiters and a distinct proper-name signatory; no fictional finite clause |
| N713 | Source **dateline** has a real place, month, ordinal and the precise incomplete year `17--`, never an inferred full year |
| N718 | Source colon links an infinitival plan `To go instantly to Geneva` and the real imperative `come with me`, with vocative Henry and purpose `to order the horses` |
| N721 | `The most violent storm` is the agent of `hung`; `north of the town` is a locative, and the lake-part relative `which lies between ...` attaches to the **part of the lake**, not to the storm |
| N730 | `So with the second.` is a source-licensed anaphoric **elliptic** utterance: no missing finite verb is fabricated |
| N732 | The quoted thought is **interrupted by an original double dash**, with the real honorific Dr. and source name Livesey, followed by independent reporter `I began` |
| N735 | `In the meantime` is temporal, `as I supposed` is an epistemic parenthetical and `before me` remains the separate concluding locative |
| N749 | **Inverted existential condition** `Had there been a breath of wind`, modal-perfect consequences `should have fallen` and shared `slipped`, a mutineers-relative with passive `were left`, plus final verbless `away to sea` with no synthetic `gone`; resolves the one saturated case without more chart budget |
| N763 | Original split quotations preserve `I beg, sir`, reporter `he returned respectfully`, modal-passive `you will be seated` and shared-subject `allow me to do this`; the object **me controls do**, rather than modifying `seated` |
| N791 | Semicolon contrast, `perhaps` incise and `I think` content surround an equative comparison of `your husband` with overt **`Jane's` possessive ellipsis**, preserving exactly the original apostrophe-s token and its antecedent without inventing `husband` after Jane |
| N795 | Fronted `Vain indeed must be all her attentions` plus parallel verbless adjectival predication over `her affection` and `her praise`, with explicit conditional `if he were ... self-destined for another` |
| N797 | Intercalated `said Lydia` reports initial `Thank you` and a causal `for if you did` with anaphoric **did** and two consequent modal clauses `I should certainly tell you all`, `Wickham would be angry`, in sequence |

Each corrected selected tree is checked on its exact frozen source, an
independent grammatical positive and a matched negative. Tests assert the
selected root, full source offsets, key constituent categories, selected
semantic-graph relationships and no new budget saturation. Additional deep
checks cover N704's plural noun, N713's truncated year, N730's omitted
predicate, N749's directional ellipsis and N791's overt possessive token.
The 15 selected-tree and selected-graph SHA-256 fingerprints, with review
evidence, live in `novel-800-candidate-review.json`.

## Hosted checks and protected predecessors

[Full hosted final replay](https://github.com/leye0/seman2/actions/runs/44173694683)
passed with **100/100 N800**, **33 passing focused and ladder tests**,
all **97 already-completed N800 tree/graph signatures unchanged** during
the final three fixes, and a byte-for-byte comparison of **both** 100/100
Novel-600 and 100/100 Novel-700 selected tree/graph signature sets.
Earlier incremental stages independently compared all 85 original complete
N800 trees, so the full inherited subset is protected. The frozen source
cohort, original baseline and resource budgets remain unchanged.

### Final legacy and direct-grammar certification

The [final pinned N800 and historical protection run](https://github.com/leye0/seman2/actions/runs/44174605724)
also completed **successfully** after the final 100/100 pin.
It confirms:

- **100/100 N800** with all 100 pinned source/tree/graph signatures
  unchanged, **15/15** recovery reviews present and matching.
- **100/100 Novel-600 and 100/100 Novel-700** with byte-for-byte identical
  selected tree and selected graph signatures.
- **500/500 Novel-500** with the historical selected fingerprint unchanged.
  The long-standing 16 complete analyses carrying a forest-saturation flag
  are unchanged; no new failed or timed-out case.
- **30/30 anchored real-dialogue witnesses** unchanged.
- **120/120 direct gold syntax/annotations**, all **24/24 grammatical
  positive contrasts** maintained with no worsened negative acceptance.
- **33 tests** in the focused Novel-800, ladder and preanalysis suite passed.

## Quality and promotion boundary

**100/100 complete is not synonymous with 100/100 individually verified
attachment correctness.** We have individually examined and recorded the
15 recovered selected trees; the other 85 complete N800 analyses have not
yet had their own source-by-source semantic attachment review. Novel-700
also still needs 76 such reviews. Keep this cohort exploratory and PR in
draft: do **not** create `novel-800-accepted.json`, merge into the
accepted ladder or select Novel-900 before both review gates are closed.
