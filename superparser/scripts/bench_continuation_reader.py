#!/usr/bin/env python3
"""Honest 300-sentence benchmark for the single-path continuation reader.

Run from superparser/: python scripts/bench_continuation_reader.py --limit 300 --baseline
Failed parses remain in all wall-time percentiles; no fallback is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'superparser'))

from seman_parser.continuation_reader import ContinuationReader, ContinuationCounts
from seman_parser.engine import Parser, ParserResources
from scripts.evaluate_reference_300 import normalized_gold, normalized_parser


def quantile(samples: list[float], p: float) -> float:
    samples = sorted(samples)
    if not samples:
        return 0.0
    x = (len(samples)-1)*p
    lo = int(x)
    hi = min(len(samples)-1, lo+1)
    return round(samples[lo]*(1-(x-lo))+samples[hi]*(x-lo), 4)


def summary(rows: list[dict]) -> dict:
    times = [float(x['ms']) for x in rows]
    stats = ['decisions_executed', 'frames_opened', 'rules_completed',
             'lexical_consumptions', 'unification_attempts', 'choices_deferred',
             'revisions', 'extensions_activated', 'dead_ends', 'recursive_guard',
             'frames_max_depth', 'checkpoints_max']
    return {
        'sentences': len(rows),
        'native_coverage': sum(bool(x['complete']) for x in rows) / len(rows),
        'reference_exact_diagnostic': sum(bool(x['exact']) for x in rows) / len(rows),
        'p50_ms_all': quantile(times,.5), 'p95_ms_all': quantile(times,.95),
        'p99_ms_all': quantile(times,.99), 'max_ms_all': round(max(times),4),
        'total_ms_all': round(sum(times),4),
        'count_totals': {k:sum(int(x['stats'].get(k,0)) for x in rows) for k in stats},
        'failures': [{'id':x['id'],'sentence':x['text'],'reason':x['stats'].get('stopped_by')}
                     for x in rows if not x['complete']],
    }


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--corpus',type=Path,default=ROOT/'data/seman2_reference_300_compact.json')
    ap.add_argument('--data-dir',type=Path,default=ROOT/'superparser/data')
    ap.add_argument('--model',type=Path,default=ROOT/'superparser/data/continuation_counts.json')
    ap.add_argument('--untrained',action='store_true')
    ap.add_argument('--baseline',action='store_true')
    ap.add_argument('--limit',type=int,default=300)
    ap.add_argument('--max-steps',type=int,default=1800)
    ap.add_argument('--model-weight',type=float,default=0.7)
    ap.add_argument('--output',type=Path,default=ROOT/'superparser/continuation_reader_benchmark.json')
    args=ap.parse_args()
    data=json.loads(args.corpus.read_text(encoding='utf-8'))['sentences'][:args.limit]
    resources=ParserResources.from_dir(args.data_dir)
    if args.untrained or not args.model.is_file():
        counts=ContinuationCounts()
        trained=False
    else:
        counts=ContinuationCounts.load(args.model)
        trained=True
    reader=ContinuationReader(resources, counts=counts, max_steps=args.max_steps,
                              model_weight=args.model_weight)
    reader.parse('Warm engines turn.')  # warm WordNet without sentence-result cache
    production=Parser(resources,cache_size=0) if args.baseline else None
    if production:
        production.parse('Warm engines turn.').result.best()
    experiments={}
    output=[]
    for row in data:
        result=reader.parse(row['text'])
        exact=result.completed and normalized_parser(result.item)==normalized_gold(row['tree'])
        x={'id':row['id'],'text':row['text'],'complete':result.completed,
           'exact':bool(exact),'ms':result.stats['total_wall_ms'],'stats':result.stats}
        output.append(x)
        if len(output) % 50 == 0:
            print('reader',len(output),'/',len(data),'covered',sum(q['complete'] for q in output),
                  file=sys.stderr,flush=True)
    experiments['reader']={'summary':summary(output),'rows':output}
    if production:
        baseline=[]
        for row in data:
            started=perf_counter()
            result=production.parse(row['text']).result.best()
            duration=(perf_counter()-started)*1000
            baseline.append({'id':row['id'],'text':row['text'],'complete':result is not None,
               'exact':result is not None and normalized_parser(result)==normalized_gold(row['tree']),
               'ms':duration,'stats':{}})
        experiments['production']={'summary':summary(baseline),'rows':baseline}
    payload={'format':'seman2-continuation-reader-benchmark-v1',
             'protocol':{'experimental':True,'training_corpus_overlap_possible':trained,
                         'trained_counts_loaded':trained,'max_steps':args.max_steps,
                         'production_fallback':False,'timings_include_failures':True,
                         'language_plausibility_audited':False,
                         'wordnet_warmed':True},'engines':experiments}
    args.output.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['summary'] for k,v in experiments.items()},indent=2))


if __name__=='__main__':
    main()
