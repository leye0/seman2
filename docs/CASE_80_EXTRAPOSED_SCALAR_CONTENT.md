# Novel-500 #80 — extraposed infinitive and two scalar viewpoints

Source (David Copperfield, case `766:57dba5c2e4bb4629`):

> It was difficult to believe that a night so long to me, could be short to anybody else.

## Source and diagnosis

PR #77 head `dece7b6d6614208e37e48304d311b9ef8e45c0c2` is the grammar baseline (487/500).
The complete sentence occupies offsets 0–87 of normalized source paragraph
4005. The next sentence starts “This consideration set me thinking”.
The historical subject pause is internal to the that-clause and is not a
segmentation boundary. The baseline returns roots without a valid analysis.
Removing the comma for diagnosis alone did not recover the intended tree:
the canonical parse read `long` as an adverb, misinherited first person on
the subject, and took `short` and `else` as nouns. On their own, the
anticipatory copular matrix with clausal infinitive and the pronoun
`anybody else` were also unsupported by the baseline.

## Selected tree

- `It` is anticipatory, not referential and not the agent of `believe`.
  `Difficult` is the matrix attribute and the entire `to believe …`
  clause is the extraposed subject. There is no infinitival object gap.
- `Believe` selects the finite `that` content (28–86). Its subject
  is `a night so long to me` (33–54), third-person singular. The integrated
  AP modifies `night`. `So` grades `long` and `to me` supplies the viewpoint
  of `long`. The original comma (54–55) remains between subject and VP.
- `Could` selects base `be` and `short` is its predicative adjective.
  The other viewpoint, `to anybody else`, belongs to `short` alone.
  `Else` postmodifies the indefinite pronoun `anybody`.

The source planner only proposes spans. Composition requires attested
anticipatory it, the lexical adjective frame, a base verb with clausal
valency, a canonically proven nominal, the overt scalar degree marker,
two adjective viewpoint phrases, and a finite modal with base be. The
comma is optional in this construction and preserved when present. The
public lattice and unscoped grammar retain their previous alternatives.
The route is deliberately bounded to these overt frames and does not
license arbitrary commas between any subject and verb.

## Validation

The four focused tests check the selected source tree, semantic edges and
forbidden crossed attachments, a plural independent example with and without
the pause, and nine negatives for agreement, case, valency and punctuation.
The local paired pass preserves the corpus text and SHA
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`,
WordNet 3.0, the public `parse_corpus_case` gateway and the 50k/500k/10s
budgets. Coverage rises from 487 to 488. Only #80 changes status, all 487
earlier rank-one trees match, neither per-case saturation flag changes,
and the pre-existing #110 timeout stays visible.
