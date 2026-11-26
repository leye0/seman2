"""Paired raw-text external diagnostic: frozen UD EWT test, restricted relation projection.

Scores are recall of a deliberately narrow set of gold relations, NOT UD LAS.
Seman2 uses its selected semantic graph; ERG uses native MRS. Gold is not
passed to either engine. Unmapped output and failed parses are misses.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import signal

from delphin import ace
from delphin.codecs import simplemrs
from scripts.benchmark_native_erg import observe, hash_file
from scripts.evaluate_novel_transfer import measure, Parser, ParserResources, ROOT, MAX_ITEMS, _deadline
from research.typed_resource_poc.resources import UD_COMMIT, download
from research.typed_resource_poc.evaluation import read_conllu

KINDS = ("nsubj", "obj", "amod", "advmod")
# Conservative coarse mapping; labels not listed count as unrepresented.
S_ROLES = {
    "nsubj": {"AGENT", "EXPERIENCER", "PREDICAND", "SUBJECT", "ACTOR", "THEME", "POSSESSOR", "PATIENT"},
    "obj": {"AFFECTED", "PATIENT", "THEME", "OBJECT", "CONTENT", "TARGET", "SOURCE", "POSSESSED", "RECIPIENT"},
    "amod": {"MODIFIER", "ATTRIBUTE", "PROPERTY"},
    "advmod": {"MODIFIER", "MANNER", "DEGREE", "ADJUNCT", "TEMPORAL", "FREQUENCY", "DURATION", "LOCATION", "MITIGATOR", "EMPHASIS", "REPETITION"},
}

def align(text, tokens):
    spans = {}
    cursor = 0
    for word in tokens:
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if not text.startswith(word.text, cursor):
            return None
        spans[word.id] = [cursor, cursor + len(word.text)]
        cursor += len(word.text)
    return spans if not text[cursor:].strip() else None

def targets(gold, spans):
    by_id = {w.id:w for w in gold.tokens}
    active_transitive = {w.head for w in gold.tokens if w.deprel == "obj"
                         and w.upos in {"NOUN", "PROPN", "PRON"}}
    out = []
    for w in gold.tokens:
        h = by_id.get(w.head)
        if not h or w.deprel not in KINDS:
            continue
        if w.deprel in {"nsubj", "obj"}:
            if h.upos != "VERB" or h.id not in active_transitive or w.upos not in {"NOUN","PROPN","PRON"}:
                continue
            if any(t.head == h.id and t.deprel in {"aux:pass","nsubj:pass"} for t in gold.tokens):
                continue
        elif w.deprel == "amod" and (w.upos != "ADJ" or h.upos != "NOUN"):
            continue
        elif w.deprel == "advmod" and (w.upos != "ADV" or h.upos not in {"ADJ","VERB"} or w.lemma in {"not","n't","never"}):
            continue
        out.append({"kind":w.deprel,"head":spans[h.id],"dep":spans[w.id],
                    "head_text":h.text,"dep_text":w.text})
    return out

def same_span(text, observed, target):
    if not observed or len(observed) != 2:
        return False
    a,b = observed
    x,y = target
    if not (0 <= a <= x < y <= b <= len(text)):
        return False
    return all(not c.isalnum() and not c.isspace() for c in text[a:x]+text[y:b])

def seman_hit(text, graph, target):
    nodes = {n["id"]:n for n in graph.get("nodes",[])}
    for edge in graph.get("relations",[]):
        if edge["relation"] not in S_ROLES[target["kind"]]:
            continue
        h = nodes.get(edge["source"],{}).get("span")
        d = nodes.get(edge["target"],{}).get("span")
        if same_span(text,h,target["head"]) and same_span(text,d,target["dep"]):
            return True
    return False

def erg_hit(text, mrs, target):
    eps = [ep for ep in mrs.rels if not ep.is_quantifier()
           and ep.predicate.strip('"') not in {"unknown","quoted","fw_seq"}]
    h = [ep for ep in eps if same_span(text,[ep.cfrom,ep.cto],target["head"])]
    d = [ep for ep in eps if same_span(text,[ep.cfrom,ep.cto],target["dep"])]
    if target["kind"] in {"nsubj","obj"}:
        arg = "ARG1" if target["kind"] == "nsubj" else "ARG2"
        return any(y.iv is not None and x.args.get(arg)==y.iv for x in h for y in d)
    return any(x.iv is not None and y.args.get("ARG1")==x.iv for x in h for y in d)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ace",type=Path,required=True)
    p.add_argument("--grammar",type=Path,required=True)
    p.add_argument("--wordnet-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--limit",type=int,default=200)
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    raw=download(f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{UD_COMMIT}/en_ewt-ud-test.conllu",
                 args.out_dir/"source.conllu")
    gold=read_conllu(raw.decode("utf-8"))
    eligible=[]
    selection=Counter()
    for g in gold:
        if not 4 <= len(g.tokens) <= 32:
            selection["length_excluded"]+=1
            continue
        spans=align(g.text,g.tokens)
        if spans is None:
            selection["gold_alignment_excluded"]+=1
            continue
        ts=targets(g,spans)
        if not ts:
            selection["no_target_relation_excluded"]+=1
            continue
        eligible.append((g,ts))
    eligible.sort(key=lambda item: sha256(("native-paired-ewt-v1:"+item[0].sent_id).encode()).digest())
    chosen=eligible[:args.limit]
    if len(chosen)!=args.limit:
        raise RuntimeError("Too few eligible external cases")
    manifest=[{"sent_id":g.sent_id,"text":g.text,"targets":ts} for g,ts in chosen]
    (args.out_dir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    options=["-n","10","--timeout=10","--max-words=200","--max-chart-megabytes=1200","--max-unpack-megabytes=1500"]
    parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir),cache_size=0,max_items=MAX_ITEMS)
    parser.parse("John opened the box.")
    old=signal.signal(signal.SIGALRM,_deadline)
    counts={k:Counter() for k in KINDS}
    status=Counter()
    try:
        with (args.out_dir/"ace.stderr.log").open("w") as stderr, ace.ACEParser(str(args.grammar),executable=str(args.ace),cmdargs=options,stderr=stderr) as er, (args.out_dir/"paired.jsonl").open("w",encoding="utf-8") as out:
            for i,(g,ts) in enumerate(chosen,1):
                # Non-Gutenberg raw utterance. Preserve text, no invented quotation context.
                case={"text":g.text,"source_text":g.text,"balanced_analysis_text":g.text,
                      "balanced_synthetic_prefix":"","balanced_synthetic_suffix":"","balanced_synthetic_terminal":False}
                try:
                    s=measure(parser,case,with_semantics=True)
                except Exception as exc:
                    s={"status":"interface_error","error":repr(exc)}
                e=observe(er,g.text,10)
                decoded=[]
                errors=[]
                for result in e["results"]:
                    try:
                        decoded.append(simplemrs.decode(result["mrs"]))
                    except Exception as exc:
                        decoded.append(None)
                        errors.append(repr(exc))
                graph=(s.get("selected_graph") or {}).get("graph",{})
                judgments=[]
                for target in ts:
                    sh=seman_hit(g.text,graph,target)
                    hits=[k+1 for k,m in enumerate(decoded) if m is not None and erg_hit(g.text,m,target)]
                    c=counts[target["kind"]]
                    c.update({"gold":1,"seman_hit":int(sh),"erg_rank1_hit":int(1 in hits),"erg_any_hit":int(bool(hits))})
                    judgments.append({**target,"seman_hit":sh,"erg_ranks":hits})
                status.update({"seman_"+s["status"]:1,"erg_"+e["status"]:1,"mrs_decode_errors":len(errors)})
                out.write(json.dumps({"sent_id":g.sent_id,"text":g.text,"judgments":judgments,
                                      "seman":s,"erg":e,"mrs_decode_errors":errors},default=str,ensure_ascii=False)+"\n")
                out.flush()
                if i%10==0:
                    print("PAIRED_PROGRESS",i,dict(status),{k:dict(v) for k,v in counts.items()},flush=True)
    finally:
        signal.signal(signal.SIGALRM,old)
    total=Counter()
    for c in counts.values():total.update(c)
    report={"kind":"restricted_external_gold_relation_recall_not_LAS","ud_commit":UD_COMMIT,
            "source_sha256":sha256(raw).hexdigest(),"grammar_sha256":hash_file(args.grammar),
            "ace_sha256":hash_file(args.ace),"eligible":len(eligible),"selected":len(chosen),
            "selection_exclusions":dict(selection),"status":dict(status),"by_kind":counts,
            "totals":total,"warning":"Different representational conventions may produce false misses. Review projection against native outputs; not full syntax or semantics accuracy."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,indent=2))
    print("PAIRED_FINAL",json.dumps(report),flush=True)
    if status["mrs_decode_errors"] or status["seman_interface_error"] or status["erg_interface_error"]:
        raise SystemExit("Interface errors: inspect artifact before interpreting scores")

if __name__=="__main__":
    main()
