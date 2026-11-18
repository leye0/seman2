# Novel-1000 — source-first exploratory extension

## Scope and status

This research branch extends source sampling from Novel-800 to
Novel-900 (N801–N900) and Novel-1000 (N901–N1000), **200 new cases**.
It is stacked on PR #100, where the exact N601–N800 selected syntax and
semantic graphs are individually verified. It does not merge or silently
promote the still-exploratory Novel-800 into the production ladder.

**A new complete parse is not a verified semantic analysis.**
N900/N1000 first-pass results start with zero independently verified
cases, even if parsing produces a complete rank-one tree. Their original
source identity and initial selected signatures are immutable baselines,
not accuracy claims.

## Deterministic source selection

- The same four cleaned Gutenberg book editions as Novel-500 through
  Novel-800; the legacy Novel-500 source fingerprint is preserved.
- Exactly 100 new cases per rung, 25 per book and 25 per length band.
- No reused source paragraph or normalized text identity from any of
  the first 800 cases or the other new cohort.
- Identical source-only hash-ranking policy, fixed original book offsets,
  paragraph IDs and source SHA-256. Grammar and parse results never
  influence selection; no synthetic quote or punctuation repair.
- Always use the canonical parse_corpus_case gateway through the
  existing parser and measure routine. WordNet 3.0, 50,000 chart items,
  500,000 k-best work units and 10 seconds per case are unchanged.

The hosted workflow writes N900/N1000 candidate cohort manifests and
initial parse results to
superparser/research/novel_1000_exploration/.
It rejects changed source manifests or initial selected-result
fingerprints on reruns. Source-backed review files begin empty.

## Running locally

From repository root:

    export PYTHONPATH=superparser
    python -m unittest -q superparser.tests.test_novel1000_exploratory
    python -m scripts.novel1000_exploratory stage
    python -m scripts.novel1000_exploratory run \
      --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel1000-baseline

Stage checks the predecessor N600/N700 evidence and all 100
source-bound N800 reviews, then freezes both new candidate source sets.
Run emits per-case JSONL, selected tree/semantic graph hashes, real
coverage counts and the diagnostic baseline. No review is fabricated.

## Hosted regression contract

The workflow .github/workflows/novel-900-1000-exploratory.yml
runs selection invariants, earlier N600/N700/N800 replays, the
complete N700/N800 semantic gate, the N900/N1000 initial passes,
the N500 fingerprint and 30 real dialogues, and direct grammar
positive/negative controls. It saves an artifact and commits the
new source pins and baseline only after all gates pass.

**Neither new cohort is advertised as 100/100 correct semantics.**

## Next acceptance steps

Inspect the original contiguous source paragraph, typed constituents,
rank-one syntax and actual semantic graph for each case. Preserve
unresolved source dependencies, never invent antecedents. Each repair
requires an independent positive and negative attachment contrast,
plus the full fixed-cohort regression comparison.

Only 100 verified case-level syntax + semantic verdicts can qualify a
rung for acceptance. Promotion must be sequential: Novel-800, then
Novel-900, then Novel-1000. Until then these are candidates, not
production ladder rungs.
