# Preserve quoted statement and question boundaries

The first repair from [Novel Transfer 24](https://github.com/leye0/seman2/pull/91) targets T45-0545 in Gutenberg #45. Its exact source unit is in paragraph 305 of the pinned narrative body, at offsets 89377–89479. Source preanalysis already gives three distinct spoken spans in one balanced quotation. The old selected tree instead treated the second sentence's period like an appositive comma and made the final question part of the preceding predicate nominal.

The new scoped assembly uses the original spans and punctuation. Its rank-one tree has three separate speech acts:

1. A finite assertion with emphatic `do`. `So` introduces the assertion, `then` is an adverb associated with it, and the comma introduces the conventional stance supplement.
2. A negated copular assertion. The subject is `You`; `quite a heathen` is a predicative nominal with `heathen` as noun. The negation applies to the assertion.
3. A wh-adjunct question with its own subject, finite `did`, bare `learn` and demonstrative direct object. The question is not an apposition or a syntactic dependent of the previous utterance.

Only one original, unattributed, unnested quotation with one or two typed statement spans and a final do-supported wh-adjunct question is eligible. First scope uses a pronominal subject. Real terminal marks are required, agreement is checked, and phrase proofs plus assembly share the existing item and extraction limits. Failed proof leaves the original full-dialogue route. The new rules do not enter the unrestricted grammar or the existing finite-only quote assembler. Imperative-plus-salutation and attributed/split sequences are outside this repair.

## Validation

- Compared 500 rank-one serialized tree hashes, source identities, statuses and both saturation flags before and after with WordNet 3.0, 50,000 forest items, 500,000 k-best work units, and the 10-second per-case deadline. All 500 rows match on the pinned cohort, including all 30 historical dialogues. There are 16 forest flags and no k-best flags on either side. Both ordered snapshot files have SHA-256 `5a0a5b189ba1fb0f65e1da26eee423b2fe5b818ba8b57e91d98f7fcfee149a07`.
- Replayed the 24-case transfer sample at its original hash. Only the selected T45-0545 tree changes. The 23/24 completion count and per-case saturation flags are unchanged. This is a repair on an observed diagnostic case, not a new held-out score.
- Focused controls cover one and two preceding statements, an abbreviation inside a statement, inverted do agreement, past morphology after do, negative nominal predication, a lexical stance-formula variant, missing question marks, subordinate fragments, nested and split quotations, and a small work budget. The attested case also asserts the selected speech, negation, predication and question links.
