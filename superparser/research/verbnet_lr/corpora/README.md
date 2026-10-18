# Cleaned public-domain novel corpus

Four complete English novels for **grammatical analysis**, including the existing David Copperfield benchmark source and three additional authors. Texts are committed in this directory so parsing runs can use a stable, local corpus without downloading a mutable Gutenberg edition.

| Book (Project Gutenberg ebook ID) | Author | Narrative paragraphs | Chapter headings removed |
|---|---|---:|---:|
| David Copperfield (766) | Charles Dickens | 7,107 | 64 |
| Pride and Prejudice (1342) | Jane Austen | 2,057 | 61 |
| Frankenstein (84) | Mary Shelley | 677 | 24 (plus 4 letter headings) |
| Treasure Island (120) | Robert Louis Stevenson | 1,375 | 34 (plus 6 part headings) |

Each `.txt` is **narrative prose**, without Project Gutenberg header/footer/license, credits, prefaces, tables of contents, illustrations, editorial bracketed notes, decorative dividers, chapter/part headings, or stand-alone epistolary date/address/signature headers. The corpus preserves the novel's paragraph breaks, order, dialogue, vocabulary, original sentence punctuation and genuine literary fragments. Gutenberg hard line wrapping is joined inside each paragraph; original curly/straight dialogue quotes and apostrophes are **preserved**, and underscored emphasis markup is removed. The text is not paraphrased and has **not** been labeled with gold sentence boundaries. Literary verse or odd punctuation **inside** the narrative is genuine book content; further filtering may be needed for strict sentence benchmarks.

These are four different historical English styles, deliberately not a representative sample of modern English. The novel prose itself is public domain in Canada and the United States; the upstream source files come from [Project Gutenberg](https://www.gutenberg.org) through the [GITenberg](https://github.com/GITenberg) mirrors. See `manifest.json` for per-book upstream URLs, original Git blob SHAs and checked-in cleaned Git blob SHAs. Source revision drift is detected rather than silently accepted.

## Loading the cleaned books

From `superparser/`:

```python
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from research.verbnet_lr.clean_novel_corpus import load_cleaned

book = TRAIN_BOOKS[0]  # David Copperfield
text, metadata = load_cleaned(book)
candidates, counters = extract(book, text, length_min=4, length_max=45)
# candidates[*]["text"] still includes the dialogue quote marks and initials
```

The existing `gutenberg_novels.download()` intentionally **still downloads original Gutenberg files**. Old 5k/10k benchmarks have a hard-coded raw-source SHA-256; changing their source silently would destroy reproducibility. New cleaned-corpus experiments should use `load_cleaned()` explicitly, and record its distinct cleaned-text SHA-256 and source provenance. The four books are all in the existing TRAIN set; held-out authors (Jane Eyre / Middlemarch) remain separate.

## Verification and rebuild

From `superparser/`:

```sh
python -m research.verbnet_lr.clean_novel_corpus --check
python -m unittest tests.test_clean_novel_corpus
```

Rebuilding from the pinned upstream source bytes (network required):

```sh
python -m research.verbnet_lr.clean_novel_corpus --rebuild
```

`--rebuild` refuses to overwrite a corpus if either the original upstream Git blob SHA or the regenerated cleaned Git blob SHA differs from the manifest. It records exactly which chapter and letter headings were removed. The existing committed files are the reference corpus.

No grammatical rules, parser scores, evaluation results, or held-out sets are changed here.

## Quote/initial regression fix

**Corpus v2 (2026-10-18)** restores the original source quotation marks in Dickens and Austen; the ASCII originals of Shelley and Stevenson are unchanged. This is a **lossless textual correction**: punctuation and typography are kept in the stored prose. Sentence-level extraction is separate, now using `seman_parser.sentence_boundaries.split_prose_sentences`; no leading or trailing quotation marks are stripped. The shared splitter conservatively protects sequences like `J. R. R. Tolkien`, `A. B. Smith`, `Mrs. Bennet`, dotted acronyms, and decimals. It accepts punctuation followed by closing quotes. Short quoted dialogue is not discarded solely due to length. In ambiguous cases it prefers keeping clauses together, rather than inventing a fake one-letter sentence.

`seman_parser.coverage.extract_sentences` now uses the same boundary rules. The Gutenberg research extractor was also repaired, so **sentence selections and benchmark counts produced by the new code may differ from historical commits**, even if the upstream raw-source SHA has not changed. To reproduce previous benchmark numbers exactly, check out the earlier commit. This parser remains heuristic, **not** a gold-standard literary sentence segmentation.
