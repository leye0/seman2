# Literary transfer replay — attachment, control, and quoted speech

This pass starts from the transfer-24 fixes and quoted double-object commands
(PRs #93 and #94). It does not change the pinned Novel-500 or select on parser
output. It keeps the source delimiters, ellipses, contractions and all spans.
The selected tree, including attachments, matters more than accepting a root.

## Outcome

| Sample | Before | After | Selected-tree comparison |
|---|---:|---:|---|
| Literary replay (96, used for diagnosis) | 72/96 complete | 93/96 complete | 21 repaired. All 72 previously complete trees unchanged. |
| Transfer-24 (diagnostic replay) | 24/24 complete | 24/24 complete | 8 repaired rank-one trees, 16 unchanged. One previous forest saturation removed. |
| Blind control (48 other units, same two books) | 41/48 complete | 41/48 complete | All 48 trees/statuses and budget flags unchanged. |
| Pinned Novel-500 | 500/500 complete | 500/500 complete | All 500 selected trees byte-identical in the snapshot, including original source identity, statuses and budget flags. |
| Historical dialogue | 30/30 complete | 30/30 complete | All 30 retained in Novel-500. |

The blind 48 were selected from previously uninspected units with separate
source paragraphs from both diagnostic sets, in the same two books and from
a second deterministic salt. They were not used to adjust the parser.
This measures coverage and lack of observed changes on that sample. It does
not measure full-tree accuracy or demonstrate a gain on unseen sentences.

## Repaired selected trees

| Source case | Attachment or distinction preserved |
|---|---|
| U35-0012 | A stance about previous content, a request to wait with a duration, and a separate modal question with overt typographic emphasis inside its subject. |
| U35-0009 | Negative inversion under `nor`; `only` restricts the whole list of dimensions, and the participle shares the modal clause's subject. |
| U35-0156 | The narrator looks around for the traveller. The dash interrupts that action and introduces a separately attributed clock statement, not a second predicate of the narrator. |
| U35-0006 | The negative copular question contains an object-controlled infinitive and stranded preposition. The description of Filby attaches to the reporter, outside the quote. |
| U35-0534 | Negative answer plus vocative, negative human indefinite plus perfect motion, and progressive expectation. The subject of the expectation controls `find`; `here` locates finding. |
| U35-0460 | The candor preface, the assertion and its subject intensifier, and the unfinished contrast remain separate. No missing predicate is invented. |
| U35-0478 | The lamp is picked up and carried. The flaring supplement describes the carried object; the door lies on the route and the corridor is the goal. |
| U35-0113 | The outer parentheses retain one complete episode. The infinitive of purpose is linked to the Psychologist, who both serves himself and tries to light the uncut cigar. |
| U35-0487 | The same subject looks and tells. Hesitation scopes over telling, the progressive belongs to the reported proposition, and `at which` introduces a reaction to the report. |
| U35-0017 | Separate the abandoned demonstrative and its hesitant resumption across the reporter; keep the speaker's separate efforts and literal spaced ellipsis. |
| U35-0108 | Standing is prior to the move; the jar's location remains nominal; the orientation of the body is a circumstance of the second coordinated action only. |
| U35-0257 | The writing gerund has an overt object and particle. The dash-delimited reformulation shares the infinitival complement, which does not modify `feel` or `keenness`. |
| U45-3062 | A proper name modifies a singular scholarship in a verbless exclamation. No finite verb is inferred. |
| U45-2260 | Causal `for` introduces a full clause. The finite perfect auxiliary and adverb scope over filling, with the PP outside the nominal subject. |
| U45-1540 | The modal perfect retains its scope, and `I think` is a speech supplement. The contiguous `mourned to [name]` tag carries an independently scoped time adjunct. |
| U45-0212 | An exclamative perfect precedes a contrast and an embedded belief; the dialectal consequence marker `so’s` belongs to describing, not a copula. |
| U45-3246 | `Away` directs the motion, `kindly` modifies it, and Anne is the affected participant of leaving and the controller of keeping vigil. |
| U45-3080 | The negated modal licenses the opinion and its finite complement. `Sort` remains the nominal head, and the object gap in the relative belongs to the domain noun. |
| U45-1730 | The family name and origin appose the cousins. The overt semicolon separates two clauses. Floating `all` quantifies `they`; straw and robes are distinct conjuncts. |
| U45-1807 | A modal echo question is distinct from both the hedged assertion and the nominal rebuke. The tag does not become an argument, and no missing complement is supplied. |
| U45-2722 | Both modal perfects remain distinct. The first day qualifies the retrospective judgment, and `three years ago` anchors the time of being there. |
| T35-0181 | The three finite predicates share one subject. `But` coordinates, `painfully` modifies coming, and the last PP remains inside the motion nominal. |
| T35-0071 | `About the room` stays inside the passive relative on the plural domain of the partitive. The two legs are a circumstance of placing. |
| T35-0462 | `Turn over` is a particle predicate. Seeing selects an independent progressive with its own subject; the location modifies the scars. |
| T45-1554 | `None` is a negative anaphoric proform, not a common noun or adverb. No discourse antecedent is asserted by Layer 1. |
| T45-1716 | `Spell her down` and `leave her clear out of sight` share an agent. `Her` is an affected participant, not the possessor of a nominal `clear`. |
| T45-0495 | The name and the age statement are the speaker's two separate quoted contributions. Reticence and its subject-controlled infinitive belong to the reporter. |
| T45-1816 | The sound is an event appositive. The waiting supplement belongs to Diana, the causee and controller of `give`. |
| T45-2854 | The two participles share the matrix subject. Half a dozen is a quantified object of `use up`; the finite temporal boundary is not an object or a nominal modifier. |

## Reproduction and limits

Use the two pinned UTF-8 Gutenberg source editions described in
[NOVEL_TRANSFER_24.md](NOVEL_TRANSFER_24.md), WordNet 3.0 and the existing
50,000 chart-item, 500,000 k-best work-unit and 10-second sentence limits.
From the repository root:

```sh
PYTHONPATH=superparser python -m scripts.evaluate_novel_transfer_replay \
  --books-dir /path/to/pinned-editions --wordnet-dir "$WORDNET_DICT" \
  --out-dir /tmp/seman2-literary-replay
```

Replay ordered source SHA-256
`5bb2c0bc51e92b3ed9b00ce84f81ed363305960bb3b306e294eff763ae718df6`.
Blind control ordered source SHA-256
`704a8e94ffbb4e0de9d5ff7ea9fa9979a4a78249dab44be62e1e5ee967bdefc3`.
The Novel-500 source SHA-256 is still
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`.
The byte-identical selected-tree snapshot digest is
`5a0a5b189ba1fb0f65e1da26eee423b2fe5b818ba8b57e91d98f7fcfee149a07`
(16 pre-existing forest flags and zero k-best flags).

The direct grammar certificate retains 120/120 gold annotations and 24/24
grammatical contrasts, with the 9 known false accepts unchanged. Targeted
tests also exercise independent variants and reject close agreement, role,
scope, quotation, and punctuation counterexamples.

No text is dropped from the replay. Its remaining cases are U45-2643 (forest limit), U45-1550 (a standalone postscript
marker), and U35-0368 (the opening italic marker has no closing marker within
the sampled unit). The latter two are better investigated as source-unit
classification questions before proposing a grammatical repair. Verse
T45-1665 remains untouched.

This is the historical result at the end of the attachment replay. The
[source follow-up](TRANSFER_SOURCE_FOLLOWUP.md) records the subsequent
repairs, the current reproduction filenames, and the independent 42-unit
control.
