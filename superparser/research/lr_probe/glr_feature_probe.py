"""POC lexical feature refinement for Seman2 GLR; no production edits."""
import json
import multiprocessing as mp
import re
import resource
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from parglare import Grammar, GLRParser
from parglare.closure import LR_0
from parglare.parser import Token
from parglare.tables import create_load_table
from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure, Variable, unify
from seman_parser.segmentation import build_lattice

ROOT = Path('research/lr_probe')
GRAMMAR = ROOT / 'grammar_features.pg'
CACHE = ROOT / 'grammar_features_slr.pgc'
META = ROOT / 'grammar_features_meta.json'
OLD = ROOT / 'real_lattice_100.json'
OUT = ROOT / 'real_features_100.json'


def tag(s):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)


def prepare_grammar():
    original = Grammar.from_file(str(ROOT / 'grammar.pg'), _no_check_recognizers=True)
    old_terminals = set(original.terminals)
    rules = [json.loads(s) for s in Path('data/grammar.jsonl').read_text().splitlines() if s.strip()]
    nts = {r['lhs']['category'] for r in rules}
    bridges = sorted(c for c in nts if 'TK_' + tag(c) in old_terminals)
    names, specs, alternatives, owners = {}, {}, defaultdict(set), defaultdict(list)

    def terminal(cat, features=None, requires=()):
        features = features or {}
        key = json.dumps([cat, features, sorted(requires)], sort_keys=True)
        if key not in names:
            name = f'TK_{tag(cat)}__F{len(names):03d}'
            names[key] = name
            specs[name] = {'category': cat, 'features': features, 'requires': sorted(requires)}
        return names[key]

    for rule in rules:
        lhs = 'NT_' + tag(rule['lhs']['category'])
        rhs = tuple(
            'NT_' + tag(s['category']) if s['category'] in nts else
            terminal(s['category'], s.get('features'), s.get('requires', ()))
            for s in rule['rhs']
        )
        if not rhs:
            raise ValueError(f"Production vide non prévue : {rule['id']}")
        alternatives[lhs].add(rhs)
        owners[(lhs, rhs)].append(rule['id'])

    for cat in bridges:
        lhs = 'NT_' + tag(cat)
        rhs = (terminal(cat),)
        alternatives[lhs].add(rhs)
        owners[(lhs, rhs)].append('lexical_bridge_' + cat)

    lines = ['DOCUMENT: NT_CLAUSE;', '']
    for lhs, rhs_set in sorted(alternatives.items()):
        alts = [' '.join(rhs) for rhs in sorted(rhs_set)]
        lines.append(lhs + ': ' + '\n    | '.join(alts) + ';')
        lines.append('')
    lines.append('terminals')
    for name in sorted(specs):
        lines.append(f'{name}: "{name}";')

    GRAMMAR.write_text('\n'.join(lines) + '\n')
    META.write_text(json.dumps({
        'terminals': specs,
        'rule_map': [
            {'lhs': lhs, 'rhs': rhs, 'ids': ids}
            for (lhs, rhs), ids in owners.items()
        ],
        'bridges': bridges,
        'original_rules': len(rules),
        'unique_productions': sum(map(len, alternatives.values())),
    }, indent=2))
    print('Règles originales :', len(rules))
    print('Productions distinctes :', sum(map(len, alternatives.values())))
    print('Terminaux raffinés :', len(specs))
    print('Raccordements lexicaux :', bridges, flush=True)


def load_table():
    g = Grammar.from_file(str(GRAMMAR), _no_check_recognizers=True)
    t = time.perf_counter()
    table = create_load_table(g, itemset_type=LR_0,
                              prefer_shifts=False, cache_path=str(CACHE))
    print('Table :', len(table.states), 'états |',
          round(time.perf_counter() - t, 2), 's |',
          'SR', len(table.sr_conflicts), '| RR', len(table.rr_conflicts), flush=True)
    return g, table


def candidate_edges(text, lexicon, specs):
    t = time.perf_counter()
    lattice = build_lattice(text, lexicon)
    lexical_ms = (time.perf_counter() - t) * 1000
    by_cat = defaultdict(list)
    for name, spec in specs.items():
        by_cat[spec['category']].append((name,
            FeatureStructure.build(spec['features']), spec['requires']))

    t = time.perf_counter()
    edges, coarse, tries, pruned = set(), set(), 0, 0
    for c in lattice.candidates:
        coarse.add((c.span_start, c.span_end, c.category))
        for name, conditions, required in by_cat.get(c.category, ()):
            tries += 1
            has_evidence = all(
                c.features.has(field)
                and not isinstance(c.features.get(field), Variable)
                for field in required
            )
            if has_evidence and unify(conditions, c.features) is not None:
                edges.add((c.span_start, c.span_end, name))
            else:
                pruned += 1
    filter_ms = (time.perf_counter() - t) * 1000
    return sorted(edges), {
        'tokens': len(lattice.tokens),
        'raw_lattice_edges': len(coarse),
        'refined_edges': len(edges),
        'tests': tries,
        'incompatible_tests': pruned,
        'lexical_ms': round(lexical_ms, 3),
        'filter_ms': round(filter_ms, 3)
    }


def worker(text, edges, pipe):
    try:
        budget = 768 * 1024 * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            budget = min(budget, hard)
        resource.setrlimit(resource.RLIMIT_AS, (budget, budget))
        grouped = defaultdict(list)
        for a, b, name in edges:
            grouped[a].append((b, terminal_symbols[name]))

        def recognize(head, fallback):
            at, actions = head.position, head.state.actions
            return [Token(sym, text[at:end], at, length=end-at)
                    for end, sym in grouped.get(at, ()) if sym in actions]

        parser = GLRParser(grammar, table=lrtable,
                           lexical_disambiguation=False,
                           custom_token_recognition=recognize)
        started = time.perf_counter()
        try:
            forest = parser.parse(text)
            status, reason = 'OK', ''
            tree_excerpt = (forest.get_first_tree().to_str()[:3500]
                            if text.startswith('After school, Maya') else None)
        except Exception as exc:
            reason = f'{type(exc).__name__}: {exc}'[:220]
            status = 'REJECT' if type(exc).__name__ == 'SyntaxError' else 'ERROR'
        result = {'status': status, 'reason': reason,
                  'first_tree': tree_excerpt if status == 'OK' else None,
                  'parse_ms': round((time.perf_counter()-started)*1000, 3),
                  'rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    except BaseException as exc:
        result = {'status': 'ERROR', 'reason': f'{type(exc).__name__}: {exc}'[:220]}
    try:
        pipe.send(result)
    finally:
        pipe.close()


def bench():
    global grammar, lrtable, terminal_symbols
    grammar, lrtable = load_table()
    terminal_symbols = grammar.terminals
    specs = json.loads(META.read_text())['terminals']
    resources = ParserResources.from_dir('data')
    cases = json.loads(OLD.read_text())['results']
    ctx = mp.get_context('fork')
    rows = []

    for i, case in enumerate(cases, 1):
        text = case['text'].strip()
        if text.endswith(('.', '!')):
            text = text[:-1].rstrip()
        edges, lexical = candidate_edges(text, resources.lexicon, specs)
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=worker, args=(text, edges, send))
        proc.start()
        send.close()
        proc.join(2.5)
        if proc.is_alive():
            proc.terminate()
            proc.join(1)
            answer = {'status':'TIMEOUT'}
        elif recv.poll(0.15):
            try:
                answer = recv.recv()
            except EOFError:
                answer = {'status':'CRASH', 'reason':f'exit={proc.exitcode}'}
        else:
            answer = {'status':'CRASH', 'reason':f'exit={proc.exitcode}'}
        recv.close()
        row = {'id':case['id'], 'source':case['source'], 'text':case['text'],
               'old_status':case['status'], 'old_parse_ms':case.get('parse_ms'),
               **lexical, **answer}
        rows.append(row)
        OUT.write_text(json.dumps({'results':rows}, indent=2, ensure_ascii=False))
        if i % 10 == 0:
            counts = Counter(r['status'] for r in rows)
            print(f'{i}/100 | OK={counts["OK"]} | REJECT={counts["REJECT"]} | '
                  f'TIMEOUT={counts["TIMEOUT"]} | ERROR={counts["ERROR"]+counts["CRASH"]}', flush=True)

    print('\n==== COMPARAISON ====')
    for source in ('référence', 'roman', 'ensemble'):
        subset = [r for r in rows if source == 'ensemble' or r['source'] == source]
        old = sum(r['old_status'] == 'OK' for r in subset)
        valid = [r for r in subset if r['status'] == 'OK']
        elapsed = sorted(r['parse_ms'] for r in valid)
        p50 = round(statistics.median(elapsed),2) if elapsed else None
        p95 = round(elapsed[min(len(elapsed)-1, int(.95*(len(elapsed)-1)))], 2) if elapsed else None
        print(f'{source}: {old}/{len(subset)} -> {len(valid)}/{len(subset)} | '
              f'p50={p50} ms | p95={p95} ms')

    tests = sum(r['tests'] for r in rows)
    pruned = sum(r['incompatible_tests'] for r in rows)
    print(f'Confrontations candidat × contrainte : {tests} | incompatibles : {pruned} '
          f'({(100 * pruned / tests):.1f} %)' if tests else 'Aucune confrontation')
    print('\nRégressions structurelles :')
    for r in rows:
        if r['old_status'] == 'OK' and r['status'] != 'OK':
            print(' ',r['status'],r['id'],r['text'][:110])
    print('\nCas ponctuation :')
    for r in rows:
        if r['text'].startswith('After school, Maya'):
            print(' ',r['status'],r.get('parse_ms'), 'ms ;',
                  'candidats',r['raw_lattice_edges'],'->',r['refined_edges'])
            if r.get('first_tree'):
                print(r['first_tree'][:1500])
    print('\nSortie :',OUT)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else 'bench'
    if mode == 'build':
        prepare_grammar()
        load_table()
    elif mode == 'bench':
        bench()
    else:
        raise SystemExit('Utilisation : build | bench')
