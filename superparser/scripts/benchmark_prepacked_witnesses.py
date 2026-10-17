"""A/B/C benchmark: canonical vector, C agenda only, C certified subtree replay.

The 50 development sentences are the sole source of candidate patterns.
Validation + holdout and 24 minimal pairs are never used to learn them.
Unification/combinations are measured by the native vector materializer.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.hybrid_vector import HybridVectorParser
from seman_parser.engine import Parser, ParserResources

ROOT=Path(__file__).resolve().parents[1]
METRICS=("recognition_operations","partial_proposals","unification_attempts",
         "combinations_visited_total","nodes_visited_total",
         "compact_analyses","materialized_items")


def _structure(node):
    if node is None:
        return None
    c=node.lexical_candidate
    return (
        node.category,node.start,node.end,node.rule_id,
        node.features.as_dict(),node.syntax.as_dict(),
        (c.category,c.surface,c.lemma,c.sense_id) if c else None,
        tuple(_structure(x) for x in node.children),
    )


def _quantile(values,p):
    if not values:
        return None
    ordered=sorted(values)
    return round(ordered[int((len(ordered)-1)*p)],3)


def run(wordnet_dir, *, limit=70):
    samples=[json.loads(line) for line in
             (ROOT/"data/syntax_correctness_validation.jsonl").read_text().splitlines()
             if line.strip()]
    pairs=[json.loads(line) for line in
           (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl").read_text().splitlines()
           if line.strip()]
    dev=[x for x in samples if x["split"]=="dev"]
    holdout=[x for x in samples if x["split"]!="dev"][:limit]
    assert len(dev)==50 and len(pairs)==24
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    baseline=Parser(resources,cache_size=0)
    guided=HybridVectorParser(resources,cache_size=0)
    packed=HybridVectorParser(resources,cache_size=0,prepacked_witnesses=True)
    trained=0
    for sample in dev:
        report=baseline.parse(sample["text"])
        if not report.result.completed or report.result.best() is None:
            continue
        for learner in (guided,packed):
            learner.observe(report,source_id=sample["id"])
        trained+=1
    assert guided.compile_guidance()==packed.compile_guidance()

    engines=(("canonical",baseline),("agenda_only",guided),
             ("prepacked",packed))
    inputs=[(row["id"],row["text"],"holdout") for row in holdout]
    inputs.extend((row["id"],row["text"],"invalid") for row in pairs)
    inputs.extend((row["id"],row["contrast"],"contrast") for row in pairs)
    results={}
    for label,engine in engines:
        data={}
        for index,(id_,sentence,kind) in enumerate(inputs,1):
            start=perf_counter()
            report=engine.parse(sentence).result
            best=report.best()
            alternatives=report.alternatives(limit=2)
            elapsed=(perf_counter()-start)*1000
            stats=report.stats
            data[(kind,id_)]={
                "completed":report.completed,
                "best":_structure(best),
                "best_score":best.score if best else None,
                "alternatives":tuple(_structure(x) for x in alternatives),
                "forest":(stats.get("forest_nodes"),stats.get("structural_derivations"),
                          stats.get("partial_states"),stats.get("partial_derivations")),
                "lattice":tuple(sorted((x.span_start,x.span_end,x.category)
                                       for x in report.lattice.candidates)),
                "ms":elapsed,
                "ops":{k:stats.get(k,0) for k in METRICS},
                "c_match_ms":stats.get("c_witness_match_ms",0),
                "witness":dict(stats.get("prepacked_witnesses",{})),
                "budget":bool(stats.get("budget_exceeded",False)),
            }
            if index%25==0:
                print("PROGRESS "+label+" "+str(index)+"/"+str(len(inputs)),flush=True)
        results[label]=data

    mismatches=[]
    for key in results["canonical"]:
        a=results["agenda_only"][key]
        b=results["prepacked"][key]
        # Comparing C replay with C agenda isolates subtree savings from any
        # agenda-order differences. Full lexical CATEGORY MULTIPLICITY and
        # the first two alternatives are checked, not just acceptance.
        for field in ("completed","best","best_score","alternatives","lattice","forest"):
            if a[field]!=b[field]:
                mismatches.append({"case":key,"field":field})
        if a["budget"]!=b["budget"]:
            mismatches.append({"case":key,"field":"budget"})
    measurements={}
    for label in results:
        data=list(results[label].values())
        measurements[label]={
            "tested":len(data),
            "complete":sum(x["completed"] for x in data),
            "by_kind":{kind:sum(x["completed"] for x in data if key[0]==kind)
                       for kind in ("holdout","invalid","contrast")
                       for key,x in results[label].items() if key[0]==kind},
            "p50_ms":_quantile([x["ms"] for x in data],.5),
            "p95_ms":_quantile([x["ms"] for x in data],.95),
            "total_ms":round(sum(x["ms"] for x in data),2),
            "total_ops":{metric:sum(x["ops"][metric] for x in data)
                         for metric in METRICS},
            "C_match_ms":round(sum(x["c_match_ms"] for x in data),2),
            "certified_witnesses":sum(x["witness"].get("certified",0) for x in data),
            "reused_witnesses":sum(x["witness"].get("reused",0) for x in data),
            "budget_exceeded":sum(x["budget"] for x in data),
        }
    old=measurements["agenda_only"]["total_ops"]
    new=measurements["prepacked"]["total_ops"]
    differences={metric:old[metric]-new[metric] for metric in METRICS}
    return {
        "schema":"seman2-certified-C-vector-AB-v1",
        "trained_candidate_sentences":trained,
        "training_count":len(dev),
        "holdout_count":len(holdout),
        "unseen_minimal_pairs":len(pairs),
        "measurements":measurements,
        "saved_native_ops_vs_agenda_only":differences,
        "mismatches":mismatches,
        "parity_pass":not mismatches,
        "qualifications":[
            "C matching time is included in end-to-end elapsed and reported separately.",
            "Direct-grammar assertions are not a full gold tree.",
            "The replay is restricted to proven unique context-independent subtrees.",
            "A faster materializer does not imply a faster end-to-end reader.",
            "Recognition still performs the canonical exhaustive category chart.",
            "A budgeted chart disables C reuse; no incomplete structure is accepted.",
            "This small development corpus does not establish cross-author generalization.",
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--limit",type=int,default=70)
    args=ap.parse_args()
    report=run(args.wordnet_dir,limit=args.limit)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print("RESULT "+json.dumps({
        "parity":report["parity_pass"],
        "measurements":report["measurements"],
        "saved_native_ops":report["saved_native_ops_vs_agenda_only"],
        "mismatches":report["mismatches"][:5],
    }),flush=True)
    if not report["parity_pass"]:
        raise SystemExit("C witness replay changed the canonical agenda outputs")


if __name__=="__main__":
    main()
