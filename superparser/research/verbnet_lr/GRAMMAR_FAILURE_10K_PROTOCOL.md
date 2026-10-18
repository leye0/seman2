# 10,000 genuine-novel parsing failures — research protocol

This experiment is strictly descriptive/diagnostic. It does **not** modify the production grammar or the snap engine. Branch: `research/verbnet-left-to-right-poc`.

## Corpus and reproducibility

- First **10,000 distinct eligible sentences** in Gutenberg *David Copperfield* (ebook 766), in original order, 4–32 tokens, exactly the same extraction and source SHA-256 used in the 5,000-sentence benchmark.
- First-pass VectorGrammar; forest state cap 20,000 and explicit k-best work budget 100,000. **No per-sentence wall-clock timeout**.
- WordNet remains warmed across the 10,000 sentences. Counterfactuals reuse the **exact same in-memory lexical lattice** as the original parse for a bounded, stratified sample, avoiding WordNet morphological drift.
- `python -m unittest superparser.tests.test_characterize_failed_10k` runs the diagnostic tests.
- Workflow: `.github/workflows/characterize-failed-10k.yml`.

## Saved artifacts

The workflow uploads:

1. `per_sentence_10000.jsonl`: full 10k inventory, each original sentence, timing by phase, categories of lexical readings, root recognition, forest capacity, k-best work, completion and failure label.
2. `expensive_and_failed_corpus.jsonl`: union of **every incomplete sentence** and **every sentence above five times the empirical corpus median**, including expensive successful analyses.
3. `counterfactual_observations.jsonl`: detailed case-by-case grammar relaxation experiments (only bounded representative samples).
4. `failure_characterization_summary.json`: failure-mode counts; p50/p95/p99; tail contribution to total runtime; token-length stratification; representative worst cases; per-family evidence; counterfactual recovery versus changed-success controls.

No novel text is committed into the repository. Workflow artifacts expire after 21 days.

## Failure modes — distinct questions

- `no_root_under_current_grammar`: the recognizer finished its bounded forest *without* a CLAUSE spanning the sentence. Suspect missing lexical reading, missing constructions, or category/RHS patterns. This alone does not prove a *specific* rule is absent.
- `lexical_gap`: a non-punctuation token has no covering candidate; likely upstream lexicon/tokenization.
- `forest_budget_no_root`: recognition reached 20,000 nodes+partials without reaching a full root. **Unknown whether a legal tree exists.**
- `forest_budget_root_present`: recognition truncated but a structural root exists; no valid best tree was returned. **Unproven, not necessarily prohibited**.
- `root_without_feature_valid_witness`: a structural root exists but no complete constrained derivation was returned within normal accounting. Test unification/positive evidence requirements; this still is not a proof of a specific bad rule.
- `kbest_budget_unproven`: there is no certified best analysis after 100,000 work units; **not an indication of grammatical rejection**.
- `complete`: best tree obtained; may still have touched the forest budget, tracked separately.

## Controlled rule hypotheses

Each independently tested counterfactual keeps exactly the original rule categories, RHS ordering and scores; only one constraint family is removed. A new VectorGrammar is compiled *in memory*:

- `requires_subcat` — remove only the positive-evidence requirement for valency/subcategory.
- `requires_any` — remove all positive evidence requirements (broad upper-bound experiment).
- `feature_number`, `feature_person`, `feature_vform`, `feature_subcat`, `feature_voice`, `feature_wh_gap`, `feature_inversion` — remove that feature constraint from grammar LHS/RHS symbols.

Report for each: cases recovered, previously successful controls whose best tree/lexical selection changed, new forest and k-best budget hits, extra runtime, and rule IDs from recovered trees touched by the ablation.

**Interpretation:** a recovered sentence suggests a constraint family may be unnecessarily strict. It does not establish that the resulting interpretation is correct. Removing a feature *globally* is only a hypothesis generator, not a production patch. Inspect rescued derivations and then attempt minimal **per-rule** edits with regression tests and a held-out corpus.

## Engineering sequence after the run

1. Separate genuine `no_root` / `lexical_gap` cases from censored `forest_budget` / `kbest_budget` cases.
2. Examine expensive complete parses and cases with near-saturated forests: measure rules/partials per category and repeated structural ambiguity.
3. For counterfactual recoveries, isolate individual rule IDs and feature assignments, then test one-rule modifications, retaining all earlier parses.
4. Evaluate on a different novel/author as held-out; changes should improve *verified* linguistic coverage without simply accepting more nonsensical parses.
