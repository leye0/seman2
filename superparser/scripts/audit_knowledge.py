"""Run real providers on a frozen dialogue corpus, without adding grammar rules.

The diagnostic target cases are probes, not new lexical entries. Score provider
observations only; no predicted speaker or selected ERG reading is changed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from seman_parser.knowledge import Knowledge,Wiktionary
from scripts.novel_sources import EXPECTED_MANIFEST

# These are evaluation targets, not logic in the provider or parser.
PROBES={"Q3-652":"returned","Q3-11":"Miss","Q3-763":"returned"}
WORDS=("return","sternly","Miss","murmur")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--wiktionary",action="store_true")
    p.add_argument("--model",default="en_core_web_sm")
    args=p.parse_args()
    summary=json.loads((args.baseline/"summary.json").read_text())
    if summary["manifest_sha256"]!=EXPECTED_MANIFEST or summary["totals"]["dialogues"]!=327:
        raise ValueError("Wrong pinned dialogue baseline")
    args.out_dir.mkdir(parents=True,exist_ok=True)
    engine=Knowledge(args.model)
    counts=Counter()
    probes=[]
    with (args.baseline/"graphs.jsonl").open() as f,(args.out_dir/"providers.jsonl").open("w") as out:
        for line in f:
            row=json.loads(line)
            text=row["source_text"]
            k=engine.inspect(text)
            if k["source_sha256"]!=sha256(text.encode()).hexdigest():
                raise ValueError("Source identity changed")
            counts["passages"]+=1
            counts["tokens"]+=len(k["tokens"])
            counts["entities"]+=len(k["entities"])
            for key,v in k["lexicon"].items():
                counts["lexical_queries"]+=1
                for provider,values in v.items():
                    counts[provider+"_nonempty"]+=bool(values)
            if row["case_id"] in PROBES or "sternly" in text:
                keys=[key for key in k["lexicon"] if key.lower() in {"return","returned","sternly","miss","dartle","murdstone","agnes"}]
                probes.append({"case_id":row["case_id"],"text":text,"tokens":k["tokens"],
                               "entities":k["entities"],
                               "lexicon":{key:{"wordnet":[{"id":s["id"],"pos":s["pos"],"lexname":s["lexname"],"definition":s["definition"]} for s in k["lexicon"][key]["wordnet"]],
                                              "verbnet":[v["class_id"] for v in k["lexicon"][key]["verbnet"]],
                                              "framenet":[v["frame_name"] for v in k["lexicon"][key]["framenet"]]} for key in keys}})
            out.write(json.dumps({"case_id":row["case_id"],**k},ensure_ascii=False,default=str)+"\n")
            if counts["passages"]%50==0: print("KNOWLEDGE_PROGRESS",dict(counts),flush=True)
    if counts["passages"]!=327: raise ValueError("Incomplete corpus")
    dictionary=[]
    if args.wiktionary:
        wiki=Wiktionary()
        dictionary=[wiki.lookup(word) for word in WORDS]
        (args.out_dir/"wiktionary.json").write_text(json.dumps(dictionary,ensure_ascii=False,indent=2))
    lexical_probes={w:{"wordnet":engine.wordnet(w),
                       "verbnet":[v["class_id"] for v in engine.verbnet(w)],
                       "framenet":[{"lu":v["lu_name"],"frame":v["frame_name"]} for v in engine.framenet(w)]}
                    for w in WORDS}
    report={"manifest_sha256":EXPECTED_MANIFEST,"providers":engine.provenance,
            "counts":dict(counts),"probes":probes,"lexical_probes":lexical_probes,
            "wiktionary":[{"word":d["word"],"status":d["status"]} for d in dictionary],
            "interpretation":"Provider outputs only; no rule, ranking, selected sense or measured accuracy improvement."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    print("KNOWLEDGE_FINAL",json.dumps({"providers":engine.provenance,"counts":dict(counts),
          "wiktionary":report["wiktionary"],
          "probes":[{"case_id":p["case_id"],"text":p["text"],"entities":p["entities"],
                     "tokens":[t for t in p["tokens"] if t["text"].lower() in {"returned","sternly","miss","dartle","agnes","murdstone"}]} for p in probes],
          "lexical_probes":{w:{"wordnet":[{"id":s["id"],"pos":s["pos"],"lexname":s["lexname"],"definition":s["definition"]} for s in v["wordnet"]],
                               "verbnet":v["verbnet"],"framenet":v["framenet"]} for w,v in lexical_probes.items()}},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
