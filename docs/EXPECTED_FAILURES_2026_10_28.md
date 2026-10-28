# Seven expected failures converted to ordinary regression tests

Baseline: main `3a74c4032ad05c96ecb4403171adf46358587e16`.

All seven tests are retained, with their expected-failure decorators removed.
The two novel tests now use pinned cases 248 and 485 through `parse_corpus_case`,
with the unchanged balanced quotation/provenance contract and search budgets.
Their assertions require the correct subject/object spans and actual verb-particle
children, in addition to rejecting the formerly selected bad analyses.

## Changes

- Postposed determiners require positive `position=post` evidence. Unspecified
  determiners such as *the* can no longer follow a nominal. This fixes both
  imperative homograph tests without removing the noun senses of *open* or *box*.
- Tough predicates require a licensed adjective and a genuine transitive object
  gap. *Easy to read* retains this structure; *green to believe* does not obtain
  a tough analysis. This is a construction-level assertion, not a claim that all
  other analyses of that artificial sentence are appropriate.
- The existing lexically licensed adjective/infinitive rule is preferred over
  a spurious prepositional reading of *to* plus a noun homograph. *Ready to leave* now contains a verbal infinitive,
  rather than merely avoiding tough movement by reading *leave* as a noun.
- Object topicalization factors the modal/object-gap suffix, including an
  intervening adverb. The nominal head requires positive third-person evidence;
  an ambiguous bare demonstrative cannot steal a complementizer. Factoring avoids
  duplicating the costly NP-NP prefix and preserves the budget-sensitive case 359.
- Consumptive *drink* forms license the existing verb-particle construction.
  Case 485 selects *drank up* rather than a second imperative headed by *up*.
- Declarative countability metadata refines WordNet noun senses without replacing
  them. The bare-nominal restriction follows the head through nominal modifiers.
  *Heavy gale* and *severe blizzard* fail as bare NP arguments; determined forms,
  plurals, and mass *heavy snow* remain accepted. This is a limited initial lexical
  inventory, not comprehensive English countability coverage.

## Validation and explicitly retained debt

The full 24-module core suite passes **454 tests, zero failures and zero expected
failures** (112.568 seconds). The previous suite had 453 tests and seven expected
failures; the additional test certifies a positive tough-construction object gap.

The unchanged quality contract passes 120/120 annotations and 24/24 grammatical
contrasts, with the same nine known negative acceptances. No annotation was edited.
The canonical corpus uses 50,000 forest items, 500,000 k-best work units and a
10-second per-case deadline; the cohort SHA-256 remains
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.

Canonical completion decreases from **472/500 to 465/500**. The seven status
changes are 109, 202, 233, 354, 371, 392 and 449. Every previous selected tree
used an invalid postposed determiner (e.g. *in the*, *be the*, or
*his blood-stained knife the*). The before/after trees are retained for inspection.
These grammatical passages need correct constructions in future work; their
incorrect former roots are not restored merely to protect a completion score.
All other per-case statuses are unchanged, including the pre-existing timeout.
A controlled ablation removing only the two new postposed-determiner guards
restores completion on all seven cases, confirming the source of the change.

Zero expected failures does **not** mean every selected corpus tree is correct.
In particular, the other attachments in case 485 are outside the narrow
verb-particle assertion. The selected-tree artifact makes those limits visible.

Artifacts: `expected-failures-validation.json`,
`expected-failures-selected-trees.txt`, and
`expected-failures-coverage-before-after.txt`.
