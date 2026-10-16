# Project Gutenberg novel-scale syntax experiment

This independent research experiment tests whole-sentence grammatical snapping
on a substantially bigger sample than 600 sentences. No production or main
branch parser changes are made.

Training comprises twelve Project Gutenberg English classics: David
Copperfield (766), Great Expectations (1400), Oliver Twist (730), Pride and
Prejudice (1342), Emma (158), Sense and Sensibility (161), Moby Dick (2701),
Dracula (345), Frankenstein (84), Little Women (514), The Adventures of
Sherlock Holmes (1661), and Treasure Island (120).

Evaluation uses Jane Eyre (1260), Charlotte Bronte, and Middlemarch (145),
George Eliot. Neither author nor book is present in training. The actual
plain-text source URL and SHA256 for each ebook are recorded at run time.
The downloaded text is never committed or uploaded.

The extractor heuristically separates prose sentences, drops Gutenberg
front/back matter, headings and malformed fragments, records per-book
counts and rejections, and refuses ebooks missing proper markers.

The run deterministically selects UP TO 50,000 unique 4-32 token novel
observations balanced across the twelve books; it explicitly fails if the
required milestone is unreachable. It dispatches exactly every tenth
observation to the separate budgeted Earley grammar teacher: approximately
5,000 actual verification attempts on a full 50,000-observation run.
The other 90 percent are seen but NOT parsed, and may not be described as
grammatically verified. An Earley FOUND gives a grammar-compatible tree,
not a unique or independently human-gold derivation.

Checkpoints: 0, 5,000, 20,000, and 50,000 observed training sentences.
At each checkpoint evaluate heldout novel snap/completion rates split by
word count, author and book, with total processing latency. Separately
record performance against Seman2's 70 partially annotated heldout positives
and 24 grammar-negative contrasts. Novel sentences do NOT have human-gold
syntax labels: a snap match is a retrieval, not an accuracy success.

If an expanded cache accepts more negative sentences than the original,
the expansion is experimental and must not be enabled by default. The
experiment never treats teacher budget UNKNOWN as ungrammatical.

Workflow: .github/workflows/snap-gutenberg-novels.yml
Script: superparser/scripts/benchmark_snap_novels.py
Corpus: superparser/research/verbnet_lr/gutenberg_novels.py
Result: GitHub Actions artifact seman2-novel-scale-report (aggregate only).
