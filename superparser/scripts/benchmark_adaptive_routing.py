"""Paired, label-free calibrated research audit of preparse complexity routing.

For each held-out Gutenberg book, calibrate only the preparse rule-start
score distribution on the other THREE books. No parse outcome or latency
enters the threshold choice. Always test ALL selected examples (easy and
hard), with A/adaptive/A ordering and exact output comparisons.

Research only. The policy remains disabled by default and is not a
generalized author-held-out production model.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.complexity_routing import ComplexityPolicy, StructuralRiskRouter
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]
ARMS=("reference_a","adaptive","reference_b")


def percentile(values,quantile):
    vals=sorted(values)
    if not vals:
        raise ValueError("Cannot learn from empty eligible cohort")
    return vals[min(len(vals)-1,int(math.ceil(len(vals)*quantile)-1))]


def calibrate(rows,router,min_tokens,share):
    """Train one cutoff per held-out book without touching result labels."""
    scores={
        i:router.score(r["lattice"])
        for i,r in enumerate(rows)
        if (r["tokens"]>=min_tokens and
            not any(q in r["text"] for q in ('"','“','”','‘','’')))
    }
    learned={}
    for book in sorted({row["book_id"] for row in rows}):
        other=[score for i,score in scores.items()
               if rows[i]["book_id"]!=book]
        learned[book]=max(1,percentile(other,1-share))
    return learned,scores


def timed(parser,lattice):
    tick=perf_counter_ns()
    parsed=parser.parse_grammar_lattice(
        lattice,max_items=20000,kbest_work_limit=100000)
    best=parsed.best()
    trees=[x.as_dict() for x in parsed.alternatives(limit=2)]
    ms=(perf_counter_ns()-tick)/1e6
    return parsed,{
        "ms":round(ms,5),
        "completed":parsed.completed,
        "best":best.as_dict() if best else None,
        "alternatives":trees,
        "budget":bool(parsed.stats.get("budget_exceeded")),
        "kbest_budget":bool(parsed.stats.get("kbest_budget_exceeded")),
        "nodes":parsed.stats.get("forest_nodes",0),
        "partials":parsed.stats.get("partial_states",0),
        "partial_derivations":parsed.stats.get("partial_derivations",0),
        "structural_derivations":parsed.stats.get("structural_derivations",0),
        "recognition_operations":parsed.stats.get("recognition_operations",0),
        "route":parsed.stats.get("complexity_route"),
        "score":parsed.stats.get("complexity_score"),
        "reason":parsed.stats.get("complexity_reason"),
        "probe_ms":parsed.stats.get("complexity_probe_ms",0),
        "flat":bool(parsed.stats.get("online_prefix_flat_enabled")),
    }


def parity(reference,variant):
    keys=("completed","best","alternatives","budget","kbest_budget",
          "nodes","partials","partial_derivations",
          "structural_derivations","recognition_operations")
    bad=[key for key in keys if reference[key]!=variant[key]]
    if bad:
        raise AssertionError("Canonical grammatical/budget parity failed: "+str(bad))


def complete_edge_parity(a,b):
    x,y=a.shared_forest,b.shared_forest
    if len(x.partials)!=len(y.partials):
        raise AssertionError("Different partial counts")
    count=0
    for original,alternative in zip(x.partials,y.partials):
        if (original.rule_index,original.start,original.end,original.dot)!=(
            alternative.rule_index,alternative.start,alternative.end,
            alternative.dot):
            raise AssertionError("Partial identity changed")
        left=[(d.previous_id,d.child_id) for d in original.derivations]
        right=[(d.previous_id,d.child_id) for d in alternative.derivations]
        if left!=right:
            raise AssertionError("Rule-specific derivations changed")
        count+=len(left)
    return count


def quantile(xs,p):
    v=sorted(xs)
    if not v:
        return None
    i=(len(v)-1)*p
    j=int(i)
    return round(v[j]+(v[min(j+1,len(v)-1)]-v[j])*(i-j),4)


def group(rows):
    result={"n":len(rows),"selection":dict(Counter(r["adaptive"]["reason"] for r in rows)),
            "routed":sum(r["adaptive"]["route"]=="flat" for r in rows),
            "verified_edges":sum(r["verified_edges"] for r in rows)}
    for arm in ARMS:
        time=[r[arm]["ms"] for r in rows]
        result[arm]={
            "total_ms":round(sum(time),3),
            "p50_ms":quantile(time,.5),"p95_ms":quantile(time,.95),
            "completed":sum(r[arm]["completed"] for r in rows),
            "forest_budget":sum(r[arm]["budget"] for r in rows),
        }
    a=result["reference_a"]["total_ms"]
    result["adaptive"]["ratio_vs_a"]=(
        round(result["adaptive"]["total_ms"]/a,4) if a else None)
    result["reference_b"]["ratio_vs_a"]=(
        round(result["reference_b"]["total_ms"]/a,4) if a else None)
    result["probe_total_ms"]=round(sum(r["adaptive"]["probe_ms"] for r in rows),3)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=4)
    p.add_argument("--minimum-tokens",type=int,default=17)
    p.add_argument("--hard-share",type=float,default=.25)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    if not 0<args.hard_share<1:
        p.error("hard-share must be between zero and one")
    raw,sources=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    reference=Parser(resources,cache_size=0,max_items=20000)
    prototype=StructuralRiskRouter(
        reference._vector_grammar.grammar,ComplexityPolicy(
            1,min_tokens=args.minimum_tokens))
    cases=[{**item,"lattice":build_lattice(
                item["text"],resources.lexicon,multiword_max=1)}
           for item in raw]
    learned,training_scores=calibrate(
        cases,prototype,args.minimum_tokens,args.hard_share)
    parsers={book:Parser(
        resources,cache_size=0,max_items=20000,
        complexity_policy=ComplexityPolicy(
            rule_start_threshold=cutoff,
            min_tokens=args.minimum_tokens,
            difficult_strategy="flat"))
        for book,cutoff in learned.items()}
    args.out_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as stream:
        for i,item in enumerate(cases):
            lattice=item["lattice"]
            tasks=[("reference_a",reference),("adaptive",parsers[item["book_id"]]),
                   ("reference_b",reference)]
            if i%2:
                tasks.reverse()
            results={}
            reports={}
            for name,parser in tasks:
                results[name],reports[name]=timed(parser,lattice)
            parity(reports["reference_a"],reports["adaptive"])
            parity(reports["reference_a"],reports["reference_b"])
            routed=reports["adaptive"]["route"]=="flat"
            checked=(complete_edge_parity(
                results["reference_a"],results["adaptive"]) if routed else 0)
            if not routed:
                # Critical: low-risk uses unmodified canonical grammar and
                # has exactly zero work from the specialized recognizer.
                if reports["adaptive"]["flat"]:
                    raise AssertionError("Unselected parse entered alternative engine")
            row={
                "index":i,"book_id":item["book_id"],"band":item["band"],
                "tokens":item["tokens"],"text":item["text"],
                "sha256":sha256(item["text"].encode()).hexdigest(),
                "threshold":learned[item["book_id"]],
                "train_score":training_scores.get(i),
                "verified_edges":checked,
                **{k:{f:v for f,v in record.items()
                      if f not in ("best","alternatives")}
                   for k,record in reports.items()},
            }
            records.append(row)
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%8==0:
                print("ADAPTIVE_PROGRESS",json.dumps({
                    "seen":i+1,"routed":sum(
                        r["adaptive"]["route"]=="flat" for r in records),
                    "verified_edges":sum(r["verified_edges"] for r in records),
                }),flush=True)
    result={
        "schema":"adaptive-grammar-risk-routing-aab-v1",
        "thresholds":{str(k):v for k,v in learned.items()},
        "threshold_training":"top-quartile of preparse score on other 3 novels, no outcomes",
        "sources":sources,
        "all":group(records),
        "easy":group([r for r in records if r["tokens"]<args.minimum_tokens]),
        "eligible":group([r for r in records if r["tokens"]>=args.minimum_tokens]),
        "routed":group([r for r in records if r["adaptive"]["route"]=="flat"]),
        "not_routed":group([r for r in records if r["adaptive"]["route"]!="flat"]),
        "by_band":{band:group([r for r in records if r["band"]==band])
                   for band,_,_ in BANDS},
        "notes":[
            "Same lexicon, lattice, identical parser budgets and underlying grammar.",
            "No grammatical answer, elapsed time or saturation used to choose thresholds.",
            "A/A measurement bracketed around adaptive implementation; order counterbalanced.",
            "Short text has no preparse score and never instantiates a specialized forest.",
            "Complexity score and routing happen before any syntax tree/forest is built.",
            "Dialogue is always routed to the specialist canonical dialogue grammar.",
            "Every selected case has every rule-specific partial edge checked for equivalence.",
            "Fast/default sentences keep canonical mode; runtime policy is not enabled by default.",
            "Four-book exploratory sample has historical leakage into research decisions.",
            "The performance verdict requires repeated independent authors and fast-sentence safeguards.",
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("ADAPTIVE_FINAL",json.dumps(result),flush=True)


if __name__=="__main__":
    main()
