"""Does a compact grammar-prefix signature explain cost beyond sentence length?

Uses one genuine, quote-aware canonical parse per sentence on the identical
four-novel sample; the diagnostic runs *before* parsing. No grammar changes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from research.verbnet_lr.continuation_probe import ContinuationIndex
from scripts.audit_lexical_ambiguity_risk import lexical_ambiguity,auc
from scripts.benchmark_heavy_sentence_ab import choose_cases, BANDS
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]
METRICS=("tokens","category_bits","syntactic_bits",
         "struct_start_sum","struct_start_peak","struct_pair_sum",
         "struct_pair_peak","struct_pair_log_sum","struct_variant_excess")


def matched_auc(rows,key,target):
    """AUC using ONLY positive-negative pairs of exactly equal token length.

    The conditioning removes the trivial effect of longer sentences on both
    lexical option product and structural rule count. No ML is fitted.
    """
    groups={}
    for r in rows:
        groups.setdefault(r["tokens"],[]).append(r)
    wins=0.0
    pairs=0
    for group in groups.values():
        positive=[r[key] for r in group if r[target]]
        negative=[r[key] for r in group if not r[target]]
        for p in positive:
            for n in negative:
                wins+=(p>n)+.5*(p==n)
        pairs+=len(positive)*len(negative)
    return (round(wins/pairs,5) if pairs else None,pairs)


def evaluate(rows):
    def rank(group):
        return {m:{"auc":auc(group,m,"forest_budget"),
                   "exact_length_auc":matched_auc(group,m,"forest_budget")[0],
                   "slow_150ms_auc":auc(group,m,"slow_150ms"),
                   "slow_exact_length_auc":matched_auc(group,m,"slow_150ms")[0]}
                for m in METRICS}
    times=[r["struct_probe_ms"] for r in rows]
    parse=[r["parse_ms"] for r in rows]
    return {
        "schema":"structural-prefix-risk-v1",
        "count":len(rows),
        "forest_budget_hits":sum(r["forest_budget"] for r in rows),
        "kbest_budget_hits":sum(r["kbest_budget"] for r in rows),
        "slow_150ms":sum(r["slow_150ms"] for r in rows),
        "completed":sum(r["completed"] for r in rows),
        "ranking":rank(rows),
        "by_band":{b:{"n":sum(r["band"]==b for r in rows),
                      "ranking":rank([r for r in rows if r["band"]==b])}
                   for b,_,_ in BANDS},
        "by_book":{str(book):rank([r for r in rows if r["book_id"]==book])
                   for book in sorted({r["book_id"] for r in rows})},
        "matched_positive_negative_pairs":{
            "forest_budget":matched_auc(rows,"struct_pair_sum","forest_budget")[1],
            "slow_150ms":matched_auc(rows,"struct_pair_sum","slow_150ms")[1],
        },
        "probe_cost_ms":{
            "median":round(median(times),5) if times else None,
            "p95":quantile(times,.95),"max":round(max(times),5) if times else None,
            "total":round(sum(times),3),
            "total_parse_ms":round(sum(parse),3),
            "whole_corpus_ratio":round(sum(times)/sum(parse),5) if sum(parse) else None,
            "slow_probe_over_1ms":sum(t>1 for t in times),
        },
        "notes":[
            "Precompiled optimistic FIRST(1) and first two RHS slots, NOT a complete grammar parse.",
            "Adjacent-token second-slot match is a heuristic; the first constituent may span several tokens.",
            "Only compatible direct lexical features are checked; indirect features are conservatively unknown.",
            "Metric is diagnostic and cannot safely prune analyses or guarantee grammatical validity.",
            "Exact-length AUC compares ONLY opposite-outcome sentences with identical token counts.",
            "No success/timeout measured by this study implies correctness of a grammar tree.",
            "Full compiler startup work is excluded from per-sentence probe cost and must be amortized.",
            "The corpus is stratified, not a representative population of running text.",
            "No grammar changes, altered parses, active router, or runtime optimization."
        ],
    }


def quantile(xs,p):
    if not xs:
        return None
    xs=sorted(xs)
    pos=(len(xs)-1)*p
    i=int(pos)
    return round(xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(pos-i),5)


def run(args):
    cases,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    begin=perf_counter_ns()
    predictor=ContinuationIndex(parser._vector_grammar.grammar)
    compiler_ms=(perf_counter_ns()-begin)/1e6
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as out:
        for i,case in enumerate(cases):
            lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
            lexical=lexical_ambiguity(lattice)
            structural=predictor.signal(lattice)
            begin=perf_counter_ns()
            result=parser.parse_grammar_lattice(
                lattice,max_items=20000,kbest_work_limit=100000)
            best=result.best() if result.completed else None
            parse_ms=(perf_counter_ns()-begin)/1e6
            stats=result.stats
            row={
                "index":i,"book_id":case["book_id"],"band":case["band"],
                "sentence":case["text"],"tokens":lexical["tokens"],
                "category_bits":lexical["category_bits"],
                "syntactic_bits":lexical["syntactic_bits"],
                "lexical_candidates":lexical["candidate_count"],
                **structural,
                "forest_budget":bool(stats.get("budget_exceeded")),
                "kbest_budget":bool(stats.get("kbest_budget_exceeded")),
                "partial_states":int(stats.get("partial_states",0)),
                "forest_nodes":int(stats.get("forest_nodes",0)),
                "recognition_ms":float(stats.get("recognition_ms",0)),
                "kbest_ms":float(stats.get("best_ms",0)),
                "parse_ms":round(parse_ms,5),
                "slow_150ms":parse_ms>=150,
                "completed":best is not None,
            }
            rows.append(row)
            out.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%32==0:
                print("STRUCT_PREFIX_PROGRESS",json.dumps({
                    "seen":i+1,
                    "saturated":sum(r["forest_budget"] for r in rows),
                    "probe_p50_ms":round(median(r["struct_probe_ms"] for r in rows),4)
                }),flush=True)
    summary=evaluate(rows)
    summary["grammar_compiler"]={
        "compiler_ms":round(compiler_ms,4),
        "rule_count":predictor.rule_count,
        "skeleton_count":predictor.skeleton_count,
        "index_slots":predictor.compiler_slots,
    }
    summary["source"]=sources
    (args.out_dir/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("STRUCT_PREFIX_FINAL",json.dumps({
        "count":summary["count"],"ranking":summary["ranking"],
        "probe_cost_ms":summary["probe_cost_ms"],
        "matched_pairs":summary["matched_positive_negative_pairs"],
        "grammar_compiler":summary["grammar_compiler"],
    }),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=16)
    p.add_argument("--out-dir",type=Path,required=True)
    run(p.parse_args())


if __name__=="__main__":
    main()
