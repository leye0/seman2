# Parser coverage and syntactic quality — 22 October 2026

## Verified fixed-cohort checkpoint

Repository: `leye0/seman2`, direct commits to `main`.
Canonical Gutenberg cohort: exactly 500 fixed cases, SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
The quote-balancing preparation, corpus sampling, parser public API,
50,000-item forest limit, 500,000 k-best work budget and 10-second
per-case diagnosis remain unchanged.

- Earlier benchmark: **457/500 (91.4%)**, [run 39715992353](https://github.com/leye0/seman2/actions/runs/39715992353).
- After initial grammar changes: **459/500**, [run 39769842005](https://github.com/leye0/seman2/actions/runs/39769842005).
- After structural factorization and quote quality correction:
  **460/500 (92.0%)**, [run 39771925120](https://github.com/leye0/seman2/actions/runs/39771925120).
- Focused validation: **11/11 tests**, positive/negative contrasts,
  full original case tree checks, controlled quote ablations;
  [run 39771799512](https://github.com/leye0/seman2/actions/runs/39771799512).
- The final full diagnostic also ran **155 integration/diagnostics
  tests successfully**.

The exact old-to-current per-sentence change set, checked using both
retained `per_sentence.jsonl` artifact files, is:

| Index | Before | After | Interpretation |
| --- | --- | --- | --- |
| 122 | timeout | complete | Previously resource-limited dialogue; count the gain as a recognition, not independent tree-quality proof |
| 349 | roots without valid analysis | complete | Within + NP, explicit degree–adjective–indefinite nominal, and finite clausal postverbal negation |
| 427 | roots without valid analysis | complete | Fronted participial manner clause and comma-detached benefactive **for + NP** |
| 439 | roots without valid analysis | complete | Perfect reporting predicate, initial conjunction + discourse adverb, and **rather to ... than ...** alternatives |
| 414 | complete | roots without valid analysis | **Intentional rejection of a prior spurious analysis** (details below) |

Case 359, which temporarily changed from `complete` to a
`forest_budget_exceeded` failure at 459/500, is **complete again**
at the original 50,000-item ceiling in the final run.

Final mutually exclusive outcomes: 460 complete, 11 without structural
root, 22 with roots but no valid analysis, 4 forest-budget failures,
3 timeouts, 0 errors. Some completed parses still hit a forest budget;
completion is **not** a certificate that the best tree is linguistically sound.

## Later 22 October checkpoint: productive negative inversion

The following changes were committed **directly to `main`** with no change
to the fixed 500-case cohort, quote preparation, resource limits or public parser.
A full diagnostic after negative-inversion rules and their regression tests
produced **462/500 recognized** ([run 39824039007](https://github.com/leye0/seman2/actions/runs/39824039007)):
462 complete, 10 no structural root, 21 roots without a valid analysis,
4 forest-budget failures, 3 timeouts and no errors.

Relative to the earlier verified 460/500 run:

- **#361** was recovered by a lexically gated `nor + finite MODAL + NP + VP-NP`
  declarative inversion. The selected actual tree includes the correct
  `nor could I ask information from a single human being` construction
  ([full diagnostic 39822230151](https://github.com/leye0/seman2/actions/runs/39822230151)).
- **#423** was newly counted complete via copular inversion, but the **selected
  full tree is linguistically wrong**: it treats
  `that wonderful, seeing how cavalier had been` as an appositive NP,
  `how cavalier` as a nominal interrogative, and
  `the captain's answer` as a second predicative NP. This status is
  a **recognition only, not a syntactic-quality gain**. The tree was
  inspected in [core run 39825063636](https://github.com/leye0/seman2/actions/runs/39825063636).
  Do not report 462 as 462 certified correct trees.

The corpus comparison between 461 and 462 found no other changed grammatical
success/failure status. The production for bare `N + CONJ -> NP`, responsible
for impossible structures such as `water than`, was removed. Degree/as
constructions now require explicit lexical `degree` features on the
conjunction, verified against both ordinary `as` and comparative `than`.
The extended core validation passed **380 tests (8 known expected failures)**,
the global grammar gate and canonical/adaptive smoke checks on
[run 39825063636](https://github.com/leye0/seman2/actions/runs/39825063636).

After that checkpoint, the grammar was adjusted to prefer two **existing,
lexically licensed, general constructions** in the original #359 sentence:
`V[object_control] NP TO VP-NP` (rather than treating `allowed` as
ditransitive) and `HAVE[finite] V[ed,transitive] NP` (rather than treating
`had` as lexical possession). Tests now inspect both selected spans in
the **original complete quoted sentence** and check ordinary ditransitive,
possessive-`have`, perfect and object-control contrasts. These later
changes were pushed in `0a60247c` and `15d0b5e2` and a fresh CI
checkpoint was triggered via `70e7953e`; the numerical and tree-quality
effects must not be claimed before that newer validation is inspected.

## Subsequent grammar-quality work (awaiting fresh CI evidence)

The following are **generic, lexically constrained** productions added after
the 462-recognition checkpoint. Do not count their intended benefits as verified
until the corresponding selected-tree tests and full 500-case diagnostics pass.

- **#359:** Existing licensed object-control (`allow NP to VP`) and
  transitive past-participle perfect (`had formed NP`) were promoted in
  structural ranking. The original full quoted sentence now has a
  selected-span regression test, plus ordinary ditransitive and possession
  contrasts.
- **#427:** `np_with_absolute_modifier` allows a headed NP to take a
  separately licensed `PP[absolute_supplement=true]`. This distinguishes
  `a bottle [with some brandy left]` from a VP-level adverb
  `found ... left` or an ordinary `with + NP` modifier. The test
  requires the full original tree to select both the nominal attachment
  and the `with + NP + ADJP` absolute.
- **#439:** The `rather to VP than VP` construction now more strongly
  favors a *lexically licensed raising* interpretation over an incidental
  subject-control reading on `seem`; it retains a positive
  subject-control contrast on `try`. This does **not** resolve the
  independent scope ambiguity between reported content and matrix
  coordination, which must be audited separately.
- **Potential #213 and related modal perfects:** A factored
  `VP-NP -> HAVE[base] V[ed,transitive] NP` construction, with its
  intransitive counterpart, composes with the pre-existing finite
  `MODAL + VP-NP` rule. This supplies overt argument structure for
  examples like `would have answered the question` and
  `might have arrived`. The original #213 case remains a hypothesis
  until its full analysis is inspected; it may have other independent
  obstacles.

The core tree audit now includes the original #427, #213, #226 and #232
examples in addition to #359, #361, #423 and #439. No change was made
to the corpus hash, quote-balancing transfer, budgets, or public API.
The grammar edits were committed directly to `main` in
`d62dca58`, `4f22eafe` and `19d55259`; the regression tests in
`9dc48023`, `1659bb56` and `837fc36a`. The previous attempt
at verifying #359 alone remains distinct from this grouped checkpoint.

## Generalizable grammar changes

The grammar now licenses the preposition `within`; separates
subject-control alternatives from subject-raising `seem`; recognizes
lexically bounded `rather to ... than ...`; distinguishes nominal-focus
particles (`even`, `only`, `just`) from discourse adverbs (`indeed`);
supports `so/too ADJ a/an N`, finite HAVE + clausal participle,
finite clausal verb + NOT + THAT + proposition, fronted `V-ing ADV`
adjuncts and comma-detached benefactive `for NP`.

The `with NP ADJP` absolute is **factorized through**
`PP-SUPPLEMENT[supplementary_with=true] + ADJP`. It first constructs
and licenses `with + NP` and only then admits the predicate, instead
of eagerly carrying an extra `PREP NP ADJP` search. Controlled
single-rule ablation established that the original unfactorized
`pp_absolute_with_np_adjp` was *sufficient* to push the genuine quoted
case 359 over the 50,000-item ceiling. With the factorized version,
case 359 is recognized at that unchanged ceiling. The new PP itself
is validated independently of a matrix sentence's top-k ranking.

## Why case 414 must not be counted as an actual regression

Canonical quoted unit: `"and now here on my own account, in a manner
of speaking."`. The original *Treasure Island* paragraph contains
earlier coordinated statements separated by semicolons. This unit
inherits omitted context; it is not necessarily an autonomous finite
declarative clause.

A controlled ablation restored the former unrestricted
`np_coord_adv = COORD ADV NP` production **only inside the experiment**.
That made case 414 `complete`, but its actual best tree incorrectly
classified `and now here on my own account, in a manner of speaking`
as an NP; it further analyzed `in a` as an `N + DET` construction.
Restoring this overpermissive nominal rule would also reintroduce
the erroneous treatment of `and indeed he` as a nominal subject
in case 439. The production now requires a *positively licensed*
nominal-focus ADV, and the erroneous 414 recognition is not restored.
A future context-aware ellipsis/utterance model may recognize it
legitimately without inventing a finite clause or bizarre NP.

## Open quality limitations

- **349:** Correct adverbial/PP and degree + indefinite NP; explicit
  `doubted not that` clause is now the selected derivation.
- **427:** The fronted `Foraging about` and trailing `for Hands`
  are correct in the best tree. `with some brandy left` can form
  a licensed with-absolute PP in isolation, but the selected matrix
  tree still interprets `left` as a VP-level ADV.
- **439:** The best tree now avoids `np_coord_adv(and indeed he)`
  and correctly has a perfect reporting predicate. It still takes
  the second coordinated clause inside the reported complement and
  picks a subject-control rather than a *raising* reading of `seemed`.
  Valid raising analyses exist deeper in the forest; changing scores
  without structural justification is not an acceptable repair.
- **359:** Recognition is restored, but selected `allowed this
  intimacy to take place` and `had formed ...` still show
  object-control / perfect-auxiliary misattachments. Do not claim
  full syntactic correction from the status `complete`.

## Reproduce

```bash
WORDNET_DICT=/path/to/wordnet/dict PYTHONPATH=superparser \
  python -m unittest -v \
    superparser.tests.test_parser_integration.ResidualLiteraryCoverageTests

PYTHONPATH=superparser python -m scripts.audit_quote_regressions \
  --wordnet-dir /path/to/wordnet/dict \
  --indices 359,414 --budget 50000 --raised-budget 60000

PYTHONPATH=superparser python -m scripts.diagnose_novel_parses \
  --wordnet-dir /path/to/wordnet/dict --count 500 \
  --max-items 50000 --kbest-work-limit 500000 \
  --deadline-seconds 10 --out-dir /tmp/seman2-novel-final
```

An accurate research dashboard must report *both* corpus recognition and
annotation/tree quality, and avoid treating resource exhaustion or
context-dependent fragments as grammatical failures.
