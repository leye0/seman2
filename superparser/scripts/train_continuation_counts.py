#!/usr/bin/env python3
"""Bootstrap continuation probabilities from externally qualified production trees.

Training on the reference-300 corpus is FOR DEVELOPMENT only, not a holdout.
Only normalized-exact matching parses contribute by default.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'superparser'))
from seman_parser.engine import Parser
from seman_parser.continuation_reader import ContinuationCounts
from scripts.evaluate_reference_300 import normalized_gold, normalized_parser

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--corpus',type=Path,default=ROOT/'data/seman2_reference_300_compact.json')
    ap.add_argument('--data-dir',type=Path,default=ROOT/'superparser/data')
    ap.add_argument('--output',type=Path,default=ROOT/'superparser/data/continuation_counts.json')
    ap.add_argument('--limit',type=int,default=300)
    args=ap.parse_args()
    corpus=json.loads(args.corpus.read_text(encoding='utf-8'))['sentences'][:args.limit]
    parser=Parser.from_dir(args.data_dir,cache_size=0)
    model=ContinuationCounts()
    accepted=0
    for i,row in enumerate(corpus):
        tree=parser.parse(row['text']).result.best()
        if tree is not None and normalized_parser(tree)==normalized_gold(row['tree']):
            model.observe_tree(tree)
            accepted+=1
        if (i+1)%50==0:
            print(f'{i+1}/{len(corpus)}: {accepted} trusted trees',file=sys.stderr,flush=True)
    model.save(args.output)
    print(f'Saved {accepted} trusted trees to {args.output}; training and evaluation corpus overlap.')
if __name__=='__main__':main()
