# Whole-structure snapping: measured research findings

Research branch: `research/verbnet-left-to-right-poc`. No production parser
change, no modification to `main`.

## Hypothesis

Preserve **all one-token lexical candidate categories and syntactic features** in
Seman2's lexical lattice. Recognize a sentence by matching that lattice against
a cache of **whole grammatical derivation trees**, not by rebuilding NP/PP/VP
groups for every familiar pattern. A single lexical category sequence may
index multiple different full-tree attachments. Return one grammar-compatible
tree immediately, preserve other templates, and expose them via a paged
`template_offset` lookup for future semantic layers.

Recognition performs real `PredictiveParser._reduce` feature unification
for the chosen complete template. A lexical signature is merely an index key,
not itself a proof of grammatical validity.

## Implemented research files

- `full_structure_snap.py`: whole derivation `Structure`, categorical trie,
  provenance-aware `Template`, multi-candidate lexical matching, feature
  unification, optional fast path, deferred alternatives via template offsets.
- `packed_witness.py`: `return_compact_node=True` allows offline Earley
  witness tree extraction without changing ordinary JSON report output.
- `benchmark_verbnet_snap.py`: 50 dev training / 70 unseen
  validation-and-holdout cases with independent grammar teacher and existing
  explicit syntax assertions.
- `benchmark_snap_scale.py`: synthetic 100/1k/10k/100k identical-lexical-key
  worst-case cache scaling. **Not a natural-language corpus.**
- `test_verbnet_lr_full_structure_snap.py`: lexical ambiguity, distinct
  full-tree attachments, genuine feature rejection, provenance, budgets,
  and deferred lookup regression tests.
- Workflows: `verbnet-lr-research.yml` for real syntax benchmarking and
  `verbnet-snap-scale.yml` for isolated synthetic stress.

## Held-out syntax results (GitHub Actions 38969542939)

Corpus: `data/syntax_correctness_validation.jsonl`, 120 total;
training uses **50 dev**; testing uses **50 validation + 20 holdout**;
no held-out trees or gold labels enter the cache.

| Metric | L-R-only templates | L-R + bounded Earley teacher |
|---|---:|---:|
| Full-tree patterns in cache | 15 | **42** |
| Unseen sentence hits (any matched derivation) | 11/70 | **25/70** |
| Hits not truncated by search budgets | 6/70 | **12/70** |
| Unseen sentences with multiple matched structures | 4 | **6** |

Teacher allowed **0.35 seconds per dev sentence**, sought witnesses on all
50 dev sentences. Of these, 31 found a feature-unified Earley witness under
the construction guard; **19** had been incomplete in the L-R-only parser.
17 teacher attempts yielded UNKNOWN, and 2 category-level rejections.

Of 25 unseen sentence hits, **20** had at least one matching tree satisfying
all **explicit corpus assertions**. Only **18** had every enumerated matching
tree satisfy those assertions. This is *not* proof of unique human-intended
syntax or exhaustive correctness. The saved templates' provenance is
`candidate` or `grammar_witness`: **0 independently verified gold templates**.

Latency from that run (before newest deferred-first optimization):
- Snap lookup, warmed lattice: p50 **0.02862 ms**, p95 **0.83242 ms**.
- Snap + lexical lattice: p50 **1.25064 ms**, p95 **2.19049 ms**.
- Existing L-R baseline incl. lattice: p50 **4.40769 ms**,
  p95 **8.99582 ms**.
- THESE are separate timings; overall hybrid latency also includes L-R
  fallback after a no-hit. The newest benchmark now measures that path too.

Report: `snap_holdout_report.json` (automatically saved after successful CI).

## Synthetic cache scaling

Source: GitHub Actions **38970509444**, Python 3.12 Linux runner.

Grammar: `CLAUSE -> X`, `X -> N | X X`. The 13-token input is all `N`
and the cache holds thousands of complete but *synthetic feature-free*
binary grammar derivations with that **same exact lexical signature**.
They are not real verified language examples.

| Templates | Top-1, p50 | Top-8, p50 | Last template by offset, p50 |
|---|---:|---:|---:|
| 100 | 0.342 ms | 2.786 ms | 0.334 ms |
| 1,000 | 0.367 ms | 2.711 ms | 0.337 ms |
| 10,000 | 0.335 ms | 2.737 ms | 0.329 ms |
| **100,000** | **0.334 ms** | **2.718 ms** | **0.336 ms** |

All results include grammar unification and materialization of the requested
one or eight trees, but exclude external lexical analysis. Results explicitly
retain `incomplete=True` when additional whole-tree templates remain.

Measured process RSS at 100k synthetic templates was about **73 MB**,
including Python, grammar and generator caches. Do not extrapolate this to a
20-million-entry production store; `Structure` uses Python objects and the
synthetic generator shares many subtrees. Actual corpus distributions, Unicode,
detailed lexical features, persistence and persistence indexes all matter.

Before bounded terminal lookup, 100k entries cost **12.78 ms p50**
materializing eight trees, because every terminal ID was first enumerated.
The new capped + offset-sliced lookup avoids O(number-of-candidates) iteration.

## Architectural constraints

1. The raw lexical lattice is never overwritten by the selected structure.
2. A sentence may have several compatible whole-tree templates.
3. One valid derivation suffices for *operational* fast-path response.
   `SnapResult.incomplete` and `next_template_offset` preserve deferred
   ambiguity; there is no need to enumerate all trees within 5 ms.
4. Only grammar-licensed rule IDs from the SAME loaded grammar are applied.
   Observe must reject unsupported multiword spans instead of splitting them.
5. A grammar witness is not a gold linguistic annotation. UNKNOWN, timeout,
   lookup miss or exhausted budget never mean agrammatical.
6. Candidate templates from a completed L-R tree may be wrong despite
   successful feature unification. Strong gold labels require an independent
   authority; no automatic self-promotion.
7. This prototype does NOT yet cover multiword lexical candidates, persistence
   across processes, or production-scale 20M entry storage.

## Next experimental gates

- Validate **hybrid** end-to-end p50/p95/p99, including miss/fallback cost,
  syntax assertion agreement and negative false accepts, on unseen sentences.
- Feed many more **authentic** grammatical structures from an offline teacher,
  ideally with explicit grammatical gold; track learning curves vs 100, 1k, 10k
  unique templates rather than extrapolating from a synthetic grammar.
- Optimize missed-lattice reuse between snapping and L-R fallback.
- Evaluate packed/columnar/ID-coded shape storage and persistence before
  targeting millions of structures.
- Preserve verified alternatives as distinguishable candidate sets for layer 2;
  keep grammatical ambiguity independent of semantic plausibility.

## Final integrated guard + lexical reuse evaluation (Actions 38972058379)

This supersedes the preliminary unguarded hybrid timing above. The full
run is green. Same 50 dev training / **70 never-trained** validation+holdout
positive sentences, plus **24 separate** ungrammatical negative cases.

| Metric | L-R only | Full-tree snap + guarded L-R fallback |
|---|---:|---:|
| Completed positive sentences | 28/70 | **41/70** |
| Passes all explicitly annotated syntax checks | 22/70 | **30/70** |
| Negative sentences incorrectly accepted | **6/24** | **6/24** |
| End-to-end p50 | 4.21023 ms | **2.31628 ms** |
| End-to-end p95 | 8.58356 ms | **8.21967 ms** |
| End-to-end p99 | 9.56945 ms | **9.40980 ms** |

Positive gold case delta: **9 newly passing**, **1 previously passing
case lost** (`h003`). Do NOT label this strict nonregression. The fast
path still chooses a candidate grammatical tree without semantic context;
multiple correct-looking trees remain available for later disambiguation.
Explicit syntax assertions are incomplete, so 30/70 is not certified full
grammatical correctness.

The 24 negative cases exposed an important failure before guarding:
the unguarded snapper had **9/24 false accepts**, three more than L-R
(`neg001`, `neg005`, `neg006`), due to missing
construction/morphology checks on reconstructed `ChartItem` trees. The
existing `ConstructionGuard` now also reads `ChartItem.lexical_candidate`
and rule IDs. `SnappingResearchReader` rejects such candidates for its
fast path (without evicting templates from memory), falling back to L-R
if none survives. Result: **zero new negative false accepts** on these
24 cases, while retaining the 9 positive annotation gains.

The L-R compiled adapter can now accept an already computed identical
lexical lattice, avoiding duplicate WordNet morphology lookup when the
one-token snap index misses. This reduces miss overhead and is included
in the integrated end-to-end benchmark. The production `Parser` and
`main` have not changed.

**Not yet achieved**: 5 ms p95 (or hard worst-case bound), exhaustive
well-formed parse enumeration, representative million-template memory
or latency measurements, zero positive-gold regressions, long-sentence
syntax coverage, or human/semantic disambiguation. The offline Earley
teacher remains bounded and its grammar witnesses are NOT manually
verified linguistic gold. Never treat a timeout or UNKNOWN as invalid.

Canonical links:
- [Whole-tree index source](https://github.com/leye0/seman2/blob/research/verbnet-left-to-right-poc/superparser/research/verbnet_lr/full_structure_snap.py)
- [Holdout benchmark report](https://github.com/leye0/seman2/blob/research/verbnet-left-to-right-poc/superparser/research/verbnet_lr/snap_holdout_report.json)
- [Full integrated CI success](https://github.com/leye0/seman2/actions/runs/38972058379)
- [Synthetic scale benchmark](https://github.com/leye0/seman2/actions/runs/38970509444)
