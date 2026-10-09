"""Diagnose WHY unfixed sentences fail: tokens, coverage gaps, waiting partials."""
import sys
sys.path.insert(0, '.')
from seman_parser.engine import Parser
from seman_parser.segmentation import build_lattice
from seman_parser.chart import Chart
from seman_parser.unfixed import UNFIXED

p = Parser.from_dir('data', goal_category='CLAUSE')
p.parse('warm up')

only = sys.argv[1:]

for idx, text in UNFIXED:
    if only and str(idx) not in only:
        continue
    print(f'\n===== {idx}: {text}')
    lattice = build_lattice(text, p.resources.lexicon)
    tokens = lattice.tokens
    print(f'TOKENS ({len(tokens)}):')
    for t in tokens:
        cands = [c for c in lattice.candidates if c.span_start == t.start and c.span_end == t.end]
        cats = ', '.join(f'{c.category}:{c.score:.2f}' for c in sorted(cands, key=lambda x: -x.score)[:6])
        print(f'  [{t.index:2d} @{t.start:3d}:{t.end:3d}] {t.text!r:22s} -> {cats}')

    chart = Chart(p.resources.grammar, beam=p.beam, max_items=p.max_items, goal_category='CLAUSE')
    result = chart.parse_lattice(lattice)
    print(f'completed={result.completed} roots={len(result.roots)} packed={len(chart.packed)}')

    # Character-span coverage per token start
    by_start: dict[int, list] = {}
    for (start, end, cat_id), node in chart.packed.items():
        by_start.setdefault(start, []).append((end, node.category, node.best.score))

    def tok_at(char_pos):
        for t in tokens:
            if t.start <= char_pos < t.end:
                return t.index
        return None

    print('SPANS FROM EACH TOKEN START (top 3, char ends):')
    for t in tokens:
        items = sorted(by_start.get(t.start, []), key=lambda x: (-x[0], -x[2]))[:3]
        if items:
            ends = []
            for e, cat, sc in items:
                te = tok_at(e - 1) if e > 0 else None
                ends.append(f'{cat}[t{t.index}..t{te}]@{e}={sc:.1f}')
            print(f'  t{t.index:2d} {t.text!r:18s}: {", ".join(ends)}')
        else:
            print(f'  t{t.index:2d} {t.text!r:18s}: (no span)')

    # Greedy chain using token-index coverage
    tok_end = {t.start: t.end for t in tokens}
    idx_of = {t.start: t.index for t in tokens}
    # build reach[i] = max token index (exclusive) reachable from token i
    reach = {t.index: t.index for t in tokens}
    for (start, end, cat_id), node in chart.packed.items():
        if start not in idx_of:
            continue
        ti = idx_of[start]
        # find token containing end-1
        te = None
        for t in tokens:
            if t.start < end <= t.end or (end == t.end):
                if t.end == end or (t.start < end < t.end):
                    te = t.index + 1
                    break
        if te is None:
            # end might be after last token (period)
            for t in tokens:
                if t.end <= end:
                    te = max(te or 0, t.index + 1)
        if te and te > reach[ti]:
            reach[ti] = te

    pos, chain = 0, []
    guard = 0
    while pos < len(tokens) and guard < 50:
        guard += 1
        nxt = reach.get(pos, pos)
        if nxt <= pos:
            chain.append(f'GAP@t{pos}({tokens[pos].text!r})')
            break
        chain.append(f't{pos}->{nxt}')
        pos = nxt
    print('GREEDY:', ' '.join(chain))

    # Partials waiting
    waiting = []
    for coords, items in chart._partials.items():
        for pi in items:
            if pi.next_category:
                waiting.append((pi.start, pi.end, pi.rule_id, pi.dot, pi.next_category, pi.score))
    waiting.sort(key=lambda x: (-x[1], -x[5]))
    print('TOP PARTIALS WAITING:')
    for start, end, rid, dot, nc, sc in waiting[:12]:
        ts, te = tok_at(start), tok_at(max(start, end - 1)) if end > start else None
        print(f'  t{ts}..t{te} @{start}:{end} rule={rid} dot={dot} needs={nc} score={sc:.2f}')
