# Novel-900 / Novel-1000 — immutable exploratory first-pass baseline

Hosted run: https://github.com/leye0/seman2/actions/runs/44234214727
(complete and successful). This is **recognition coverage**, not certified
attachment or semantic accuracy. Every new candidate review register is
initially empty; zero of the 200 new cases is independently verified.

## Pinned source identities

- Novel-900: N801–N900, cohort SHA-256
  9cd8d748ba82640c90feb9e2bb13908b1b51658bcf5f8330b934f2ac59b87f78
- Novel-1000: N901–N1000, cohort SHA-256
  c1f12a2349db846d73618baa4927a75754e90073f15b174d780d9cac19815ad2
- Each cohort includes exactly 100 previously unseen source paragraphs:
  25 per source edition and 25 per 4–8, 9–16, 17–24, 25–32 token band.
- Canonical original cleaned-source offsets and text hashes, no synthetic
  quotation marks or punctuation, no parse-dependent resampling.
- Same shared parser, canonical parse_corpus_case gateway, WordNet 3.0,
  50k chart states, 500k k-best work units and 10 seconds per source.

## First-pass selected output

| Diagnostic status | Novel-900 | Novel-1000 | Total |
| --- | ---: | ---: | ---: |
| Complete selected syntax + graph | **84** | **76** | **160** |
| Roots but no valid selected analysis | 10 | 16 | 26 |
| No structural root | 3 | 6 | 9 |
| Forest budget exceeded without completion | 2 | 1 | 3 |
| Timeout | 1 | 1 | 2 |
| **Source cases** | **100** | **100** | **200** |
| Independently verified semantics | **0** | **0** | **0** |

First-pass results and immutable pins are in
superparser/research/novel_1000_exploration/. Full source text, parse
diagnostics, selected trees and semantic graphs are in the hosted run's
novel900-1000-frozen-source-baseline artifact. The artifact includes
per-case manifests and previous-rung semantic audit evidence.

### Open N900 cases by failure class

- No selected unified analysis: N813, N814, N815, N827, N845, N869,
  N885, N890, N898, N900.
- No structural root: N830, N837, N839.
- Forest ceiling: N872, N899.
- Deadline: N820.

### Open N1000 cases by failure class

- No selected unified analysis: N911, N937, N943, N944, N946, N952,
  N961, N962, N964, N965, N970, N974, N984, N990, N993, N1000.
- No structural root: N907, N919, N960, N981, N992, N996.
- Forest ceiling: N950.
- Deadline: N918.

These classifications describe the parser's current result. Resource
saturation or timeout is explicitly inconclusive, not evidence that a
grammatical construction is unsupported.

## Initial source-based triage

1. **Short non-clausal documentary material**: N830 is exactly
   "J. T."; N907 is "Walton, in continuation." Both require checking
   source context and descriptive function before any grammar rule.
2. **Quoted minor and intercalated dialogue**: N813 ("Are you mad,
   my friend?" said he.), N814, N837 ("Si-lence!"), N890, N943,
   N946, N960, N962, N965, N981, N992, N993 and N996 should be
   examined for original quotation spans, reporting tags, vocatives,
   repairs and genuine ellipsis. N981 is "What, none of you?".
3. **Clause links and long-range attachment**: N839 has a fronted
   conditional; N919 combines an imperative, a source semicolon,
   negative inversion and comparison; N990 has a semicolon and a
   passive; N1000 has a semicolon, a relative clause and a stranded
   preposition. No semicolon may be split into a new extraction unit.
4. **Nonfinite and contextual constructions**: N827 is the attested
   fragment "No sooner thought upon than done."; N885 has a reduced
   participial modifier; N898 contains "from whence"; N937 coordinates
   motion and depictions; N964 has a reflexive event modifier.
5. **Independent resource diagnostics**: N820 and N918 timed out;
   N872, N899 and N950 hit the forest ceiling without selecting a
   complete analysis. Keep original caps while testing focused
   root/attachment hypotheses.

These are **triage leads, not source-verified repair verdicts**.
For every case, inspect its original contiguous paragraph and typed
constituents first. Match a corrected rank-one selected tree and
semantic-graph edges to the exact source, add independent positive
and matched negative controls, and rerun all 1,000 protected cases.
A source case that remains incomplete must not be called verified.

## Protected regression result

The same successful workflow preserved:

- Novel-500 ordered diagnostic fingerprint and 30 source-bound real
  dialogues;
- Novel-600 and Novel-700 frozen syntax and semantic signatures;
- The complete source-bound Novel-700/800 semantic quality gate;
- Direct grammar and independent negative-control checks.

No earlier cohort was resampled, no resource limit was increased,
and no candidate was accepted solely because a full-span tree exists.
