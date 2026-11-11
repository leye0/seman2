# Prose segmentation v2 — dependent continuations and quoted coordination

## Why this exists

The historical corpus extractor splits at **every** semicolon. In David
Copperfield (Gutenberg 766), it turned:

> I could do no less, under these circumstances, than make Mr. Micawber known
> to Uriah Heep and his mother; which I accordingly did.

into an independent analysis case, `which I accordingly did.`. That fragment
has no independent antecedent: *which* is a supplementary relative referring
back to the preceding action. The orphan may fail parsing even if the complete
grammar can eventually represent the construction.

The same structural issue affects explicitly subordinate continuations
(`although`, `because`, `while`, `when`, `if`, etc.). This is an error of
**analysis-unit selection**, not automatically a missing grammatical rule.

Three further examples were verified against the *original contiguous*
Gutenberg text (not only the already-split 500-case sample):

| Frozen case | Source construction | Dependency lost by the v1 split |
| --- | --- | --- |
| 94, *David Copperfield* | `She gently chid me ...; and, keeping me close ..., turned to thank ...` | `chid` and `turned` share the subject `She`; the participial insertion does not introduce another subject. |
| 182, *Pride and Prejudice* | `He found her as handsome ...; as good natured, and as unaffected ...` | The parallel comparative adjectives share the matrix predicate `found her`. |
| 194, *Pride and Prejudice* | `They paid little attention; avoiding ..., saying ..., and nothing ...` | The nonfinite participial series modifies the preceding finite clause. |

V2 now protects these three narrowly identifiable constructions too. The
test suite includes near-matches containing an overt subject after a comma
(`and, keeping ..., she turned`; `walking ..., Mary left`), which **must**
remain independent. This avoids simply coalescing every clause beginning
with a conjunction, a comparison, or an `-ing` form.

## Quoted exclamation/question before shared-subject coordination

A separate case, frozen Dickens **64**, has the contiguous source:

> Mr. Creakle whispered, ‘Hah! What’s this?’ and bent his eyes upon me, as if he would have burnt me up with them.

The v1 sentence splitter cuts after `Hah!` while still inside the quote.
Consequently, `and bent` is analyzed without the shared overt subject.
Opt-in v2 now recognizes only a **narrow** continuation: after a potential
`!` or `?` boundary **inside an open quote**, exactly one following
quoted complete sentence must reach the closing quote, and the next
outside-quote word must be `and`, `but`, or `or`.
In that case it keeps the two quoted utterances and the coordinated
predicates together.

This rule is enabled via `preserve_quoted_coordination` only in the v2
`preserve_dependent_continuations` path; default v1 extraction and
historical boundaries remain untouched. Regression controls include another
quoted question + shared-subject coordination, independent quoted speech
followed by another sentence, non-coordinated quotes, and exact source
round trips. The v2 case is reconstructed through `extract(...,
segmentation_version=2)` and `parse_corpus_case`, **not** by feeding a
hand-edited fragment directly to the grammar.

Actions [42950058760](https://github.com/leye0/seman2/actions/runs/42950058760)
and [42950284824](https://github.com/leye0/seman2/actions/runs/42950284824)
confirmed the joined unit, 31 boundary/provenance tests, and 7 independent
parser probes. A complete tree exists under original budgets, but its
`upon me`, `as if`, and interjection attachments are wrong in the
top-three trees. See [CASE_64_QUOTED_SHARED_SUBJECT.md](CASE_64_QUOTED_SHARED_SUBJECT.md).
**No case64 grammar resolution or 500-case gain is claimed.**

## Nested quotation followed by a causal aside (frozen case 105)

In *David Copperfield* the source is a **single reported-speech construction**:

> ‘Says Em’ly, “Martha, is it you? Oh, Martha, can it be you?”--for they had sat at work together, many a day, at Mr. Omer’s.’

Historical v1 splits **after the first internal question**. The resulting
second unit, `Oh, Martha, can it be you?”--for ...`, has lost the opening
reported-speech clause and is a poor target for autonomous grammatical
analysis. The previous v2 quoted-continuation rule recognized coordination
(`and/but/or`) after a quote, not a dash-led causal explanation.

V2 now also keeps the whole construction when an open quote contains **exactly
one following complete quoted sentence**, which reaches that quote's closing
delimiter and is immediately followed by `--for`, `—for`, `–for` or a
corresponding `because` explanation. This requires both **quote-stack
evidence** and **source punctuation**; it is not a word-specific exception
for *Martha* or *Dickens*. Distinct narrative sentences without this
continuation still split normally; `--fortunately` and `--forgone` are not
causal markers.

The test for case 105 compares the **exact v1 two-unit source split** with
the **v2 one-unit source** and the full `extract(...,
segmentation_version=2)` quote-balanced provenance, plus two independent
positives and adverse contrasts. The 500-case SHA, ordinals and reference
scores **are unchanged**. This addresses the extraction defect; it
does **not** by itself prove the larger v2 sentence has a grammatical
rank-1 parse.

## Versioned behavior

- **v1 (historical, default in corpus extraction):** split at every
  semicolon. This preserves the frozen 500-case cohort, ordinals and SHA.
- **v2 (opt-in in corpus extraction; default for direct prose segmentation):**
  preserve the semicolon when the following segment clearly begins a
  supplementary `which`-relative or a subordinate clause. A direct
  `which … ?` / `when … ?` question is not merged. Semicolons introducing
  ordinary independent clauses still split. Subordinate-fronted *complete*
  sentences such as `when she arrived, I left` also remain independent.
  Attested shared-subject predicate coordination, comparative lists, and
  nonfinite participial lists are additionally retained when their
  structural cues are present. In a quoted multi-sentence utterance followed
  by external predicate coordination, v2 also retains a narrowly verified
  internal exclamation/question boundary.
- **Quotation balancing:** unchanged. The same quote stack, synthetic
  prefix/suffix, synthetic terminal, and original `source_text` are used.
  A semicolon retained in the unit remains a literal source character;
  `semicolon_split` indicates whether a cut actually occurred.

The version is explicit when extracting a *new* corpus:

```python
from research.verbnet_lr.gutenberg_novels import Book, extract

cases, counts = extract(
    Book(766, "David Copperfield", "Charles Dickens", "train"),
    cleaned_novel_text,
    segmentation_version=2,
)
```

Each v2 eligible case records `segmentation_version=2`. The v1 fields and
case selection stay unchanged. To analyze an extracted case, always use
`corpus_pipeline.parse_corpus_case(parser, case)`, which applies the recorded
quote-balanced input. No alternate parser entry point is introduced.

## What this does *not* prove

Keeping the entire relative construction together **does not establish** that
the parser finds a complete, correctly attached tree. Its grammar must still
recognize the sentential relative and its antecedent. Longer v2 units may also
be excluded by the existing token-length selection window; extraction counts
must be compared between v1/v2 before claiming a change in grammar quality.

The current decision rules deliberately favor high-confidence subordination
markers over broad assumptions about conjunctions, noun lists and prose
parentheticals. Future changes should:

1. Record before/after unit counts and exact source round-trips on a held-out
   corpus, including how many units are too long or remain fragments.
2. Add positive examples and adverse counterexamples for any new boundary cue.
3. Evaluate parser completeness **and correct attachment** via the standard
   `parse_corpus_case` gateway, without modifying the frozen 500-case score.

Regression tests: `superparser/tests/test_sentence_boundaries.py`.
