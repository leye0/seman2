"""One-shot global diagnosis of feature proofs lost between lexical leaves and grammar parents.

Read-only. Works on fixed negative minimal pairs and their correct contrasts;
never modifies scores, lexical entries or grammar. Detailed structured
diagnostics are retained as JSON rather than printed in bulk.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import json,argparse
from pathlib import Path
from seman_parser.engine import Parser,ParserResources
ROOT=Path(__file__).resolve().parents[1]

def tree_facts(item):
    if item is None:return None
    facts={"category":item.category,"rule":item.rule_id,
           "features":item.features.as_dict(),"span":[item.start,item.end],
           "children":[tree_facts(x) for x in item.children]}
    if item.lexical_candidate is not None:
        x=item.lexical_candidate
        facts["lexical"]={"surface":x.surface,"lemma":x.lemma,
                          "category":x.category,"features":x.features.as_dict(),
                          "source":x.source,
                          "constraints":repr(x.syntactic_constraints)[:250]}
    return facts

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    data=[json.loads(x) for x in (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl").read_text().splitlines() if x.strip()]
    res=ParserResources.from_dir(ROOT/"data",wordnet_dict=a.wordnet_dir)
    parser=Parser(res,cache_size=0)
    rows=[]
    by_family=defaultdict(Counter)
    for x in data:
        obj={"id":x["id"],"family":x["family"]}
        for key,text in (("negative",x["text"]),("contrast",x["contrast"])):
            r=parser.parse(text).result
            item=r.best()
            obj[key]={"text":text,"complete":r.completed,
                      "tree":tree_facts(item)}
            by_family[x["family"]][key+"_complete"]+=int(r.completed)
        rows.append(obj)
        def sketch(item):
            if item is None:return "-"
            if item.get("lexical"):
                leaf=item["lexical"]
                return f'{leaf["surface"]}:{leaf["category"]}{leaf["features"]}'
            return item["category"]+":"+str(item["rule"])+"{"+str(item["features"])+"}("+",".join(sketch(t) for t in item["children"])+")"
        print("PAIR "+x["id"]+" "+x["family"]+
              " bad="+sketch(obj["negative"]["tree"])[:2000]+
              " good="+sketch(obj["contrast"]["tree"])[:2000],flush=True)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({"schema":"seman2-grammar-constraints-one-pass-v1",
                 "families":{k:dict(v) for k,v in by_family.items()},
                 "cases":rows},indent=2)+"\n")
    print("SUMMARY "+json.dumps({k:dict(v) for k,v in by_family.items()}),flush=True)

if __name__=="__main__":main()
