# Annotated syntax quality: 120/120 — 26 October 2026

Base commit: `65a9452046e92e2a81ffbbf0ee853adeb69bd847`.
All measurements below are local, not a claim about GitHub Actions.

## What was wrong

Two annotated linking predicates exported the surface **seems** as their lemma.
The lexical paradigm now exports **seem** and preserves the existing WordNet
readings. The existing surface-based agreement projection also recognizes
third-person singular **seems** once the lemma is canonical.

Closer inspection of the other three trees found conflated seed entries:
**can** could be exported as *will* or *could*, **might** as *will* or *should*,
and **which** as the person-denoting *who*. The modal entries now distinguish
unrelated lexemes, and **which/what** keep their nominal/pronoun categories
with their own referential lexical identities. Open-class homographs remain.
No grammar score, recognition algorithm or search budget changes.

## Why three annotations changed

The modal trees already used the correct `MODAL + VP-NP` structure through
`vp_modal_bare`, but d013 and v013 demanded the older duplicate rule ID
`vp_modal`. The embedded question in v047 already grouped **which route** as
`WH-NOM`; its lexical **which** used `WH-PRONOUN`, which the old annotation
incorrectly treated as a phrase-category failure.

These three assertions are replaced, not simply deleted. The new declarative
`structures` assertions check immediate children in order, complete subject
and object spans, finite modality, bare verb morphology, canonical lexical
identities, matrix complement boundaries and the embedded object gap. Lexical
**which** may use either existing WH category, while its whole nominal phrase
must remain `WH-NOM`. All 120 sentence texts, IDs and split assignments are
unchanged. Other existing rule and POS assertions remain exact.

The matcher is tested against swapped roles, detached objects, wrong modal
lemmas and finite verbs substituted for bare predicates. Renaming a production
alone does not change the structural result. Unknown assertion fields raise
an error rather than silently weakening validation.

## Comparable scores

| Parser | Original v1 annotations | Revised structural annotations |
|---|---:|---:|
| Published baseline 65a9452 | 115/120 | 115/120 |
| Corrected lexical data | 117/120 | **120/120** |

The annotation update alone does **not** raise the baseline score: it exposes
the wrong modal and WH lexical identities in the previously accepted trees.
Do not report the final 120 as a score on the unchanged v1 assertions. The
remaining three v1 failures are exactly the obsolete rule/category demands.
The new contract is `syntax-correctness-v2-ordered-subtrees` and both annotation
file hashes are retained in the validation JSON.

## Regression checks

- 453 tests, the same 7 expected failures, no unexpected failures.
- 120/120 annotated cases complete; 120/120 satisfy the revised assertions.
- 24/24 grammatical contrasts; the same 9/24 existing negative acceptances.
- The complete pinned 500-case run still uses `parse_corpus_case`, quote
  provenance, 50,000 forest items, 500,000 k-best work units and a 10-second
  per-case deadline. Per-case results are recorded in the validation JSON.
- The global gate now requires all 120 annotations and all 24 contrasts,
  and permits no increase above the existing 9 negative acceptances.

See `quality-120-validation.json` for the comparison and corpus measurements,
and `quality-120-selected-trees.txt` for the five selected trees. The prior
#99, #215 and #356 attachment tests remain in the full suite. This is coverage
of the declared annotations, not a full gold-tree certification of all 120
sentences or of the 500-case novel cohort.
