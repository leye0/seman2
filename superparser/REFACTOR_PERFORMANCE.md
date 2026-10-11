# Syntax/semantics refactor microbenchmark

Protocol: Python 3.14, WordNet warmed, parse caches disabled, 100 repetitions,
one GC collection followed by GC disabled during each measured series. The
baseline is Git `53e3bf4`; subsequent phases use the same three sentences and
parser settings. Run the maintained comparison with:

```bash
PYTHONPATH=superparser python superparser/scripts/bench_syntax_semantics.py
```

## Semantic composition removal (deduplication disabled)

| sentence | baseline parse p50/p90/p95 | syntax parse p50/p90/p95 | best gain p50 | deferred semantics p50 |
|---|---:|---:|---:|---:|
| John opened the box. | 6.035/6.276/6.297 | 5.864/6.222/6.257 | 4.5% | 0.134 |
| John gave Mary the box. | 7.730/8.057/8.115 | 7.528/7.883/7.953 | 5.7% | 0.162 |
| I saw the man with the telescope. | 14.742/15.068/15.122 | 14.623/15.067/15.499 | 2.3% | 0.230 |

The isolated syntax path improves parse p50 by 0.8–2.8% and best-tree
materialization by 2.3–5.7%. Tail latency is mostly neutral; the ambiguous
sentence's parse p95 regresses 2.5%. Semantic work is now separately visible at
0.13–0.23 ms when requested. Adding it back means there is no end-to-end speed
gain for callers that always request semantics; the benefit is architectural
and applies to syntax-only callers.

## Lexical deduplication (same syntax-only implementation)

| sentence | candidates off → on | parse p50 off → on | best p50 off → on | k-best p50 off → on |
|---|---:|---:|---:|---:|
| John opened the box. | 42 → 28 | 5.864 → 6.268 | 1.631 → 1.611 | 1.378 → 1.565 |
| John gave Mary the box. | 32 → 23 | 7.528 → 7.694 | 1.952 → 1.872 | 1.889 → 2.916 |
| I saw the man with the telescope. | 56 → 37 | 14.623 → 14.887 | 4.677 → 4.519 | 1.469 → 1.772 |

Candidate count falls 28–34% and best-tree materialization improves 1–4%.
Cold total parsing currently regresses about 2–7%, and four-best extraction
can take longer. The reason is observable rather than hidden: before
deduplication, different WordNet senses filled early k-best ranks as duplicate
syntax; afterward the extractor searches deeper for four genuinely distinct
structural analyses. Forest node/derivation counts remain unchanged
(43/100, 54/130, 97/292), confirming that this vector recognizer already packs
lexical candidates by span/category before feature materialization. Further
speed claims would therefore require optimizing lexical projection or changing
the k-best stopping contract, not discarding ambiguity.

## Repeated identical parses

The parser previously looked up `_parse_cache` but never inserted a result.
After adding writes for both hierarchical and normal parsing, 2,000 cache hits
per sentence produced:

| sentence | miss p50 | hit p50/p90/p95 | p50 speedup |
|---|---:|---:|---:|
| John opened the box. | 6.268 ms | 0.001503/0.001523/0.001533 ms | ~4,170× |
| John gave Mary the box. | 7.694 ms | 0.001533/0.001603/0.001653 ms | ~5,020× |
| I saw the man with the telescope. | 14.887 ms | 0.001523/0.001573/0.001593 ms | ~9,775× |

Every run recorded 2,000 hits, one miss, one stored entry, and reuse of the
exact same `ParseResult`. This applies only to repeated normalized text on the
same `Parser` instance; first-time sentences still pay the full syntax cost.
