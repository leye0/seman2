"""Build a reproducible 10k-sentence expensive/failed grammar corpus.

A failure is NOT silently equated with a missing rule:
  - lexical gap (no candidate for at least one required token)
  - structurally absent root, recognizer forest truncated/untruncated
  - root present but contextual constraints have no complete witness
  - k-best proof hit its explicit work budget (NOT a grammar rejection)

Optional single-family *counterfactuals* use the exact original lexical
lattice, recompile a grammar whose one feature requirement is removed, and
record both newly recovered failures and changed previously valid parses.
No counterfactual rules are committed or applied to the production parser.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
from hashlib import sha256
import json
import math
from pathlib import Path
from time import perf_counter_ns

from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract
from scripts.profile_gutenberg_slow_sentences import (
    characterization, distribution, quantile, token_band
)
from seman_parser.engine import Parser, ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_SHA="51650d348820a64ca4d4233da035f804819d2231801b59373db4e1279a1985e0"
# Explicit, easy-to-audit hypotheses; all preserve rule categories and scores.
ABLATIONS={
    "requires_subcat":("requires",frozenset({"subcat"})),
    "requires_any":("requires",None),
    "feature_number":("feature",frozenset({"number"})),
    "feature_person":("feature",frozenset({"person"})),
    "feature_vform":("feature",frozenset({"vform"})),
    "feature_subcat":("feature",frozenset({"subcat"})),
    "feature_voice":("feature",frozenset({"voice"})),
    "feature_wh_gap":("feature",frozenset({"wh","gap"})),
    "feature_inversion":("feature",frozenset({"inversion"})),
}


def relax_grammar(grammar,variant):
    """Replace only relevant constraint fields; keep RHS order and all rules."""
    kind,keys=ABLATIONS[variant]
    changed=defaultdict(set)
    new=[]
    for rule in grammar:
        symbols=(rule.lhs,)+rule.rhs
        patched=[]
        for symbol in symbols:
            if kind=="requires":
                requires=() if keys is None else tuple(
                    k for k in symbol.requires if k not in keys)
                if requires!=symbol.requires:
                    changed[rule.rule_id].update(set(symbol.requires)-set(requires))
                patched.append(replace(symbol,requires=requires))
            else:
                original=dict(symbol.features.items())
                # Use symbols in the feature structure: avoid string/int mismatch.
                from seman_parser.symbols import intern
                discarded={intern(key) for key in keys}
                filtered={k:v for k,v in original.items() if k not in discarded}
                removed=set(original)-set(filtered)
                if removed:
                    from seman_parser.symbols import resolve
                    changed[rule.rule_id].update(resolve(k) for k in removed)
                patched.append(replace(symbol,features=FeatureStructure(filtered)))
        new.append(replace(rule,lhs=patched[0],rhs=tuple(patched[1:])))
    return Grammar(new),{k:sorted(v) for k,v in changed.items()}


def has_root(forest,goal):
    if forest is None:
        return False,0
    found=[node for node in forest.nodes
           if node.category==goal and forest._root_span(node.start,node.end)]
    return bool(found),sum(len(n.derivations) for n in found)


def label_case(row):
    if row["completed"]:
        return "complete"
    if row["kbest_budget_exceeded"]:
        return "kbest_budget_unproven"
    if row["forest_budget_exceeded"]:
        return "forest_budget_root_present" if row["root_recognized"] else "forest_budget_no_root"
    if row["lexical_missing_tokens"]:
        return "lexical_gap"
    if row["root_recognized"]:
        return "root_without_feature_valid_witness"
    return "no_root_under_current_grammar"


def lexical_gaps(lattice):
    tokens=lattice.tokens
    missing=[]
    for tok in tokens:
        if tok.text in (".","!","?",",",";",":"):
            continue
        if not any(c.span_start<=tok.start and c.span_end>=tok.end
                   for c in lattice.candidates):
            missing.append(tok.text)
    return missing


def observe(index,row,lattice,result,elapsed,lex_ms):
    stats=result.stats
    exists,root_derivs=has_root(result.shared_forest,result.stats.get("goal_category","CLAUSE"))
    # goal_category is CLAUSE on the baseline Parser used here.
    attrs=characterization(row["text"],lattice)
    record={
        "index":index,"ordinal":row["ordinal"],"sentence":row["text"],
        "sentence_sha256":sha256(row["text"].encode()).hexdigest(),
        **attrs,
        "completed":bool(result.completed),
        "root_recognized":exists,"root_derivations":root_derivs,
        "forest_budget_exceeded":bool(stats.get("budget_exceeded")),
        "kbest_budget_exceeded":bool(stats.get("kbest_budget_exceeded")),
        "lexical_missing_tokens":lexical_gaps(lattice),
        "lex_ms":round(lex_ms,5),
        "recognition_ms":stats.get("recognition_ms",0),
        "kbest_ms":stats.get("best_ms",0),
        "full_ms":round(elapsed,5),
        "forest_nodes":stats.get("forest_nodes",0),
        "structural_derivations":stats.get("structural_derivations",0),
        "partial_states":stats.get("partial_states",0),
        "partial_derivations":stats.get("partial_derivations",0),
        "kbest_work_units":stats.get("kbest_work_units",0),
        "unification_attempts":stats.get("unification_attempts",0),
        "unification_rejections":stats.get("unification_rejections",0),
        "hint_unification_rejections":stats.get("hint_unification_rejections",0),
        "materialized_items":stats.get("materialized_items",0),
    }
    record["failure_family"]=label_case(record)
    return record


def choose_probes(rows,cache,max_per_family):
    """Deterministic per-failure-mode sampling, not just longest/most costly."""
    buckets=defaultdict(list)
    for r in rows:
        if r["index"] not in cache:
            continue
        buckets[r["failure_family"]].append(r)
    selected=[]
    for label in sorted(buckets):
        arr=buckets[label]
        # Half extreme cases, half spread through length bands; retain controls.
        n=max_per_family
        chosen=sorted(arr,key=lambda r:(-r["full_ms"],r["index"]))[:max(1,n//2)]
        chosen_ids={r["index"] for r in chosen}
        for band in ("04-08","09-16","17-24","25-32"):
            subset=[r for r in arr if r["length_band"]==band
                    and r["index"] not in chosen_ids]
            # Earliest deterministic exemplar from each band.
            if subset and len(chosen)<n:
                r=sorted(subset,key=lambda r:r["index"])[0]
                chosen.append(r);chosen_ids.add(r["index"])
        # Evenly distribute remaining cases by ordinal, prevent all from head.
        remaining=[r for r in sorted(arr,key=lambda r:r["index"])
                   if r["index"] not in chosen_ids]
        left=n-len(chosen)
        if left>0 and remaining:
            for i in range(min(left,len(remaining))):
                at=min(len(remaining)-1,int((i+.5)*len(remaining)/min(left,len(remaining))))
                r=remaining[at]
                if r["index"] not in chosen_ids:
                    chosen.append(r);chosen_ids.add(r["index"])
        selected.extend(chosen)
    return selected


def best_signature(item):
    if item is None:return None
    # Lexical selection can change while structural grammar stays valid;
    # the feature-relaxation probes must report this, not suppress it.
    lex=[]
    agenda=[item]
    ids=Counter()
    while agenda:
        node=agenda.pop()
        if node.rule_id:ids[node.rule_id]+=1
        if node.lexical_candidate is not None:
            c=node.lexical_candidate
            lex.append((c.span_start,c.span_end,c.category,c.lemma))
        agenda.extend(node.children)
    return {
        "root_rule":item.rule_id,
        "rule_ids":list(ids.elements()),
        "lexical":sorted(lex),
    }


def run_probes(probes,cache,source_grammar,native,args,out):
    compiled={}
    changed={}
    for name in ABLATIONS:
        altered,diff=relax_grammar(source_grammar,name)
        compiled[name]=VectorGrammar(altered)
        changed[name]=diff
    results=[]
    summary={}
    for name,engine in compiled.items():
        recovered=[]
        altered_known=[]
        no_change=[]
        budget=Counter()
        wall=[]
        candidate_rules=Counter()
        for case in probes:
            lattice,base_sig=cache[case["index"]]
            began=perf_counter_ns()
            result=engine.parse_lattice(
                lattice,beam=native.beam,max_items=20000,
                goal_category=native.goal_category,
                kbest_work_limit=args.kbest_work_limit)
            elapsed=(perf_counter_ns()-began)/1e6
            wall.append(elapsed)
            best=result.best() if result.completed else None
            sig=best_signature(best)
            status=(
                "recovered" if case["failure_family"]!="complete" and best is not None
                else "changed_valid" if case["failure_family"]=="complete" and sig!=base_sig
                else "same_valid" if case["failure_family"]=="complete"
                else "not_recovered"
            )
            budget["kbest_exhausted"]+=bool(result.stats.get("kbest_budget_exceeded"))
            budget["forest_exhausted"]+=bool(result.stats.get("budget_exceeded"))
            implicated=[]
            if status=="recovered":
                recovered.append(case["index"])
                for rule_id in (sig or {}).get("rule_ids",()):
                    if rule_id in changed[name]:
                        candidate_rules[rule_id]+=1
                        implicated.append(rule_id)
            elif status=="changed_valid":
                altered_known.append(case["index"])
            elif status=="same_valid":
                no_change.append(case["index"])
            entry={
                "variant":name,"index":case["index"],
                "baseline_failure_family":case["failure_family"],
                "baseline_complete":case["completed"],
                "baseline_ms":case["full_ms"],"baseline_tokens":case["tokens"],
                "new_complete":best is not None,"status":status,
                "new_ms":round(elapsed,3),
                "new_forest_budget_exceeded":bool(result.stats.get("budget_exceeded")),
                "new_kbest_budget_exceeded":bool(result.stats.get("kbest_budget_exceeded")),
                "new_root_rule":best.rule_id if best else None,
                "candidate_rule_ids":sorted(set(implicated)),
            }
            results.append(entry)
            out.write(json.dumps(entry,separators=(",",":"))+"\n")
        summary[name]={
            "test_cases":len(probes),
            "previous_failures_tested":sum(not c["completed"] for c in probes),
            "previously_valid_controls":sum(c["completed"] for c in probes),
            "recoveries":len(recovered),
            "recovered_indices":recovered[:30],
            "changed_previously_valid_controls":len(altered_known),
            "changed_control_indices":altered_known[:20],
            "same_valid_controls":len(no_change),
            "counterfactual_kbest_exhausted":budget["kbest_exhausted"],
            "counterfactual_forest_exhausted":budget["forest_exhausted"],
            "probe_elapsed_ms":distribution(wall),
            "altered_grammar_rules":len(changed[name]),
            "suspect_rule_ids_in_recovered_trees":candidate_rules.most_common(20),
        }
        print("ABLATION",json.dumps({"variant":name,
            "rescued":len(recovered),
            "changed_controls":len(altered_known),
            "counterfactual_kbest_exhausted":budget["kbest_exhausted"],
            "counterfactual_forest_exhausted":budget["forest_exhausted"]}),flush=True)
    return summary


def summarize(rows,probes,ablation_summary,args,corpus_info):
    times=[r["full_ms"] for r in rows]
    median=quantile(times,.5)
    p95=quantile(times,.95)
    p99=quantile(times,.99)
    limits={"over_5x_median":5*median,"over_10x_median":10*median,
            "over_1_second":1000.0,"top_5pct":p95,"top_1pct":p99}
    family=Counter(r["failure_family"] for r in rows)
    def cohort(rs):
        return {
            "count":len(rs),
            "completed":sum(r["completed"] for r in rs),
            "lexical_ms":distribution(r["lex_ms"] for r in rs),
            "forest_ms":distribution(r["recognition_ms"] for r in rs),
            "kbest_ms":distribution(r["kbest_ms"] for r in rs),
            "total_ms":distribution(r["full_ms"] for r in rs),
            "tokens":distribution(r["tokens"] for r in rs),
            "candidates":distribution(r["lexical_candidates"] for r in rs),
            "ambiguous_positions":distribution(r["ambiguous_positions"] for r in rs),
            "partial_states":distribution(r["partial_states"] for r in rs),
            "kbest_work":distribution(r["kbest_work_units"] for r in rs),
            "family":dict(Counter(r["failure_family"] for r in rs)),
            "dominant_phase":dict(Counter(max((
                ("lexical",r["lex_ms"]),("forest",r["recognition_ms"]),
                ("kbest",r["kbest_ms"])),key=lambda x:x[1])[0] for r in rs)),
        }
    by_status={status:cohort([r for r in rows if r["failure_family"]==status])
               for status in sorted(family)}
    slow={name:cohort([r for r in rows if r["full_ms"]>=threshold])
          for name,threshold in limits.items()}
    bands={}
    for b in ("04-08","09-16","17-24","25-32"):
        rs=[r for r in rows if r["length_band"]==b]
        if rs:
            bands[b]={
                "all":cohort(rs),
                "incomplete":cohort([r for r in rs if not r["completed"]]),
                "over_5x":sum(r["full_ms"]>=5*median for r in rs),
                "forest_exhausted":sum(r["forest_budget_exceeded"] for r in rs),
            }
    sorted_times=sorted(times,reverse=True)
    total=sum(times)
    top_share={str(frac):round(100*sum(sorted_times[:math.ceil(len(rows)*frac)])/total,3)
               for frac in (.01,.05,.1)}
    top_failed=sorted((r for r in rows if not r["completed"]),
                      key=lambda r:r["full_ms"],reverse=True)[:60]
    def select(r):
        return {k:r[k] for k in (
            "index","ordinal","sentence","full_ms","lex_ms","recognition_ms",
            "kbest_ms","completed","root_recognized","failure_family",
            "lexical_candidates","ambiguous_positions","tokens",
            "partial_states","forest_nodes","structural_derivations",
            "kbest_work_units")}
    return {
        "source":corpus_info,
        "configuration":{"max_tokens":args.max_tokens,
            "forest_max_items":20000,"kbest_work_limit":args.kbest_work_limit,
            "corpus_size":len(rows),"sample_per_family":args.sample_per_family},
        "overview":cohort(rows),
        "median_ms":round(median,4),
        "p95_ms":round(p95,4),"p99_ms":round(p99,4),
        "outlier_thresholds_ms":{k:round(v,4) for k,v in limits.items()},
        "family_counts":dict(family),
        "tails":slow,"by_failure_family":by_status,
        "by_token_length":bands,
        "runtime_share":top_share,
        "worst_failed_examples":list(map(select,top_failed)),
        "counterfactual":{"sample_count":len(probes),
            "sample_by_failure_family":dict(Counter(r["failure_family"] for r in probes)),
            "tests":ablation_summary},
        "interpretation_limits":[
            "A truncated forest is an unresolved search, not evidence that grammar excludes the sentence.",
            "A kbest-work-limit hit is an unresolved search, not a proven feature conflict.",
            "A root without accepted witness suggests unification/evidence rejection or search incompleteness; it does not identify a specific wrong rule.",
            "Counterfactual successes are NOT gold grammatical correctness, and relaxing a feature globally does not isolate one rule.",
            "The controls record changed top analyses but cannot establish semantic validity; inspect every rescued tree before changing production rules.",
            "Only 10k eligible <=32 token sentences from the same David Copperfield Gutenberg edition were analyzed.",
            "No source text or production grammar changes are committed to the GitHub repository.",
        ]
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--size",type=int,default=10000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--kbest-work-limit",type=int,default=100000)
    ap.add_argument("--sample-per-family",type=int,default=15)
    ap.add_argument("--checkpoint",type=int,default=50)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()
    raw,info=download(TRAIN_BOOKS[0])
    if info["sha256"]!=EXPECTED_SHA:
        raise RuntimeError("Gutenberg corpus has changed since prior 5000-sentence test")
    corpus,extra=extract(TRAIN_BOOKS[0],raw,length_min=4,length_max=args.max_tokens)
    if len(corpus)<args.size:
        raise RuntimeError(f"Corpus has {len(corpus)} eligible, need {args.size}")
    corpus=corpus[:args.size]
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    native=Parser(resources,cache_size=0,max_items=20000)
    folder=args.out_dir
    folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    cached={}
    begun=perf_counter_ns()
    with (folder/"per_sentence_10000.jsonl").open("w",encoding="utf8",buffering=1) as allfile:
        for i,row in enumerate(corpus):
            begin=perf_counter_ns()
            lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
            lex_ms=(perf_counter_ns()-begin)/1e6
            res=native._vector_grammar.parse_lattice(
                lattice,beam=native.beam,max_items=20000,
                goal_category=native.goal_category,
                kbest_work_limit=args.kbest_work_limit)
            best=res.best() if res.completed else None
            record=observe(i,row,lattice,res,(perf_counter_ns()-begin)/1e6,lex_ms)
            rows.append(record)
            allfile.write(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n")
            # Keep the exact lexical hypotheses for the counterfactual:
            # no second WordNet lookup that can change lexical interpretations.
            # Bounded sample cache: all expensive problems (first 1500),
            # plus deterministic spread of cheaper failures and controls.
            keep=(
                record["failure_family"]!="complete" and
                (record["full_ms"]>=100 and len(cached)<1500
                 or i%80==0)
            ) or (record["completed"] and i%150==0)
            if keep:
                cached[i]=(lattice,best_signature(best))
            if (i+1)%args.checkpoint==0:
                recent=rows[-args.checkpoint:]
                print("COLLECT",json.dumps({
                    "seen":i+1,
                    "completed":sum(r["completed"] for r in rows),
                    "forest_limited":sum(r["forest_budget_exceeded"] for r in rows),
                    "kbest_limited":sum(r["kbest_budget_exceeded"] for r in rows),
                    "last_window_p50_ms":round(quantile([r["full_ms"] for r in recent],.5),3),
                    "worst_ms":round(max(r["full_ms"] for r in recent),3),
                }),flush=True)
    median=quantile([r["full_ms"] for r in rows],.5)
    tail_cut=5*median
    with (folder/"expensive_and_failed_corpus.jsonl").open(
        "w",encoding="utf8") as file:
        for r in rows:
            if r["full_ms"]>=tail_cut or r["failure_family"]!="complete":
                file.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")
    probes=choose_probes(rows,cached,args.sample_per_family)
    with (folder/"counterfactual_observations.jsonl").open("w",encoding="utf8",buffering=1) as file:
        results=run_probes(probes,cached,native._vector_grammar.grammar,native,args,file)
    summary=summarize(rows,probes,results,args,{
        "book":TRAIN_BOOKS[0].title,
        "ebook_id":TRAIN_BOOKS[0].ebook_id,
        "sha256":info["sha256"],"extraction":extra,
    })
    (folder/"failure_characterization_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("FINAL_DIAG",json.dumps({
        "count":len(rows),"median_ms":summary["median_ms"],
        "p95_ms":summary["p95_ms"],"p99_ms":summary["p99_ms"],
        "failure_families":summary["family_counts"],
        "outlier_over_5x":summary["tails"]["over_5x_median"]["count"],
        "worst_5pct":summary["tails"]["top_5pct"]["dominant_phase"],
        "runtime_share":summary["runtime_share"],
        "ablation_results":{k:{"recoveries":v["recoveries"],
            "changed_controls":v["changed_previously_valid_controls"]}
            for k,v in results.items()},
        "walltime_s":round((perf_counter_ns()-begun)/1e9,3)
    }),flush=True)


if __name__=="__main__":
    main()
