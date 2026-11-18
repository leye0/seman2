# Novel-700 / 800 — final semantic repair pass

Starting point: `57fd22f8045d781f47e37c86198039b0f2ddbdf9`
([previous pass](NOVEL700800_SEMANTIC_BATCH4.md)).

| Cohort | Complete selected outputs | Verified before → after | Still open |
| --- | ---: | ---: | ---: |
| Novel-700 | 100 | 83 → 100 | 0 |
| Exploratory Novel-800 | 100 | 74 → 100 | 0 |
| Total | 200 | **157 → 200** | **0** |

The last 43 cases have independent source-level verification. Forty-two
selected trees and graphs changed, and the 157 earlier verified signatures
are identical. N655 keeps its correct original selected tree and graph.
Its blocker was an independent ungrammatical contrast, not another
attachment in its original sentence.

## Representative corrections

- **N620 and N674** keep the antecedents and subjects distinct in pairs
  of relative clauses. In N620 the elapsed days belong to *during which*,
  Strasbourg belongs to *where*, and Clerval is the person awaited.
- **N675** keeps *hadn’t* on the original span as the negative perfect
  auxiliary of *said*. *I* is the subject of *said*. The separate
  *rather not* ellipsis has its own scope.
- **N746 and N750** keep different kinds of gaps. The boat is the object
  of *brought* and the predicand of *handier*. In N750, the coldest
  *morning* is the antecedent of the stranded *in*.
- **N771 and N798** keep ownership and predication separate. The hand
  absolutes share a single partitive set. In N798, *here* and *so very
  often* belong inside *his coming*, the complement of *discourage*.
- **N774** keeps *page* in its historical attendant sense and treats
  *six pounds ten per annum* as a rate. The source numeral *ten* is
  classified as the implied shilling supplement, with no fabricated word.
- **N655** rejects *He shake his head* and an independent *take* contrast.
  The lexical paradigm marks only documented nonpast bare stems, and
  finite materialization and root selection preserve that constraint.
  *Shook*, *shakes*, plural *shake*, modal *shake* and invariant past
  *cut* remain valid.

The [case fixtures](../superparser/tests/data/semantic_batch5_controls.json)
contain the selected source attachments and the independent positive and
negative controls for the 42 replaced analyses. N655 has a separate
[morphology test](../superparser/tests/test_semantic_ladder_review_candidates.py).
All gates still use the original corpus spans, constituent proofs, WordNet
3.0 and the existing parser. Candidate selection and source text did
not change.

## Certification scope

The auditor derives the certification state from the complete replay and
the verified reviews, then checks it against the saved state. No source
fingerprint, selected digest check, per-case evidence check, conflict,
unreviewed case or defect criterion is bypassed. The gate passes for these
two cohorts with 200 individually reviewed analyses and no open defects.

Novel-500 retains the ordered pinned syntax and budget fingerprint and
all 30 anchored dialogues. Novel-600 retains all 100 accepted syntax and
semantic signatures. All 103 focused tests passed. The caps remain 50,000 chart items,
500,000 k-best units and ten seconds per case. Seven repaired cases
no longer hit the chart cap, and no new limit was reached. The direct grammar checks retain
120/120 gold annotations and 24/24 grammatical contrasts, with the same
nine already known negative false accepts. This is certification of
these source cohorts, not a claim of unrestricted English coverage.
