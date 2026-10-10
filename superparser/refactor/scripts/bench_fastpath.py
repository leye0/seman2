#!/usr/bin/env python3
"""Warm benchmark + structural regression on Seman2's actual corpus.

Examples (from the ZIP directory):
  python scripts/bench_fastpath.py /path/to/seman2/superparser --mode baseline --limit 850 --output before.json
  python scripts/bench_fastpath.py /path/to/seman2/superparser --mode fast --limit 850 --output after.json --compare before.json
  python scripts/bench_fastpath.py /path/to/seman2/superparser --mode scan --limit 850 --output scanner.json
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter


def quantile(items, p):
    if not items:
        return None
    values = sorted(items)
    return round(values[int((len(values) - 1) * p)], 3)


def semantic_fingerprint(best):
    """Ignore process-global semantic node IDs; compare logical endpoints."""
    if best is None:
        return []
    graph = best.semantic.graph
    def norm(node_id):
        n = graph.nodes.get(node_id)
        return (n.kind, tuple(n.span or ()), n.type_name, n.surface) if n else (node_id,)
    return sorted((e.relation, norm(e.source), norm(e.target)) for e in graph.relations)


def snapshot(report):
    result = report.result
    best = result.best()
    return {
        'completed': result.completed,
        'best_category': best.category if best else None,
        'best_rule_id': best.rule_id if best else None,
        'best_features': best.features.as_dict() if best else None,
        'semantic_relations': semantic_fingerprint(best),
        'num_root_analyses': len(result.roots),
    }


def run():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('superparser', help='path to superparser/ folder')
    ap.add_argument('--corpus', default=None, help='override corpus file')
    ap.add_argument('--limit', type=int, default=850)
    ap.add_argument('--mode', choices=['baseline', 'fast', 'scan', 'recognize'], default='fast')
    ap.add_argument('--output', default=None)
    ap.add_argument('--compare', default=None)
    args = ap.parse_args()
    root = Path(args.superparser).expanduser().resolve()
    if root.name != 'superparser' and (root / 'superparser' / 'seman_parser').exists():
        root = root / 'superparser'
    sys.path.insert(0, str(root))
    from seman_parser.engine import Parser
    from seman_parser.coverage import extract_sentences
    if args.mode in ('fast', 'scan', 'recognize'):
        from seman_parser.fastpath import FastParser
        parser = FastParser.from_dir(root / 'data', cache_size=0)
    else:
        parser = Parser.from_dir(root / 'data', cache_size=0)
    guesses = (root.parent / 'data' / 'the_map_of_everything_nlp_novel.txt',
               root / 'data' / 'the_map_of_everything_nlp_novel.txt')
    corpus = Path(args.corpus) if args.corpus else next((x for x in guesses if x.exists()), guesses[0])
    if not corpus.exists():
        ap.error(f'corpus not found: {corpus}; use --corpus PATH')
    cases = extract_sentences(corpus, limit=args.limit)
    parser.parse('The woman opened a box.')  # warm-up; excluded from timing
    records = []
    for case in cases:
        t0 = perf_counter()
        matches = None
        if args.mode == 'scan':
            matches = parser.scan_constructions(case.text)
            elapsed = (perf_counter() - t0) * 1000
            snap = None
            stats = {'matches': len(matches)}
        elif args.mode == 'recognize':
            recognition = parser.recognize_structure(case.text)
            elapsed = (perf_counter() - t0) * 1000
            snap = None
            stats = {
                'possible': recognition.possible,
                'states': recognition.state_count,
                'completions': recognition.completion_count,
                'budget_exceeded': recognition.exceeded_budget,
            }
        else:
            result = parser.parse(case.text)
            elapsed = (perf_counter() - t0) * 1000
            snap = snapshot(result)
            stats = dict(result.result.stats)
        records.append({
            'index': case.index, 'text': case.text, 'ms': round(elapsed, 4),
            'snapshot': snap, 'stats': stats,
        })
        if (len(records) % 25) == 0:
            print(f'{len(records):4d}/{len(cases)}  latest={elapsed:.2f} ms', flush=True)
    elapsed = [x['ms'] for x in records]
    summary = {
        'count': len(records), 'mode': args.mode,
        'median_ms': quantile(elapsed, .5), 'p90_ms': quantile(elapsed, .9),
        'p95_ms': quantile(elapsed, .95), 'p99_ms': quantile(elapsed, .99),
        'mean_ms': round(statistics.mean(elapsed), 3) if elapsed else None,
        'max_ms': max(elapsed) if elapsed else None,
    }
    if args.mode == 'fast':
        summary['lexical_cache'] = parser.lexical_cache.stats()
    payload = {'summary': summary, 'records': records}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.compare:
        baseline = json.loads(Path(args.compare).read_text(encoding='utf-8'))
        old = {x['index']: x for x in baseline['records']}
        incompatible = []
        for new in records:
            previous = old.get(new['index'])
            if previous is None or previous['text'] != new['text']:
                incompatible.append((new['index'], 'missing/different input'))
            elif previous['snapshot'] != new['snapshot']:
                incompatible.append((new['index'], 'output difference'))
        print('REGRESSION mismatches:', len(incompatible))
        for mismatch in incompatible[:30]:
            print(' ', mismatch)
        if incompatible:
            print('Do not deploy: investigate mismatches (especially lost ambiguity).')
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Wrote', args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
