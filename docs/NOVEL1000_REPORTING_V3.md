# Novel-1000 v3 — quotation reporting and remaining Layer 1 repairs

The input reference is [PR #102][v2] at
`9cc515662de7cc07a41dd0d3eb1528c07b139ab5`. That release recorded 11
unresolved Novel-500 cases, and 500 completed parses across the five
extension groups. Its manifest, queue and measured baseline remain
unchanged. The comparison gate uses the same WordNet 3.0 resource, normal
corpus gateway and 50,000 chart items, 500,000 k-best work and 10-second
deadlines. No parsing or grammar outcome influences source selection.

## Complete source before grammar

A source quote ending in `?` or `!` can be followed by a capital `I` that
introduces a postposed reporting clause, not a fresh independent sentence.
The active paragraph segmenter now keeps a real closed quotation together
with a contiguous first-person speech verb and overt comma-separated
participial supplement. A new independent clause with an object, or a new
opening quotation, remains separate. No punctuation or words are added.

Two selected sources contained detached reporting tags. The recovered
Dickens utterance is `‘Am I grown?’ I said, drying my eyes.` The broader
inventory also recovers Stevenson's `"Mr. Silver, sir?" I asked, holding out
the note.` The latter tag had an already-complete **isolated** parse in v2,
but that was the wrong source extent. The revision uses the unique
canonical containing source span in the same book and paragraph, retaining
the other **998** exact benchmark source anchors. Both full utterances move
from the 4–8 to the 9–16 token band, explicitly recorded for the 500-case
sample. All five 100-case extension cohorts retain their exact source
anchors and band counts. Scores on the two different source versions are
reported independently. All comparisons of tree and graph identity use
unchanged sources.

## Selected grammar and graph checks

| v3 anchor | What was missing | Selected attachment now checked |
| --- | --- | --- |
| Q3-5 | Postposed reporting clause separated from the question | The direct question is the content of *said*. Its reporting *I*, not the quoted *I*, controls *drying* |
| Q3-9 | No root for a standalone echo plus manner | *Astonishment* modifies the *No?* discourse act. There is no invented speaker or speech predicate |
| Q3-13 | No root for an emphasized negative reply and inverted report | *Indeed* emphasizes *No*. *I* is the speaker of *said* |
| Q3-14 | Exclamatory idiom followed by a reporting supplement | *Dear me* is reported by *he*, which also controls *considering* |
| Q3-20 | Formulaic multiword assent with inverted report | *Of course* is the reported act and *the Doctor* supplies the speaker |
| Q3-44 | Control complement interrupted by a speech tag | *Martha* controls *go*, *London* is its destination, and *Ham* is the addressee of *said* |
| Q3-47 | Nominal apposition after a semicolon | *Peggotty* is the source, *something* is appositive to the matrix subject, and both properties describe it |
| Q3-107 | Coordinated control and an embedded fused relative | Both infinitives attach to *tried*. *There* scopes over *going on*, and *in vain* applies to the attempt |
| Q3-109 | Purpose and embedded polar question inside a supplement | *To know* is the purpose of *tapping*. *If tea were ready* is the content of *know*, not of the main predicate |
| Q3-111 | Optative, resumed beneficiary and gesture supplements | The wishes keep separate recipient spans. The reporter controls both overt gestural participles |
| Q3-116 | Shared agent and temporal condition across a particle predicate | *Dora* is agent of both actions. *Whenever* scopes over both, and *at the door* locates the aunt in the report |
| Q3-383 | Detached report had a complete isolated parse | The nominal question is the content of *asked*. *I* controls the note-holding gesture |

All rows have independent positive and negative controls, real source span
checks, and assertions on rank-one graph attachments. The workflow checks
for retained tree and graph signatures of the **988** previously complete
benchmark sources that did not change and all **30** dialogue witnesses.
Reproduction requires every v3 case to have a selected tree and graph
with the existing limits and no new search-limit flags. The 17 inherited
flags (from complete parses with censored alternative searches) are
unchanged. None of the 12 checked repairs hits a limit. This does not
certify the meaning of every unchanged parse.

From the repository root with WordNet 3.0 installed:

```sh
export PYTHONPATH=superparser
python -m scripts.novel_source_reporting_v3 replay --group all \
  --wordnet-dir "$WORDNET_DICT" --out-dir /tmp/novel-reporting-v3
python -m scripts.novel_source_reporting_v3 check --out-dir /tmp/novel-reporting-v3
```

The full reproduction pins, including a separate new case queue, live at
`superparser/research/novel_source_reporting_v3/`.

[v2]: https://github.com/leye0/seman2/pull/102
