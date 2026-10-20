"""Single global quality gate for direct in-place grammar and morphology repairs.

No pattern overlays, no per-sentence exception patches. Classify complete
grammatical negative contrasts and the original 120 annotated sentences
with the same canonical vector parser, plus 500-ms research diagnostics.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
from time import perf_counter
import argparse,json
from seman_parser.engine import ParserResources,Parser
from seman_parser.segmentation import build_lattice
from scripts.evaluate_syntax_correctness import checks_for,all_pass

ROOT=Path(__file__).resolve().parents[1]

def stats(v):
    if not v:return {}
    v=sorted(v)
    return {f"p{int(q*100)}":round(v[int((len(v)-1)*q)],3)
            for q in (.5,.95,.99)} | {"max":round(v[-1],3)}

def run(wordnet_dir):
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    parser=Parser(resources,cache_size=0)
    pairs=[json.loads(x) for x in
           (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl").read_text().splitlines()
           if x.strip()]
    gold=[json.loads(x) for x in
          (ROOT/"data/syntax_correctness_validation.jsonl").read_text().splitlines()
          if x.strip()]
    assert len(gold)==120 and len(pairs)==24
    positive=Counter(); neg=Counter();family=defaultdict(Counter)
    timings=[];outliers=[];failed_gold=[];pairs_detail=[]
    for row in gold:
        started=perf_counter()
        result=parser.parse(row["text"]).result
        item=result.best()
        ms=(perf_counter()-started)*1000
        timings.append(ms)
        annotated=bool(item and all_pass(checks_for(item,row,row["text"])))
        positive["tested"]+=1;positive["completed"]+=int(result.completed)
        positive["annotations_met"]+=int(annotated)
        positive["syntax_exported"]+=int(item is not None and hasattr(item,"syntax"))
        positive["over_500_ms"]+=int(ms>500)
        if not annotated:
            detailed=checks_for(item,row,row["text"]) if item else {}
            failed_gold.append({"id":row["id"],"split":row["split"],
                                "text":row["text"],"completed":result.completed,
                                "root_rule":item.rule_id if item else None,
                                "failed_assertions":{
                                    k:v for k,v in detailed.items() if not all(v)
                                }})
        if ms>500:outliers.append({"id":row["id"],"ms":round(ms,2)})
    for row in pairs:
        pair={"id":row["id"],"family":row["family"]}
        for kind,text in (("negative",row["text"]),("grammatical_contrast",row["contrast"])):
            result=parser.parse(text).result
            item=result.best()
            pair[kind]={"completed":result.completed,
                        "root_rule":item.rule_id if item else None}
            neg[kind+"_tested"]+=1
            neg[kind+"_completed"]+=int(result.completed)
            family[row["family"]][kind+"_tested"]+=1
            family[row["family"]][kind+"_completed"]+=int(result.completed)
        pairs_detail.append(pair)
    # Inspect lexical morphology independently of whether a CLAUSE assembles:
    # we do not wish to confuse absent lexical evidence with chart failure.
    lexical={}
    examples=("barks","bark","are","is","was","were","has","have","does","did")
    for surface in examples:
        lattice=build_lattice(surface,resources.lexicon)
        lexical[surface]=sorted(set(
            (c.category,str(c.features.as_dict()))
            for c in lattice.candidates))
    summary={
        "schema":"seman2-direct-grammar-consolidation-one-pass-v1",
        "design":"direct declarative grammar + lexical morphology, no runtime overlay",
        "positive_gold":dict(positive),"negative_pairs":dict(neg),
        "by_negative_family":{k:dict(v) for k,v in family.items()},
        "positive_wall_ms":stats(timings),"positive_gt_500_ms":outliers,
        "failed_gold":failed_gold,"pair_details":pairs_detail,
        "lexical_morphology":lexical,
        "previous_same_corpus_baseline":{
            "gold_complete":120,"gold_annotations_met":115,
            "negative_completed":19,"grammatical_contrast_completed":22,
            "note":"Historical separate runner measurement; compare coverage not wall-time."},
        "caveats":[
            "Gold assertions cover only selected syntactic facts, not a whole gold tree.",
            "Negative labels describe standard written English; rare dialectal or coerced readings may differ.",
            "Research observation of 500-ms overruns is not a forced parser timeout.",
            "A grammar production witness remains only a candidate, not proof of semantic truth.",
            "The canonical grammar can remain too permissive after these fixes.",
            "Direct corpus dev/test scores on 120 cases are still not external validation.",
        ],
    }
    return summary


def quality_gate(summary):
    # A single system-level gate, not 24 phrase-specific assertions.
    # Annotations still include old grammar rule IDs; an alternate
    # equivalent licensed construction may differ without being wrong.
    p=summary["positive_gold"]
    n=summary["negative_pairs"]
    return {
        "full_sentence_trees_preserved":(
            p["tested"]==120 and p["completed"]==120
            and p["syntax_exported"]==120),
        "annotations_not_materially_regressed":p["annotations_met"]>=113,
        "fewer_ungrammatical_acceptances":n["negative_completed"]<=10,
        "positive_contrasts_preserved":n["grammatical_contrast_completed"]>=22,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run(a.wordnet_dir)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    checks=quality_gate(result)
    print("DIRECT_GLOBAL "+json.dumps({
        "gold":result["positive_gold"],
        "negative":result["negative_pairs"],
        "by_family":result["by_negative_family"],
        "latency_ms":result["positive_wall_ms"],
        "failed_gold":result["failed_gold"],
        "quality_gate":checks,
        "lexical_sample":{k:v for k,v in result["lexical_morphology"].items() if k in ("barks","are","did")},
    }),flush=True)
    for pair in result["pair_details"]:
        if pair["negative"]["completed"]:
            print("DIRECT_NEGATIVE_FALSE_ACCEPT "+json.dumps(pair),flush=True)
    if not all(checks.values()):
        raise SystemExit("System-level grammar quality gate FAILED")


if __name__=="__main__":main()
