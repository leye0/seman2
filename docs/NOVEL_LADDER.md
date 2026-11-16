# Novel Ladder — additive 100-case cohorts

Novel-500 is the permanent historical prefix. The first new batch is
Novel-600, with stable public IDs **N501–N600**. The 500 historical anchors,
indices, grading scripts and 30-dialogue audit are retained as-is.
Do not regenerate them with the 600-case sampler.

## Selection and measurement

The 100 new cases come from the four existing cleaned Gutenberg editions,
with 25 cases per book and 25 per length band. Every chosen case has a
distinct source paragraph that was not represented in Novel-500 or a
preceding rung. Normalized duplicate text is disallowed. Ranked SHA-256
selection is determined by the policy, batch and source coordinates
without a parser call. Source manifests store only edition digests, offsets
and text hashes. Resolution uses the one active corpus extractor and
fails on anchor drift. The same-author extension measures transfer to
unseen passages, not transfer to unseen authors or genres.

The immutable Novel-600 **first pass** was taken on the merged PR #96
tree, commit `312ce361d9bbc30c01714d8516985848c23f97c1`, before grammar
changes for this lot. The same 100 source anchors were replayed twice on
that tree. Both runs returned identical case statuses, budget flags, and
selected trees.

| Initial Novel-600 slice | Result |
| --- | ---: |
| Complete rank-one trees | 78 |
| Roots without a unified analysis | 18 |
| No structural root | 1 |
| Forest limit reached without a complete tree | 1 |
| Deadline reached | 2 |

Two of the 78 completions also had forest flags. The 78 is a structural
completion count, not a gold attachment score. The immutable file
`novel-600-initial.json` records the measurement independently from the
living, reviewed comparison reference `novel-600-current.json`.

All cases use `parse_corpus_case` and WordNet 3.0, with 50,000 chart items,
500,000 k-best work units, and a 10-second deadline per case. GitHub
reuses the canonical Novel-500 diagnostic run, including the existing
30-dialogue audit, and adds the frozen batch. The gate fails on a
historical tree change, a current approved tree change, a lost completion,
a new budget flag, an execution error, or source/budget drift. There are
no parse-count-based case substitutions.

## Working on a rung

```sh
export PYTHONPATH=superparser
python -m scripts.novel_ladder next
python -m scripts.novel_ladder run \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel-ladder
python -m scripts.novel_ladder check --out-dir /tmp/novel-ladder
```

The queue is in stable source-ID order. A blocked case stays in it, and
`next --after INDEX` advances the diagnostic cursor. Timeout and budget
cases must be diagnosed separately from true grammar misses. Upon
explicit attachment review, update the current reference with the audited
tree changes and attach a reproducible explanation to the PR. Never
overwrite the initial result to accommodate a grammar edit.

When all 100 selected parses have been reviewed and accepted, preserve
the final result as `novel-600-accepted.json`, with
`rank_one_reviewed` listing each reviewed index. The next command extends
the ladder without regenerating any prior case. Future CI checks accepted
rungs strictly and continues to report their untouched starting scores.

```sh
python -m scripts.novel_ladder freeze
```

## Novel-600 repair pass

The first repair pass reaches 100 complete trees out of 100, using the
same limits. The 22 formerly incomplete cases have attachment tests.
Five already-complete cases also had selected-tree repairs, N509, N512,
N513, N516 and N559. The 73 other initially complete trees are unchanged.
These are audited changes, not 100 independently verified analyses.

For example, N509 keeps the original subject of both coordinated verbs
and treats *then* as a sequencing modifier. N559 makes *before the fire*
locate the chair, which is the destination of the motion.

The current result records known remaining rank-one review cases. Start
with `next` for N522, where an apparent imperative breaks a comparison,
then audit N543, N566, N588 and N599. Keep this rung open while selected
trees still need review. No Novel-700 anchors have been drawn yet.
