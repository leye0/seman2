#!/usr/bin/env python3
"""Benchmark native expectation parser over the existing 300-sentence corpus.

Run from the repository's superparser/ directory:
    python scripts/bench_expectations_300.py --limit 30
    python scripts/bench_expectations_300.py --limit 300 --baseline --output expectation_300.json

No production fallback. No auto-correction of reference annotations.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'superparser'))

from seman_parser.engine import Parser, ParserResources  # noqa: E402
from seman_parser.expectation_parser import ExpectationParser  # noqa: E402
from seman_parser.predictive import TransitionModel  # noqa: E402
from scripts.evaluate_reference_300 import normalized_parser, normalized_gold  # noqa: E402


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo), 4)


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    timings = [row['total_wall_ms'] for row in items]
    completed = [row for row in items if row['complete']]
    return {
        'sentences': len(items), 'native_coverage': len(completed) / len(items) if items else 0,
        'exact_normalized_diagnostic': sum(bool(x['exact']) for x in items) / len(items) if items else 0,
        'grammatical_derivations': len(completed),
        'linguistic_plausibility_verified': False,
        'wall_ms_all_sentences': {
            'p50': percentile(timings, .5), 'p95': percentile(timings, .95),
            'p99': percentile(timings, .99), 'max': round(max(timings), 4) if timings else None,
            'total': round(sum(timings), 4),
        },
        'wall_ms_successes_only': {
            'p50': percentile([x['total_wall_ms'] for x in completed], .5),
            'p95': percentile([x['total_wall_ms'] for x in completed], .95),
        },
        'totals': {
            key: sum(row['stats'].get(key, 0) for row in items)
            for key in ('states_created', 'transitions_executed', 'expectations_requested',
                        'expectations_activated', 'first_rejections', 'follow_rejections',
                        'lexical_scans', 'unification_attempts', 'shared_partials',
                        'shared_nodes', 'feature_rejections')
        },
        'failures': [{'id': x['id'], 'text': x['text'], 'why': x['stats'].get('stopped_by')}
                     for x in items if not x['complete']],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', type=Path, default=ROOT / 'data' / 'seman2_reference_300_compact.json')
    ap.add_argument('--data-dir', type=Path, default=ROOT / 'superparser' / 'data')
    ap.add_argument('--model', type=Path, default=ROOT / 'superparser' / 'data' / 'predictive_transitions.json')
    ap.add_argument('--limit', type=int, default=300)
    ap.add_argument('--max-states', type=int, default=60_000)
    ap.add_argument('--follow', action='store_true', help='Experimental FOLLOW pruning (may lose coverage)')
    ap.add_argument('--statistical-weight', type=float, default=0.15)
    ap.add_argument('--baseline', action='store_true')
    ap.add_argument('--trace-first', action='store_true')
    ap.add_argument('--output', type=Path, default=Path('expectation_300.json'))
    args = ap.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding='utf-8'))['sentences'][:args.limit]
    resources = ParserResources.from_dir(args.data_dir)
    model = TransitionModel.load(args.model) if args.model.is_file() else TransitionModel()
    experiment = ExpectationParser(resources, model=model, max_states=args.max_states,
                                   use_follow=args.follow, statistical_weight=args.statistical_weight)
    production = Parser(resources, cache_size=0) if args.baseline else None
    # Preload WordNet once, but no phrase result cache in either parser.
    experiment.parse('The child laughed.')
    if production:
        production.parse('The child laughed.').result.best()
    results: dict[str, list[dict[str, Any]]] = {'expectations': []}
    if production:
        results['production'] = []
    for i, row in enumerate(corpus, 1):
        gc.collect() if i == 1 else None
        r = experiment.parse(row['text'])
        item = r.item
        result = {
            'id': row['id'], 'text': row['text'], 'complete': bool(r.completed),
            'total_wall_ms': float(r.stats['total_wall_ms']),
            'exact': bool(item is not None and normalized_parser(item) == normalized_gold(row['tree'])),
            'stats': r.stats,
        }
        results['expectations'].append(result)
        if args.trace_first and i == 1:
            print('EXPECTATIONS-FIRST:', json.dumps(r.stats['expected_by_position'], ensure_ascii=False), flush=True)
        if production:
            t0 = perf_counter()
            old = production.parse(row['text']).result.best()
            ms = 1000 * (perf_counter() - t0)
            results['production'].append({
                'id': row['id'], 'text': row['text'], 'complete': old is not None,
                'total_wall_ms': round(ms, 4),
                'exact': bool(old is not None and normalized_parser(old) == normalized_gold(row['tree'])),
                'stats': {},
            })
        if i % 25 == 0 or i == len(corpus):
            print(f'{i}/{len(corpus)} | new={sum(x["complete"] for x in results["expectations"])}',
                  flush=True, file=sys.stderr)
    payload = {
        'format': 'seman2-active-expectations-benchmark-v0',
        'protocol': {
            'experimental': True, 'corpus': str(args.corpus),
            'sample_size': len(corpus), 'production_fallback': False,
            'model_used': str(args.model) if args.model.is_file() else 'untrained',
            'trained_corpus_may_overlap_test': True,
            'wordnet_warmed': True, 'limits_are_operations_not_seconds': True,
        },
        'summaries': {name: summarize(rows) for name, rows in results.items()},
        'per_sentence': results,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['summaries'], ensure_ascii=False, indent=2))
    print(f'Full results: {args.output.resolve()}')


if __name__ == '__main__':
    main()
