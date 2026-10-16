"""Independent, deterministic UD English-EWT dev-set generalization probe.

Downloads an exact pinned upstream commit; never trains on it, alters grammar
or uses any held-out annotation to rank parser hypotheses.

Separates acceptance from *gold token POS accuracy*. Failed/incomplete
analyses are NOT scored as valid just because they terminate quickly.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import tokenize

ROOT = Path(__file__).resolve().parents[1]
REVISION = "4a4d77f599ea53cc405f85d0cec4b2f14f81d42b"
URL = f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{REVISION}/en_ewt-ud-dev.conllu"
BINS = ((8, 14), (15, 24), (25, 39), (40, 70))
POS = {
    "NOUN":{"N"}, "PROPN":{"PROPER-NOUN"}, "VERB":{"V"},
    "AUX":{"AUX","AUX-BE","COPULA","HAVE","MODAL","V"},
    "DET":{"DET"}, "PRON":{"PRONOUN","PRON","EXPL","WH-PRONOUN","WH-NOM"},
    "ADJ":{"ADJ"}, "ADV":{"ADV"}, "ADP":{"PREP","PREP-BY","TO"},
    "PART":{"PARTICLE","NEG","TO"}, "NUM":{"NUM"},
    "CCONJ":{"COORD"}, "SCONJ":{"CONJ","COMP-THAT"},
    "INTJ":{"INTJ"},
}


def read_conllu(text):
    for block in text.split("\n\n"):
        sid, sentence, tokens = None, None, []
        for line in block.splitlines():
            if line.startswith("# sent_id = "):
                sid = line.partition("=")[-1].strip()
            elif line.startswith("# text = "):
                sentence = line.partition("=")[-1].strip()
            elif line and not line.startswith("#"):
                cols = line.split("\t")
                if len(cols) >= 4 and cols[0].isdigit():
                    tokens.append((cols[1],cols[3]))
        if sid and sentence and tokens:
            yield {"id":sid,"text":sentence,"tokens":tokens}


def sample(cases, limit_per_bin):
    grouped = defaultdict(list)
    for case in cases:
        words=len(case["tokens"])
        if not case["text"].isascii() or "\t" in case["text"]:continue
        for a,b in BINS:
            if a <= words <= b:
                grouped[f"{a}-{b}"].append(case)
                break
    out=[]
    for a,b in BINS:
        name=f"{a}-{b}"
        # Stable random-like selection; do not select by parse success.
        subset=sorted(grouped[name],
                      key=lambda c:hashlib.sha256(c["id"].encode()).hexdigest())
        out.extend((name,c) for c in subset[:limit_per_bin])
    return out


def leaves(node):
    if getattr(node,"lexical_candidate",None) is not None:
        yield node.lexical_candidate
    for child in getattr(node,"children",()):
        yield from leaves(child)


def pos_accuracy(case,item):
    if item is None:return {"aligned":False,"matched":0,"total":0}
    pred=[(c.surface.casefold(),c.category) for c in leaves(item)]
    gold=[(surface.casefold(),POS[upos]) for surface,upos in case["tokens"]
          if upos in POS]
    if len(pred)!=len(gold) or any(p[0]!=g[0] for p,g in zip(pred,gold)):
        return {"aligned":False,"matched":0,"total":0}
    return {"aligned":True,"matched":sum(p[1] in g[1] for p,g in zip(pred,gold)),
            "total":len(gold)}


def percentile(values,q):
    if not values:return None
    values=sorted(values)
    return round(values[min(len(values)-1,int((len(values)-1)*q))],4)


def run(wordnet_dir=None,limit_per_bin=8,repetitions=2):
    req=Request(URL,headers={"User-Agent":"Seman2-research-UD-evaluation"})
    with urlopen(req,timeout=90) as response:
        source=response.read().decode("utf8")
    selected=sample(read_conllu(source),limit_per_bin)
    if not selected:raise RuntimeError("No matched EWT sentences")
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    modes={
        "baseline":SemanCompiledReader(resources),
        "local2_guard":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=2,construction_guard=True),
        "local3_guard":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=3,construction_guard=True),
        "fast_local3_guard":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=3,construction_guard=True,
                                          fast_multiword=True),
        "token_only_baseline":SemanCompiledReader(resources,token_only_lattice=True),
        "token_only_guard3":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=3,construction_guard=True,
                                          token_only_lattice=True),
        "token_cache_baseline":SemanCompiledReader(resources,token_only_lattice=True,
                                           fast_multiword=True),
        "token_cache_guard3":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=3,construction_guard=True,
                                          token_only_lattice=True,fast_multiword=True),
        "promoted_guard3":SemanCompiledReader(resources,stack_checkpoints=True,
                                          checkpoint_budget=3,construction_guard=True,
                                          token_only_lattice=True,
                                          infer_unary_promotions=True),
    }
    for _,case in selected:
        for machine in modes.values():machine.parse(case["text"])
    rows=defaultdict(list)
    for repeat in range(repetitions):
        for group,case in selected:
            for mode,machine in modes.items():
                t=perf_counter()
                outcome=machine.parse(case["text"])
                elapsed=(perf_counter()-t)*1000
                tok_count=len(tokenize(case["text"]))
                furthest=max((ev.at for ev in outcome.outcome.events),default=0)
                gold=pos_accuracy(case,outcome.item) if outcome.complete else {
                    "aligned":False,"matched":0,"total":0}
                rows[(mode,group)].append({
                    "id":case["id"],"words":len(case["tokens"]),
                    "complete":bool(outcome.complete),"time_ms":round(elapsed,4),
                    "lexical_ms":round(outcome.lexical_ms,4),
                    "read_ms":round(outcome.reading_ms,4),
                    "max_progress":round(furthest/max(1,tok_count),3),
                    "gold":gold,
                })
    results={}
    for mode in modes:
        results[mode]={}
        for a,b in BINS:
            name=f"{a}-{b}"
            subset=rows[(mode,name)]
            n=len(subset)
            if not n:continue
            results[mode][name]={
                "sentences":n//repetitions,
                "mean_words":round(sum(x["words"] for x in subset)/n,2),
                "complete":sum(x["complete"] for x in subset)/repetitions,
                "reached_75pct":sum(x["max_progress"]>=.75 for x in subset)/repetitions,
                "wall_p50_ms":percentile([x["time_ms"] for x in subset],.5),
                "wall_p95_ms":percentile([x["time_ms"] for x in subset],.95),
                "lexical_p50_ms":percentile([x["lexical_ms"] for x in subset],.5),
                "read_p50_ms":percentile([x["read_ms"] for x in subset],.5),
                "aligned_completed":sum(x["gold"]["aligned"] for x in subset)/repetitions,
                "pos_matches":sum(x["gold"]["matched"] for x in subset),
                "pos_gold_tokens":sum(x["gold"]["total"] for x in subset),
            }
    return {
        "schema":1,"source":URL,"pinned_revision":REVISION,
        "selection":"SHA256(sentence ID), independent of parse result",
        "max_per_length_bin":limit_per_bin,"repetitions":repetitions,
        "cases":len(selected),"results":results,
        "limitations":[
            "UPOS is coarser than Seman2's categories; mapping is approximate.",
            "POS accuracy applies only when completed leaves align exactly.",
            "Grammar/attachment correctness is not measured by UPOS alone.",
            "An incomplete parse is not a claim that the source sentence is ungrammatical.",
            "Holdout EWT annotations are not used to tune parser decisions or grammar.",
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir")
    p.add_argument("--per-bin",type=int,default=8)
    p.add_argument("--repetitions",type=int,default=2)
    p.add_argument("--report",default=str(ROOT/"research"/"verbnet_lr"/"ud_ewt_probe.json"))
    a=p.parse_args()
    if a.per_bin<1 or a.repetitions<1:p.error("per-bin and repetitions must be positive")
    result=run(a.wordnet_dir,a.per_bin,a.repetitions)
    Path(a.report).write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps({mode:{bucket:{k:v for k,v in stats.items()
                 if k in ("complete","reached_75pct","wall_p50_ms","aligned_completed","pos_gold_tokens")}
                 for bucket,stats in bins.items()}
                 for mode,bins in result["results"].items()},indent=2))


if __name__=="__main__":
    main()
