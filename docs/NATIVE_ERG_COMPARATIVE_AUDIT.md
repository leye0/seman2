# Native ERG versus historical Seman2 — exploratory relation audit, 2026-11-26

## Reproducibility and limits

- ERG native artifact [run 45756780706](https://github.com/leye0/seman2/actions/runs/45756780706), commit 6a4f38c3df4857eeb4e52c53412e9c9da678ec08.
- Historical Seman2 artifact [run 44411552227](https://github.com/leye0/seman2/actions/runs/44411552227), commit be72ff25205b07acf5cccaea42e37dc915eb069d. This is the historical V3 baseline, not a new replay of current main.
- Same 1,000 case IDs and identical analysis text character for character; manifest SHA-256 93bb915a30a956fef8c465a7dd684e57cfd2b2866f225409c9fd4686d0b2e5af.
- Sample: first 30 case IDs sorted by SHA-256 of UTF-8 "blind-audit-v1:" + case_id. No prediction-based case exclusions. 75 relations selected from source text before inspecting predictions for the sampled cases; a nonsampled case was inspected earlier to determine formats. Single model annotator/adjudicator, not an independently expert-reviewed blind evaluation. No claim of statistical significance or complete sentence accuracy.
- Compare selected Seman2 semantic graph against native MRS predicate arguments, allowing transparent copular bridges, coordination, and aspectual raising. Broad target relation and argument attachment, not sense/role-label equivalence; do not award a patient coded as agent, or a merely quoted token. Absent explicit relation is a miss; do not infer control from lexical world knowledge alone. An ERG no-result case counts as all misses. This is not LAS, precision, or a full semantic graph audit. Alternative score is per relation (not necessarily the same parse for all targets).
- Manual adjudication is preliminary; retain every row for revision by independent reviewers. The source text, MRS and graphs are available in the original archives.

## Scores

| Metric | Correct | Total | Rate |
|---|---:|---:|---:|
| Seman2 historical selected graph | 54 | 75 | 72.00% |
| ERG first returned analysis | 64 | 75 | 85.33% |
| ERG any of first ten, per relation | 67 | 75 | 89.33% |
| All sampled targets correct on one first analysis, Seman2 | 15 | 30 | 50.00% |
| All sampled targets correct on one first analysis, ERG | 23 | 30 | 76.67% |

Full-corpus diagnostic: 957/1000 returned an MRS and derivation, 43 no result. 164 top-ranked outputs contain an exact MRS predicate named fw_seq, quoted or unknown; 107 passages have at least one of those markers in every returned result. This is a flag for inspection, not proof that the whole output is unusable. Unknown lexical predicates with a POS subtype are distinct and not counted by this diagnostic. Sum of per-source elapsed times 569.94 seconds; median 0.184 seconds. ACE stderr reports memory-limit termination/unpacking in the run but does not associate each warning with a source. Do not call the 43 failures grammar gaps without further work.

## Case-level audit ledger

S = 1 supported, 0 not supported; ERG = first supported rank, 0 not found. Values correspond in order to listed targets. These are manual judgments, not an automatic evaluation.

| Case | Targets | S | ERG rank |
|---|---|---|---|
| Q3-203 | reflected/she subject; increased/astonishment patient | 1,0 | 1,1 |
| Q3-671 | occupied/I passive patient; revival/regrets theme | 1,1 | 0,0 |
| Q3-366 | resolved/I subject; sail/I controlled subject; procure/nourishment object | 1,0,1 | 1,1,1 |
| Q3-287 | son/Henry Clerval predication; merchant/Geneva nominal attachment | 1,1 | 1,1 |
| Q3-697 | fortunate/ladies predication; wore/coat object; rode/horse object | 1,1,1 | 1,1,1 |
| Q3-3 | felt/I subject; felt/it object; sorely/felt modifier | 1,1,1 | 1,1,1 |
| Q3-485 | growling/he controlled subject; crawled/he subject; hoist/himself object | 0,1,0 | 0,1,1 |
| Q3-968 | said/I speaker (reporting clause); lawyer/you predication | 1,0 | 1,1 |
| Q3-378 | murmured/he speaker; done/me object | 1,1 | 1,1 |
| Q3-465 | say/I speaker (question); come/good subject | 0,0 | 0,0 |
| Q3-130 | wish/I subject; may/it modal ellipsis | 1,1 | 1,1 |
| Q3-102 | burnt/face, neck, and hands coordinated patient; unaccustomed/exposure modifier | 0,0 | 1,1 |
| Q3-380 | cried/squire speaker; heard/him prepositional complement | 1,0 | 1,2 |
| Q3-86 | glanced/Dora subject; wistfully/glanced modifier; hinted/Dora subject | 1,0,0 | 1,1,1 |
| Q3-611 | quitted/I subject; quitted/country object/source attachment; native/country modifier | 1,1,1 | 1,1,1 |
| Q3-840 | said/mother speaker; take/money object; faint/I subject | 1,1,0 | 1,1,1 |
| Q3-41 | said/I subject; thought/I subject; ashamed/they predication | 1,0,0 | 1,1,1 |
| Q3-208 | said/Elizabeth subject; gratified/her object; exceedingly/gratified modifier | 1,1,1 | 1,1,1 |
| Q3-799 | observe/Elizabeth controlled subject; delightful/friend modifier; checked/herself object | 1,1,1 | 1,1,1 |
| Q3-225 | awake/He predication; closed/He subject; unconsciously/closed modifier | 0,0,1 | 1,1,1 |
| Q3-131 | silent/He predication | 1 | 1 |
| Q3-767 | looked/He subject; steadily/looked modifier; made/sign object | 1,1,1 | 1,1,1 |
| Q3-149 | distressed/Jane predication/patient | 1 | 1 |
| Q3-319 | attained/I subject; resolved/parents subject; student/I predication (second I) | 1,1,0 | 1,1,2 |
| Q3-199 | friendly/farewell predication; perfectly/friendly modifier | 0,1 | 1,1 |
| Q3-40 | said/master speaker; quit/I predication attachment (not lexical sense) | 1,0 | 1,2 |
| Q3-517 | finished/being subject (aspectual raising accepted); fixed/being subject; fixed/looks object | 1,1,1 | 1,1,1 |
| Q3-116 | muffled/Dora subject; shut/Dora subject; reported/aunt patient | 1,1,1 | 1,1,1 |
| Q3-363 | enjoyed/I subject; enjoyed/scene object; embittered/enjoyment patient | 1,1,1 | 1,1,1 |
| Q3-356 | struggled/she subject; collected/she subject; audible/voice modifier | 1,1,0 | 0,0,0 |

### Counterexamples and decisions

- Q3-86: ERG first MRS _glance_v_at ARG1 Dora, _wistfully/RB_u_unknown ARG1 glanced, _hint_v_to ARG1 Dora. Seman2's selected graph has glanced/AGENT/Dora but neither modifier nor shared subject for hinted.
- Q3-203: Seman2 assigns increased/AGENT/astonishment alongside increased/AGENT/review. ERG top MRS has review ARG1 and astonishment ARG2 of _increase_v_cause.
- Q3-380: first ERG result represents "Heard of him!" as unknown content; rank 2 has _hear_v_of ARG2 him.
- Q3-465: ERG has fw_seq/quoted in all ten; no targeted internal relation, and Seman2 only emits good/NEGATIVE_QUANTIFIER/No.
- Q3-671 and Q3-356: ERG no result, Seman2 explicitly represents four of five targeted relations. They stay in denominator.
- Q3-319: first MRS predicative become ARG2 refers to a generic entity, not student; rank 2 connects the second I to student.
- Q3-40: rank 2 links quit to I, but the historical adjectival sense "rid of" is not demonstrated by the _quit_v_1 label. Attachment score is not lexical sense accuracy.
- No grammar edits follow from this audit. Next evaluate on an external annotated corpus with source offsets, predeclared relation mappings and missed cases in denominator; rerun current main separately from historical baseline.
