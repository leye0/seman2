"""Held-out study of full-structure snapping vs existing L-R baseline.

The training source is only completed L-R trees on the dev split, tagged
candidate (not gold). No held-out trees ever enter the pattern index.
A hit proves reusable grammar-licensed topology plus successful re-unification,
not unique grammatical correctness. The test set never trains the cache.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex, SnappingResearchReader
from research.verbnet_lr.packed_witness import seek_packed_witness
from research.verbnet_lr.construction_guard import ConstructionGuard
from seman_parser.predictive import PredictiveParser
from seman_parser.reading_kernel_compiled import Event
from scripts.benchmark_verbnet_reader import syntax_assertions
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def quantile(values, fraction):
    if not values:
        return None
    values.sort()
    return round(values[min(len(values)-1,int((len(values)-1)*fraction))],5)


def run(*, wordnet_dir, max_train=60, max_eval=60, repetitions=3,
        teacher_seconds=0.35):
    corpus=ROOT / "data/syntax_correctness_validation.jsonl"
    rows=[json.loads(row) for row in corpus.read_text().splitlines() if row.strip()]
    train=[r for r in rows if r.get("split")=="dev"][:max_train]
    evaluation=[r for r in rows if r.get("split")!="dev"][:max_eval]
    resources=ParserResources.from_dir(ROOT / "data",wordnet_dict=wordnet_dir)
    lr=SemanCompiledReader(resources, token_only_lattice=True)
    snap=FullStructureSnapIndex(resources)
    training=Counter()
    for case in train:
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        r=lr.parse(case["text"])
        if r.complete:
            try:
                snap.observe(r.item, lattice=lattice, evidence="candidate")
                training["lr_candidate_added"]+=1
            except ValueError:
                training["lr_unsupported"]+=1
        else:
            training["lr_incomplete"]+=1
        # Independent offline grammar derivation: grammar-unified but NOT gold.
        # This teacher may find a structure even when greedy L-R failed.
        # A timeout, cutoff or UNKNOWN adds no negative evidence.
        if teacher_seconds > 0:
            guard=ConstructionGuard(modal_forms={
                c.surface.casefold() for c in lattice.candidates
                if c.category == "MODAL"})
            witness=seek_packed_witness(
                resources.grammar,lattice,max_seconds=teacher_seconds,
                max_items=60_000,max_expansions=30_000,
                max_paths_per_item=4,max_backpointers=4,
                validate_tree=guard.validate,return_compact_node=True)
            if witness["status"] == "FOUND" and witness["witness_node"] is not None:
                try:
                    item=snap._materializer._materialize(witness["witness_node"])
                    snap.observe(item,lattice=lattice,evidence="grammar_witness")
                    training["grammar_witness_added"]+=1
                    if not r.complete:
                        training["teacher_rescued_lr_incomplete"]+=1
                except ValueError:
                    training["teacher_unsupported"]+=1
            else:
                training["teacher_"+witness["status"].lower()]+=1
    hybrid=SnappingResearchReader(resources,index=snap,fallback=lr)
    totals={"lr":[],"snap_recognition":[],"snap_including_lattice":[],
            "hybrid_including_lattice":[]}
    case_results=[]
    def snapped_gold(case, item):
        # Produce the same evidence representation consumed by the existing
        # explicit annotation assessor; never call this proof of correctness.
        events=[]
        def visit(node):
            if node.lexical_candidate is not None:
                c=node.lexical_candidate
                events.append(Event(0,c.surface,"CONSUME",c.category,""))
            for ch in node.children:
                visit(ch)
            if node.rule_id:
                events.append(Event(0,"","COMPLETE",node.category,node.rule_id))
        visit(item)
        from types import SimpleNamespace
        return syntax_assertions(case,SimpleNamespace(
            complete=True,item=item,outcome=SimpleNamespace(events=events)))
    for case in evaluation:
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        for _ in range(repetitions):
            t=perf_counter()
            hit=snap.match(lattice)
            totals["snap_recognition"].append((perf_counter()-t)*1000)
        t=perf_counter()
        lattice2=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        hit=snap.match(lattice2)
        totals["snap_including_lattice"].append((perf_counter()-t)*1000)
        t=perf_counter()
        baseline=lr.parse(case["text"])
        totals["lr"].append((perf_counter()-t)*1000)
        t=perf_counter()
        hybrid_result,hybrid_path=hybrid.parse(case["text"])
        totals["hybrid_including_lattice"].append((perf_counter()-t)*1000)
        gold_scores=[snapped_gold(case,m.item) for m in hit.matches]
        match_details=[{
            "template_id":m.template_id,
            "root_rule":m.item.rule_id,
            "score":round(m.item.score,6),
            "grammar_witness":m.grammar_witness_template,
            "independently_verified":m.independently_verified_template,
            "gold_pass":g["pass"],
            "gold_checks":g.get("checks"),
            "missing_required":g.get("missing_required"),
        } for m,g in zip(hit.matches,gold_scores)]
        baseline_gold=syntax_assertions(case,baseline)["pass"]
        hybrid_gold=(snapped_gold(case,hybrid_result.item)["pass"]
                     if hybrid_path=="snap" else
                     syntax_assertions(case,hybrid_result)["pass"])
        case_results.append({
            "baseline_gold_pass":baseline_gold,
            "hybrid_gold_pass":hybrid_gold,
            "first_snap_gold_pass":gold_scores[0]["pass"] if gold_scores else None,
            "id":case["id"],"split":case.get("split"),
            "any_explicit_gold_pass":any(g["pass"] is True for g in gold_scores),
            "all_explicit_gold_pass":bool(gold_scores) and all(
                g["pass"] is True for g in gold_scores),
            "matched_grammar_witness_templates":sum(
                m.grammar_witness_template for m in hit.matches),
            "snap_matches":len(hit.matches),
            "snap_incomplete":hit.incomplete,"snap_reason":hit.reason,
            "candidate_templates":hit.candidate_templates,
            "match_details":match_details,
            "lr_complete":baseline.complete,
            "hybrid_path":hybrid_path,
            "hybrid_complete":hybrid_result.complete,
            "snap_rule_ids":sorted({m.item.rule_id for m in hit.matches}),
        })
    # Grammatical negatives remain completely disjoint from training.
    negatives=ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl"
    negative_rows=[json.loads(x) for x in negatives.read_text().splitlines()
                   if x.strip()]
    neg_results=[]
    for row in negative_rows:
        control=lr.parse(row["text"])
        experimental,route=hybrid.parse(row["text"])
        contrast,contrast_route=hybrid.parse(row["contrast"])
        neg_results.append({
            "id":row["id"],"family":row["family"],
            "baseline_false_accept":control.complete,
            "hybrid_false_accept":experimental.complete,
            "hybrid_route":route,
            "contrast_completes":contrast.complete,
            "contrast_route":contrast_route,
        })
    def metrics(seq):
        return {"p50_ms":quantile(seq[:],.5),"p95_ms":quantile(seq[:],.95),
                "p99_ms":quantile(seq[:],.99)}
    return {
        "schema":"seman2-full-structure-snap-v1",
        "training_source":"dev L-R completed candidate trees (NOT fully verified)",
        "evaluation_source":"non-dev unseen sentences; no online training",
        "training_cases":len(train),"evaluation_cases":len(evaluation),
        "training":dict(training),"index":snap.summary(),
        "teacher_seconds_per_dev_case":teacher_seconds,
        "recognition":{"hits":sum(bool(r["snap_matches"]) for r in case_results),
                       "fully_explored_hits":sum(bool(r["snap_matches"]) and
                                                   not r["snap_incomplete"] for r in case_results),
                       "hits_with_teacher_templates":sum(
                           r["matched_grammar_witness_templates"]>0 for r in case_results),
                       "hits_passing_explicit_gold":sum(
                           r["any_explicit_gold_pass"] for r in case_results),
                       "hits_all_matches_pass_explicit_gold":sum(
                           r["all_explicit_gold_pass"] for r in case_results),
                       "hybrid_snap_fastpath":sum(
                           r["hybrid_path"] == "snap" for r in case_results),
                       "hybrid_lr_fallback":sum(
                           r["hybrid_path"] == "left_to_right" for r in case_results),
                       "baseline_explicit_gold_pass":sum(
                           r["baseline_gold_pass"] is True for r in case_results),
                       "hybrid_explicit_gold_pass":sum(
                           r["hybrid_gold_pass"] is True for r in case_results),
                       "new_gold_passes":sum(
                           r["hybrid_gold_pass"] is True and
                           r["baseline_gold_pass"] is not True
                           for r in case_results),
                       "lost_gold_passes":sum(
                           r["baseline_gold_pass"] is True and
                           r["hybrid_gold_pass"] is not True
                           for r in case_results),
                       "multi_structure_hits":sum(r["snap_matches"]>1 for r in case_results),
                       "incomplete":sum(r["snap_incomplete"] for r in case_results),
                       "no_hit":sum(not r["snap_matches"] for r in case_results)},
        "latency":{
            "snap_recognition_warmed_lattice":metrics(totals["snap_recognition"]),
            "snap_including_lexical_lattice":metrics(totals["snap_including_lattice"]),
            "lr_baseline_including_lattice":metrics(totals["lr"]),
            "hybrid_snap_then_lr_fallback":metrics(totals["hybrid_including_lattice"]),
        },
        "cases":case_results,
        "negative_probe":{
            "cases":len(neg_results),
            "baseline_false_accepts":sum(
                r["baseline_false_accept"] for r in neg_results),
            "hybrid_false_accepts":sum(
                r["hybrid_false_accept"] for r in neg_results),
            "new_false_accepts":sum(
                r["hybrid_false_accept"] and not r["baseline_false_accept"]
                for r in neg_results),
            "contrast_completes":sum(
                r["contrast_completes"] for r in neg_results),
            "details":neg_results,
        },
        "limitations":[
            "Only previously observed full trees are indexed; zero hits do not disprove grammaticality.",
            "One-token lexical slots; trailing period and exclamation are excluded like current L-R.",
            "Candidate templates come from L-R; grammar_witness templates come from independent bounded Earley+unification, NOT gold syntax.",
            "The teacher tests only dev. UNKNOWN from its budgets is not evidence of invalid grammar.",
            "Only one lexical derivation is materialized per matched whole-tree template.",
            "Hard budgets can truncate lookup; such cases are marked incomplete; a valid match still takes fast path.",
            "Hybrid miss reuses the same one-token lexical lattice when the fallback reader uses the same lexical options.",
            "The corpus explicit syntax assertions test only annotated constraints, not complete linguistic correctness.",
            "No 20-million-template memory or on-disk index performance has been claimed.",
        ]
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--max-train",type=int,default=60)
    p.add_argument("--max-eval",type=int,default=60)
    p.add_argument("--repetitions",type=int,default=3)
    p.add_argument("--teacher-seconds",type=float,default=0.35)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=run(wordnet_dir=a.wordnet_dir,max_train=a.max_train,
               max_eval=a.max_eval,repetitions=a.repetitions,
               teacher_seconds=a.teacher_seconds)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("training","index","recognition","latency")},indent=2))
