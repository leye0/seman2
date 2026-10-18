# Layer 1 repository cleanup — change and preservation manifest

Date: 18 October 2026. Pre-cleanup reference: `e8322eb7fdb6ab1213c1a44f9b3d032f29d4d7a8`.
Permanent, explicitly named archive: [`archive/legacy-parsers-2026-10-18`](https://github.com/leye0/seman2/tree/archive/legacy-parsers-2026-10-18).

## Removed from the active tree

The cleanup commit `37ed781e334cca5877f9447f8e31e71f3f2474dd` removed **160 legacy executable/CI files**:

| Area | Removed | Reason |
|---|---:|---|
| GitHub Actions | 33 | Old snapping/GLR/left-to-right/hybrid pipelines and excessive duplicate CI |
| Historical `research/verbnet_lr` implementations | 24 | Compiled LR, C/hybrid, partial witnesses, snapping and separate readers, not canonical |
| Research scripts | 52 | One-off ablations, outdated benchmarks and redundant replay/snapping runs |
| Historical alternatives within `seman_parser` | 8 | Competing predictive, expectation and reading-kernel implementations and a backup file |
| Tests tied to those obsolete implementations | 43 | No longer describe the supported Layer 1 path |

**No corpus or resource deletions** were included in that 160-file cleanup. In particular, `Parser`, `VectorGrammar`, all grammatical rules, lexical alternatives, syntax/semantic interpretation and cleaned Gutenberg processing are kept. The structural-prefix risk probe remains a read-only research module, and its benchmarks no longer depend on abandoned snapping/relaxation scripts.

The commit history, not a collection of stale runnable duplicate parsers, is the definitive archive. In particular, use the named archive branch to recover experimental code or output rather than recreating approaches from memory.

## Preserved corpus/data — content SHA verified

A tree-to-tree Git blob comparison against the pre-cleanup `main` confirmed **47 protected files unchanged (47/47)**. This includes `data/`, `superparser/data/`, the cleaned-novel corpus and the corpus loading/cleaning utilities.

| Cleaned novel | Git blob ID |
|---|---|
| `david_copperfield_766.txt` | `a2014e83c76ed27f187976f0fa14b5a4ea679ed5` |
| `pride_and_prejudice_1342.txt` | `a5a0e0026cf14130b9fa3d8ee45d9dbf451df1cc` |
| `frankenstein_84.txt` | `d48b9e881b583c2ce36bc747ebd8df3c19a46582` |
| `treasure_island_120.txt` | `ab18d4971b820ae1742b53c2d84a81b746bbc25b` |

**Wikipedia corpus:** no filename containing wiki/Wikipedia/Wikidata was present in the tracked repository tree at the reference revision. Previous discussions concerned an English Wikipedia corpus, but never established a concrete local tracked path. Therefore we have neither deleted nor migrated a wiki dataset. Find and register its actual storage location before any future data cleanup. Do not infer that its absence from this Git tree means the corpus does not exist elsewhere.

## New tests, checks and scope

- Layer 1 output contract now tests original surface spans, lexical lattice retention, syntax serialization and post-parse semantic interpretation.
- `WORDNET_DICT` is an explicit supported resource path (and tests no longer assume one developer's `.local` directory).
- Regular CI tests the current canonical parser and corpus; the expensive 256-sentence risk audit is **manual**. The direct-grammar validation remains a distinct quality gate.
- Current architecture and outstanding limitations are recorded in [`ARCHITECTURE_LAYER1.md`](ARCHITECTURE_LAYER1.md) and [`KNOWN_LIMITS_AND_ROADMAP.md`](KNOWN_LIMITS_AND_ROADMAP.md), with negative research findings in [`RESEARCH_HISTORY_AND_DECISIONS.md`](RESEARCH_HISTORY_AND_DECISIONS.md).

### Still outside this cleanup

`archives/` and `research/induction/` were deliberately left untouched: they are historical material and future downstream-learning research, not verified Layer 1 replacements. Additional old root-level POCs and experimental reports were not removed by the validated 160-file change. They remain historical clutter for a separate, explicitly scoped review; do not claim the entire repository contains only the canonical parser.
