# Structural snap: preserve grammatical feature variables

Research branch: `research/verbnet-left-to-right-poc` only. Production `main` unchanged.

## Confirmed failure

The canonical `VectorGrammar` chart propagates contextual RHS grammar constraints
to each child. A locally underspecified lexical reading can legitimately carry
a variable such as `gender=?g`, `person=?p` or `tense=?t` from a parent
symbol. The old `FullStructureSnapIndex.match` rebuilt a tree with
`PredictiveParser._reduce` bottom-up. This verified licenses, but exposed
the original lexical features without merging inherited grammar constraints.
Consequently, rule topology and syntax were identical while a variable on
a descendant silently disappeared.

## Changes

- `full_structure_snap.py`: before publishing a reconstructed tree, replay
  contextual RHS constraints **top-down** with Seman2's original
  `unify` and `substitute_structure`.
- Project each inherited environment to the variables reachable from that
  child interface, using the **same `_project_bindings`** logic as the native
  vector materializer. Without projection, independently scoped `?p` or
  `?g` variables can collide across unrelated local productions and
  introduce fake resolved values.
- Validate **every bounded lexical realization** of a remembered rule
  topology, not just the first one. The first locally viable leaf
  combination might fail a higher parent constraint even when a later
  combination succeeds.
- Preserve explicit search budgets; an incomplete match is still
  `incomplete=True`, and is not a proof of ungrammaticality.
- No saved text or cached `ParseResult` is used to reconstruct a snap.

## Validated

[GitHub Actions: Snap Tree Fidelity Diagnosis, SUCCESS #39056315212](https://github.com/leye0/seman2/actions/runs/39056315212).

- **17/17 unit regressions pass** (existing snapping tests plus feature
  propagation, nested variable and incompatible gender rejection).
- **300** deterministic Gutenberg sentences sampled from the 12 training
  classics, 4–32 tokens; run with the real canonical vector grammar
  and a per-sentence bounded parser.
- **126** of those complete vector trees were admitted to the whole-tree
  structural index.
- **126/126** originals were recovered on the exact identical input:
  category/rule/span topology **126/126**,
  selected lexical readings **126/126**,
  full recursive `features.as_dict()` **126/126**,
  and `syntax.as_dict()` **126/126**.
- `--strict` makes any missing stored pattern or any topological/lexical/
  feature/syntax difference fail the CI job. This catches regression
  rather than just printing differences.

These are **parity with the canonical parser on the same input**, not
independently human-annotated grammatical correctness or proof of
generalization to new texts. This change does not claim a runtime speedup
or change the canonical grammar. The broader long-run caching benchmarks
must be remeasured if quoting speed after this reconstruction change.
