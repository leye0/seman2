"""Like-for-like syntax quality comparison: production vector forest vs research L-R.

Same annotated English sentences, same grammar/WordNet and warmed resources.
The vector grammar keeps multiword lexical spans; L-R currently requires
token-only spans. The difference is deliberately disclosed, not hidden.

Outputs aggregate metrics only. No training on gold and no source rewrite.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from seman_parser.engine import Parser,ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from scripts.evaluate_syntax_correctness import all_pass,checks_for

ROOT=Path(__file__).resolve().parents[1]


def pct(seq,percent):
    if not seq:return None
    s=sorted(seq)
    return round(s[min(len(s)-1,int((len(s)-1)*percent))],3)


def has_syntax(node):
    """Full derivation with structural roles/attachments and lexical anchors."""
    if node is None or node.category!="CLAUSE":return False
    found_rule=False
    leaves=0
    stack=[node]
    while stack:
        item=stack.pop()
        if item.rule_id:found_rule=True
        if item.lexical_candidate is not None:leaves+=1
        if not hasattr(item,"syntax"):return False
        stack.extend(item.children)
    return found_rule and leaves>0


def assess(wordnet_dir,*,limit=120):
    gold=[json.loads(x) for x in
          (ROOT/"data/syntax_correctness_validation.jsonl").read_text().splitlines()
          if x.strip()]
    negatives=[json.loads(x) for x in
          (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl").read_text().splitlines()
          if x.strip()]
    if limit<1 or limit>len(gold):raise ValueError("Invalid gold corpus limit")
    gold=gold[:limit]
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    vector=Parser(resources,cache_size=0)
    lr=SemanCompiledReader(resources,token_only_lattice=True)
    out={}
    for name in ("vector_forest","lr_compiled"):
        successes=Counter()
        by_split=defaultdict(Counter)
        durations=[]
        failing_reasons=Counter()
        for idx,row in enumerate(gold,1):
            start=perf_counter()
            if name=="vector_forest":
                result=vector.parse(row["text"]).result
                completed=result.completed
                root=result.best() if completed else None
            else:
                result=lr.parse(row["text"])
                completed=result.complete
                root=result.item if completed else None
            wall_ms=1000*(perf_counter()-start)
            durations.append(wall_ms)
            ok=(completed and root is not None
                and all_pass(checks_for(root,row,row["text"])))
            pool=(successes,by_split[row["split"]])
            for c in pool:
                c["tested"]+=1
                c["complete"]+=int(bool(completed))
                c["all_gold_assertions_met"]+=int(ok)
                c["full_tree_with_syntax_package"]+=int(has_syntax(root))
                c["complete_but_annotations_wrong"]+=int(completed and not ok)
            if not completed and name=="lr_compiled":
                failing_reasons[result.outcome.reason.split("_at_")[0]]+=1
            if idx%30==0:
                print("PROGRESS "+name+" "+str(idx)+
                      " complete="+str(successes["complete"])+
                      " correct="+str(successes["all_gold_assertions_met"]),
                      flush=True)
        negative_stats=Counter()
        for row in negatives:
            for label,text in (("negative",row["text"]),
                               ("positive_contrast",row["contrast"])):
                if name=="vector_forest":
                    report=vector.parse(text).result
                    passed=bool(report.completed and report.best() is not None)
                else:
                    report=lr.parse(text)
                    passed=report.complete
                negative_stats[label+"_tested"]+=1
                negative_stats[label+"_completed"]+=int(passed)
        out[name]={
            "positive_gold":dict(successes),
            "by_gold_split":{k:dict(v) for k,v in by_split.items()},
            "negatives":dict(negative_stats),
            "wall_ms":{"p50":pct(durations,.5),"p95":pct(durations,.95),
                       "p99":pct(durations,.99),"max":round(max(durations),3)},
            "lr_stop_reasons":dict(failing_reasons),
        }
    return {
        "schema":"seman2-parser-lineage-apples-to-apples-v1",
        "positive_cases":len(gold),
        "negative_contrasts":len(negatives),
        "shared_data":"identical gold assertions, grammar and WordNet, independent no-cache parse",
        "known_difference":"production vector uses full multi-span lattice and full packed forest; L-R uses one-token lattice and a single path",
        "methodological_limits":[
            "Positive gold checks are partial assertions, not proof the entire dependency graph is correct.",
            "Small gold corpus previously used to develop grammar and ranking, so not truly unseen.",
            "A completed negative parse counts as a possible false accept, not a standalone proof of linguistic invalidity.",
            "Latency includes lexical warmup and annotation verification in the measured positive loop.",
            "No absolute wall-clock timeout; runner CPU speed differs from the earlier experiments.",
            "Vector grammar can find fully well-formed structures in the packed forest even when top-1 differs from annotated choice.",
        ],
        "engines":out,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--limit",type=int,default=120)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=assess(a.wordnet_dir,limit=a.limit)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print("FINAL_LINEAGE "+json.dumps(result["engines"]),flush=True)
