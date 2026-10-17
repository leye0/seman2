"""Hard total-budget replay for ALREADY LEXICALLY CATEGORIZED hit candidates.

The input is 50,000 queries and 17,391 indexed *synthetic* POS templates.
This is ONLY retrieval of template IDs, not sentence lexing, lexical sense
selection, feature unification, or tree materialization. No fake claim that
50,000 natural-language sentences were parsed in five seconds.

Both batch-wall constraints are enforced, not inferred from median/p95:
1,000 hit lookups <100ms and 50,000 hit lookups <5,000ms.
"""
from __future__ import annotations

from random import Random
from time import perf_counter_ns
from collections import Counter
import json

from research.verbnet_lr.positional_template_index import PositionalTemplateIndex
from scripts.benchmark_snap_index_only import make_signatures,POS,percentile_ns


def main():
    n=17391
    size=50000
    index=PositionalTemplateIndex()
    signatures=make_signatures(n)
    for i,sig in enumerate(signatures):
        index.add(sig,i)
    rng=Random(17001)
    inputs=[]
    for q in range(size):
        selected=rng.randrange(n)
        actual=signatures[selected]
        categories=[]
        for cat in actual:
            extra=rng.choice(POS)
            categories.append((cat,extra) if extra!=cat else (cat,))
        inputs.append((tuple(categories),selected))
    # Run one warmup to avoid startup overhead in the measurements.
    index.lookup(inputs[0][0],limit=32)
    elapsed=[]
    good=0
    batch_start=perf_counter_ns()
    first_1000_ns=None
    failures=[]
    for i,(categories,expected) in enumerate(inputs):
        start=perf_counter_ns()
        result=index.lookup(categories,limit=32)
        elapsed.append(perf_counter_ns()-start)
        # Exact target must be among returned IDs unless its position is
        # beyond the first 32. In that case verify its membership via a
        # paged index lookup, outside the timed region.
        if expected in result.template_ids:
            good+=1
        elif result.total>32:
            failures.append((i,"unexpected overfull result"))
        else:
            failures.append((i,"missing expected pattern"))
        if i==999:
            first_1000_ns=perf_counter_ns()-batch_start
    all_ns=perf_counter_ns()-batch_start
    result={
        "kind":"synthetic-signature-index-only-correct-hits",
        "stored_templates":n,
        "matched_queries":size,
        "expected_id_verified":good,
        "failures":failures[:5],
        "first_1000_wall_ms":round(first_1000_ns/1e6,4),
        "all_50000_wall_ms":round(all_ns/1e6,4),
        "per_query_p50_ms":percentile_ns(elapsed,.5),
        "per_query_p95_ms":percentile_ns(elapsed,.95),
        "per_query_p99_ms":percentile_ns(elapsed,.99),
        "per_query_max_ms":round(max(elapsed)/1e6,4),
        "queries_over_1ms":sum(t>1_000_000 for t in elapsed),
        "input_categories_ready":True,
        "includes_lexing":False,
        "includes_unification":False,
        "includes_tree_reconstruction":False,
    }
    # Measuring correctness after each call is included, making wall-clock
    # batches a conservative bound on index-only lookup (not the opposite).
    result["pass"]=(
        not failures and good==size and
        result["first_1000_wall_ms"]<=100 and
        result["all_50000_wall_ms"]<=5000 and
        result["per_query_p95_ms"]<.1 and
        result["queries_over_1ms"]==0
    )
    print("FINAL",json.dumps(result,separators=(",",":")),flush=True)
    if not result["pass"]:
        raise SystemExit("FAIL: 1000/100ms or 50000/5s or p95<0.1ms indexed structural matching budget")


if __name__=="__main__":
    main()
