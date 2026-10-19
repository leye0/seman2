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
import gc
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter_ns, process_time_ns

from scripts.corpus_samples import BANDS,choose_cases
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


def calibrate_bands(rows,scores,min_tokens,share):
    """Length-conditioned thresholds, learned from other books' scores only."""
    bounds=((17,24),(25,32))
    results={}
    for book in sorted({row["book_id"] for row in rows}):
        calibrated=[]
        for lower,upper in bounds:
            if upper<min_tokens:
                continue
            other=[score for i,score in scores.items()
                   if rows[i]["book_id"]!=book
                   and lower<=rows[i]["tokens"]<=upper]
            if other:
                calibrated.append((max(min_tokens,lower),upper,
                                   max(1,percentile(other,1-share))))
        results[book]=tuple(calibrated)
    return results


def timed(parser,lattice):
    tick=perf_counter_ns()
    cpu_tick=process_time_ns()
    parsed=parser.parse_grammar_lattice(
        lattice,max_items=20000,kbest_work_limit=100000)
    best=parsed.best()
    trees=[x.as_dict() for x in parsed.alternatives(limit=2)]
    ms=(perf_counter_ns()-tick)/1e6
    cpu_ms=(process_time_ns()-cpu_tick)/1e6
    return parsed,{
        "ms":round(ms,5),
        "cpu_ms":round(cpu_ms,5),
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
        "recognition_ms":parsed.stats.get("recognition_ms",0),
        "best_ms":parsed.stats.get("best_ms",0),
        "kbest_work_units":parsed.stats.get("kbest_work_units",0),
        "trie":bool(parsed.stats.get("lazy_trie_recognition")),
    }


def parity(reference,variant):
    keys=("completed","best","alternatives","budget","kbest_budget",
          "nodes","partials","partial_derivations",
          "structural_derivations","recognition_operations")
    bad=[key for key in keys if reference[key]!=variant[key]]
    if bad:
        raise AssertionError("Canonical grammatical/budget parity failed: "+str(bad))


def normalized_forest_edges(result):
    forest=result.shared_forest
    normalized={}
    for p in forest.partials:
        key=(p.rule_index,p.dot,p.start,p.end)
        edges=set()
        for d in p.derivations:
            if d.previous_id is None:
                prev=None
            else:
                parent=forest.partials[d.previous_id]
                prev=(parent.rule_index,parent.dot,parent.start,parent.end)
            child=forest.nodes[d.child_id]
            edges.add((prev,child.category_id,child.start,child.end))
        normalized[key]=edges
    return normalized


def quantile(xs,p):
    v=sorted(xs)
    if not v:
        return None
    i=(len(v)-1)*p
    j=int(i)
    return round(v[j]+(v[min(j+1,len(v)-1)]-v[j])*(i-j),4)


def group(rows):
    result={"n":len(rows),"selection":dict(Counter(r["adaptive"]["reason"] for r in rows)),
            "routed":sum(r["adaptive"]["route"] not in (None,"canonical") for r in rows),
            "verified_edges":sum(r["verified_edges"] for r in rows),
            "strict_trie_cases":sum(r["strict_trie_parity"] for r in rows),
            "saturated_uncertified":sum(r["saturated_uncertified"] for r in rows),
            "saturated_tree_mismatches":sum(r["saturated_tree_mismatch"] for r in rows)}
    for arm in ARMS:
        time=[r[arm]["ms"] for r in rows]
        result[arm]={
            "total_ms":round(sum(time),3),
            "cpu_total_ms":round(sum(r[arm]["cpu_ms"] for r in rows),3),
            "p50_ms":quantile(time,.5),"p95_ms":quantile(time,.95),
            "completed":sum(r[arm]["completed"] for r in rows),
            "forest_budget":sum(r[arm]["budget"] for r in rows),
        }
    a=result["reference_a"]["total_ms"]
    result["adaptive"]["ratio_vs_a"]=(
        round(result["adaptive"]["total_ms"]/a,4) if a else None)
    result["reference_b"]["ratio_vs_a"]=(
        round(result["reference_b"]["total_ms"]/a,4) if a else None)
    cpu_a=result["reference_a"]["cpu_total_ms"]
    for arm in ("adaptive","reference_b"):
        result[arm]["cpu_ratio_vs_a"]=round(
            result[arm]["cpu_total_ms"]/cpu_a,4) if cpu_a else None
    result["probe_total_ms"]=round(sum(r["adaptive"]["probe_ms"] for r in rows),3)
    result["gc_setup_ms"]=round(sum(r["gc_setup_ms"] for r in rows),3)
    result["recognition_totals_ms"]={
        arm:round(sum(r[arm]["recognition_ms"] for r in rows),3)
        for arm in ARMS}
    result["kbest_totals_ms"]={
        arm:round(sum(r[arm]["best_ms"] for r in rows),3)
        for arm in ARMS}
    result["kbest_work_totals"]={
        arm:sum(r[arm]["kbest_work_units"] for r in rows)
        for arm in ARMS}
    # Baseline A/A alone is noisy on shared runners; bracket adaptive latency
    # with the geometric mean of two same-sentence canonical passes.
    paired=[math.sqrt(r["reference_a"]["ms"]*r["reference_b"]["ms"])
            for r in rows]
    total_paired=sum(paired)
    result["bracketed_baseline_ms"]=round(total_paired,3)
    result["adaptive"]["ratio_vs_bracketed_baseline"]=(
        round(result["adaptive"]["total_ms"]/total_paired,4)
        if total_paired else None)
    result["baseline_aa_drift_over_20pct"]=sum(
        abs(math.log(r["reference_a"]["ms"]/r["reference_b"]["ms"]))
        >math.log(1.2) for r in rows
        if r["reference_a"]["ms"] and r["reference_b"]["ms"])
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=4)
    p.add_argument("--minimum-tokens",type=int,default=17)
    p.add_argument("--hard-share",type=float,default=.25)

    p.add_argument("--isolate-gc",action="store_true",
                   help="Collect before each sentence and suspend cyclic GC only for A/B/A timing")
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
    learned_bands=calibrate_bands(
        cases,training_scores,args.minimum_tokens,args.hard_share)
    policies={book:ComplexityPolicy(
        rule_start_threshold=cutoff,
        min_tokens=args.minimum_tokens,
        difficult_strategy="trie",
        band_thresholds=learned_bands[book])
        for book,cutoff in learned.items()}
    parsers={book:Parser(
        resources,cache_size=0,max_items=20000,
        complexity_policy=policy)
        for book,policy in policies.items()}
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
            # Research timing only: never let an unpredictable cyclic-GC
            # scan land inside one of the three timed arms. We still
            # measure aggregate cleanup separately, not as an optimization.
            setup_ns=perf_counter_ns()
            if args.isolate_gc:
                gc.collect()
            gc_setup_ms=(perf_counter_ns()-setup_ns)/1e6
            was_gc_enabled=gc.isenabled()
            if args.isolate_gc:
                gc.disable()
            try:
                for name,parser in tasks:
                    results[name],reports[name]=timed(parser,lattice)
            finally:
                if args.isolate_gc and was_gc_enabled:
                    gc.enable()
            parity(reports["reference_a"],reports["reference_b"])
            routed=reports["adaptive"]["route"]=="trie"
            strict=False
            saturated_uncertified=False
            saturated_tree_mismatch=False
            checked=0
            if routed:
                original=reports["reference_a"]
                candidate=reports["adaptive"]
                saturated_uncertified=bool(original["budget"] or candidate["budget"])
                same_trees=(
                    original["completed"]==candidate["completed"]
                    and original["best"]==candidate["best"]
                    and original["alternatives"]==candidate["alternatives"])
                if not saturated_uncertified:
                    if not same_trees:
                        raise AssertionError("Unsaturated trie changed best/top-k")
                    left=normalized_forest_edges(results["reference_a"])
                    right=normalized_forest_edges(results["adaptive"])
                    if left!=right:
                        raise AssertionError("Unsaturated trie lost original rule derivations")
                    checked=sum(len(edges) for edges in left.values())
                    strict=True
                else:
                    saturated_tree_mismatch=not same_trees
            else:
                parity(reports["reference_a"],reports["adaptive"])
            if not routed:
                # Critical: low-risk uses unmodified canonical grammar and
                # incurs zero specialized recognition.
                if reports["adaptive"]["trie"]:
                    raise AssertionError("Unselected parse entered alternative engine")
            row={
                "index":i,"book_id":item["book_id"],"band":item["band"],
                "tokens":item["tokens"],"text":item["text"],
                "sha256":sha256(item["text"].encode()).hexdigest(),
                "threshold":policies[item["book_id"]].threshold_for(item["tokens"]),
                "train_score":training_scores.get(i),
                "verified_edges":checked,
                "strict_trie_parity":strict,
                "saturated_uncertified":saturated_uncertified,
                "saturated_tree_mismatch":saturated_tree_mismatch,
                "gc_setup_ms":round(gc_setup_ms,4),
                **{k:{f:v for f,v in record.items()
                      if f not in ("best","alternatives")}
                   for k,record in reports.items()},
            }
            records.append(row)
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%8==0:
                print("ADAPTIVE_PROGRESS",json.dumps({
                    "seen":i+1,"routed":sum(
                        r["adaptive"]["route"]=="trie" for r in records),
                    "verified_edges":sum(r["verified_edges"] for r in records),
                }),flush=True)
    result={
        "schema":"adaptive-grammar-risk-routing-aab-v1",
        "strategy":"trie",
        "isolated_cyclic_gc":args.isolate_gc,
        "thresholds":{str(k):v for k,v in learned.items()},
        "band_thresholds":{str(k):v for k,v in learned_bands.items()},
        "threshold_training":"top-quartile of preparse score within each 17-24 / 25-32 length band on other 3 novels, no outcomes",
        "sources":sources,
        "all":group(records),
        "easy":group([r for r in records if r["tokens"]<args.minimum_tokens]),
        "eligible":group([r for r in records if r["tokens"]>=args.minimum_tokens]),
        "routed":group([r for r in records if r["adaptive"]["route"]=="trie"]),
        "not_routed":group([r for r in records if r["adaptive"]["route"]!="trie"]),
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
            "Length-conditioned thresholds prevent raw length dominating all hard-case picks.",
            "Each result also reports A/A drift and geometric-mean bracketed baseline timing.",
            "Lazy trie is fully certified only when neither forest saturated.",
            "Saturated routed cases report differences separately, without claiming full equivalence.",
            "If isolate-gc set, cyclic GC is suspended during A/B/A but GC setup is measured separately; this is NOT inclusive production throughput.",
            "The performance verdict requires repeated independent authors and fast-sentence safeguards.",
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("ADAPTIVE_FINAL",json.dumps(result),flush=True)


if __name__=="__main__":
    main()
