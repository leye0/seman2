import sys
sys.path.insert(0, '.')
from pathlib import Path
from seman_parser.coverage import extract_sentences
from seman_parser.engine import Parser

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end = int(sys.argv[2]) if len(sys.argv) > 2 else start + 10
cases = extract_sentences(Path('../data/the_map_of_everything_nlp_novel.txt'), limit=500)[start:end]
p = Parser.from_dir('data', goal_category='CLAUSE')
p2 = Parser.from_dir('data', goal_category='NP')
p.parse('warm up')
p2.parse('warm up')
ok = 0
for i, c in enumerate(cases, start):
    r = p.parse(c.text)
    good = r.result.completed or p2.parse(c.text).result.completed
    ok += bool(good)
    print(f'{"OK" if good else "FAIL"} {i:3d}. {c.text[:72]!r}', flush=True)
print(f'--- {ok}/{len(cases)}', flush=True)
