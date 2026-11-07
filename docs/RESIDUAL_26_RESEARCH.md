# The 26 residual cases: observed failures, not 26 grammar errors

This is the living research protocol for the unchanged Gutenberg 500-case cohort.
Frozen cohort SHA-256: `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a`.
At the November 7 baseline on `main` (`3cfef10`), the parser completed
**474/500** balanced units and left **26 residuals**:

| Canonical outcome | Count | Interpretation |
|---|---:|---|
| `no_structural_root` | 8 | No full CLAUSE root was built; does **not** establish grammatical incorrectness |
| `roots_without_valid_analysis` | 13 | A root was proposed but did not yield a valid selected complete analysis |
| `forest_budget_exceeded` | 4 | Resource-censored, grammatical status **inconclusive** |
| `timeout` | 1 | Resource-censored, grammatical status **inconclusive** |

Among these 26, **7 have a structural root in their scoped dialogue attempt**
but no valid complete dialogue analysis; the ordinary fallback may still
report zero roots. These are evidence of internal dialogue recognition/
unification issues, not proof of grammatical incorrectness.

All **25 failed cases with available lexical diagnostics** had an empty
`words_without_any_candidate` list. The timed-out case #312 lacks that
diagnostic; do not extrapolate to it or assert that lexicon completeness
means the constituent structure is correct.

## Use every case as research material

The frozen 26-case baseline is stored in
[`superparser/research/residual_26_reference.json`](../superparser/research/residual_26_reference.json),
with exact case ID, canonical status, review hypothesis and evidence level.
The artifacts are produced by
[`scripts.triage_residual_26`](../superparser/scripts/triage_residual_26.py)
*after* the existing canonical 500-case parse and source-context audit.

The generated `residual_research_cases.jsonl` and
`residual_research_overview.md` preserve:

- baseline status **and current status**, including recovered historical cases;
- exact text, source/analysis distinction, semicolon source part, actual preceding
  segment and the full original sentence;
- source-context cues and lexical evidence (or explicit unavailability);
- overlapping **provisional** research tracks, not forced one-to-one diagnoses;
- surfaced **new failures** when the fixed 500-case output changes.

**Tracks overlap** and do not sum to 26: contextual fragment (4), dialogue
structure (9), finite syntax (13), discourse construction (13), genre/notation
(1), resource limitation (5) and marked agreement (2).

## Initial investigation priorities

1. **Proven marked usage versus strict absence:** #463 and #480 are pinned by
   existing marked-parser regression tests. Test that an opt-in, attested
   disagreement can be explained structurally; do not convert it to a
   sentence-level or author-intent verdict. Their marked evidence is *not*
   re-executed by the triage script.
2. **True source dependency:** #8 (continuative `which`), #94 (subject
   shared across semicolon), #182 (adjective comparison), and #194
   (nonfinite participial adjunct) are candidate discourse dependencies.
   The preceding source segment is reproduced for validation.
3. **Finite grammatical structures the parser misses:** #115 has overt
   `Dora` / `Agnes` subjects and should not be dismissed as a fragment
   merely because it follows a semicolon. #226 studies PP-fronted
   inversion; #233 studies `But when` subordination and extraposition;
   #116, #344, #347, #491 and #497 provide additional attachment and
   discourse controls.
4. **Dialogue, punctuation and genre:** #64, #96, #105, #109, #167,
   #220, #466 and the marked #463/#480. #167 is letter ending
   `Yours, etc.`, not ordinary declarative prose. Existing quote
   transfer is preserved, never silently replaced.
5. **Resource censoring, not grammar failure:** #235, #243, #248, #312
   and #487. Study budgets, search saturation and alternative ranking
   without changing the canonical 50,000/500,000/10s contract.

The full case-by-case annotated report is generated with each CI run; it
must not be mistaken for linguistic gold-standard annotation.

## P2 implementation contract

Next, build a **local constraint-evidence layer**, with explicit subject
and finite-predicate anchors, proof spans and lexical morphology.
Only an observed incompatible pair *with a defensible syntactic link* may
be called a proven conflict. A lexical sequence, quote, semicolon or
noncompletion alone can only open a **hypothesis**.

Keep recognition status, grammar conformity of the selected complete
tree, resource saturation, contextual dependency and genuine
usage deviation separate. Do not fabricate a full tree or overwrite
the source text to improve coverage.

## Reproduction

Run the existing workflow **Seman2 - Novel parse diagnostics (500 sentences)**.
Its artifact `novel-parse-diagnostics-500` includes the original reports
and the three new files: `residual_research_cases.jsonl`,
`residual_research_summary.json`, `residual_research_overview.md`.
The CI checks exact cohort checksum, 500 aligned identities and statuses,
failed-only lexicon rows, the 26 pinned original case IDs, recovery
retention and explicit appearance of newly failed cases.

## Instruments opt-in : rejets de contraintes

`Parser.parse(text, rejection_trace_limit=48)` utilise exactement le
recognizer habituel, avec une collection **bornée** d'événements de
`_LazyMaterializer`. La valeur par défaut **0** désactive toute collecte.
Les résultats d'usage standard ou marqué ne changent pas de contrat.

Le champ `stats.rejection_trace` comporte `schema`,
`observed_by_stage`, `observed_events`, `sample_limit`, `events`,
`truncated`, `exhaustive=false` et
`grammatical_fault_established=false`. Chaque événement expose
`stage`, `rule_id` le cas échéant, `category`,
`analysis_span` et éventuellement le contexte d'un enfant refusé.
Les étapes observées incluent les rejets d'unification lexicale,
de LHS des règles, les indices lexicaux/règles en k-best, et un
`child_context_exhausted` **uniquement** si le flux contextuel est
réellement épuisé (pas un cycle provisoire).

`direct_atom_conflicts` n'est rempli que pour des atomes explicitement
opposés après application des bindings **de cet essai**. Une variable
libre, un trait inconnu, une disjonction ou un enfant épuisé ne suffit
pas à conclure à un désaccord grammatical. Une alternative lexicale
rejetée peut être parfaitement normale.

L'audit canonique continue d'appeler le parseur une seule fois par
phrase, sans collecte active. **Après** la cohorte de référence,
`scripts.probe_dialogue_rejections` sélectionne les échecs où le
scope dialogue avait au moins une racine, puis rejoue uniquement ces
cas avec les mêmes budgets et le texte balancé. Il stocke
`dialogue_rejection_probes.jsonl`, `dialogue_rejection_summary.json`
et `dialogue_rejection_report.md` dans l'artefact GitHub Actions.
Le statut de ce replay diagnostique ne remplace **jamais** celui de
la première passe et un délai de replay reste censuré.
