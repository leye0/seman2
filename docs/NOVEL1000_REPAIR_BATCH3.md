# Novel-900 / Novel-1000 grammar repair batch 3

The frozen results retain the original 200 source anchors and the original
WordNet 3.0, 50k chart items, 500k k-best work, and 10-second deadline.
All 181 previously complete selected tree and graph signatures are
preserved. Completion is not full semantic certification.

| Frozen cohort | Initial complete | Batch 2 | Batch 3 |
| --- | ---: | ---: | ---: |
| Novel-900 | 84/100 | 91/100 | 100/100 |
| Novel-1000 | 76/100 | 90/100 | 99/100 |
| Combined | 160/200 | 181/200 | 199/200 |

## New selected analyses

Each of these 18 source spans has its selected root, overt endpoint spans,
and relevant edges pinned in the tests, together with an independently
worded positive and a negative control. The documentary controls require
adjacent provenance and reject the same wording in isolation.

| Source | Construction checked |
| --- | --- |
| N815 | Inverted negative coordinator, separately scoped negative attendant, and coordinated complements |
| N820 | Shared agent, literal destination and result, two gerundial means, and object control of the infinitive |
| N830 | Overt initials are a signature, attested by their repetition at the end of the following postscript |
| N837 | Emphatically hyphenated interjection, postposed reporter, separate motion and simile |
| N839 | Inverted conditional, nominal apposition, modal negation, and subject-controlled infinitive |
| N845 | Negative existential and nominal corrective ellipsis, with the two inchoative modifiers attached separately |
| N869 | Equative hypothetic simile with independently analyzed perfect passive, measure and material |
| N899 | Two overt non-overlapping negation spans, one in the fused modal and one in the negative confirmation tag |
| N900 | Temporal gerund and shared agent, independent genitive destination, locative relative and coordinated passive patients |
| N907 | Narrator-resumption heading attested by the actual following dateline, not a finite assertion |
| N918 | Shared locative preposition, two coordinated grounds and subject vs passive-agent relatives |
| N943 | Self-identification and elliptical reprise, with the historical dialect past form licensed only as the perfect complement in this construction |
| N944 | Fronted comparison set, superlative predication and separate bearer of the anxiety |
| N946 | Request plus target refinement. The following paragraph identifies Hands as the person at the gun, not an anatomical object |
| N962 | Epistemic modal embedding and honorific vocative |
| N964 | Shared agent, genitive shop ellipsis and subject intensifier, not another object |
| N974 | Elliptical punctuality location, emphatic do-support and metalinguistic insert inside a work simile |
| N1000 | Perspective frame, two coordinated relatives, controlled degree complement and stranded preposition |

## Why N952 is still an open source issue

The frozen N952 anchor ends at `custom!` even though the single quotation
continues in the paragraph. The curly mark inside `accordin’ to` is a
dialect apostrophe. It is not the end of the utterance. Do not append
a synthetic closing quote, silently replace the case, or count a tree
for the truncated fragment as a success.

In a separate local source experiment, a continuation-aware quote scanner
returned the complete, balanced 126-token interrupted quote, including
the two real quote portions around the reporter. That authentic unit lies
beyond the ladder's 32-token maximum, and the source change also changed
the inherited Novel-500 fingerprint. Therefore neither the experimental
scanner nor a replacement source has been silently substituted into these
frozen runs. A new source edition of the benchmark requires resampling and
new source/result pins, with the old and new results clearly separated.
