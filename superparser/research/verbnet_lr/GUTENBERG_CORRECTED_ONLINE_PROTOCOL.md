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
