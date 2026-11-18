# Novel-900 / Novel-1000 grammar repair batch 1

The original source IDs and the initial measurements are unchanged. This
batch keeps reusable constructions, with exact-source tree and graph
checks, independent positives and rejected near misses. Completion is
not full semantic certification. No case is promoted or marked verified
by the acceptance process as a side effect of the new controls.

| Cohort | Initially complete | Current complete | Still incomplete |
| --- | ---: | ---: | ---: |
| N801–N900 | 84 | 89 | 11 |
| N901–N1000 | 76 | 86 | 14 |
| Total | 160 | 175 | 25 |

## Corrected constructions and witnesses

The primary and independent graph assertions and negative contrasts are
in `superparser/tests/test_novel1000_grammar_repairs.py`. Each corpus replay
uses WordNet 3.0 via the canonical source gateway with unchanged 50k chart,
500k k-best and 10-second limits.

| Case | Selected construction and attachment tested |
| --- | --- |
| N813 | Reported copular question with separately proven subject, predicative adjective, vocative and reporter |
| N814 | Intercalated reporter, quotation resumption, modal passive patient and purpose infinitive |
| N827 | Elliptical temporal comparison between two overt past participles, not a fabricated finite clause |
| N872 | One quote with three independently proved finite clauses and a final elliptical locative nominal |
| N885 | Supplementary state predicated of the subject, with the *by* phrase attached to the state |
| N911 | Infinitival complement to the attitude adjective, controlled subject and separate motion goal |
| N937 | Shared agent across coordinated predicates with two predicative states, including an *-ing* predicate |
| N950 | Three parallel predicates with one shared agent, a locative relative, and two depictives whose subject is internal to the relative |
| N960 | Elliptical gerund question with an overt patient and adjacent quotative tag |
| N965 | Imperative object control, reporting manner and elliptical modal conditional scoped to the request |
| N970 | Shared perception with negative coordination across a place and a time circumstance |
| N984 | Interrupted predication with subject, stance parenthesis, result theme and recipient distinguished |
| N990 | Contrast across a semicolon, separate passive patient and near-negative frequency adjunct |
| N992 | Intercalated report in a single copular predication with coordinated nominals and separate adjective modifiers |
| N996 | Distinct source spans for the two negations, gerund talk recipient, and a separate perfect wish complement |

Each assembler candidate must account for all source characters. Dialogue
plans require the actual quote spans and, when applicable, the reporting and
split-turn provenance. Lexical roles and nested phrases are independently
proved in the existing parser. The new paths do not switch the corpus to a
different grammar engine and do not edit punctuation. Composition plans
are bounded by construction rather than keyed by case ID or sentence hash.

## Remaining work

- **N900**: N815, N820, N830, N837, N839, N845, N869, N890, N898, N899, N900.
- **N1000**: N907, N918, N919, N943, N944, N946, N952, N961, N962, N964,
  N974, N981, N993, N1000.

N830 is the signature at the end of a letter annex in *Treasure Island*,
and N907 is a narrator-resumption heading before a date in *Frankenstein*.
Both need explicit documentary provenance rather than an ordinary finite
sentence. At N952, the contiguous *David Copperfield* paragraph shows that
the apostrophe in the elided `accordin’` belongs to the word and the speech
continues past `custom!`. The current extraction treats that apostrophe as
closing speech. It is left visible as an unresolved source defect. Repair
the source boundary separately, with a measured change in cohort identity
if it affects membership. Do not invent a closing quote or treat the
truncated segment as a successful grammatical correction.

An earlier experimental run measured 185 complete trees, but several
new roots depended on narrow wording or did not withstand scrutiny of
the selected attachments. That patch is not the candidate measurement.
