#!/usr/bin/env python3
"""Trace executed grammar transitions, independently from production parsing."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader  # noqa:E402

SAMPLES = (
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
    'The document Emma examined disappeared.',
    'Were the papers behind the desk?',
    'The editor cataloged poems, songs, and stories.',
    'Are the keys still inside the box?',
    'The teacher listed dates and names.',
    'The teacher listed dates, places, times, and names.',
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('text', nargs='*')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--data-dir', type=Path, default=BASE / 'data')
    ap.add_argument('--json-out', type=Path)
    ap.add_argument('--lexical-diagnostics', action='store_true',
                    help='Print actual WordNet categories/features for each token')
    ap.add_argument('--include-unsupported', action='store_true',
                    help='Also try relative with adverb; existing VP-GAP grammar lacks ADV V')
    args = ap.parse_args()
    kernel = SemanCompiledReader.from_dir(args.data_dir)
    sentences = list(SAMPLES if args.all or not args.text else [' '.join(args.text)])
    if args.include_unsupported:
        sentences.append('The recipe Rosa carefully followed failed.')
    print('COMPILED', json.dumps(kernel.compiled.stats, sort_keys=True))
    reports = []
    for sentence in sentences:
        if args.lexical_diagnostics:
            from seman_parser.segmentation import build_lattice
            lattice = build_lattice(sentence, kernel.resources.lexicon)
            print('\nLEXICAL EVIDENCE:', sentence)
            for token in lattice.tokens:
                same_span = [c for c in lattice.candidates if
                             c.span_start == token.start and c.span_end == token.end]
                values = {}
                for c in same_span:
                    bucket = values.setdefault(c.category, [])
                    desc = f"{c.features.as_dict()} score={c.score:.2f}"
                    if desc not in bucket and len(bucket) < 3:
                        bucket.append(desc)
                print(f'  {token.index:>2} {token.text:<13} {values}')
        r = kernel.parse(sentence)
        print('\n%s: %s' % ('ACCEPT' if r.complete else 'STOP', sentence))
        for e in r.outcome.events:
            print(f'{e.at:>3}  {e.word:<13} {e.action:<10} {e.expected:<15} {e.detail}')
        print(' COUNTERS', json.dumps(r.outcome.counters, sort_keys=True))
        print(' TIMINGS ms: lexical=%.3f reading=%.3f materialization=%.3f' %
              (r.lexical_ms, r.reading_ms, r.materialization_ms))
        if r.outcome.reason:
            print(' REASON:', r.outcome.reason)
        reports.append(dict(text=sentence, complete=r.complete, reason=r.outcome.reason,
                            stats=r.outcome.counters,
                            events=[e.as_dict() for e in r.outcome.events],
                            lexical_ms=r.lexical_ms, reading_ms=r.reading_ms,
                            materialization_ms=r.materialization_ms))
    if args.json_out:
        args.json_out.write_text(json.dumps(dict(format='seman2-reading-kernel-compiled-v1',
                          grammar=kernel.compiled.stats, rows=reports), indent=2) + '\n',
                                  encoding='utf8')


if __name__ == '__main__':
    main()
