# Quote-source revision v2

The apostrophe in Dickens’s `accordin’ to` is a lexical mark inside an
open quotation, not a closing delimiter. Both paragraph extraction and the
parser’s quotation lattice now use the same bounded orthographic check:
an overt clipped participle, a continuation cue, and a later real close
before another opening single quote. The text and offsets are preserved.
The controls cover independent dialogue, a real close with similar
spelling, nesting, unclosed speech, and the contiguous Dickens paragraph.

## The original damaged anchor

The old N952 record in the frozen v1 benchmark ended at `custom!`.
Its recovered source includes the full interrupted turn and nested speech,
with a balanced **126-token** source. It is not eligible for the 4–32-token
benchmark. A separate diagnostic with WordNet 3.0 and the original chart
and k-best limits reached the chart limit on the full turn. This release
fixes its **source boundary**, not long-turn grammar coverage. It does not
score a truncated or synthetically closed quote as a successful parse.

## Reproducible v2 source selection

The v1 cohort files, result pins and verdicts on [PR #101][v1] are
unaltered. On the v2 research branch, resampling is explicit and has its
own IDs (`Q2-…`), baseline, and result hashes. The original selector
resamples Novel-500 using the corrected extractor. For each of the five
additive rungs, still-eligible v1 anchors are reserved when disjoint from
the new sample. Deficits are filled, without inspecting parse results,
by the original stable source-hash rank within the same book and length
band. Each rung still has 25 cases per book and 25 per band.

Two v1 anchors need replacement. The source paragraph behind v1 N668 is
already represented in the new Novel-500 sample. The source behind v1
N952 no longer enters a 32-token sampler. The deterministic new selections
are **Q2-669**, a dialectal negative question with a reporting adjunct,
and **Q2-956**, `Away we went.` Independent selected-graph checks now
protect the negative tag and reporting scope on the first, and both
direction and agent on the second.

## Measured baseline

| Track | Complete on v2 |
| --- | ---: |
| Resampled Novel-500 | 489/500 |
| Novel-600 extension | 100/100 |
| Novel-700 extension | 100/100 |
| Novel-800 extension | 100/100 |
| Novel-900 extension | 100/100 |
| Novel-1000 extension | 100/100 |
| Historical dialogue sources, resolved by source ID | 30/30 |

All 498 retained source passages in the five extension rungs kept their
selected tree and graph signatures, matched by source rather than index.

Novel-500 changed **41 selected source texts**. Its 11 outstanding cases
are all newly selected. Its measured queue is separately pinned. No
historical score or semantic review is copied into a changed cohort.
Completion does not certify every selected semantic relation. For the
original v1 result, use the linked v1 branch and its original validation.

Run from the root with WordNet 3.0 installed:

```sh
export PYTHONPATH=superparser
python -m scripts.novel_quote_source_v2 plan --out-dir /tmp/q2
python -m scripts.novel_quote_source_v2 replay --group all \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/q2
python -m scripts.novel_quote_source_v2 check --out-dir /tmp/q2
```

The replay uses the same parser entry point and 50,000 chart items,
500,000 k-best work, and 10 seconds per case. The v1 commands retain
their original acceptance guards. They are not used to release this
different source baseline. The v2 manifest, measured result hashes and
case queue are in `superparser/research/novel_source_quote_v2`.

[v1]: https://github.com/leye0/seman2/pull/101
