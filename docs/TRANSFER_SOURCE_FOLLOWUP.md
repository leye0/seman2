# Literary transfer: source typography and attachment follow-up

The parser previously returned a full tree for T45-1665 even though the
second verse line was being interpreted inside the comparison on the first
line. The source indentation supplies the missing boundary. The selected
tree now separates the comparison, condition, and consequent; the exceptive
subject and counted pronoun belong to the consequent. The original line
break is evidence, not an inserted comma.

## Matched comparisons

| Frozen cohort | Before | After | Changes to previously complete trees |
| --- | ---: | ---: | --- |
| Novel-500 | 500/500 | 500/500 | None, including derivation and score |
| Original transfer (24) | 24/24 | 24/24 | T35-0164 and T45-1665 only |
| Literary replay (96 source anchors) | 93/96 | 95/95 analyzable + 1 documentary marker | None |
| Literary extension (48) | 41/48 | 48/48 | None |
| Independent control (42) | 33/42 | 33/42 | None |

All runs use the public corpus gateway, WordNet 3.0 and the established
50,000 chart-item, 500,000 k-best work-unit and 10-second sentence limits.
No new forest or k-best flags were observed in the matched comparisons. The
30 historical dialogue cases still complete. The direct certificate still
checks 120/120 gold annotations and 24/24 grammatical contrasts, with the
same 9 known false accepts among the 24 negative examples.

Novel-500 source SHA-256 remains
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`.
The serialized snapshot of source identity, completion, budget flags and
selected trees remains
`5a0a5b189ba1fb0f65e1da26eee423b2fe5b818ba8b57e91d98f7fcfee149a07`.

## Corrected analyses

| Source anchor | Selected reading checked |
| --- | --- |
| U45-2643 | The opening pseudocleft has a demonstrative matrix subject and a free-relative complement with a theme gap. The vocative addresses Anne, and the condition governs the telling act. The next sentence remains a separate reported turn. |
| U35-0368 | Matching emphasis marks belong to the paragraph, not to sentence syntax. The opening sentence has three predicates sharing one subject. The participle and comparison describe the flowers, while the destination modifies placing. |
| Following unit of U35-0368 | The next sentence ends at its own full stop and closes the paragraph emphasis. It now has its own finite matrix tree. |
| U35-0538 | The elapsed time expression attaches to the vanishing event and does not become another argument. |
| U35-0037 | Emphasized positive ability and the fused negative modal are separate, contrasted clauses. Both directional PPs have local governors. |
| U35-0018 | The clause about what is overlooked is the extraposed evaluation content. The cheerfulness supplement modifies the act of continuing speech. |
| U45-1501 | The opening vocative and the intercalated gesture belong to the same dialogue turn. The overt question keeps its own subject and its emphasized main verb. |
| U45-3166 | The ellipsis belongs to the first report, with an overt recipient. The emphatic predicate and its complement stay inside the second report. |
| U45-0110 | The braids are the postposed subject of the locative clause. The extent participle modifies the braids and is not an adjunct of wearing. |
| U45-2679 | A previous pluperfect state contrasts with a cessation of doubt. The final finite ellipsis provides the equative standard rather than another matrix clause. |
| T35-0164 | The demonstrative is the patient of explaining. The coordinated request has an embedded relative attached to the quoted nominal, with its temporal phrase inside that relative. |
| T45-1665 | The source line separates the conditional comparison from the consequence. The negative subject contains an exception, and the postposed numeral quantifies the pronominal object. |

U45-1550 was the literal marker `P.S.` by itself. It is now a documentary
component of the following postscript, with its own exact marker span and
an embedded prose-content span. It is not counted as a grammar repair or
silently dropped. The legacy anchor resolves to the original owner's span.

## Exposure and reproduction

The 48 units were held out in the *previous* implementation pass, but served
as development examples for these repairs. The 42-unit control was selected
by deterministic SHA-256 ordering with salt `seman2-blind-followup-v1`,
before examining its parse outputs, excluding paragraphs represented in
the preceding development cohorts. Up to six units per available book and
length band were retained. The Wells 25–32 band had no available units under
that exclusion. No fixes were derived from this control. Its nine incomplete
cases comprise four without structural roots, four without a valid analysis,
and one with a forest limit. Completion is not a full gold attachment audit.

The live extractor can reselect a different 24-unit transfer set after a
legitimate source-boundary change. That set has a new source SHA-256
`0d6439dc568a49f8b7b6dcc48d7f2c323fd2bacd9c0815d4c74f0eca3293b4a5`.
It was run on both parser revisions with the same extraction and was 24/24
on both. Do not compare the new extraction score to the legacy sample
by ordinal.

The frozen manifest stores only original book coordinates, source hashes and
stable labels. It resolves against the **one** active extractor, validates
every source identity and rejects a missing anchor unless its documentary
owner is established. Source books are not committed. With the pinned
editions from [NOVEL_TRANSFER_24.md](NOVEL_TRANSFER_24.md), run from the
repository root:

```sh
PYTHONPATH=superparser python -m scripts.evaluate_novel_transfer_replay \
  --books-dir /path/to/pinned-editions --wordnet-dir "$WORDNET_DICT" \
  --out-dir /tmp/seman2-literary-followup
```

The runner writes paired `_cohort.jsonl` and `_parses.jsonl` files for
`transfer24-v1`, `replay96-v1`, `extension48-v1` and `blind42-v1`.
Only the source manifest is emitted with `--sample-only`.

## Second, separate development sample

A 24-unit development sample from Anne of Green Gables uses paragraphs
outside the four frozen sets above. It was sampled without replacement
within each paragraph, with six units in each of four length bands
(6–10, 11–17, 18–23, and 24–28 tokens), ordered by SHA-256 of book ID,
source start offset and salt `seman2-dev-scout-v1`. This sample was then
used to develop two additional repairs, so it is not a control.

| Source anchor | Verified change |
| --- | --- |
| S45-0913 | Direction home and the independent genitive origin both modify the motion. The implicit possessed location stays distinct from its possessor and no noun is inserted into the tree. The same subject governs the coordinated call to account. |
| S45-3220 | The two coordinated participants are agents of the attempt and its controlled infinitive, not the observer. The resulting state is a goal of restoring, not a claim that recovery happened. |

The locked development sample moves from 21/24 to 23/24, with all 21
previous selected trees unchanged. Its original ordered source anchors are
replayable as `scout24-v1` through the same command. The remaining case,
S45-3011, combines coordinated possessors, a quoted title used as a direct
object, and two coordinated actions. It is kept as an open development case.
