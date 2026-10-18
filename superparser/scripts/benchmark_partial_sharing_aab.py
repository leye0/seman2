"""Paired A/A/B evaluation of lossless boundary reuse and partial skeletons.

Experiment only. The memoized mode is OFF in production. Baseline is
parsed twice to estimate ordinary timing noise on the *same* pinned text
and lexical lattice. All tree/forest parity checks are mandatory.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

ROOT=Path(__file__).resolve().parents[1]
ARMS=("baseline_a","cached","baseline_b")
PARITY=("completed","forest_nodes","partial_states",
        "structural_derivations","partial_derivations",
        "budget_exceeded","kbest_budget_exceeded","dialogue_scoped")


def prepared_parser(resources,cache_boundaries):
    parser=Parser(resources,cache_size=0,max_items=20000)
    if cache_boundaries:
        parser._vector_grammar=VectorGrammar(
            parser._vector_grammar.grammar,cache_boundaries=True)
        if parser._dialogue_vector_grammar is not None:
            parser._dialogue_vector_grammar=VectorGrammar(
                parser._dialogue_vector_grammar.grammar,
                preserve_quote_delimiters=True,cache_boundaries=True)
    return parser


def structural_duplication(result):
    """Optimistic common-category-skeleton budget, NOT safe parse merging.

    Rules with different constraints or semantic actions MUST NOT be merged
    just because their LHS/RHS category names agree. This measures only
    whether trying such a design could be worthwhile.
    """
    forest=result.shared_forest
    if forest is None:
        return {"partials":0,"skeleton_slots":0,"potential_duplicates":0,
                "prefix_slots":0,"potential_prefix_reuse":0}
    full_skeleton=set()
    prefix_slots=set()
    prefix_cache={}
    for partial in forest.partials:
        rule=forest.compiled.rules[partial.rule_index].rule
        full_skeleton.add((
            partial.start,partial.end,partial.dot,
            rule.lhs.category,tuple(slot.category for slot in rule.rhs)))
        key=(partial.rule_index,partial.dot)
        prefix=prefix_cache.get(key)
        if prefix is None:
            # A matched rule prefix may be shared only if *all its own*
            # constraints and named exports are identical. RHS suffix,
            # rule identity/score and semantic actions remain independent.
            prefix=tuple(json.dumps(slot.as_dict(),sort_keys=True,
                                    separators=(",",":"),ensure_ascii=False)
                         for slot in rule.rhs[:partial.dot])
            prefix_cache[key]=prefix
        prefix_slots.add((partial.start,partial.end,partial.dot,prefix))
    return {
        "partials":len(forest.partials),
        "skeleton_slots":len(full_skeleton),
        "potential_duplicates":len(forest.partials)-len(full_skeleton),
        "prefix_slots":len(prefix_slots),
        "potential_prefix_reuse":len(forest.partials)-len(prefix_slots),
    }


def run_parse(parser,lattice):
    began=perf_counter_ns()
    result=parser.parse_grammar_lattice(
        lattice,max_items=20000,kbest_work_limit=100000)
    elapsed=(perf_counter_ns()-began)/1e6
    best=result.best()
    return result,{
        "ms":round(elapsed,6),
        "completed":result.completed,
        "best":best.as_dict() if best else None,
        "forest_nodes":result.stats.get("forest_nodes",0),
        "partial_states":result.stats.get("partial_states",0),
        "structural_derivations":result.stats.get("structural_derivations",0),
        "partial_derivations":result.stats.get("partial_derivations",0),
        "budget_exceeded":bool(result.stats.get("budget_exceeded")),
        "kbest_budget_exceeded":bool(result.stats.get("kbest_budget_exceeded")),
        "dialogue_scoped":bool(result.stats.get("dialogue_scoped",False)),
        "boundary_cache_hits":result.stats.get("boundary_cache_hits",0),
        "boundary_cache_misses":result.stats.get("boundary_cache_misses",0),
    }


def quantile(values,q):
    if not values:
        return None
    v=sorted(values)
    i=(len(v)-1)*q
    at=int(i)
    return round(v[at]+(v[min(at+1,len(v)-1)]-v[at])*(i-at),4)


def cohort(rows):
    result={"n":len(rows)}
    for arm in ARMS:
        vals=[r[arm]["ms"] for r in rows]
        result[arm]={
            "p50_ms":quantile(vals,.5),
            "p95_ms":quantile(vals,.95),
            "total_ms":round(sum(vals),3),
        }
    for arm in ("cached","baseline_b"):
        result[arm]["total_ratio_vs_baseline_a"]=(
            round(result[arm]["total_ms"]/result["baseline_a"]["total_ms"],4)
            if result["baseline_a"]["total_ms"] else None)
        result[arm]["slower_over_20pct"]=sum(
            r[arm]["ms"]>1.2*r["baseline_a"]["ms"] for r in rows)
    return result


def summarize(rows,sources):
    return {
        "schema":"boundary-cache-and-skeleton-aab-v1",
        "sources":sources,
        "all":cohort(rows),
        "by_length":{label:cohort([r for r in rows if r["band"]==label])
                     for label,_,_ in BANDS},
        "by_book":{str(book):cohort([r for r in rows if r["book_id"]==book])
                   for book in sorted({r["book_id"] for r in rows})},
        "parity_failures":sum(not r["parity"] for r in rows),
        "baseline_repeat_failures":sum(not r["repeat_parity"] for r in rows),
        "forest_saturations":sum(r["baseline_a"]["budget_exceeded"] for r in rows),
        "skeletons":{
            "logical_partial_states":sum(r["sharing"]["partials"] for r in rows),
            "category_skeleton_slots":sum(r["sharing"]["skeleton_slots"] for r in rows),
            "optimistic_duplicate_slots":sum(r["sharing"]["potential_duplicates"] for r in rows),
            "feature_exact_prefix_slots":sum(r["sharing"]["prefix_slots"] for r in rows),
            "potential_feature_exact_prefix_reuse":sum(
                r["sharing"]["potential_prefix_reuse"] for r in rows),
            "by_length":{label:{
                "partial_states":sum(r["sharing"]["partials"] for r in rows if r["band"]==label),
                "category_skeleton_duplicates":sum(r["sharing"]["potential_duplicates"]
                                                     for r in rows if r["band"]==label),
                "potential_feature_exact_prefix_reuse":sum(
                    r["sharing"]["potential_prefix_reuse"]
                    for r in rows if r["band"]==label)}
                 for label,_,_ in BANDS},
        },
        "boundary_cache":{
            "hits":sum(r["cached"]["boundary_cache_hits"] for r in rows),
            "misses":sum(r["cached"]["boundary_cache_misses"] for r in rows),
        },
        "notes":[
            "A/A/B same one lexical lattice; order counterbalanced on alternating samples.",
            "Baseline parser and grammar unchanged; memoization research-only, default OFF.",
            "Every completed tree, syntax anchor, lexical source, completion, forest count and budget must agree.",
            "Category skeleton duplicates are optimistic, not sound shared states.",
            "Feature-exact matched prefixes can share recognition evidence only; future rule variants and semantic actions remain distinct.",
            "Measure separate fast-sentence cohort and A/A noise before enabling any optimization.",
            "Timings exclude lattice building and structural-duplication audit.",
            "Corpus stratification is not a representative web/text workload.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=8)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    cases,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    baseline=prepared_parser(resources,False)
    cached=prepared_parser(resources,True)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as out:
        for i,case in enumerate(cases):
            lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
            tasks=[("baseline_a",baseline),("cached",cached),("baseline_b",baseline)]
            if i%2:
                tasks=list(reversed(tasks))
            measured={}
            outcomes={}
            for name,parser in tasks:
                outcome,record=run_parse(parser,lattice)
                measured[name]=record
                outcomes[name]=outcome
            base=measured["baseline_a"]
            parity=(all(measured["cached"].get(key)==base.get(key) for key in PARITY)
                    and measured["cached"]["best"]==base["best"])
            repeat=(all(measured["baseline_b"].get(key)==base.get(key) for key in PARITY)
                    and measured["baseline_b"]["best"]==base["best"])
            sharing=structural_duplication(outcomes["baseline_a"])
            rec={
                "index":i,"book_id":case["book_id"],"band":case["band"],
                "ordinal":case["ordinal"],"text":case["text"],
                "sentence_sha256":sha256(case["text"].encode()).hexdigest(),
                "tokens":case["tokens"],"parity":parity,"repeat_parity":repeat,
                "sharing":sharing,
                **{key:{k:v for k,v in val.items() if k!="best"}
                   for key,val in measured.items()},
            }
            records.append(rec)
            out.write(json.dumps(rec,ensure_ascii=False)+"\n")
            if (i+1)%16==0:
                print("PREFIX_AAB_PROGRESS",json.dumps({
                    "seen":i+1,"parity_failures":sum(not x["parity"] for x in records),
                    "skeleton_duplicates":sum(x["sharing"]["potential_duplicates"] for x in records),
                }),flush=True)
    summary=summarize(records,sources)
    (args.out_dir/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("PREFIX_AAB_FINAL",json.dumps(summary),flush=True)
    if summary["parity_failures"] or summary["baseline_repeat_failures"]:
        raise SystemExit("FAILED: structural/tree parity mismatch between matched parses")


if __name__=="__main__":
    main()
