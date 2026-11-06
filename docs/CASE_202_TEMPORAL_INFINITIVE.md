# Case 202: infinitival subject with a temporal incise

> To persuade him against returning into Hertfordshire, when that conviction had been given, was scarcely the work of a moment.

Baseline: `main` at `8f6b31870b8ffea498379586b5c90b121cdc9589`.
The quote-balanced Austen case had a structural dialogue root, but no valid
materialized grammatical analysis. The published 500-case result was 467/500.

The recovered selected tree retains four distinct relationships:

1. **Infinitival subject:** *To persuade him against returning into Hertfordshire*
   functions as the subject of the finite predicate *was ...*.
2. **Object and gerund complement:** *him* is the object of *persuade*;
   *against* heads a PP containing the nominal gerund *returning into
   Hertfordshire*. The directional PP *into Hertfordshire* modifies *returning*,
   not *him* or the matrix copula.
3. **Temporal incise:** *when that conviction had been given* is a complete
   finite passive subordinate clause between two literal commas.
4. **Nominal copular predicate:** *was scarcely the work of a moment* has a
   finite copula, a licensed scope adverb, and a complete nominal predicate
   containing *of a moment*.

The construction is compositional. `against` has a genuine closed-class
preposition entry. `np_intransitive_gerund_pp` requires positively attested
`ing` morphology and intransitive valency. `vp_cop_adv_np_scoped` requires
an explicitly licensed nominal-scope adverb (currently *scarcely* and *hardly*)
and has lower precedence than complete adjective/comparative analyses. This
preserves *scarcely less eager to meet her* as an adjective phrase.

The seven-part `clause_infinitive_subject_temporal_incise` rule requires the
two commas, a lexical temporal conjunction, an independently complete finite
subordinate clause, and a finite matrix VP. A contextually licensed
`TO-TEMPORAL-SUBJECT` start category opens this rule only where a following
comma-delimited temporal marker is actually in the lexical lattice. The
`V-INTRANSITIVE-ING` view likewise avoids opening gerund searches at unrelated
verbs. Both are copies of existing lexical candidates: original categories,
all alternatives, offsets, features, sense IDs and sources remain available.
The views **do not validate** a clause by themselves; unification still must
accept the full grammar. These bounded lexical starts also preserve the
previously saturated case 359 under the unchanged forest limit.

Positive and negative regression tests certify actual selected-tree spans,
the original WordNet evidence, valid independent gerund+PP examples, incorrect
verb forms, unlicensed nominal-scope adverbs, missing incise commas, and
*whether* in place of a temporal *when*.

## Verified comparison

- Same SHA-pinned 500-case corpus (SHA-256
  `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`),
  same quote-balanced `parse_corpus_case` gateway, and identical WordNet 3.0.
- **467/500 → 468/500.** Exactly one status changes: case 202,
  `roots_without_valid_analysis` → `complete`. No previous completed case is lost.
- Case 312 remains the same pre-existing timeout in both full passes; four
  forest-budget failures remain in both passes. No search budget was raised:
  50,000 forest items, 500,000 k-best work units, 10 seconds per case.
- **464 unit tests pass**, zero errors and zero expected failures.
- Direct quality remains **120/120** selected structural annotations,
  **24/24** grammatical contrasts, with the same **nine** known negative
  acceptances; canonical, optional lazy-trie and dialogue smoke all pass.

Evidence: [selected tree](case-202-selected-tree.txt),
[validation report](case-202-validation.json). These results certify this
specific tree and the fixed validation sets, not universal grammatical
correctness of all 468 completed sentences.
