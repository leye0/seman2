# Novel-700 / 800 — second semantic repair pass

See the [third pass](NOVEL700800_SEMANTIC_BATCH3.md) for the current count.

The starting point was `1cbeb826787c143ddf95b00ed4cefe6deba5d7ca`
([first repair pass](NOVEL700800_SEMANTIC_NEGATION_REPAIR.md)).
The second pass groups failures by construction and checks the exact selected
tree and graph, not the presence of a generated analysis.

| Cohort | Complete selected outputs | Verified before → after | Still open |
| --- | ---: | ---: | ---: |
| Novel-700 | 100 | 28 → 42 | 58 |
| Exploratory Novel-800 | 100 | 16 → 30 | 70 |
| Total | 200 | **44 → 72** | **128** |

## Twenty-eight newly verified analyses

| Family | Cases | Evidence on the selected output |
| --- | --- | --- |
| Selected complement roles | N602, N604, N628, N712, N729, N786 | Medium vs recipient, stimulus vs experiencer, topic vs information content, manner vs destination, and the addressee vs reason for gratitude. N786's three predicates share the overt subject. |
| Question and relative scope | N605, N608, N653, N778 | Lexical-verb attachment in do-support, separate matrix and relative modals, modal passive patient, and locative copular question. N608 now links the relative pronoun to its antecedent and keeps negation local to think. |
| Copular attributes, aspect and degree | N606, N651, N676, N677, N726, N753, N754, N776, N779, N780 | Non-agentive predicands, temporal rather than manner links, two coordinated properties, present possession with has got, passive participle as head, adjectival content, and degree or duration modification. |
| Negation and minor utterances | N626, N629, N678, N679, N703, N727, N734, N777 | Overt negative and affirmative replies, the negative minimizer, example list, negative quantifier, literary apostrophe, and adjectival quotation with genuine reporter and optional instrumental depictive. |

There are three distinct changes. First, semantic recipes now reference the
correct selected lexical node or explicit child export, even when an auxiliary
would otherwise default to the head. Second, role choices can depend on a
selected rule path or an attested lexical lemma or inflection. This separates
genuine recipients from goals, grounds and media without looking up corpus IDs.
Third, where syntax itself was wrong, source-span plans require existing
lexical evidence or a ranked constituent and assemble a declarative grammar
tree. They preserve source punctuation and do not insert missing words,
subjects or antecedents. Narrow construction coverage is not a claim of
general disambiguation where the source evidence is absent.

## Other changed outputs

- **N625** was already verified. The existential now also records the
  negative quantifier on comfort.
- **N648** was already verified. Reinspection found groping selected as an
  adjective inside a nominal, despite the source's progressive. The actual
  selected clause now proves the finite auxiliary, verbal participle,
  floating quantifier and direction, and links the speaker to the
  simultaneous leaving. Its previous structural relationships were rechecked.
- **Twenty** previously blocked analyses changed without being promoted.
  These are N620, N621, N644, N650, N657, N664, N675, N689, N690, N710,
  N711, N722, N733, N739, N745, N746, N761, N764, N765 and N783.
  For example, N733 now has a comparison standard and no partitive self-loop,
  but its degree and ordinal still have no semantic roles, and its copular
  subject is still mislabeled. N761 has its perfect auxiliary, but the first
  utterance remains conflated with the second. Each residual problem is
  recorded against the new selected signature in the defect ledger.

## Verification

- The targeted test matrix revisits all 28 source cases through
  `parse_corpus_case`, with independent positives and contrasting examples.
  Tests check the necessary selected rules, source spans and graph edges.
  N648 has additional source, independent and negative controls.
- Novel-500 retains the frozen rank-one syntax/status/budget fingerprint,
  including all 30 anchored dialogue cases. Novel-600 preserves its complete
  accepted tree/graph signatures and budget flags.
- The same WordNet 3.0, source cohorts and limits were used throughout
  (50k chart items, 500k k-best work, 10 seconds per sentence). Novel-700/800
  retain all 200 completion statuses and budget flags.
- Of the 50 changed outputs in Novel-700/800, 28 were promoted, two prior
  verdicts were revalidated and 20 remain blocked. The automatic report
  flags 14 cases, down from 17. That count is an automated diagnostic,
  not a substitute for the 128 individual open verdicts.
- The Layer 1 smoke passes. Direct grammar quality remains 120/120 on
  annotated positives and 24/24 on their grammatical contrasts, with the
  same nine known false accepts among the 24 negative controls.

The acceptance gate stays closed. Remaining high-impact families include
perfect and modal chains whose lexical head is still wrongly selected,
intercalated speech with false nominal attachments, and noun/verb
ambiguity in relative and coordinated clauses.
