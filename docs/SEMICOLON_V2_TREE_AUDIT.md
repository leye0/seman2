# Semicolon v2 — syntax-tree audit (research in progress)

## Contract

The source passages for original frozen indices **8, 94, 182, 194** were
checked against David Copperfield (Gutenberg 766) and Pride and Prejudice
(Gutenberg 1342). The prospective v2 segmentation now keeps each passage
in one original-source unit instead of orphaning its dependent continuation.
That does **not** mean Seman2 builds the correct selected tree.

The reproducible audit is:

```bash
WORDNET_DICT=/path/to/wordnet3/dict
PYTHONPATH=superparser python -m scripts.audit_semicolon_context \
  --wordnet-dir "$WORDNET_DICT"
```

The script uses `gutenberg_novels.extract(..., segmentation_version=2)`
then **exclusively** `corpus_pipeline.parse_corpus_case` at the normal
`max_items=50000` and `kbest_work_limit=500000` budgets. It prints
the selected tree with exact rule IDs/spans and the parent chain of the
literal semicolon. It never rewrites the 500-case benchmark.

## Local diagnostic without WordNet (not canonical)

The scratch environment lacks WordNet 3.0. We reconstructed the existing
parser code and checked the four original passages without WordNet; these
results are useful for locating failure types but **cannot** be compared
to the canonical 500-case run:

| Frozen index | v2 unit | Parse complete? | Forest nodes | Structural observation |
| --- | --- | --- | --- | --- |
| 8 | Whole sentence with `which I accordingly did` | No | 619 | No selected root |
| 94 | Whole clause with `and, keeping …, turned` | No | 1,150 | No selected root |
| 182 | Whole comparison `as handsome …; as good natured …` | No | 437 | No selected root |
| 194 | Whole clause with `avoiding …, saying …` | Yes | 1,160 | **Wrong** selected attachment: `vp_comma_coord` treats the nonfinite series as a coordinated VP instead of a participial adjunct |

As an independent minimal probe, `He promised to return; which he did.`
produces a complete tree **but attaches** `which he did` under
`np_appos_comma` as part of the nominal `return`, rather than as a
sentential relative of the preceding event. A successful recognition is
therefore not a correct analysis.

The function-word lexicon already supplies the token `;` with the
`COMMA` syntactic category. The parser sees the original punctuation; this
is not a missing-token issue.

## Required next validation

1. Re-run `scripts.audit_semicolon_context` on the reference WordNet 3.0
   installation, keeping all search budgets unchanged.
2. For each selected tree, verify its exact parent/child spans:
   - Case 8: `which` refers to the **preceding event**, not a noun.
   - Case 94: `chid` and `turned` share `She` as their subject.
   - Case 182: parallel comparatives are licensed by `found her`.
   - Case 194: `avoiding` and `saying` are nonfinite adjuncts, not two
     independently finite coordinate predicates.
3. Only after these tests, consider a **general**, typed grammatical rule
   with independent positive examples, negative controls and the saturated
   case 359. Do not promote a speculative rule based on this no-WordNet run.
4. Keep the historical 500-case cohort fixed; evaluate v2 separately
   before any proposed benchmark migration.

This remains **in progress** until the correct *rank-one* attachments and
canonical regression gates are demonstrated.
