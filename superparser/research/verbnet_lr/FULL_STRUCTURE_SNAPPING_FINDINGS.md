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

## Latest: authentic EWT train learning curve and 10% offline sampling

Experiment workflow SUCCESS: [Actions #38974747805](https://github.com/leye0/seman2/actions/runs/38974747805), commit `1c2283b`.
Separate pinned UD English-EWT **TRAIN** sentences (selection by SHA256
sentence ID; 4–18 tokenizer tokens; ASCII, de-duplicated; all Seman2
validation/holdout/negative/contrast texts excluded). 600 **authentic
sentences** were ingested into two indexes from the same 50 DEV seed:
one queried bounded Earley on all 600, the other on **60/600 (10%)**
using the explicit offline sampling queue. Evaluations and negative
tests were NEVER used as cache training observations.

| Additional external observations | Full teacher cache | 10% teacher cache |
|---|---:|---:|
| 0 | 42 whole trees | 41 whole trees |
| 100 | 54 | 42 |
| 300 | 77 | 45 |
| 600 | **106** | **48** |
| Held-out Seman2 hits / 70 after 600 | **27** | **25** |
| Positive explicit-gold passes / 70 | 30 | 30 |
| Grammatical negative false accepts / 24 | **8** | **7** |

The all-sentence teacher found 65 witnesses / 600 (plus 236 UNKNOWN
and 299 category-rejected under limited grammar/budget). The sampled
queue verified 60 sentences, found 7 grammar witnesses, and recorded
53 unknown/rejected; no queue overflow.

**Interpretation:** For this corpus pair, a larger whole-tree dictionary
barely raises held-out coverage and can amplify existing grammar
overacceptance. Neither 10% nor 100% external training meets a strict
zero-new-false-accept safety gate. DO NOT promote these additional
EWT-derived templates to default parsing, or assert the architecture
scales to millions of **useful** natural-language patterns. The
tenth-sentence method reduces teacher executions by 90% but may also
miss rarer productive forms. The experiment shows no improvement in
explicit positive-gold accuracy from the EWT extension.

The queue lives in
`research/verbnet_lr/sampled_teacher.py`.
`SnappingResearchReader(..., sampler=queue)` only enqueues one of every
ten incoming parse events; it NEVER runs Earley synchronously. An
explicit `queue.drain_teacher(index, max_cases=N)` external worker
does bounded verification, marking successful trees
`grammar_witness` (NOT gold). Without such a worker, queued observations
do not improve the cache. The pending queue is memory bounded.
This is an opt-in research prototype, not an active background task or
the production Seman2 parser.

Report: [authentic-syntax-learning-report.zip](https://github.com/leye0/seman2/actions/runs/38974747805/artifacts/12078226870).

## Corrected fair-seed learning experiment and h003 structural ranking

The original 10%-sampling experiment seeded one fewer full tree in the
sampled cache due to re-reading a ranked derivation rather than copying the
actual teacher witness. Corrected at `2d8ef4e`: both indexes now start
with exactly **42 identical full structures**, confirmed by an assertion
against their full derivation maps and provenance counts.

The follow-up syntactic ranking study on h003
(`Thomas offered Rachel a seat.`) identified THREE complete snapped
trees. The first was a **bounded Earley witness** with
`clause_np_coord_aux_adv` at score **8.02**, and it FAILED
the annotated `vp_ditransitive` requirement. A different complete
candidate was `clause_np_vp`, scored **16** and PASSED every explicit
annotation, including `vp_ditransitive`. The teacher therefore proved
grammatical *existence* without proving the *preferred structure*.
The index now orders complete matches by the grammar + lexical score
ahead of mere Earley witness provenance, preserves every alternative,
and does not look at holdout annotations to rank at runtime.
Regression tests enforce that a lower-scored witness cannot override a
higher-scored eligible tree.

With this source-generic ranking rule, the latest independent learning
curve ([Actions #38975334358](https://github.com/leye0/seman2/actions/runs/38975334358))
has:

| External real EWT train observations | All-teacher patterns | 10% patterns | Positive syntax assertion passes on 70 | Negative false accepts on 24 (all / 10%) |
|---|---:|---:|---:|---:|
| 0 | 42 | 42 | 31 | 6 / 6 |
| 100 | 53 | 43 | 31 | 7 / 7 |
| 300 | 76 | 46 | 31 | 7 / 7 |
| 600 | 106 | 49 | 31 | **8 / 7** |

The syntax assertions are still partial human-provided checks, not
comprehensive linguistic gold. 600 authentic extra observations yield
at most **2 extra test hits** (27 vs initial 25), but ZERO additional
positive syntax assertion passes and 1–2 additional negative false
accepts. Neither external expansion clears the no-new-negative gate.
Do NOT turn on expanded EWT-derived patterns by default; first improve
teacher-side grammatical constraints or require stronger verification.

Only one of ten selected external sentences is sent to Earley in the
sampling version, with a fixed queue budget and explicit offline drains.
There is NO implicit background verifier and no production parser change.

## Definitive no-lost-positive-gold result after score-first ranking

Full research workflow green: [Actions #38975292898](https://github.com/leye0/seman2/actions/runs/38975292898).
Saved reproducible report: snap_holdout_report.json.

| Held-out metric (70 Seman2 sentences) | L-R | Guarded snap+L-R |
|---|---:|---:|
| Completed analyses | 28 | 41 |
| Passed all annotated syntax checks | 22 | **31** |
| New annotated-gold passes | — | **9** |
| Annotated-gold passes lost | — | **0** |
| Incorrect sentences accepted / 24 negatives | 6 | **6** |
| End-to-end p50 | 4.53143 ms | **2.63944 ms** |
| End-to-end p95 | 8.82181 ms | **8.41763 ms** |
| End-to-end p99 | 11.06915 ms | **9.10768 ms** |

The formerly regressing h003 now selects the annotated clause_np_vp
complete tree with vp_ditransitive, score **16**. Its other grammatical
alternatives at scores **13** and **8.02** remain available for layer 2.
The bounded Earley-witness structure at score 8.02 is NOT privileged
simply for being recognized by an independent grammar algorithm.

Quality improved on this SMALL FIXED test set, but 9 gained/0 lost is
not a population-level guarantee; p95 8.42 ms does not meet the 5 ms
worst-case objective. 13/25 matched sentences still had truncated
lexical-variant exploration and must preserve an incompleteness marker.

For authentic EWT expansion, see Actions #38975334358: both caches
start with identical 42 DEV templates, then at 600 EWT train sentences
contain 106 (all-teacher) vs 49 (10%-teacher). Neither improved 31/70
explicit positive-gold syntax cases and negative false acceptance rose
to 8/24 and 7/24, respectively. Hence NO default deployment of newly
EWT-trained templates until improved grammar checking. The initial
42-template DEV cache remains the better-supported experimental mode.

All modifications remain research-only on research/verbnet-left-to-right-poc.
Production Parser and main are untouched.
