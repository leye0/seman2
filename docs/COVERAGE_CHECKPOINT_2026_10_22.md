# Parser coverage and syntactic quality — 22 October 2026

## Sentence #99 — attested elided name and possessive, 471/500 (94.2%)

The exact canonical sentence begins `I should have gone to bed with a sore
heart indeed` and ends `which sheltered little Em’ly’s head.` It failed
without budget exhaustion because the elided name and its possessive were
not available as the required lexical spans. Register the attested Dickens
spelling `Em'ly` / `Em’ly` in the literary dictionary and project dictionary-
licensed internal-apostrophe names before separating a final apostrophe-s.
This mechanism handles straight, curly and mixed apostrophes, requires an
explicit proper-name lexical reading, and leaves all existing candidates,
tokens and source offsets intact. No grammar rule or search budget changes.

The selected tree preserves modal-perfect `should have gone`, the proper-name
span `Em’ly`, separate genitive `’s`, possessor `little Em’ly` and head `head`.
The new tests certify those structures, original corpus provenance and negative
controls against inventing names from apostrophe shape. **This is a lexical
recovery, not a claim of complete syntactic gold quality:** the selected tree
still attaches the long prepositional sequence and the `but that which ...`
exception too broadly under `to`; that attachment issue is left explicit.

Local validation against `c0f91f7878c058c6f82371f3406d28642809f028`:
**438 tests pass with the same 7 expected failures**. Canonical balanced
coverage rises **470 -> 471/500**; #99 is the only status change, all previous
complete cases remain complete, and all other residual statuses are unchanged.
The SHA-pinned cohort and `parse_corpus_case` gateway remain unchanged, with
50,000 forest items, 500,000 k-best work units and a 10-second corpus deadline.
Direct grammar quality passes with unchanged 120/120 completions, 114/120
annotations, 24/24 grammatical contrasts and 9/24 existing negative acceptances.
These are local measurements; see `docs/case-99-validation.json`.

## Sentence #215 — extraposed infinitival subject and nominal object predicate

The selected analysis of `It would vex me, indeed, to see you again the dupe
of Miss Bingley's pretended regard` now preserves anticipatory **it**, modal
**would**, experiencer object **me**, the comma-delimited **indeed** incise,
and the extraposed infinitival subject. Inside that infinitive, **you** is
the object of **see**, **again** is an adverb, and **the dupe ...** is the
nominal object predicate. The genitive and attributive **pretended regard**
remain intact. This is not analyzed as object control by **vex**.

The grammar adds base-form nominal object predication with and without an
interposed adverb, licensed by existing `complex_transitive` lexical evidence.
A `V-NOMINAL-PRED` lattice view is derived only from positively attested base
complex-transitive readings. It retains each original V candidate, feature
structure, span, score, sense IDs and source; no lexical hypothesis is removed.
A distinct anticipatory-it reading anchors modal extraposition, whose base
experiencer predicates are explicitly attested (`vex`, `please`, `annoy`,
`surprise`). Ordinary referential-it and possessive hypotheses are unchanged.
These typed entry categories keep irrelevant structural searches out of
sentences that do not contain eligible lexical heads.

Regression tests assert the actual selected #215 tree through
`parse_corpus_case`, contrast eligible/ineligible verbs and inflections,
require anticipatory it and an overt experiencer, and verify preservation
of lexical provenance. The pinned corpus, quote-transfer implementation,
public parsing gateway and budgets are unchanged (50,000 forest items,
500,000 k-best work units, 10-second corpus deadline).

Local verification against main `b63ab1d5858dfa253ebd3a9724c6397e623cd295`
(Python 3.12, WordNet 3): **435 tests pass, with the same 7 expected failures**.
The baseline reproduces **469/500**, the final version reaches **470/500 (94%)**.
The only status change is #215: `roots_without_valid_analysis` -> `complete`.
All 469 previously complete cases remain complete, including #359 and #485;
all other non-complete statuses are unchanged. The corpus checksum is unchanged.

Direct grammar quality passes: 120/120 complete, 114/120 annotations met,
24/24 grammatical contrasts preserved, the same 9/24 existing negative
acceptances and identical failed-gold IDs and negative-pair details.
Canonical/adaptive/dialogue smoke passes. These are local measurements, not
claims of a new GitHub Actions run. See `docs/case-215-validation.json` for
machine-readable before/after counts and the exact test scope.

## Latest measured checkpoint — sentences #189 and #212 recovered, 469/500 (93.8%)

Code commit `b6dd1780079c7eb80598dbc90f2c80770815583b` recognizes independent genitives of
titled names, with an explicitly attested TITLE, proper name and apostrophe-s
suffix. St./Saint is a title; the abbreviation period stays inside its lexical
span. This is deliberately scoped to titled names, not all independent genitives.
The omitted nominal head is preserved as ellipsis, not filled with an invented
church/house. The in-that adverb retains its WordNet meaning but is marked
non-prenominal; its causal conjunction reading remains available. The existing
ADV+N rule rejects this explicit non-prenominal feature without tightening
unspecified legacy adverbs.

The selected #212 tree is tested for passive were married, the existing you know
incise, TITLE St. + Clement + genitive suffix, Wickham's headed genitive,
and compositional PREP in + DET that + N parish in the causal clause.
Quote-transfer provenance is preserved by the canonical gateway.

[Core validation](https://github.com/leye0/seman2/actions/runs/40160724897):
431 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40160724853):
469/500 complete; #189 and #212 recover from 467/500, with no completion
loss and no status change among remaining non-complete cases.
The #212 selected tree is certified by a regression test; #189 is an additional
completion gain, not a newly certified complete syntactic gold analysis.
There are 26 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40160724865)
also passes. Corpus, quote transfer, budgets and coverage gate are unchanged.

## Previous measured checkpoint — sentence #467 recovered, 467/500 (93.4%)

Code commit `b478469a7ffe43d31c737b74ea56410d103ec404` adds PREP and typed comparison-marker readings
for like, an invariant past-participle reading for set, and the attested
full-stretch adverb. Nominal comparisons reuse the existing equative incise
before a resumed PP; an external adverb cannot attach across its opening comma.
The comparison tail requires an actual comma, not the legacy COMMA category's
terminal-punctuation alternatives. The selected #467 tree is tested for the
complete subject, perfect passive had been set, full-stretch modifying that VP,
and the comparison followed by on that money.

[Core validation](https://github.com/leye0/seman2/actions/runs/40159767750):
428 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40159767724):
467/500 complete; #467 is the only recovery from 466/500, with no completion
loss and no status change among remaining non-complete cases.
There are 28 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40159767720)
also passes. Corpus, quote transfer, budgets and coverage gate are unchanged.

## Previous measured checkpoint — sentences #113, #357 and #459 recovered, 466/500 (93.2%)

Code commits `ed35264e2289cb1b1e865408cf74e2f763c94df4` and
`d6e2f801bb8af78576fee8f0e8f84eaa52e7d91a` add a typed each-of plural-pronoun distributive
inside possessive HAVE, comma-introduced subject relatives, and quoted
nominal mentions. The nominal-quote fallback ranks below split clausal
dialogue. The #357 selected-tree test checks separate distribution and
object spans, the supplementary relative and the quoted noun with its
preserved delimiters. Distributive reference resolution is left to later
processing. #113 and #459 gain completion; their selected trees have not
been independently certified by this change.

[Core validation](https://github.com/leye0/seman2/actions/runs/40137394850):
426 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40137394976):
466/500 complete; #113, #357 and #459 recover from 463/500, with no completion
loss and no status change among remaining non-complete cases.
There are 29 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40137394890)
also passes, including split quoted subject/predicate precedence.
Corpus, quote transfer, budgets and coverage gate are unchanged.


## Previous measured checkpoint — sentence #441 recovered, 463/500 (92.6%)

Final code commit `085d22e5042b72b32655ee2036645e49995465af` recognizes a paired-comma
equative manner incise before a PP. A dedicated EQUATIVE-AS lexical reading
seeds recognition only at the relevant marker. The incise and destination
compose through the existing VP+PP rule; preposition stacking cannot cross
the incise. The selected tree preserves rode + PARTICLE on, ADV fast,
the existing modal ellipsis he could, and the genitive destination.
Tests reject missing commas and substituted than markers.
Local ablation and CI preserve the sensitive #359 fixed-budget parse.

[Core validation](https://github.com/leye0/seman2/actions/runs/40123190324):
424 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40123190317):
463/500 complete; #441 is the only recovery from 462/500, with no completion
loss and no status change among remaining non-complete cases.
There are 32 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40123190366)
also passes. Corpus, quote transfer, budgets and coverage gate are unchanged.


## Previous measured checkpoint — sentence #209 recovered, 462/500 (92.4%)

Code commits `bd7f005908b5accefb0a1a0aa801baf0ad85871a` and
`1a4c701a04050db5c94ef0bc0c1121e8ece69b1f` license a degree nominal with a for-infinitive and
a selected adjectival prepositional gap. Lexical features match guilty to
of, while a dedicated DEGREE-NP constituent bounds recognition to overt
degree nominals. The selected tree keeps the entire "of decency, honour,
and interest" PP under "too great a violation" and attaches the infinitive
to that antecedent. Copular adverb recognition is restricted to this typed
nominal construction, preserving comparative adjective analyses.
Negative tests reject wrong prepositions, non-base copulas and unlicensed
adjectival gaps. The existing #359 fixed-budget test remains green.

[Core validation](https://github.com/leye0/seman2/actions/runs/40010928957):
422 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40010928872):
462/500 complete; #209 is the only recovery from 461/500, with no completion
loss and no status change among remaining non-complete cases.
There are 33 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
Corpus, quote transfer, budgets and coverage gate are unchanged.


## Previous measured checkpoint — sentence #340 recovered, 461/500 (92.2%)

Code commits `a1c1f9d5a2da2771b9fe1fc27a03573ceb1f6c15` and
`393079a39d184d65701c38caf1ec6ef357fafde9` add finite intransitive constructions for
PP plus subject depictive and purpose infinitive. The latter ranks below
lexically licensed subject control, preserving the selected analysis of
"Lena decided to read the novel". Tests enforce agreement and intransitive
valency and check #340's coordinated actions, "angry and disturbed" ADJP,
and "retired to meditate on some other mode of action" purpose construction.

[Core validation](https://github.com/leye0/seman2/actions/runs/40005242173):
420 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40005243149):
461/500 complete; #340 is the only recovery from 460/500, with no completion
loss and no status change among remaining non-complete cases.
There are 34 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
Corpus, quote transfer, budgets and coverage gate are unchanged.


## Previous measured checkpoint — sentence #112 recovered, 460/500 (92.0%)

Code commit `f21566d278232ecbf47163936bd71173d37e6318` adds the nominal_modifier reading of
exactly while preserving its ordinary WordNet adverb readings. The existing
np_adv_np production now licenses "exactly what he had before him".
No grammar production, parser algorithm, corpus or budget changes.
Tests check nominal focus, the existing object free-relative construction,
modal scope, ordinary adverb use, and the lexical gate excluding quickly.
Final PP attachment ambiguities are outside these selected-tree assertions.

[Core validation](https://github.com/leye0/seman2/actions/runs/40003608281):
418 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40003608016):
460/500 complete; #112 is the only recovery from 459/500, with no completion
loss and no status change among remaining non-complete cases.
There are 35 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40003607812)
also passes. The coverage gate remains unchanged.


## Previous measured checkpoint — sentences #232 and #237 recovered, 459/500 (91.8%)

Code commit `d6d40dbcf939a9bf29daaa2ff50ffca401c4bd45` adds the attested ADV unfrequently,
plural genitive apostrophe edges, and bounded passive object-control rules
with interposed ADV/ADVP. The participial lexical unit prevailed upon/on
retains its control valency. Curly plural-genitive edges remain consumable
without changing tokenization or the corpus quote-transfer algorithm.
The selected-tree regression for #232 checks the genitive, adverbs and
passive control; focused tests cover both apostrophes and reject incorrect
agreement, verb morphology and control valency.

[Core validation](https://github.com/leye0/seman2/actions/runs/40000029649):
416 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/40000029586):
459/500 complete. Compared with 457/500, #232 and #237 recover, no completion
is lost, and remaining non-complete statuses are unchanged.
There are 36 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors; 18 complete parses have forest saturation.
[Scoped dialogue validation](https://github.com/leye0/seman2/actions/runs/40000029673)
also passes. Corpus, budgets and coverage gate are unchanged.

## Previous measured checkpoint — sentence #239 recovered, 457/500 (91.4%)

Code commit `2e2564300d0c3e91c429e1ff0b89370cb0445930` adds temporal CONJ
before (preserving PREP/ADV) and the attested singular noun tete-a-tete.
No grammar production or budget changes. The pinned-case selected-tree test
checks the temporal clause, coordinated subject, dash-separated coordination,
and complete compound nominal span without reinterpreting its internal a as
a determiner.

[Core validation](https://github.com/leye0/seman2/actions/runs/39961780369):
413 tests, OK with 7 existing expected failures.
[Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/39961780249):
457/500 complete; #239 is the only recovery from 456/500, with no completion
loss and no status change among remaining non-complete cases.
There are 38 grammatical residuals, 4 forest-budget failures, 1 timeout and
zero errors. The existing 457/500 coverage gate is now green, unchanged.


## Previous measured checkpoint — sentence #200 recovered, 456/500 (91.2%)

Code commit `0dd760991b01b42ae2b14c160ee4fc4845899ff3` adds the missing
DET reading of any and PREP reading of beyond while retaining WordNet readings.
A finite HAVE + NEG + PP + NP construction recognizes possessive “had not at
that time the honour”, preventing the former selected nominal at/verbal time
misanalysis. The pinned-case test checks the selected predicate, interposed
temporal PP, object onset and lexical categories. PP attachment ambiguities
inside the object remain outside these assertions.

[Core validation](https://github.com/leye0/seman2/actions/runs/39960598855):
410 tests, OK with 7 expected failures. [Fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/39960599085):
456 complete, 39 grammatical residuals, 4 forest-budget failures and 1 timeout.
Compared with 455/500, only #200 recovers, no completion is lost and remaining
non-complete statuses are unchanged. Complete parses with forest saturation
increase from 17 to 18; the corpus and budgets are unchanged.
The existing 457/500 gate remains red and was not lowered.


## Previous measured checkpoint — sentence #445 repaired, 455/500 (91.0%)

Code commit `56adc49b523dea66c73568e97a47d5a1358c3a71` repairs the Treasure
Island sentence beginning “Aboard ship he carried his crutch”.
Aboard and round now have prepositional readings. The selected tree groups
“both hands” as the object of base HAVE, “as free as possible” as its adjectival
predicate, and the final comma + TO phrase as an infinitival supplement.
“Round his neck” modifies “a lanyard”. Possible remains adjectival, and hands
is not misread as a verb.

The HAVE construction is restricted to the closed-class base-form category
to avoid arbitrary V+NP partial states and preserve budget-sensitive #359.
Tests cover the exact quote-balanced corpus case, productive variants and
negative lexical/morphological/boundary contrasts.

- [Core validation](https://github.com/leye0/seman2/actions/runs/39895993940):
  407 tests, OK with 7 expected failures.
- [Latest fixed-cohort diagnostic](https://github.com/leye0/seman2/actions/runs/39954824743):
  455/500 complete, 40 grammatical residuals, 4 forest-budget failures and
  1 timeout, zero errors.
- Compared with the previous 454/500 diagnostic, only #445 changes from
  non-complete to complete; no completed case is lost, and all remaining
  non-complete statuses are unchanged. Corpus and budgets are unchanged.
- The existing 457/500 coverage gate remains red; its threshold is unchanged.


## Previous measured checkpoint — sentence #317 repaired, 454/500 (90.8%)

Code commit `48426b2c29f849268724b83bdde2c70c48b1fbf8` repairs the
Frankenstein sentence beginning “Unless I had been animated”.
The closed-class inventory now supplies `unless` as a CONJ, without WH,
degree, or interrogative-complementizer features. A generic
`vpnp_base_perfect_cop_adjp` construction combines base HAVE, participial
COPULA and ADJP under the existing modal rule.

Lexical repair alone produced a misleading complete tree: the subordinate
clause swallowed the main subject plus “would”, and “have” became a noun.
The regression now checks the selected tree's exact subordinate/main spans,
perfect passive, modal perfect copular predicate, and absence of modal ellipsis.
Additional tests cover capitalization, postposed unless, productive adjective
predicates, and malformed auxiliary forms.

- [Core validation](https://github.com/leye0/seman2/actions/runs/39894848367):
  403 tests, OK with 7 expected failures; global grammar quality gates passed.
- [Fixed 500-case diagnostic](https://github.com/leye0/seman2/actions/runs/39894848310):
  454 complete, 41 grammatical residuals, 4 forest-budget failures, 1 timeout,
  zero errors. Same corpus, quote-transfer gateway and search budgets.
- Compared with [the immediate 453/500 baseline](https://github.com/leye0/seman2/actions/runs/39893497060),
  #317 is the only recovered case; no previously completed case was lost and
  all remaining non-complete cases retained their status.
- The diagnostic workflow is still red because its existing threshold is
  457/500. This pre-existing coverage deficit is not fixed by the #317 repair;
  the threshold was not lowered. The 465/500 checkpoint below is historical.


## Historical verified checkpoint — 465/500 (93.0%)

On main, the canonical Layer 1 suite passed **385 tests with eight expected
failures** and all global grammar quality gates in
[core run 39852826036](https://github.com/leye0/seman2/actions/runs/39852826036).
The subsequent complete fixed-cohort
[diagnostic run 39853175219](https://github.com/leye0/seman2/actions/runs/39853175219)
verified **465/500 (93.0%)**, from the previous **462/500 (92.4%)**,
without changing the 500-case SHA, sentence/quotation transfer or budgets.
This checkpoint belongs to commit `1b20ca1debe56f1fb217fc68f1051c33b021347e`.
Changes on main after that commit require their own test and coverage qualification.

### Subsequent tree-quality validation (no new 500-case score yet)

After the 465/500 fixed-cohort run, the verified core suite on
[run 39856366742](https://github.com/leye0/seman2/actions/runs/39856366742)
passed **387 tests (8 expected failures)** and all global quality checks.
The selected original #439 sentence now attaches the *and indeed* discourse
conjunct at matrix scope. The implementation is a bounded, lexically
conditioned tie-break within eight best alternatives: it applies only when
a clausal-reporting VP improperly embeds an overt coordinated discourse
clause, and only when an equivalent-scoring top-level parse exists (machine
precision tolerance 1e-12). It does not change recognition rules, lexical
frames, scores, the forest budget, or the set of derivations. Productive
negative controls and two simpler positive reporting variants pass.

The same audit reveals why status and quality must not be conflated:

- **#486**: the selected tree takes `Anderson's` as NP and
  `ball--for ...` as a finite verbal predicate headed by *ball*. A
  subsequent clausal-valency constraint on one permissive comma-reporting
  rule exposed a second, redundant permissive rule; both have now been
  constrained. The genuine target contains a productive genitive
  `Anderson's ball` and an explanatory dash-delimited parenthesis.
- **#487**: the tree attaches `we were` to a spurious object-gap relative
  inside `the most part of the time we were` and takes
  `broadside on` as a particle VP. The modal-perfect sequence
  `should have made the ship` is real, but the full analysis remains
  syntactically unsound.
- **#213**: the object-bearing modal perfect is well formed, although the
  initial nominal coordination/fronting deserves a separate quality audit.

Consequently **465/500 is the verified numerical recognition score**, but
the evidence supports only #213 as a new productive grammatical recovery.
Counting #486 and #487 as improved syntax would be misleading.

A family-level investigation of #486 identified the absence of an
*overtly typed* productive apostrophe-s clitic even though `np_poss_s`
and `np_genitive` constructions pre-existed. The loaded source is
`superparser/data/function_words.jsonl`, not the legacy
`lexicon.jsonl`; an explicit `genitive_clitic=true` reading has been
added only to the morphological `'s` hypothesis, retaining alternative
copular and HAVE readings. Lexically anchored genitive rules cannot
consume an arbitrary pronominal POSS; tests include ASCII and curly
apostrophes, common and proper possessors, and missing-apostrophe
counterexamples. At the time of this entry the newly added tests are
still being stabilized, particularly the typographic apostrophe, and
no additional coverage gain is claimed.

The dialogue regression workflow now retains its short smoke test on
pushes but runs the expensive 160-case audit only upon explicit manual
dispatch or a `[dialogue-160]` marker. This limits recurring GitHub
Actions costs without removing the longer audit.

Exact per-case status comparison with the 462/500 verified reference:

| Case | Previous status | New status | Interpretation |
| --- | --- | --- | --- |
| 213 | roots_without_valid_analysis | complete | Real recovery of the licensed base HAVE + V[ed,transitive] + NP modal-perfect construction, within an attested full tree |
| 486 | timeout | complete | Numeric recovery only: selected tree is structurally invalid, with *ball* as finite verb |
| 487 | forest_budget_exceeded | complete | Numeric recovery only: selected tree has a spurious zero relative and *broadside* as finite verb |

**Zero status regressions** across the 500 cases. The current distribution is
465 complete, 10 no structural root, 20 roots without valid analysis,
3 forest-limit failures, 2 timeouts, zero errors. The forest-limit flag can
also be raised on completed examples; 18 completed analyses have saturation
flags. The #359 quoted case is complete with its required selected
constituents, but its dialogue attempt still approaches the fixed forest
ceiling, so complexity efficiency remains an active issue.

### Confirmed tree improvements in that checkpoint

- **#359** — full canonical quoted tree selects `vp_obj_control`
  for `allowed this intimacy to take place`, and `vp_perfect_trans`
  for `had formed far other plans`. Both refer to the original word spans.
- **#427** — the best tree selects the determiner+noun-headed,
  typed-absolute modifier `np_det_head_with_absolute_modifier` with
  `pp_absolute_with_np_adjp` over `with some brandy left`. An
  ordinary `with a label` cannot satisfy the absolute rule. The broad
  `NP + PP-ABSOLUTE` production had saturated #359 by creating
  unproductive partial derivations; narrowing the high-evidence NP form
  repaired that interaction without raising budgets.
- **#439** — best tree now selects `vp_finite_raising_rather_to_than`,
  rather than an incidental subject-control sense of `seem`; `try`
  keeps the genuine control reading. At this 465 checkpoint, the
  conjunction `and indeed he seemed...` still sits inside the reported
  proposition of `I have said...`. A separate typed matrix-discourse
  scope experiment is tracked after this checkpoint.
- **#213** — modal `would` governs
  `vpnp_base_perfect_transitive(have answered all my ideas of happiness)`.
  The introductory `The quiet,` is treated as a fronted NP, which warrants
  semantic/nominal coordination auditing even though recognition succeeds.

### Residual islands established without budget changes

A bounded canonical audit on
[run 39853492614](https://github.com/leye0/seman2/actions/runs/39853492614)
shows **#226** has independent failures: neither
`in an instant arose the dreadful suspicion` (declarative clause goal)
nor `the dreadful suspicion of his being purposely omitted` (NP goal)
receives a complete structure. Lexical `arose` already carries
intransitive `V[finite]` interpretations. Productive presentative
inversion would need a positive licensing class, plus a separate solution
for the nominal gerund/passive complement; a blanket `V NP` inversion is
not justified.

In **#232**, `was prevailed upon to get out` has a complete VP
candidate, while `was scarcely ever prevailed upon to get out`
has no VP root. Lexical `prevailed` carries prepositional and
intransitive valencies. The real structure combines a scoped pair of
adverbs, a prepositional passive and an infinitival complement; a
free-floating PREP and an unconstrained passive rule would misrepresent
its argument structure.

The same scope audit reveals that the *matrix* and *embedded* #439
analyses were exactly tied in score (8.99) in the verified checkpoint.
Thus a sentence-specific lexical score change is not evidence-backed;
the missing distinction is a typed matrix discourse boundary.


## Historical verified fixed-cohort checkpoint (before 465/500)

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

## Previously pending grammar-quality work (now verified above)

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

## Residual failure taxonomy and next directions

The 462-recognition fixed-cohort diagnostic leaves **31 grammar-structure
residuals** (10 without a structural root, 21 with roots but no valid
analysis), plus seven resource-limited cases (four forest budgets and
three timeouts). These are distinct forms of evidence, not 38 identical
grammar rules to add.

Inspection of the actual 31 sentence surfaces suggests the following
*investigation categories*, not yet certified causes:

| Cases | Candidate generalization | Guard against a false positive |
| --- | --- | --- |
| 213 | Modal + base HAVE + transitive participle + NP, now factored into the grammar | Verify the original NP subject and whole sentence, not just the modal span |
| 226 | Postverbal subject after fronted locative PP (`in an instant arose the dreadful suspicion`) | Require attested presentative/unaccusative inversion licensing, not every intransitive verb |
| 232 | Multi-adverb passive and stranded preposition with infinitival complement (`was scarcely ever prevailed upon to get out`) | Distinguish true valence and passive controller from free PP concatenation |
| 94, 107, 194, 340 | Shared subjects, interrupted/nonfinite predicates and coordination | Preserve each actual conjunct and prohibit spurious NP promotion |
| 96, 105, 220, 480 | Nested/reporting dialogue and interrupted quotations | Keep the canonical quote-balancing gateway and source provenance |
| 473 | Object and pied-piped PP relatives sharing an antecedent | Preserve syntactic gaps and prohibit unrestricted wh nominal substitutions |
| 8, 167, 182, 414, 434 | Context-bound fragments, letter closings, adjective or nautical ellipses | Do not invent an autonomous finite clause or artificial nominal head |

Other residuals still need their trees or lexical matrices investigated.
The ordering here favors **productive, positively licensed syntax** and
actual selected-tree improvements over simply making complete-status
numbers larger. The remaining resource-limited cases require separate
work-budget diagnosis before assigning any grammatical cause.

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
