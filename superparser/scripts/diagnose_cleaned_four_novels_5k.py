"""Per-sentence forensic audit of the exact cleaned four-novel 5000x2 sample.

Recreates the SAME 5,000 interleaved source sentences and the SAME canonical
first-pass VectorGrammar budget as benchmark_cleaned_four_novels_5k.py.
Does not use earlier raw Gutenberg corpora. Persists every sentence plus
phase times, forest shape, lexical hypotheses and failure status.

Optional held-sample, in-memory counterfactuals test grammar feature groups
without modifying parser rules and count changed successful controls.
Do not interpret newly found trees as gold syntax.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from time import perf_counter_ns

from research.verbnet_lr.compiled_structure_snap import CompiledStructureReplayer
from scripts.benchmark_cleaned_four_novels_5k import cleaned_5k_source
from scripts.characterize_failed_10k import (
    best_signature, choose_probes, run_probes,
)
from scripts.profile_gutenberg_slow_sentences import characterization, distribution, quantile
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def failure_status(completed, root_recognized, forest_limited, kbest_limited):
    """Censored searches are never asserted to be grammar rejections."""
    if completed:
        return "complete"
    if kbest_limited:
        return "kbest_budget_unproven"
    if forest_limited:
        return ("forest_budget_root_present" if root_recognized
                else "forest_budget_no_root")
    if root_recognized:
        return "root_without_feature_valid_witness"
    return "no_root_under_current_grammar"


def lexical_diagnostics(lattice):
    tokens=lattice.tokens
    by_span=defaultdict(list)
    for cand in lattice.candidates:
        by_span[(cand.span_start,cand.span_end)].append(cand)
    ambiguous=[]
    no_full_candidate=[]
    for tok in tokens:
        options=by_span.get((tok.start,tok.end),())
        categories=sorted({c.category for c in options})
        if len(categories)>1:
            ambiguous.append({"token":tok.text,"index":tok.index,
                             "readings":len(options),"categories":categories})
        if not any(c.span_start<=tok.start and c.span_end>=tok.end
                   for c in lattice.candidates):
            no_full_candidate.append(tok.text)
    # "no candidate spanning this token" is NOT equivalent to a lexical gap:
    # contractions can be covered by multiple nonspanning lexical edges.
    return {
        "ambiguous_token_examples":sorted(
            ambiguous,key=lambda x:(-x["readings"],x["index"]))[:12],
        "tokens_without_one_covering_candidate":no_full_candidate[:30],
        "uncovered_wordlike_token_count":sum(
            any(ch.isalnum() for ch in x) for x in no_full_candidate),
        "uncovered_punctuation_token_count":sum(
            not any(ch.isalnum() for ch in x) for x in no_full_candidate),
    }


def forest_diagnostics(forest,goal_category):
    if forest is None:
        return {"root_recognized":False}
    roots=[n for n in forest.nodes if n.category==goal_category and
           forest._root_span(n.start,n.end)]
    per_rule=Counter()
    next_needed=Counter()
    per_lhs=Counter()
    max_fullspan_by_category=Counter()
    for partial in forest.partials:
        compiled=forest.compiled.rules[partial.rule_index]
        rule=compiled.rule
        per_rule[rule.rule_id]+=1
        per_lhs[rule.lhs.category]+=1
        if partial.dot<len(compiled.rhs_ids):
            at=forest._next_start(partial.end)
            category=rule.rhs[partial.dot].category
            if not forest.by_start_category.get((at,compiled.rhs_ids[partial.dot])):
                next_needed[category]+=1
    for n in forest.nodes:
        if forest._root_span(n.start,n.end):
            max_fullspan_by_category[n.category]+=1
    return {
        "root_recognized":bool(roots),
        "root_derivation_count":sum(len(n.derivations) for n in roots),
        "structural_fullspan_categories":max_fullspan_by_category.most_common(15),
        "top_rules_by_partial_states":per_rule.most_common(15),
        "top_lhs_by_partial_states":per_lhs.most_common(12),
        "missing_continuation_categories":next_needed.most_common(12),
        "partial_rule_counts":per_rule,
    }


def candidate_signature(lattice):
    """Stable enough to detect lexicon drift before running a counterfactual."""
    return sha256(json.dumps([
        [c.span_start,c.span_end,c.category,c.lemma,c.features.as_dict(),
         list(c.sense_ids)]
        for c in lattice.candidates
    ],sort_keys=True,ensure_ascii=False,default=str).encode("utf8")).hexdigest()


def normalize_record(row,record):
    return {"index":record["index"],"book_id":row["book_id"],
            "text":row["text"],"ordinal":row["ordinal"],
            "status":record["failure_family"],"full_ms":record["full_ms"],
            "tokens":record["tokens"],"lexical_candidates":record["lexical_candidates"],
            "ambiguous_positions":record["ambiguous_positions"],
            "recognition_ms":record["recognition_ms"],
            "kbest_ms":record["kbest_ms"],"partial_states":record["partial_states"],
            "top_rules":record["top_rules_by_partial_states"][:6]}


def summary(records,source,probe_tests=None,probes=None):
    times=[r["full_ms"] for r in records]
    med=quantile(times,.5)
    p95=quantile(times,.95)
    cutoffs={"5x_median_ms":5*med,"10x_median_ms":10*med,
             "p95_ms":p95,"p99_ms":quantile(times,.99)}
    def cohort(rs):
        out={"n":len(rs),"completed":sum(r["completed"] for r in rs),
             "forest_budget":sum(r["forest_budget_exceeded"] for r in rs),
             "kbest_budget":sum(r["kbest_budget_exceeded"] for r in rs),
             "total_ms":distribution(r["full_ms"] for r in rs),
             "lexing_ms":distribution(r["lexing_ms"] for r in rs),
             "forest_ms":distribution(r["recognition_ms"] for r in rs),
             "kbest_ms":distribution(r["kbest_ms"] for r in rs),
             "tokens":distribution(r["tokens"] for r in rs),
             "lexical_candidates":distribution(r["lexical_candidates"] for r in rs),
             "ambiguous_positions":distribution(r["ambiguous_positions"] for r in rs),
             "partial_states":distribution(r["partial_states"] for r in rs),
             "statuses":dict(Counter(r["failure_family"] for r in rs)),
             "dominant_phase":dict(Counter(
                 max((("lexing",r["lexing_ms"]),
                      ("recognition",r["recognition_ms"]),
                      ("kbest",r["kbest_ms"])),key=lambda x:x[1])[0]
                 for r in rs))}
        return out
    overall=cohort(records)
    by_book={}
    for book in source:
        k=book["id"]
        rs=[r for r in records if r["book_id"]==k]
        by_book[str(k)]={"title":book["title"],"author":book["author"],
                         "clean_sha256":book["sha256"],
                         "data":cohort(rs)}
    by_status={s:cohort([r for r in records if r["failure_family"]==s])
               for s in sorted({r["failure_family"] for r in records})}
    extremes={
        "over_5x_median":cohort([r for r in records if r["full_ms"]>=5*med]),
        "over_10x_median":cohort([r for r in records if r["full_ms"]>=10*med]),
        "top_5pct":cohort([r for r in records if r["full_ms"]>=p95]),
        "above_1sec":cohort([r for r in records if r["full_ms"]>=1000]),
    }
    rule_cohorts={}
    for name,predicate in {
        "all":lambda r:True,
        "slow_5pct":lambda r:r["full_ms"]>=p95,
        "failed_without_root":lambda r:r["failure_family"]=="no_root_under_current_grammar",
        "root_but_no_witness":lambda r:r["failure_family"]=="root_without_feature_valid_witness",
        "forest_saturated":lambda r:r["forest_budget_exceeded"],
        "fast_successful":lambda r:r["completed"] and r["full_ms"]<=med,
    }.items():
        subset=[r for r in records if predicate(r)]
        totals=Counter()
        for r in subset:
            totals.update(dict(r.get("partial_rule_counts",[])))
        rule_cohorts[name]={"n":len(subset),
            "top_partial_producers":totals.most_common(30)}
    top_slow=sorted(records,key=lambda r:r["full_ms"],reverse=True)[:50]
    top_failure=sorted((r for r in records if not r["completed"]),
                       key=lambda r:r["full_ms"],reverse=True)[:70]
    total=sum(times)
    ordered=sorted(times,reverse=True)
    return {
        "schema":"cleaned-four-novels-problematic-5000-v1",
        "sources":source,"overall":overall,
        "by_book":by_book,"by_failure_mode":by_status,
        "thresholds":{k:round(v,4) for k,v in cutoffs.items()},
        "tails":extremes,
        "runtime_concentration_pct":{
            "top_1pct":round(100*sum(ordered[:math.ceil(.01*len(ordered))])/total,3),
            "top_5pct":round(100*sum(ordered[:math.ceil(.05*len(ordered))])/total,3),
            "top_10pct":round(100*sum(ordered[:math.ceil(.10*len(ordered))])/total,3),
        },
        "partial_rule_cohorts":rule_cohorts,
        "worst_50":top_slow,
        "worst_failed_70":top_failure,
        "counterfactual":{
            "sample":dict(Counter(r["failure_family"] for r in (probes or []))),
            "tests":probe_tests or {},
        },
        "notes":[
            "Exact same 5k sentences as the cleaned-four-novels snap run; 1250 per book, even-spread/round-robin.",
            "The same 20000 forest and 100000 kbest work ceilings apply; no wall-time sentence limit.",
            "Censored searches are labeled unproven and are not grammatical disproofs.",
            "An uncovered whole token can still be represented by multiple lexical edges; contractions and punctuation require closer examination.",
            "No roots under grammar reflects this tokenization and bounded grammar, not a verified gold parse failure.",
            "Partial counts identify expensive rules, not necessarily erroneous rules.",
            "If present, ablations are applied only in memory on a small sample, not to production grammar.",
            "A recovered tree is a hypothesis, not a certified human-quality grammatical parse.",
        ],
    }


def collect(args):
    corpus,sources=cleaned_5k_source(args.size,args.max_tokens)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    memory=CompiledStructureReplayer(resources)
    folder=args.out_dir
    folder.mkdir(parents=True,exist_ok=True)
    stats=Counter()
    records=[]
    print("DIAG_SOURCE",json.dumps({
        "book_sha256":[(x["id"],x["sha256"]) for x in sources],
        "per_book":{x["id"]:x["selected"] for x in sources},
        "total_sentences":len(corpus)}),flush=True)
    with (folder/"cleaned_5000_every_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as f:
        for i,row in enumerate(corpus):
            start=perf_counter_ns()
            lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
            lex_ms=(perf_counter_ns()-start)/1e6
            result=parser._vector_grammar.parse_lattice(
                lattice,beam=parser.beam,max_items=20000,
                goal_category=parser.goal_category,
                kbest_work_limit=args.kbest_work_limit)
            item=result.best() if result.completed else None
            before_obs=(perf_counter_ns()-start)/1e6
            indexed=False
            index_error=None
            if item is not None:
                try:
                    memory.observe(item,lattice=lattice)
                    indexed=True
                except (ValueError,OverflowError) as exc:
                    index_error=str(exc)
            forest=result.shared_forest
            fd=forest_diagnostics(forest,parser.goal_category)
            ld=lexical_diagnostics(lattice)
            s=result.stats
            record={
                "index":i,"book_id":row["book_id"],"ordinal":row["ordinal"],
                "sentence":row["text"],
                "sentence_sha256":sha256(row["text"].encode("utf8")).hexdigest(),
                "lattice_signature":candidate_signature(lattice),
                **characterization(row["text"],lattice),**ld,
                "completed":item is not None,"indexed":indexed,
                "index_error":index_error,
                "forest_budget_exceeded":bool(s.get("budget_exceeded")),
                "kbest_budget_exceeded":bool(s.get("kbest_budget_exceeded")),
                "recognition_ms":float(s.get("recognition_ms",0)),
                "kbest_ms":float(s.get("best_ms",0)),
                "lexing_ms":round(lex_ms,5),"full_ms":round(before_obs,5),
                "forest_nodes":s.get("forest_nodes",0),
                "partial_states":s.get("partial_states",0),
                "partial_derivations":s.get("partial_derivations",0),
                "structural_derivations":s.get("structural_derivations",0),
                "recognition_operations":s.get("recognition_operations",0),
                "duplicate_partial_proposals":s.get("duplicate_partial_proposals",0),
                "unification_attempts":s.get("unification_attempts",0),
                "unification_rejections":s.get("unification_rejections",0),
                "kbest_work_units":s.get("kbest_work_units",0),
                **fd,
            }
            record["failure_family"]=failure_status(
                record["completed"],record["root_recognized"],
                record["forest_budget_exceeded"],record["kbest_budget_exceeded"])
            record["partial_rule_counts"]=list(
                record["partial_rule_counts"].most_common())
            records.append(record)
            f.write(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n")
            stats[record["failure_family"]]+=1
            if (i+1)%args.checkpoint==0 or i+1==len(corpus):
                print("DIAG_PROGRESS",json.dumps({
                    "seen":i+1,"status":dict(stats),
                    "last_ms":record["full_ms"],
                    "last_50_p50_ms":round(quantile(
                        [r["full_ms"] for r in records[-args.checkpoint:]],.5),3),
                }),flush=True)
    median=quantile([r["full_ms"] for r in records],.5)
    with (folder/"cleaned_problematic_sentences.jsonl").open(
        "w",encoding="utf8") as out:
        for record in records:
            if not record["completed"] or record["full_ms"]>=5*median:
                out.write(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n")
    # CHECKPOINT FIRST: the expensive baseline must be durable BEFORE every
    # optional interpretation/ablation experiment. Never put assertions after
    # a full 5k parse unless the outputs are already persisted.
    ablations={}
    probes=[]
    report=summary(records,sources)
    report["counterfactual"]["status"]="not_started"
    report["counterfactual"]["warnings"]=[]
    summary_path=folder/"cleaned_5000_diagnostic_summary.json"

    def persist_report():
        # Atomic replacement avoids a truncated report on interrupted writes.
        temporary=summary_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
        temporary.replace(summary_path)

    persist_report()
    print("DIAG_BASELINE_SAVED",json.dumps({
        "count":len(records),
        "summary":str(summary_path),
        "status":report["overall"]["statuses"]}),flush=True)

    if args.sample_per_family:
        report["counterfactual"]["status"]="in_progress"
        persist_report()
        try:
            planned=choose_probes(records,{r["index"]:True for r in records},
                                  args.sample_per_family)
            cache={}
            drift=[]
            for r in planned:
                lattice=build_lattice(
                    corpus[r["index"]]["text"],resources.lexicon,multiword_max=1)
                actual=candidate_signature(lattice)
                if actual!=r["lattice_signature"]:
                    drift.append({"index":r["index"],"reason":"lexical_lattice_changed"})
                    continue
                # A fresh parse can disagree due to mutable caches or execution
                # state. This is experimental drift, not a baseline failure.
                result=parser._vector_grammar.parse_lattice(
                    lattice,beam=parser.beam,max_items=20000,
                    goal_category=parser.goal_category,
                    kbest_work_limit=args.kbest_work_limit)
                original=result.best() if result.completed else None
                if (original is not None)!=(r["completed"]):
                    drift.append({"index":r["index"],"reason":"completion_changed"})
                    continue
                cache[r["index"]]=(lattice,best_signature(original))
                probes.append(r)
            report["counterfactual"]["planned_sample"]=len(planned)
            report["counterfactual"]["valid_sample"]=len(probes)
            report["counterfactual"]["drift"]=drift
            if drift:
                print("DIAG_COUNTERFACTUAL_DRIFT",json.dumps({
                    "skipped":len(drift),"details":drift[:20]}),flush=True)
            persist_report()
            if probes:
                with (folder/"cleaned_rule_counterfactuals.jsonl").open(
                    "w",encoding="utf8",buffering=1) as out:
                    ablations=run_probes(
                        probes,cache,parser._vector_grammar.grammar,parser,args,out)
            report["counterfactual"]["status"]="completed_with_drift" if drift else "completed"
        except Exception as exc:
            # Secondary research is best-effort. The 5k completed baseline must
            # still be readable and the CI job must not misleadingly lose it.
            import traceback
            issue={"type":type(exc).__name__,"message":str(exc),
                   "traceback":traceback.format_exc()}
            report["counterfactual"]["status"]="failed_nonfatal"
            report["counterfactual"]["warnings"].append(issue)
            print("DIAG_OPTIONAL_ERROR",json.dumps(issue),flush=True)
        finally:
            updated=summary(records,sources,ablations,probes)
            updated["counterfactual"].update({
                k:v for k,v in report["counterfactual"].items()
                if k not in ("tests","sample")
            })
            report=updated
            persist_report()
    else:
        report["counterfactual"]["status"]="disabled"
        persist_report()

    print("DIAG_FINAL",json.dumps({
        "count":len(records),
        "status":report["overall"]["statuses"],
        "p50_ms":report["overall"]["total_ms"]["p50"],
        "p95_ms":report["overall"]["total_ms"]["p95"],
        "forest_budget":report["overall"]["forest_budget"],
        "kbest_budget":report["overall"]["kbest_budget"],
        "slow_p95_phase":report["tails"]["top_5pct"]["dominant_phase"],
        "runtime_concentration":report["runtime_concentration_pct"],
        "per_book":{k:{"completed":v["data"]["completed"],
                       "statuses":v["data"]["statuses"]}
                    for k,v in report["by_book"].items()},
        "rule_ablation":{k:{"rescued":v["recoveries"],
            "changed_good":v["changed_previously_valid_controls"]}
            for k,v in ablations.items()},
    }),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--size",type=int,default=5000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--kbest-work-limit",type=int,default=100000)
    ap.add_argument("--checkpoint",type=int,default=50)
    ap.add_argument("--sample-per-family",type=int,default=10)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()
    collect(args)


if __name__=="__main__":
    main()
