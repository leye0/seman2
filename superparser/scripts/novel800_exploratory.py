"""Exploratory, reproducible N701-N800 cohort; never bypass Novel-700 acceptance.

This candidate is intentionally *outside* research/novel_ladder so the
production ladder's freeze() / accepted_cases() review gate remains intact.
Only publish a real Novel-800 rung after all 100 Novel-700 attachments
have individually grounded verdicts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal

from scripts import novel_ladder as ladder
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources

CANDIDATE = ROOT / "research" / "novel_800_exploration" / "novel-800-candidate-cohort.json"
FIRST = 701
END = 800

def prepare(sources):
    cohorts, exclude_paragraphs, exclude_texts = ladder.read_ladder(ladder.LADDER, sources)
    if [group[-1]["ladder_index"] for _,group in cohorts] != [600,700]:
        raise RuntimeError("Novel-600 and Novel-700 are required and immutable")
    manifest700, _ = cohorts[-1]
    previous700 = ladder.read_json(ladder.LADDER/"novel-700-current.json")
    rows700 = ladder.result_cases(previous700, manifest700, 700)
    if len(rows700) != 100 or any(r["status"]!="complete" for r in rows700.values()):
        raise RuntimeError("Novel-700 must have 100 full syntax + graph results")
    accepted700 = ladder.LADDER/"novel-700-accepted.json"
    if accepted700.exists():
        raise RuntimeError("This exploratory route is obsolete once Novel-700 is accepted")
    selected = ladder.pick(sources[1],exclude_paragraphs,exclude_texts,FIRST)
    anchors=[ladder.anchor(index,band,case) for index,band,case in selected]
    manifest={
      "schema":ladder.SCHEMA,"first_index":FIRST,
      "legacy_cohort_sha256":ladder.EXPECTED_500_COHORT_SHA256,
      "editions":sources[3],
      "cohort_sha256":ladder.digest(anchors),
      "anchors":anchors,
    }
    if len({(a[1],a[2]) for a in anchors}) != 100:
        raise RuntimeError("Expected 100 unique paragraph contexts")
    cases=ladder.resolve(manifest,FIRST,sources)
    if sorted(Counter(c["book_id"] for c in cases).values())!=[25]*4:
        raise RuntimeError("Not balanced across the four books")
    if sorted(Counter(c["band"] for c in cases).values())!=[25]*4:
        raise RuntimeError("Not balanced across four length bands")
    return manifest,cases

def stage(sources):
    manifest,cases=prepare(sources)
    if CANDIDATE.exists():
        old=ladder.read_json(CANDIDATE)
        if old != manifest:
            raise RuntimeError("The staged N800 source identity differs from the deterministic selection")
    else:
        CANDIDATE.parent.mkdir(parents=True,exist_ok=True)
        ladder.write_json(CANDIDATE,manifest)
    print("N800_CANDIDATE_COHORT_SHA256",manifest["cohort_sha256"],flush=True)
    print("N800_MANIFEST_JSON",json.dumps(manifest,ensure_ascii=False,separators=(",",":")),flush=True)
    return manifest,cases

def run(wordnet_dir,out_dir):
    sources=ladder.load_sources()
    manifest,cases=stage(sources)
    parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir),
                  cache_size=0,max_items=ladder.MAX_ITEMS)
    parser.parse("John opened the box.")
    out_dir.mkdir(parents=True,exist_ok=True)
    prev=signal.signal(signal.SIGALRM,_deadline)
    rows=[]
    try:
        with (out_dir/"novel-800-candidate-parses.jsonl").open("w",encoding="utf-8",buffering=1) as stream:
            for case in cases:
                observed=measure(parser,case,with_semantics=True)
                row={**case,**observed}
                stream.write(json.dumps(row,ensure_ascii=False)+"\n")
                rows.append(row)
                brief={
                    "index":case["ladder_index"],
                    "book":case["book_id"],
                    "band":case["band"],
                    "status":row["status"],
                    "root":row.get("root_rule"),
                    "wall_ms":row["wall_ms"],
                    "forest_budget":row.get("forest_budget_exceeded",False),
                    "kbest_budget":row.get("kbest_budget_exceeded",False),
                    "source":case["source_text"],
                    "source_span":case["structural_core_source_span"],
                }
                print("N800_CASE",json.dumps(brief,ensure_ascii=False,separators=(",",":")),flush=True)
    finally:
        signal.signal(signal.SIGALRM,prev)
    counts=dict(sorted(Counter(r["status"] for r in rows).items()))
    result={
      "schema":"seman2-novel-ladder-result-v1",
      "cohort_sha256":manifest["cohort_sha256"],
      "limits":ladder.LIMITS,
      "counts":counts,
      "cases":ladder.signatures(rows)
    }
    ladder.result_cases(result,manifest,END)
    ladder.write_json(out_dir/"novel-800-candidate-initial.json",result)
    ladder.write_json(out_dir/"novel-800-candidate-current.json",result)
    summary={
       "cohort_sha256":manifest["cohort_sha256"],
       "accepted":False,
       "grammar_validated":False,
       "source_count":100,
       "counts":counts,
       "by_book":{str(k):dict(Counter(r["status"] for r in rows if r["book_id"]==k))
                  for k in sorted({r["book_id"] for r in rows})},
       "by_band":{str(k):dict(Counter(r["status"] for r in rows if r["band"]==k))
                  for k in sorted({r["band"] for r in rows})},
       "incomplete": [
          {"index":r["ladder_index"],"source_text":r["source_text"],
           "book_id":r["book_id"],"status":r["status"],
           "forest_budget_exceeded":r.get("forest_budget_exceeded",False),
           "kbest_budget_exceeded":r.get("kbest_budget_exceeded",False),
           "wall_ms":r["wall_ms"],
           "source_span":r["structural_core_source_span"]}
          for r in rows if r["status"]!="complete"
       ],
    }
    ladder.write_json(out_dir/"novel-800-candidate-summary.json",summary)
    print("N800_CANDIDATE_SUMMARY",json.dumps(summary,ensure_ascii=False,separators=(",",":")),flush=True)
    print("N800_CANDIDATE_RESULT",json.dumps(result,ensure_ascii=False,separators=(",",":")),flush=True)
    return result

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=("stage","run"))
    cli.add_argument("--wordnet-dir",type=Path)
    cli.add_argument("--out-dir",type=Path)
    args=cli.parse_args()
    if args.action=="stage":stage(ladder.load_sources())
    else:
        if args.wordnet_dir is None or args.out_dir is None:
            cli.error("run requires --wordnet-dir and --out-dir")
        run(args.wordnet_dir,args.out_dir)

if __name__=="__main__":main()
