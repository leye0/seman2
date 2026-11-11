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

For a compact machine-readable table of all four cases, add
`--summary-only`. The optional `attachment_warnings` field marks only
**known suspicious structures** on the selected semicolon path:

- `semicolon_scoped_inside_nominal_constituent`: a nominal constituent
  spans the semicolon where the source requires a clause-level relation.
- `semicolon_consumed_by_nominal_apposition`: `np_appos_comma` used the
  semicolon as if it were its literal comma.
- `semicolon_consumed_by_comma_vp_coordination`: `vp_comma_coord` or
  `vp_comma_list` absorbed a clause-level semicolon.
- `no_selected_root` / `semicolon_missing_from_selected_tree`: the
  selected result cannot provide evidence of a correct attachment.

No warnings means *not yet disproven*, **not** grammatically certified.
The positive and negative detectors have independent structural tests in
`superparser/tests/test_semicolon_attachment_audit.py`.
`diagnostic_status` therefore distinguishes `no_complete_tree`,
`resource_censored_tree`, `structurally_suspect_tree` and
`uncertified_complete_tree`; **none** means an accepted grammatical parse.

The focused workflow
`.github/workflows/semicolon-v2-tree-audit.yml` downloads the **reference
WordNet 3.0** and saves both the four compact JSONL summaries and their
**full selected trees with source spans** as a GitHub Actions artifact.
It checks source preservation, real lexical loading, stable
budgets and the diagnostics themselves; it does **not** promote a v2 parse
count to a score for the historical cohort.

## Reference WordNet 3.0 run (2026-11-10)

[Focused workflow run 42942103118](https://github.com/leye0/seman2/actions/runs/42942103118)
completed successfully and saved the four source-preserving JSONL records.
This is the first directly comparable **v2 diagnostic with reference WordNet**;
it remains a different segmentation cohort from the frozen v1 benchmark.

| Frozen index | Complete root | Forest nodes | Partial states | Budget exceeded | Critical finding |
| --- | --- | ---: | ---: | --- | --- |
| 8 | Yes | 581 | 20,296 | No | `semicolon_consumed_by_nominal_apposition`: a false attachment despite a complete root |
| 94 | No | 1,234 | 38,813 | No | No rank-one tree to validate |
| 182 | No | 770 | 28,066 | No | No rank-one tree to validate |
| 194 | Yes | 1,430 | 48,570 | **Yes** | Candidate root is resource-censored; no-warning output is *not* an approval of its attachment |

Thus **zero of the four source units is yet certified as structurally
correct**. The runner's success certifies reproducibility of the audit,
not grammatical success. A useful next diagnostic for 194 must inspect the
full selected tree and alternatives, with resource-censoring kept explicit.

## Full selected-tree paths with reference WordNet (2026-11-10)

The [second focused run 42942515283](https://github.com/leye0/seman2/actions/runs/42942515283)
saved the **full selected trees** and passed eight independent detector
tests. Its path from the top-level root to the literal semicolon exposed
two distinct errors:

- **Case 8:** `CLAUSE clause_comma` → `CLAUSE clause_front_pp` →
  `CLAUSE clause_front_pp_nocomma` → `CLAUSE clause_np_vp` →
  `VP vp_pp` → `PP pp_np_coord` → **`NP np_appos_comma`** → semicolon.
  The proposition-resuming *which I accordingly did* has been folded
  into a nominal apposition under a PP, even though the top root exists.
- **Case 194:** `CLAUSE clause_front_pp_nocomma` →
  `CLAUSE clause_np_vp` → `VP vp_prep_ditransitive` →
  **`NP np_colon_list`** → semicolon.
  The source's `avoiding …, saying …` supplement is swallowed by an
  ostensibly nominal list inside the ditransitive predicate. The parse
  also exceeded its search budget, so its ranking is not certified.

The detector now recognizes both nominal failure classes even when the
wrong selected rule is *not* `vp_comma_coord`. Crucially, this is a
**diagnosis of incorrect syntactic paths**, not a claim that changing
punctuation alone would generate correct sentential relatives, shared
subjects and participial attachments. No grammar or historical benchmark
was changed in this research stage.

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

## Focused constituent audit of case 94 (2026-11-11)

[Action 42952309195](https://github.com/leye0/seman2/actions/runs/42952309195)
replayed the original contiguous v2 sentence through the mandatory corpus
gateway with reference WordNet 3.0. It remains incomplete (1,234 forest
nodes, 38,813 partial states, no budget saturation). Twelve independent
probes isolate the missing composition of a semicolon-coordinated finite
predicate around an inserted participial clause. The simple coordination
`She gently chid me for being rude; and turned to thank the gentleman.`
does parse, but `She chid me; and, keeping me close to her shawl, turned.`
and independent analogues do not.

Critically, apparently complete shorter probes also select incorrect
attachments: `me close to her shawl` becomes `np_pp_mod` rather than
an object + predicative complement; `as to bring her home` attaches to
the entire VP instead of the degree phrase around `so much trouble`.
No grammar change or score increase is claimed. Detailed tree findings,
negative controls and next constraints are in
[CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md](CASE_94_SHARED_SUBJECT_PARTICIPIAL_INCISE.md).

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
