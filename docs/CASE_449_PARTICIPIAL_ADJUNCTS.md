# Case 449: negative minimizer and modified participial supplement

> but the murderer minded him not a whit, cleansing his blood-stained knife the while upon a wisp of grass.

Baseline main: `be81955524e12e851dd083baa95fe671b2ec7c5f`.
The sentence had no valid analysis after the invalid postposed-determiner
loophole was closed. Adding the temporal idiom alone did not recover it:
the final transitive participial construction could not take its own modifiers.

The corrected selected tree retains these distinct attachments:

- *him* is the object of *minded*;
- *not a whit* is a negative degree adjunct to *minded him*, with explicit
  negation propagated through the existing VP/adverb rule;
- *cleansing his blood-stained knife* is a transitive present-participial
  supplement to the matrix clause, with *his blood-stained knife* as object;
- *the while* is a temporal adverbial modifying that participial predicate;
- *upon a wisp of grass* is a further adjunct to the participial predicate,
  retaining *of grass* inside the *wisp* nominal.

The final participial construction is factored through a typed constituent
that can take postposed adverbs and prepositional adjuncts. Only positively
attested transitive present participles receive its lexical start category;
original V candidates, senses, features, source, and spans remain intact.
An initially unrestricted V start exhausted the unchanged budget on case 359;
the typed view eliminates those irrelevant searches. No budget was increased.
The extra intermediate constituent has score 2, exactly offsetting the parser
rule cost of 2; this preserves the pre-existing simple supplement ranking,
including *Maya crossed the square, carrying a lantern*.

The two literary expressions have lexical adverbial entries while their
component readings remain available. The independent example *He left, wiping
his hands slowly on a cloth* exposed an existing incorrect reading of *slowly*
as a spatial preposition modifier. Its lexical adverb entry now excludes that
use, preserving attachment to *wiping*. This does not claim every ambiguous
use of *the while* is correctly ranked in every context.

Four regression tests certify the target's actual spans and construction,
the independent example, rejection of finite/base/intransitive substitutes,
and the typed view's preservation of lexical evidence. The ordinary nominal
reading in *a while* remains available. No acceptance annotation was changed.

The target uses `parse_corpus_case` and the balanced quotation/provenance
contract. Canonical budgets stay at 50,000 forest items, 500,000 k-best work
units, and a 10-second deadline. Cohort SHA-256:
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.

Selected tree: `case-449-selected-tree.txt`.

Validation: **461 tests pass, zero failures or expected failures**. The unchanged
quality contract remains **120/120** with **24/24** grammatical contrasts and
the same nine known negative acceptances. Canonical completion rises from
**466/500 to 467/500**; case 449 is the only per-case status change. Full
comparison and target diagnostics: `case-449-validation.json`.
