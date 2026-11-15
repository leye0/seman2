# Novel Transfer 24 — first out-of-cohort diagnostic

**Baseline:** [`bc711eea`](https://github.com/leye0/seman2/commit/bc711eea69d25d47e295c787aaf62edf1e5e9964), unchanged parser and grammar. Its pinned Novel-500 still yields 500/500 locally and all 30 anchored dialogues complete. The new sample measures transfer, not a change in the Novel-500 score.

## Method

- Sampled [The Time Machine (Gutenberg #35)](https://www.gutenberg.org/ebooks/35) and [Anne of Green Gables (#45)](https://www.gutenberg.org/ebooks/45). Neither book nor author is in the configured Gutenberg train/test lists. The two books are balanced at 12 utterances each.
- Pinned both raw editions and cut front matter at the first narrative opening. Used the existing `gutenberg_novels.extract` pipeline, with chapter heads excluded, and rejected normalized text duplicates against Novel-500 and within the new pool. No selected case differs from the original source span after whitespace normalization, and no punctuation or quotes were added.
- Selected three evenly spaced source units per book and token band (4–8, 9–16, 17–24, 25–32). No output from the parser was used to select or replace cases. Candidate pool sizes were 310 and 2,277. The extractor excluded 180 and 85 source-dependent units, respectively, before sampling. Long units, units under four tokens, and excluded source context are outside this measurement.
- Used WordNet 3.0 and the usual `parse_corpus_case` gateway, with 50,000 forest items, 500,000 k-best work units, a 10-second deadline per utterance, and no parse cache. Audited the selected rank-one tree, not the best-looking alternative.
- The transfer SHA-256 is `2d87e7f698aba01835e5638ac140b50ee047556809e317cd47d51e545186a073`. Novel-500 retains its separate SHA-256, `d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`.

## Observed results

| Book | 4–8 | 9–16 | 17–24 | 25–32 | Structurally complete |
|---|---:|---:|---:|---:|---:|
| The Time Machine | 3/3 | 3/3 | 2/3 | 3/3 | 11/12 |
| Anne of Green Gables | 3/3 | 3/3 | 3/3 | 3/3 | 12/12 |
| Total | 6/6 | 6/6 | 5/6 | 6/6 | **23/24** |

No timeouts or k-best exhaustion. One complete case, T35-0071, also hit the forest cap. The sole incomplete case, T35-0485, had no full-span root and hit neither budget.

In the manual review, 3 cases had no material issue identified at the reviewed scope, 19 had at least one material rank-one issue, 1 was kept separate as a quoted verse, and 1 had no root. These are single-reviewer diagnostic labels, not independently annotated gold trees or an accuracy estimate for English. A case marked “no issue identified” is not a certification of semantics or discourse coreference.

| Case | Manual finding |
|---|---|
| T35-0065 | No issue identified. The psychologist is the subject and the `at` phrase belongs to `looked`. |
| T35-0217 | No issue identified. The guests are the subject and `frankly incredulous` is the predicative adjective phrase. |
| T35-0509 | `Really and truly` is one coordination of adverbs modifying the elided predicate. The tree puts `and` at clause level, before `truly I do`. |
| T35-0085 | The surrounding paragraph identifies a part of the model. `With his finger` specifies how he pointed, not which part. The tree attaches it to `part`. |
| T35-0200 | The socks are an exception to `nothing`; the tree coordinates them with `them` as the second object of `on`. |
| T35-0473 | No issue identified in the main attachments. `His hand` is the object and `to his head` the destination. |
| T35-0050 | The modal scopes over both coordinated verbs. The tree puts it on `travel` only and treats the direct object of `verify` as a clausal exclamation. |
| T35-0181 | The subject is shared, but `but` is analyzed as an adverb on `came` and `painfully` is inside the directional PP instead of modifying the motion event. |
| T35-0485 | No root. Two independent clauses are coordinated. The right clause has a comma-delimited initial PP, `in an absolute silence`, modifying `returned`. |
| T35-0071 | `About the room` belongs to `were scattered` inside the relative, not to `took`. The chosen tree treats the room as a recipient of `took`. The forest also saturated. |
| T35-0164 | `that` is the demonstrative object of `wanted` with a participial predicate, not a complementizer introducing both clauses. `account` is also misread as a finite verb. |
| T35-0462 | The matrix coordination is retained, but `over` belongs to `turned over`, and the embedded progressive `was looking` is read as copula plus a nominal gerund. |
| T45-0675 | The inverted modal perfect is found, but `n’t` is placed inside the subject NP (`n’t you`) rather than on the modal. |
| T45-1554 | The initial contrast and main event are retained, but the anaphoric `none` referring to prior `trouble` is typed as a lexical noun. |
| T45-2707 | The reporting tag is found, but `Moody Spurgeon` is one speaker. The selected tree assigns the surname as a separate addressee and treats the interjection as a proper name. |
| T45-0573 | An imperative followed by a closing formula becomes a single NP. The period is consumed as an appositive comma. |
| T45-1665 | Quoted two-line verse. The original line break is visible in the source paragraph but normalized to a space. The tree puts `as I love you` on the following clause instead of inside the condition. Retained in the coverage denominator and reported separately from the prose-tree audit. |
| T45-2808 | Speaker attribution is correct. `Wednesday` should modify the event rather than compound with `post office`, and `be haunting` is progressive rather than copula plus NP. |
| T45-0545 | Three independent spoken units are collapsed. The last question is attached as an apposition to `heathen`, and the period in between is analyzed as a comma. |
| T45-1716 | The subject and VP coordination are retained, but the second object is `her`, not a possessive noun phrase `her clear`. |
| T45-2891 | The contraction splits at the wrong grammatical boundary. The selected subject is `I do` and the predicate starts with `n’t`. |
| T45-0495 | The two genuine quotation spans and the reporting tag are recognized. The selected speaker is `the shrinking`; the head `child` is misread as an addressee instead. |
| T45-1816 | `a sound` starts a supplementary nominal. Its relative should contain `caused Diana … to give` with `Diana` controlling the infinitive. Instead `to give` is promoted into a separate clause and `gasp` becomes its finite verb. |
| T45-2854 | The two participles depend on `Anne`. Instead `oversetting` becomes a nominal head, `hands` a verb, and `could accomplish` the predicate of a spurious coordinated clause. |

## First repair candidates

**Boundary preservation inside quotations** is the first quality target. T45-0573 and T45-0545 both get full-span trees while flattening real sentence boundaries. Use the actual source utterance and spoken spans as input, then distinguish an imperative plus a formula, separate declaratives and a final question, a period in an abbreviation, and nested or attributed speech. A scoped composition only counts if each constituent has a valid independent parse and the original punctuation and offsets survive.

**Coordination with an initial right-conjunct adjunct** is the first clear coverage target. T35-0485 is a source-complete utterance with no budget saturation. In local probes, plain two-clause coordination and the right clause with just its fronted PP both complete independently. The exact combined construction and a new lexical example (`She opened the window, and, without a word, he left the room.`) both fail. Same-subject coordination is a separate control, and `and, he left` without an intervening constituent should not be accepted by any new construction. The sampled case currently receives only one provisional matrix constituent, so determine the typed boundary and governor from the contiguous source before changing grammar.

This sample becomes a diagnostic/regression cohort once it informs fixes. Keep a fresh sample, chosen before any subsequent evaluation, for the next transfer claim. Do not add these cases to the pinned Novel-500 gate.

## Reproduce

From the repository root on Linux or macOS, with a WordNet 3.0 dictionary:

```sh
mkdir -p /tmp/seman2-transfer-books
curl -fsSL https://www.gutenberg.org/cache/epub/35/pg35.txt -o /tmp/seman2-transfer-books/pg35.txt
curl -fsSL https://www.gutenberg.org/cache/epub/45/pg45.txt -o /tmp/seman2-transfer-books/pg45.txt
PYTHONPATH=superparser python -m scripts.evaluate_novel_transfer \
  --books-dir /tmp/seman2-transfer-books \
  --wordnet-dir /path/to/wordnet/dict \
  --out-dir /tmp/seman2-transfer-24
PYTHONPATH=superparser python -m unittest superparser.tests.test_novel_transfer
```

The runner writes `cohort.jsonl` (source spans and preanalysis), `per_sentence.jsonl` (rank-one trees, syntax links, statuses, and budget flags), and `summary.json` (counts per book and band). Use `--sample-only` to reproduce the pin without initializing a parser. A source or cohort hash mismatch fails before parsing. The runner does not write to the repository inputs.
