# Correction: what the 60,000-sentence Gutenberg experiment actually did

The original Gutenberg script (GitHub Actions #38982466564) read 60,000
training sentence *observations*, but the inner loop only called
build_lattice on every tenth observation and only invoked the bounded
Earley teacher on that tenth. Neither the L-R parser nor the whole-tree
snapper was invoked on the 54,000 unselected training sentences. The
lexical category lattice was not even built for those 54,000.

At the end, 6,000 independent teacher attempts produced only 529 witness
derivations. The template store grew from 41 seed templates to 514.
Its 473 extra unique shapes plus 56 duplicate witness observations DO
NOT provide a measurement of recurring grammatical structures across
60,000 actual parses: there were only 529 parsed successful samples and
the other 54,000 had no lexical representation whatsoever.

The index identity was also stricter than ordinary POS signatures:
an entire fully-nested derivation contains each selected rule_id, the
grammatical leaf category and every constituent's attachment. A shared
lexical category sequence can correspond to several stored whole trees.
No benchmark computed duplicate lexical signatures over the full corpus.

## Corrected experiment

Source: superparser/scripts/benchmark_snap_novels_online.py
Workflow: .github/workflows/snap-gutenberg-online.yml

Every one of 50,000 selected 4-to-45 token training sentences now:

1. Builds an entire one-token lexical lattice, preserving ALL candidates.
2. Counts repeated all-candidate category signatures in full and coarser
   forms, without selecting a single lexical POS beforehand.
3. Queries every cached complete derivation matching that lattice.
4. If no valid snap is available, executes the existing compiled L-R parser
   on the SAME prebuilt lattice.
5. If L-R returns a complete tree, adds it to the whole-tree index as a
   provisional CANDIDATE with clear provenance, not independent gold.
6. Independently enqueues precisely every tenth observation for Earley;
   verifies after measuring the real-time parse, outside the fast path.
   A bounded witness is labelled grammar_witness; unknown is NOT negative.
7. Separately records real snapping hits, new full trees, noncomplete L-R
   attempts, category fingerprint repetition, latency and parsing by length.

The corrected experiment retains the original author-disjoint classic
novel books and tests all 600 fixed cross-author sentences at checkpoints,
as well as ALL 18,184 held-out novel candidate sentences at the first
and last checkpoint. It also tests the fixed 70 partial syntax annotations
and 24 grammatical negatives without using them as training data.

Important: category-sequence repetition does not imply equal syntactic
attachment; newly constructed full trees remain provisional, and the
strict tree cache still has grammar coverage and representation limits.
No success or headline numbers should be reported until the corrected
workflow has actually finished.

Short reproducibility smoke:
.github/workflows/snap-gutenberg-online-smoke.yml.
This smoke checks every one of 2,500 training sentence observations rather
than only 250 sampled sentences, but skips the long full-novel evaluation.

## Crucial correction: lexical-category alternatives denote disjunctions

The 50k report originally claimed just 342 exact lexical fingerprints were
repeated. **This was the wrong question and those figures must not be used
as grammar pattern recurrence evidence.** It compared the full set of
alternative categories at each position for literal equality.

Example:

  sentence A: {DET} {N,V} {V,N,ADJ}
  sentence B: {DET,PRONOUN} {N,ADJ} {V,ADV}

Both admit the SAME complete lexical enumeration: DET N V.
Additional meanings or POS alternatives MUST NOT destroy this hit.

The corrected code stores every observed per-token category DISJUNCTION
and reports a hit if there exists at least one complete category assignment
common to two previously distinct sentences. The query is exactly:

  (A_1 intersection B_1 != empty) AND
  (A_2 intersection B_2 != empty) AND ... AND
  (A_N intersection B_N != empty)

No Cartesian product needs to be explicitly materialized. The implementation
in compatible_category_sequences.py uses integer bitset postings:
at each word position OR the sets of observed sentences containing ANY
of the candidate categories; then AND the bitsets across positions.
Its memory is proportional to observed alternatives, NOT exponentially
in the product of possible categories per word.

The new report key is compatible_category_enumerations:
- observations_with_at_least_one_prior_compatible_sequence;
- total_prior_observations_compatible_across_queries;
- number of sentences indexed, including those with unrecognized tokens.

No phrase's lexical candidate list is modified or pruned by this index.
Separately, FullStructureSnapIndex.match already navigates its trie using
ANY available category edge at every position (not an exact set fingerprint).
Once a known complete tree matches a lexical enumeration, it MUST still pass
grammar feature unification, agreement/valency restrictions and the
construction guard. A shared sequence of POS categories is not proof of
a shared valid derivation or intended meaning.

Tested by:
  superparser/tests/test_verbnet_lr_compatible_category_sequences.py
  superparser/tests/test_snap_novels_online.py
  superparser/tests/test_verbnet_lr_full_structure_snap.py

**Caveats**: this still relies on the categories actually emitted by the
lexicon; WordNet's configured sense ceiling may limit which grammatical
readings are available. The whole-tree cache still uses exact rule
derivations and explicit exploration budgets. These are separate problems.
