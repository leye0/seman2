"""Re-test ONLY unfixed sentences. Print passes and update the list."""
import sys
sys.path.insert(0, '.')
from pathlib import Path
from seman_parser.engine import Parser
from seman_parser.unfixed import UNFIXED

p = Parser.from_dir('data', goal_category='CLAUSE')
p2 = Parser.from_dir('data', goal_category='NP')
p.parse('warm up')
p2.parse('warm up')

still_failing = []
for idx, text in UNFIXED:
    r = p.parse(text)
    ok = r.result.completed or p2.parse(text).result.completed
    if ok:
        print(f'PASS {idx:3d}. {text[:72]!r}', flush=True)
    else:
        print(f'FAIL {idx:3d}. {text[:72]!r}', flush=True)
        still_failing.append((idx, text))

print(f'\n{len(UNFIXED) - len(still_failing)}/{len(UNFIXED)} fixed', flush=True)
print(f'still failing: {[i for i, _ in still_failing]}', flush=True)
