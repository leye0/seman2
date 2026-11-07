# Instrumenting unification rejection without declaring grammar errors

The public parse gateway offers an **opt-in**, bounded
`rejection_trace_limit` in the range 0–100. Default 0 is an unchanged
fast path; debug requests bypass the parse cache and are **not**
canonical 500-case measurements.

`stats.rejection_trace` and, when a failed scoped dialogue was attempted,
`stats.dialogue_attempt.rejection_trace` provide a sample of attempted
derivations rejected in the lazy k-best materializer.

- `lexical_unification` and `rule_lhs_unification`: actual unifier
  returned no result at the lexical or rule interface.
- `lexical_hint_unification` and `rule_hint_unification`: a constrained
  k-best bound was incompatible, **not** an executed full derivation.
- `child_context_exhausted`: a particular constrained child stream was
  actually exhausted; this is **not** an observed direct feature mismatch.
- `interface_unification`: segmented interface candidate rejected.

Each event retains the requested/category span, `rule_id` if available,
the requested/offered raw feature structures, and any directly
contradictory **atomic** feature pair after bound substitution. Those
atoms prove incompatibility **of that one attempted pair only**.
Open-world missing values, unbound variables, disjunctions, lexical
ambiguities and structural constraints must not be reinterpreted as
a grammatical fault. Sampling is per-stage and globally bounded;
`observed_events` can exceed the number of retained samples.

Research workflow: after the unchanged single-pass fixed 500-case
evaluation and its source-context triage, the separate
`scripts.probe_dialogue_rejections` replay selects canonical failures
where `dialogue_attempt.structural_root_nodes > 0`. It checks that
all 500 source records and the pinned cohort checksum align, and
replays only the selected dialogue cases through
`parse_corpus_case` and `Parser.parse` using their original
quote-balanced analysis text, the same 50,000/500,000 budgets, and
an independent 10-second wall deadline.

Output in the workflow artifact:
`dialogue_rejection_probes.jsonl`,
`dialogue_rejection_summary.json`,
`dialogue_rejection_report.md`. An independent replay may time out or
differ from the canonical pass; it never changes the original status.
No complete parse tree is fabricated, and no possible grammatical
violation is inferred from a failed parse alone.

This is the **first research instrument**, not yet a complete causal
explainer or a proof-licensed local anomaly detector.

## Source coordinates

The independent replay report retains original `analysis_span` coordinates,
then maps `reference_span` (and child spans) with
`PreparedCorpusInput.reference_span`. Mapping is `exact` only for
characters in the original frozen case; synthetic quotation delimiters
or unavailable regions are `null` with `reference_span_mapping=unavailable`.
No offset is inferred from token order or from source neighbors.
