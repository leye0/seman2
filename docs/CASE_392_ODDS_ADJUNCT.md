# Case 392: numeric odds adjunct

`"Ten to one this is a trick."`

The former erroneous analysis absorbed *this* into a nominal ending in a
postposed determiner. After that loophole was closed, this grammatical passage
had no valid analysis. The missing construction is an initial probability
adjunct, not a nominal subject.

The selected tree now separates:

- `Ten to one`: `ODDS-ADVERBIAL`, composed of NUM + TO + NUM;
- `this`: subject of the independent proposition;
- `is a trick`: copular predicate, with `a trick` as its nominal complement.

Three declarative productions form the numeric ratio and attach it before a
clause, with or without a literal comma. There is no sentence-specific lexical
entry, token rewrite, restored postposed-determiner loophole, or score change to
existing productions. The construction generalizes to *Two to one Mary wins*
and *Five to two, John is right*. Tests reject malformed ratios in the odds goal
and require an actual clause after the adjunct.

Validation: **457 tests pass, zero expected failures**; **120/120** structural
annotations and **24/24** grammatical contrasts remain, with the same nine known
negative acceptances. Canonical completion rises from **465/500 to 466/500**.
Case 392 is the only per-case status change. Completion remains distinct from
whole-tree quality; the target has explicit constituent/span assertions.

The pinned novel case uses `parse_corpus_case` with balanced quotation provenance.
Budgets remain 50,000 forest items, 500,000 k-best work units, and the canonical
10-second deadline. Cohort SHA-256:
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.

See `case-392-validation.json` and `case-392-selected-tree.txt` for the measured
comparison and selected tree.
