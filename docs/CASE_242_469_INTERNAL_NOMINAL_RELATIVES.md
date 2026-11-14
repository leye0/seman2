# Novel-500 #242 and #469 — internal nominal supplements

Base `9d41b4f05d654315823b5d699cae5d6fab8e2f9d`. The cohort SHA is
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`.
Both complete source sentences were checked against their contiguous
paragraph and both segmentation views. WordNet 3.0 and
`parse_corpus_case` use the same 50,000 forest items, 500,000 k-best work
units, 10-second deadline, and quote-balanced source preparation.

## #242 — Pride and Prejudice

> She had never heard of his having had any relations, except a father and mother, both of whom had been dead many years.

The complete sentence had roots without a valid analysis. The isolated
pre-exception clause incorrectly ranked finite lexical *had* and treated
*never heard of …* as its object. The new composition verifies finite
perfect *had*, negative *never* and lexical *heard*. Its *of* selects
the perfect gerund whose subject is *his*, auxiliary is *having*, and
lexical predicate is participial *had*. Its object is plural *any relations*.

*Except* introduces the coordinated pair, not a verbal exception to
*heard*. *Both of whom* is the plural subject of *had been dead* and
uses the pair as the whole in its partitive phrase. *Many years*
modifies the state.

## #469 — Treasure Island

> I remember the appearance of his coat, which he patched himself upstairs in his room, and which, before the end, was nothing but patches.

There was no structural root. In isolation the canonical grammar put
*of his coat* on *remember* instead of *appearance*. The selected
composition makes the whole outer nominal the direct object and attaches
both coordinated relatives to the inner *coat*. The first *which* fills
the object of *patched*. *Himself* emphasizes *he*, and both locative
phrases remain within that relative. The second *which* is the subject
of *was*. Its temporal incise stays inside the second relative and
*patches* is the exclusive predicative complement.

## Shared rule and validation

Both constructions use the same typed nominal supplement binder.
It exports the appropriate argument of the relative rather than
flattening all supplements onto the highest noun. Source spans are
scoped and backed by lexical readings or independently selected phrase
proofs. The lexical lattice, segmentation and parser budgets are unchanged.
The two scoped constructions are not a general relative-clause resolver.

Tests assert rank-one spans and exact semantic attachments, including
forbidden misattachments. Independent examples vary the nominal, verbs,
and supplements. Contrasts exercise pair cardinality, human antecedent,
transitivity, participial form, object-gap filling, reflexive matching,
copular agreement and the temporal-incise delimiters.

[PR #67](https://github.com/leye0/seman2/pull/67) changes Novel-500 from
470 to 472 on the same cohort. The 470 prior
rank-one trees and all 30 historical dialogues are preserved. See
[the cohort record](CURRENT_COHORT.json) for the official comparison.

#110 remains unresolved. The official runner reached the same k-best cap
before the wall-clock cutoff on the candidate. A paired isolated replay
without the wall-clock cutoff reached exactly 500,001 work units on both
versions without activating the new source plan.
