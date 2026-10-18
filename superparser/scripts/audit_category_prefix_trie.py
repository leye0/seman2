"""Audit category-prefix trie replay over the four preserved novels.

No alternate parser is substituted. Canonical forest nodes are the fixed
oracle; trie replays category-prefix transitions once per unique prefix/span.
Only NONSATURATED forests can verify all canonical rule-specific states.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from research.verbnet_lr.category_prefix_trie import CategoryPrefixTrie
from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def aggregate(rows):
    proven=[r for r in rows if not r["saturated"]]
    c=sum(r["canonical_partial_states"] for r in proven)
    t=sum(r["shared_prefix_states"] for r in proven)
    return {
        "sentences":len(rows),
        "unsaturated_verified":len(proven),
        "saturated_skipped":len(rows)-len(proven),
        "projection_failures":sum(len(r["projection_failures"]) for r in proven),
        "canonical_partials_verified":c,
        "shared_trie_partials_verified":t,
        "fewer_prefix_states":c-t,
        "potential_prefix_state_reuse_rate":round(1-t/c,5) if c else None,
        "verified_partial_derivation_edges":sum(r["verified_edges"] for r in proven),
        "canonical_recognition_total_ms":round(sum(r["canonical_recognition_ms"] for r in rows),3),
        "posthoc_trie_replay_total_ms":round(sum(r["trie_replay_ms"] for r in rows),3),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=4)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    cases,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    grammar=parser._vector_grammar
    trie=CategoryPrefixTrie(grammar)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as stream:
        for i,item in enumerate(cases):
            lattice=build_lattice(item["text"],resources.lexicon,multiword_max=1)
            result=grammar.parse_lattice(
                lattice,beam=80,max_items=20000,goal_category="CLAUSE",
                kbest_work_limit=100000)
            start=perf_counter_ns()
            replay=trie.replay(result.shared_forest,check_canonical=True)
            replay_ms=(perf_counter_ns()-start)/1e6
            row={
                "index":i,"book_id":item["book_id"],"band":item["band"],
                "tokens":item["tokens"],"text":item["text"],
                "sha256":sha256(item["text"].encode()).hexdigest(),
                "completed":result.completed,
                "canonical_recognition_ms":result.stats["recognition_ms"],
                "trie_replay_ms":round(replay_ms,4),
                **replay,
            }
            rows.append(row)
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%8==0:
                s=aggregate(rows)
                print("TRIE_AUDIT_PROGRESS",json.dumps({
                    "seen":i+1,
                    "unsaturated_verified":s["unsaturated_verified"],
                    "fewer_prefix_states":s["fewer_prefix_states"]
                }),flush=True)
    summary={
        "schema":"category-prefix-trie-replay-v1",
        "sources":sources,
        "all":aggregate(rows),
        "by_band":{band:aggregate([r for r in rows if r["band"]==band])
                   for band,_,_ in BANDS},
        "trie_nodes":len(trie.nodes),
        "grammar_rule_count":len(grammar.rules),
        "notes":[
            "Category-prefix trie shares ACTUAL category-prefix state progressions across rule variants.",
            "Forest constituents come from the completed canonical parser: this is a non-autonomous, posthoc oracle replay.",
            "Only unsaturated forests are checked for exact rule-specific state and edge equivalence.",
            "Saturated forests can have noncanonical extra potential states; excluded from reuse percentage.",
            "Features, scores, valence, full rule identity and semantics have NOT been merged.",
            "Replay time is NOT a measured runtime speedup; canonical nodes were already built first.",
            "Proof of correctness and budget semantics of a standalone online trie remains future work.",
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("TRIE_AUDIT_FINAL",json.dumps(summary),flush=True)


if __name__=="__main__":
    main()
