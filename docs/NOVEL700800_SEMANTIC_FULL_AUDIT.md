# Complete selected-tree semantic review — Novel-700 and Novel-800

**Important: this is a quality assessment, not a completed grammar repair.**

The two pinned cohorts still have 100/100 **completed selected parse trees
and generated semantic graphs**, but we now have a substantive source-to-graph
verdict for each selected output. Recognition and semantic accuracy are
different measures.

## Full individual verdicts

| Cohort | Complete syntax + graph | Individually verified selected interpretation | Needs correction / blocked |
| --- | ---: | ---: | ---: |
| Frozen Novel-700 (N601–N700) | 100 | **25** | **75** |
| Exploratory Novel-800 (N701–N800) | 100 | **16** | **84** |
| **Total** | **200** | **41** | **159** |

**Unclassified selected trees: zero.** Each of the 159 blocked cases has
an index, frozen source/tree/graph signatures, a defect description, and
a targeted linguistic correction. One of these, N660, had previously been
marked `verified` but failed a new explicit negation-scope check and was
reopened rather than hiding the contradiction.

There are **42 historical signed review entries**, including N660. Thus
only **41** presently stand without a known defect. The three new reviews
of N663, N681, and N706 have their own canonical source, independent
grammatical positive, negative contrast, selected syntax and semantic graph
tests in `test_semantic_ladder_review_candidates.py`
([green tests](https://github.com/leye0/seman2/actions/runs/44183843752)).

### Why cases fail semantic verification

Examples from actual selected rank-one graph nodes and edges:

- **N629:** `AGENT(moved,as)` in *The doctor never so much as moved.*
  The doctor should be the grammatical subject, and `never` must negate
  the movement event.
- **N608:** A complex modal question generates **no semantic relation
  edges** at all.
- **N636:** `won't` is misread as `won` (win) + a negative suffix.
- **N635:** the dialectal title `cap'n` becomes a lexical verb `cap`
  and a nominal fragment.
- **N607:** Elizabeth is the mistaken RECIPIENT of `took` in
  *the hand of Elizabeth*; she is the hand's possessor.
- **N660:** *Not I!* has an unlinked negation node, contradicting an earlier
  semantic verification.
- **N655:** the original *She shook her head.* has credible local
  semantics, but an independent **ungrammatical** `He shake his head.`
  receives the same selected finite clause. The parser's agreement
  overgeneration blocks certification, even though it is not a defect of
  the original sentence's semantic roles.
- **N800:** `offer` in `offer to introduce` is selected as a noun
  instead of an independently valenced verb.

These and the remaining cases are described in the per-case reports below.

## Immutable evidence and default gate

- [Source-identified selected defects](NOVEL700800_SEMANTIC_DEFECTS.md)
- [Second pass](NOVEL700800_SEMANTIC_SECOND_PASS.md)
- [Third pass](NOVEL700800_SEMANTIC_THIRD_PASS.md)
- [Final pass and independent contrast failures](NOVEL700800_SEMANTIC_FINAL_PASS.md)
- Machine-readable `superparser/research/semantic_quality/quality-verdicts-700-800.json`:
  every N601–N800 index, its source cohort, selected root, exact selected
  syntax + graph SHA-256, verdict, evidence and required correction
- `confirmed_selected_defects.json`: the **159** outstanding blockers,
  bound to exactly the original selected tree and graph signatures
- `scripts/audit_ladder_semantic_quality.py`: verifies every one of the
  200 actual full-replay selected trees and semantic graphs, exact source
  identity and full verdict-ledger consistency; emits complete structured
  audit and refuses fake certifications
- `novel_ladder.accepted_cases`: now also reads the semantic defect
  ledger and **refuses to accept a Novel-700+ cohort with any remaining
  confirmed defect**, even if every selected parse is complete and every
  manual review entry claims `verified`.
- [Semantic audit action](https://github.com/leye0/seman2/actions):
  deliberately **red** until all issues are repaired, source/positive/negative
  controls pass, and individual selected graph reviews are updated

The original Novel-500/600 recognized source signatures, pinned Novel-700
cohort and exploratory Novel-800 input SHA have not changed. WordNet
3.0, `parse_corpus_case`, and the 50k/500k/10s limits are not increased.

## Important non-claims

- 41 presently verified interpretations are **not** 159 repaired defects.
- An automatic flag, hash match, `completed=True`, and a well-formed
  graph are not sufficient to mark a case semantically correct.
- Changing a selected graph signature does not itself clear a defect;
  a source-backed repair and independent controls are needed.
- We have **not** merged the quality-gate PR into production `main`.
  The draft must remain open until its checks are reconciled with the
  previously stacked Novel-700 and Novel-800 work.

**Next engineering step:** Fix the documented issues in source/grammar order,
starting with incorrect subject/predicate roles, negation and auxiliaries;
then re-run canonical complete cohorts and update each semantic verdict
only after an individually demonstrated correct selected tree and graph.
