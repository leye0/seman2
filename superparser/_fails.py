import sys
sys.path.insert(0, '.')
from pathlib import Path
from seman_parser.coverage import extract_sentences
from seman_parser.engine import Parser

cases = extract_sentences(Path('../data/the_map_of_everything_nlp_novel.txt'), limit=500)
p = Parser.from_dir('data', goal_category='CLAUSE')
p2 = Parser.from_dir('data', goal_category='NP')
p.parse('warm up')
p2.parse('warm up')
fails = []
for i, c in enumerate(cases):
    r = p.parse(c.text)
    if not (r.result.completed or p2.parse(c.text).result.completed):
        fails.append((i, c.text))
print(f'fails: {len(fails)}/500', flush=True)
for i, t in fails:
    print(f'{i:3d}. {t[:90]}', flush=True)
