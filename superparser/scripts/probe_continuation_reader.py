#!/usr/bin/env python3
"""Print real action-by-action continuation-reader trace for one sentence."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'superparser'))
from seman_parser.continuation_reader import ContinuationReader,ContinuationCounts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('sentence',nargs='?',default='I saw the man with a telescope.')
    ap.add_argument('--data-dir',type=Path,default=ROOT/'superparser/data')
    ap.add_argument('--model',type=Path,default=ROOT/'superparser/data/continuation_counts.json')
    ap.add_argument('--max-steps',type=int,default=8000)
    args=ap.parse_args()
    counts=ContinuationCounts.load(args.model) if args.model.is_file() else ContinuationCounts()
    p=ContinuationReader.from_dir(args.data_dir,counts=counts,max_steps=args.max_steps,trace=True)
    r=p.parse(args.sentence)
    for row in r.stats['trace']:
        if row.get('event')=='REPAIR':
            print(f"{row['at']:>3} REPAIR {row['frame']}: {row['alternative']}")
        else:
            print(f"{row['at']:>3} {row['frame']:<10} {str(row['recognized']):<24} "
                  f"{row['action']:<10} {str(row['target']):<16} "
                  f"dormant={row['other_actions_dormant']}")
    print('COMPLETE:',r.completed,'STATS:',{k:v for k,v in r.stats.items() if k in {
       'decisions_executed','revisions','choices_deferred','frames_opened',
       'rules_completed','lexical_consumptions','total_wall_ms','stopped_by'}})
    if r.item:print('ROOT:',r.item.category)
if __name__=='__main__':main()
