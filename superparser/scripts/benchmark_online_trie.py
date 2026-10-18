"""Controlled A/trie/A benchmark of the autonomous category-prefix engine.

The canonical recognizer is still the production/default path. Both parse
engines receive exactly the same prebuilt lexical lattice, grammar, lexical
resources, forest budget and k-best budget. Recognition and materialization
timings are measured SEPARATELY. GC can be isolated from each timed arm.

For unsaturated parses, validate full logical rule-specific derivation sets
with stable category/start/end and predecessor identities (not raw IDs,
which need not share traversal order). A saturated run is deliberately
flagged as NON-EQUIVALENT/UNCERTIFIED rather than success.
"""
from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from statistics import median
from time import perf_counter_ns,process_time_ns

from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

ROOT=Path(__file__).resolve().parents[1]
ARMS=("canonical_a","trie","canonical_b")


def edge_signatures(forest):
    states={}
    for partial in forest.partials:
        key=(partial.rule_index,partial.dot,partial.start,partial.end)
        edges=set()
        for d in partial.derivations:
            if d.previous_id is None:
                previous=None
            else:
                p=forest.partials[d.previous_id]
                previous=(p.rule_index,p.dot,p.start,p.end)
            child=forest.nodes[d.child_id]
            edges.add((previous,child.category_id,child.start,child.end))
        states[key]=edges
    return states


def parse(grammar,lattice):
    begin_wall=perf_counter_ns()
    begin_cpu=process_time_ns()
    result=grammar.parse_lattice(
        lattice,beam=80,max_items=20000,goal_category="CLAUSE",
        kbest_work_limit=100000)
    best=result.best()
    alt=[x.as_dict() for x in result.alternatives(limit=2)]
    wall_ms=(perf_counter_ns()-begin_wall)/1e6
    cpu_ms=(process_time_ns()-begin_cpu)/1e6
    return result,{
        "wall_ms":round(wall_ms,5),
        "cpu_ms":round(cpu_ms,5),
        "recognition_ms":result.stats.get("recognition_ms",0),
        "kbest_ms":result.stats.get("best_ms",0),
        "completed":result.completed,
        "budget":bool(result.stats.get("budget_exceeded")),
        "kbest_budget":bool(result.stats.get("kbest_budget_exceeded")),
        "partial_states":result.stats.get("partial_states",0),
        "partial_edges":result.stats.get("partial_derivations",0),
        "nodes":result.stats.get("forest_nodes",0),
        "shared_trie_states":result.stats.get("shared_trie_states",0),
        "shared_trie_edges":result.stats.get("shared_trie_edges",0),
        "best":best.as_dict() if best else None,
        "alternatives":alt,
    }


def q(xs,p):
    vals=sorted(xs)
    if not vals:
        return None
    at=(len(vals)-1)*p
    a=int(at)
    return round(vals[a]+(vals[min(a+1,len(vals)-1)]-vals[a])*(at-a),4)


def group(rows):
    summary={
        "n":len(rows),"unsaturated_parity_checked":sum(
            r["strict_edge_parity"] for r in rows),
        "saturated_uncertified":sum(r["saturation_uncertified"] for r in rows),
        "tree_mismatches":sum(r["tree_mismatch"] for r in rows),
        "logical_forest_mismatches":sum(r["forest_mismatch"] for r in rows),
        "shared_trie_states":sum(r["trie"]["shared_trie_states"] for r in rows),
        "canonical_partial_states":sum(r["canonical_a"]["partial_states"] for r in rows),
    }
    for arm in ARMS:
        vals=[r[arm]["cpu_ms"] for r in rows]
        summary[arm]={
            "sum_cpu_ms":round(sum(vals),3),
            "p50_cpu_ms":q(vals,.5),
            "p95_cpu_ms":q(vals,.95),
            "sum_wall_ms":round(sum(r[arm]["wall_ms"] for r in rows),3),
            "sum_recognition_ms":round(sum(r[arm]["recognition_ms"] for r in rows),3),
            "sum_best_ms":round(sum(r[arm]["kbest_ms"] for r in rows),3),
            "saturations":sum(r[arm]["budget"] for r in rows),
            "completion":sum(r[arm]["completed"] for r in rows),
        }
    base=sum(sqrt(r["canonical_a"]["cpu_ms"]*
                  r["canonical_b"]["cpu_ms"]) for r in rows)
    summary["bracketed_cpu_ms"]=round(base,3)
    summary["trie"]["cpu_ratio_vs_bracketed"]=(
        round(summary["trie"]["sum_cpu_ms"]/base,5) if base else None)
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--wordnet-dir",required=True)
    parser.add_argument("--per-book-per-band",type=int,default=6)
    parser.add_argument("--minimum-tokens",type=int,default=17)
    parser.add_argument("--strategy",choices=("project","lazy"),default="lazy")
    parser.add_argument("--max-examples",type=int,default=96)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    cases,sources=choose_cases(args.per_book_per_band)
    # This isolated research audit tests the novel, harder prose first.
    candidates=[
        item for item in cases
        if item["tokens"]>=args.minimum_tokens and
           not any(q in item["text"] for q in ('"','“','”','‘','’'))
    ][:args.max_examples]
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    p=Parser(resources,cache_size=0,max_items=20000)
    standard=p._vector_grammar
    trie=VectorGrammar(
        standard.grammar,
        shared_trie_recognition=args.strategy=="project",
        lazy_trie_recognition=args.strategy=="lazy")
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as output:
        for i,item in enumerate(candidates):
            lattice=build_lattice(item["text"],resources.lexicon,multiword_max=1)
            order=[("canonical_a",standard),("trie",trie),
                   ("canonical_b",standard)]
            if i%2:
                order.reverse()
            gc.collect()
            elapsed_setup=perf_counter_ns()
            was_enabled=gc.isenabled()
            gc.disable()
            try:
                parsed={}
                measurements={}
                for name,grammar in order:
                    parsed[name],measurements[name]=parse(grammar,lattice)
            finally:
                if was_enabled:
                    gc.enable()
            a,b,c=(parsed["canonical_a"],parsed["trie"],parsed["canonical_b"])
            old,new,again=(measurements[k] for k in ARMS)
            repeat=(edge_signatures(a.shared_forest)==
                    edge_signatures(c.shared_forest))
            if not repeat or old["best"]!=again["best"]:
                raise AssertionError("Canonical A/A grammar evidence changed")
            saturated=old["budget"] or new["budget"]
            forest_equal=False
            if not saturated:
                forest_equal=(edge_signatures(a.shared_forest)==
                              edge_signatures(b.shared_forest))
                if not forest_equal:
                    raise AssertionError("Unsaturated trie forest lost rule evidence")
            same_trees=old["best"]==new["best"] and old["alternatives"]==new["alternatives"]
            if not saturated and not same_trees:
                raise AssertionError("Unsaturated trie changed top-k analyses")
            record={
                "index":i,"book_id":item["book_id"],"band":item["band"],
                "tokens":item["tokens"],"text":item["text"],
                "sha256":sha256(item["text"].encode()).hexdigest(),
                "gc_isolated":True,
                "strict_edge_parity":bool(not saturated and forest_equal),
                "saturation_uncertified":bool(saturated),
                "tree_mismatch":not same_trees,
                "forest_mismatch":bool(not saturated and not forest_equal),
                **{name:{key:value for key,value in row.items()
                    if key not in ("best","alternatives")}
                    for name,row in measurements.items()},
            }
            rows.append(record)
            output.write(json.dumps(record,ensure_ascii=False)+"\n")
            if (i+1)%5==0:
                print("ONLINE_TRIE_PROGRESS",json.dumps({
                    "seen":i+1,"strict":sum(r["strict_edge_parity"] for r in rows),
                    "trie_cpu":round(sum(r["trie"]["cpu_ms"] for r in rows),3),
                    "baseline_cpu":round(sum(r["canonical_a"]["cpu_ms"] for r in rows),3),
                }),flush=True)
    summary={
        "schema":"online-trie-recognizer-paired-aab-v1",
        "sources":sources,
        "strategy":args.strategy,
        "all":group(rows),
        "by_band":{name:group([r for r in rows if r["band"]==name])
                   for name,_,_ in BANDS},
        "trie_rule_count":len(trie.rules),
        "static_prefix_nodes":len(trie.trie_nodes),
        "notes":[
            "Online trie constructs its own lexical and grammatical forest; no reference oracle used.",
            "Canonical and trie operate on the exact same lexical lattice, budgets and grammar.",
            "Only unsaturated cases have strict all-derivation and top-k equivalence certification.",
            "Lazy strategy projects original rule partials only as needed by k-best, not during recognition.",
            "Saturated results are NOT certified even when best analyses coincide.",
            "Cyclic garbage collection is disabled around all timed A/B/A arms and setup is excluded.",
            "This run measures hard nonquoted prose only; easy sentences remain protected by separate router tests.",
            "End-to-end speedup must be evaluated after integrating any winning strategy behind preparse routing.",
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ONLINE_TRIE_FINAL",json.dumps(summary),flush=True)


if __name__=="__main__":
    main()
