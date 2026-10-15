#!/usr/bin/env python3
"""Print *executed* reading operations; an unknown construction must STOP."""
import argparse
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from seman_parser.reading_kernel_adapter import SemanReadingKernel  # noqa: E402

SAMPLES = (
    'The recipe Rosa followed failed.',
    'Are the keys inside the box?',
    'The teacher listed dates, places, and names.',
    'The document Emma examined disappeared.',
    'Were the papers behind the desk?',
    'The editor cataloged poems, songs, and stories.',
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('text', nargs='*')
    ap.add_argument('--data-dir', type=Path, default=BASE / 'data')
    ap.add_argument('--json-out', type=Path)
    ap.add_argument('--all', action='store_true', help='Use 3 original + 3 held-out structural variants')
    args = ap.parse_args()
    sentences = SAMPLES if args.all or not args.text else [' '.join(args.text)]
    kernel = SemanReadingKernel.from_dir(args.data_dir)
    outputs = []
    for sentence in sentences:
        report = kernel.parse(sentence)
        status = 'ACCEPT' if report.complete else 'STOP'
        print(f'\n{status}: {sentence}\n')
        for event in report.outcome.events:
            print(f'{event.at:>2}  {event.word:<14} {event.action:<11} {event.expected:<17} {event.detail}')
        print('  COUNTERS', json.dumps(report.outcome.counters, sort_keys=True))
        print('  TIMINGS (ms): lex=%.3f reader=%.3f mat=%.3f' %
              (report.lexical_ms, report.reading_ms, report.materialization_ms))
        print('  REASON', report.outcome.reason or '-')
        outputs.append(dict(text=sentence, complete=report.complete,
                            reason=report.outcome.reason,
                            stats=report.outcome.counters,
                            events=[e.as_dict() for e in report.outcome.events],
                            lexical_ms=report.lexical_ms, reading_ms=report.reading_ms,
                            materialization_ms=report.materialization_ms))
    if args.json_out:
        args.json_out.write_text(json.dumps(outputs, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
