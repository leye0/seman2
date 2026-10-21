# Source context versus isolated-unit parse failures — 21 October 2026

## Method and scope

The [500-case context audit](https://github.com/leye0/seman2/actions/runs/39688153491)
reconstructs the **original, unsplit Gutenberg sentence** and source-local
neighbors from the four cleaned books, using the same extraction routines
and checked-in corpus. It proves each source span is aligned with the fixed
500-case SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.

This is an **investigative review, not gold-standard linguistic labels**:
observing a previous sentence or a semicolon does not prove syntactic
dependence. The original recognizer continues to use `Parser.parse()`,
without changing grammar, lexical categories, ranks or parsing budgets.

The official diagnostic for this run reports **452 completions, 40 conclusive
recognition/unification failures and 8 inconclusive resource-limited cases**.
A separately configured left-corner experiment recognizes 455/500; the
two evaluation configurations must not be mixed when reporting failures.

| Source-continuity fact | Complete | Conclusive failure | Resource-censored |
|---|---:|---:|---:|
| Any part from a semicolon-split sentence | 153 | 15 | 5 |
| Part with a preceding part from the **same** original sentence | 86 | 9 | 4 |
| Initial coordinator followed immediately by a comma | 1 | 2 | 0 |
| Initial relative pronoun `which/whom/whose` | 0 | 1 | 0 |
| Surface ending in `-ing` at the beginning | 1 | 2 | 0 |

These are overlapping groups; do not sum their counts. In particular,
**86 successful parses** followed a semicolon in their original sentence.
Therefore semicolon origin is emphatically **not** a sufficient fragment
classification.

## Source-verified contrasts for manual review

The following is a deliberately small set of **examples**, each grounded
in the complete source sentence from `context_dependency.jsonl`.
These examples explain a plausible failure mechanism but do not alter the
500-case status or the benchmark denominator.

| Case index | Source context | Research assessment |
|---|---|---|
| 8 | `…make Mr. Micawber known to Uriah Heep and his mother; which I accordingly did.` | The isolated relative `which` refers to the preceding action; independent finite-clause analysis is not expected |
| 94 | `She gently chid me for being rude; and, keeping me close to her shawl, turned to thank…` | The second predicate shares an overt subject from before the semicolon; the isolated segment does not express that subject |
| 182 | `He found her as handsome as she had been last year; as good natured, and as unaffected…` | The right-hand adjective comparisons depend on the shared `found her` predication |
| 194 | `To the rest of the family they paid little attention; avoiding Mrs. Bennet…` | The right-hand participial supplement is not an independently finite matrix |
| 115 | `…; and Dora was to write to Agnes …, and Agnes was to write to Dora; …` | **Real finite clause** with overt subjects and infinitival complements; its source continuity does not excuse the parse failure |
| 196 | `Mr. Darcy is impatient to see his sister; and, to confess the truth, we are scarcely less eager to meet her again.` | **Real finite matrix** `we are`; likely gaps concern the comma-delimited infinitival aside and adjective–infinitive control, not missing discourse context |
| 244 | `…was a severe disappointment; and, besides, it was such a pity…` | A **successful control** for `COORD, ADV,` before an overt finite matrix |
| 427 | `Foraging about, I found a bottle with some brandy left, for Hands; …` | **Real finite clause** `I found`; the participial opener does not justify dismissing the parser failure |
| 434 | `Tall tree, Spy-glass shoulder, bearing a point to the N. of N.N.E. Skeleton Island E.S.E. and by E. Ten feet.` | Navigational notation, not ordinary declarative prose; record the register rather than inventing a full English finite clause |

**Confirmed observational fact**: original source neighbors and semicolon
boundaries. **Grammatical interpretations above**: manually inspected,
contestable research assessments, not automatic labels or external
expert gold annotations.

## Consequences for the next grammar study

1. Do **not** raise the headline coverage by subtracting any source-dependent
   fragments. Count the same 500 cases as before.
2. Test overt finite discourse clauses (#115 and #196) against the successful
   comma-adverb aside (#244), with unchanged lexical lattices.
3. Study participial VP/NP attachment on #427 and successful sentences,
   preserving participial and finite WordNet alternatives.
4. Keep context-aware discourse composition **separate** from the goal
   `CLAUSE` recognizer until the relevant utterance/fragment interfaces
   have explicit syntactic and semantic tests.

Generated source evidence lives in `context_dependency.jsonl` and
`context_summary.json` in the workflow artifact.
