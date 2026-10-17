"""Test learned C-guided vector agenda against exact canonical parse outputs.

50 development sentences train rule preferences; 70 validation/holdout
sentences are never used for training. 24 ungrammatical contrasts are tested.
Both engines share the original Grammar and WordNet lexical resources.
"""
from __future__ import annotations
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from time import perf_counter

from seman_parser.engine import Parser,ParserResources
from research.verbnet_lr.hybrid_vector import HybridVectorParser
from scripts.evaluate_syntax_correctness import all_pass,checks_for

ROOT=Path(__file__).resolve().parents[1]


def shape(root):
    if root is None:return None
    if root.lexical_candidate is not None:
        c=root.lexical_candidate
        return ("leaf",root.category,c.surface.casefold(),c.lemma.casefold())
    return (root.category,root.rule_id,tuple(shape(x) for x in root.children))


def contract(root):
    if root is None:return None
    return (root.category,root.start,root.end,
            root.syntax.as_dict(),root.features.as_dict())


def pct(data,p):
    if not data:return None
    v=sorted(data)
    return round(v[int((len(v)-1)*p)],3)


def run(wordnet_dir):
    rows=[json.loads(x) for x in
          (ROOT/"data/syntax_correctness_validation.jsonl").read_text().splitlines()
          if x.strip()]
    negatives=[json.loads(x) for x in
               (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl").read_text().splitlines()
               if x.strip()]
    training=[r for r in rows if r["split"]=="dev"]
    testing=[r for r in rows if r["split"]!="dev"]
    assert (len(training),len(testing),len(negatives))==(50,70,24)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    original=Parser(resources,cache_size=0)
    hybrid=HybridVectorParser(resources,cache_size=0)
    sources=Counter()
    for row in training:
        report=original.parse(row["text"])
        best=report.result.best()
        if best is not None and all_pass(checks_for(best,row,row["text"])):
            observation=hybrid.observe(report,source_id=row["id"],evidence="candidate")
            sources["annotated_dev_sources"]+=int(observation["learned"])
        else:sources["not_learned"]+=1
    compiled=hybrid.compile_guidance()
    print("TRAIN "+json.dumps({"sources":dict(sources),"guided_rules":compiled}),flush=True)
    results={}
    reference={}
    diffs=[]
    lattice_diffs=[]
    for label,engine in (("original_vector",original),("learned_C_vector",hybrid)):
        counts=Counter()
        by_split=defaultdict(Counter)
        lat=[]
        for i,row in enumerate(testing,1):
            start=perf_counter()
            report=engine.parse(row["text"])
            tree=report.result.best()
            latency=(perf_counter()-start)*1000
            lat.append(latency)
            ok=bool(tree is not None and all_pass(checks_for(tree,row,row["text"])))
            categories=sorted(set((x.span_start,x.span_end,x.category)
                                  for x in report.result.lattice.candidates))
            forest_metrics={key:report.result.stats.get(key) for key in (
                "forest_nodes","structural_derivations",
                "partial_states","partial_derivations")}
            k=(shape(tree),contract(tree),categories,forest_metrics)
            for bucket in (counts,by_split[row["split"]]):
                bucket["tested"]+=1
                bucket["complete"]+=int(report.result.completed)
                bucket["annotations_met"]+=int(ok)
                bucket["full_syntax"]+=int(tree is not None and bool(tree.children)
                    and hasattr(tree,"syntax"))
                bucket["budget_exceeded"]+=int(
                    report.result.stats.get("budget_exceeded",False))
            if label=="original_vector":
                reference[row["id"]]=(k,report.result.completed)
            else:
                previous,old_complete=reference[row["id"]]
                for name,match in (
                    ("same_complete",old_complete==report.result.completed),
                    ("same_best_tree",previous[0]==k[0]),
                    ("same_syntax",previous[1]==k[1]),
                    ("same_lexical_categories",previous[2]==k[2]),
                    ("same_forest_size",previous[3]==k[3])):
                    counts[name]+=int(match)
                counts["budget_fallback"]+=int(
                    report.result.stats.get("hybrid_guidance",{}).get(
                        "fallback_after_guided_budget",False))
                if previous[0]!=k[0]:diffs.append(row["id"])
                if previous[2]!=k[2]:
                    lattice_diffs.append({
                        "id":row["id"],"text":row["text"],
                        "baseline_only":sorted(set(previous[2])-set(k[2])),
                        "hybrid_only":sorted(set(k[2])-set(previous[2])),
                    })
            if i%25==0:
                print("EVAL "+label+" "+json.dumps({
                    "seen":i,"complete":counts["complete"],
                    "annotations_met":counts["annotations_met"]}),flush=True)
        neg=Counter()
        for row in negatives:
            for kind,sentence in (("ungrammatical",row["text"]),
                                  ("grammatical_contrast",row["contrast"])):
                result=engine.parse(sentence).result
                neg[kind+"_tested"]+=1
                neg[kind+"_complete"]+=int(result.completed)
        results[label]={
            "scores":dict(counts),
            "split_scores":{k:dict(v) for k,v in by_split.items()},
            "negatives":dict(neg),
            "latency_ms":{"p50":pct(lat,.5),"p95":pct(lat,.95),
                          "p99":pct(lat,.99),"max":round(max(lat),3)},
        }
    return {
        "schema":"seman2-C-hybrid-vector-vertical-slice-v1",
        "training":dict(sources),"guided_rule_compilation":compiled,
        "memory":hybrid.guidance_summary(),
        "validation":results,"tree_differences":diffs,
        "lexical_lattice_differences":lattice_diffs,
        "caveats":[
            "Only the production-rule agenda order is learned; forest outputs and grammar rules are canonical.",
            "The learned source tree agrees with selected dev assertions but is still candidate, not fully independent gold.",
            "The 70 validation and holdout sentences do not train the rule index.",
            "Annotation checks cover selected syntax properties only, not full attachment gold.",
            "Negative parse completion can be a false acceptance; we do not call it true grammaticality.",
            "The vector parser uses a full morphological and multiword lattice in both arms.",
            "WordNet lexical initialization and assertions affect reported wall time.",
            "External novels and long-sentence generalization remain unmeasured by this experiment.",
            "The hybrid does NOT yet accelerate internal chart unification or inject memoized subtree nodes."
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    report=run(a.wordnet_dir)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print("FINAL_HYBRID "+json.dumps({
        "sources":report["training"],
        "compiled":report["guided_rule_compilation"],
        "comparison":report["validation"],
        "tree_differences":report["tree_differences"],
        "lexical_lattice_differences":report["lexical_lattice_differences"],
    }),flush=True)


if __name__=="__main__":
    main()
