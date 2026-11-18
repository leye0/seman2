# Novel-1500 exploratory baseline

Novel-1500 extends [Novel-1000 v3][v3] with N1001–N1500, in five
additive groups of 100. All 1,000 inherited source anchors are unchanged.
The parent and its 30 dialogue witnesses are tested against the v3
rank-one syntax and semantic graph pins. Nothing here promotes the five
new candidate groups into the accepted Novel Ladder.

## Fixed sources

The same four cleaned Gutenberg editions and the same canonical extractor
supply the new 4–32-token units. Each new group has 25 cases per novel and
25 per length band. No new case shares a source paragraph or a normalized
text identity with another new case, an inherited case, or a dialogue
witness. The selector never reads a parse outcome.

The older diagonal grid would need 35 short *Frankenstein* paragraphs
across five groups, but only one unused 4–8-token paragraph is eligible.
The first group uses it. The group margins remain balanced by exchanging
short and longer slots between editions. Source-only hash ranking and
deterministic paragraph matching fill the frozen grid without overlapping
book paragraphs. The manifest records the exact source spans, edition and
text hashes for all 500 new cases.

## Initial coverage

| New group | Complete | No root | Roots but no valid analysis | Item ceiling | Deadline |
| --- | ---: | ---: | ---: | ---: | ---: |
| N1001–N1100 | 77 | 6 | 15 | 1 | 1 |
| N1101–N1200 | 79 | 5 | 14 | 2 | 0 |
| N1201–N1300 | 77 | 6 | 13 | 3 | 1 |
| N1301–N1400 | 77 | 3 | 17 | 0 | 3 |
| N1401–N1500 | 81 | 4 | 10 | 4 | 1 |
| **500 new sources** | **391** | **24** | **69** | **10** | **6** |

Cumulative parse coverage is **1,391/1,500**. A complete result has a
selected tree and semantic graph. No new case is yet certified by a
case-by-case semantic audit. Resource stops are inconclusive. The replay
permits a wall-clock deadline and an item or k-best ceiling to trade places
for an already censored case on a different runner, but never counts it
as complete.

The frozen [repair queue][queue] records all 109 unresolved cases in
source order. The first is N1010, a valid *Frankenstein* source span.
Recognition produced roots but no valid selected analysis. In context,
the nonrestrictive relative after *Ingolstadt* describes *journey*, and
*for these and many other reflections* attaches to *leisure*.
Those attachments still need to be proved by a selected tree and graph.
Two following failures exercise repeated declarative *do* inversion
across a semicolon (N1013) and a coordinated speech report followed by
a single quote containing a vocative and a temporal clause modifying an imperative (N1014).
Neither is eligible for punctuation splitting to get a passing result.

## Replay and repair

From the repository root with the same WordNet 3.0 dictionary installed:

```sh
export PYTHONPATH=superparser
python -m scripts.novel1500_exploratory replay \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel1500
python -m scripts.novel1500_exploratory check --out-dir /tmp/novel1500
python -m scripts.novel1500_exploratory inspect --out-dir /tmp/novel1500
```

Use `--group 1100` for a single replay group or `inspect --index 1010`
to display an exact contiguous source paragraph and the pinned signature.
With a replay directory, inspection also returns the full rank-one tree
and graph when available. Run without a replay directory for source-only
triage. The JSONL outputs remain separate from the immutable initial pins.
Replay starts a fresh parser per group in either mode. Reusing a parser
across groups can carry WordNet insertions into a later group's mutable
lexical indexes and change a selected sense, even without a change in
coverage. We pin the standalone-group initialization and require exact
tree and graph signatures within it.

Every replay uses `parse_corpus_case`, WordNet 3.0, 50,000 chart items,
500,000 k-best work units and a 10-second case deadline. A later grammar
repair should pin its own current results, retain the initial measurements,
and demonstrate the selected attachments plus independent positive and
negative contrasts under the same limits.

[v3]: https://github.com/leye0/seman2/pull/103
[queue]: ../superparser/research/novel_1500_exploration/repair-queue.json
