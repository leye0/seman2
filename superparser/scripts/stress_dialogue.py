"""Failure-seeking benchmark, frozen source annotations and controlled contrasts.

No policy is fitted to these outcomes; report errors, ambiguity, abstention
and candidate recall independently. No automatic production promotion.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import re
from pathlib import Path
from seman_parser import Parser
from scripts.novel_sources import EXPECTED_MANIFEST
from scripts.evaluate_dialogue_gold import assess_option

def locate(text, needle, start=0, end=None):
    end=len(text) if end is None else end
    matches=list(re.finditer(r'(?<!\w)'+re.escape(needle)+r'(?!\w)', text[start:end]))
    if len(matches)!=1: raise ValueError(f'Gold word anchor not unique: {needle} in {text[start:end]}')
    return start+matches[0].start(), start+matches[0].end()

from scripts.speaker_selection import POLICIES, speaker_options

ROOT=Path(__file__).resolve().parents[1]
GOLD=ROOT/"research"/"dialogue_speaker_holdout_v2.json"

def outcome(options,np,head):
    if not options: return "unresolved"
    if len(options)>1: return "ambiguous"
    return "correct" if assess_option(options[0],np,head) else "wrong"

def evaluate_attribution(g, attrs, np, head):
    if not attrs: return {k:{"status":"missing_attribution","gold_in_candidates":False} for k in POLICIES}
    # Only the expected quote's attribution; do not reward a correct speaker
    # on a different quotation.
    a=attrs[0]
    all_options=[e["speaker_source_spans"] for e in a["native_report_evidence"] if e["speaker_source_spans"]]
    recall=any(assess_option(o,np,head) for o in all_options)
    return {k:{"status":outcome(speaker_options(g,a,k),np,head),
               "gold_in_candidates":recall,"options":speaker_options(g,a,k)} for k in POLICIES}

def holdout_rows(path):
    gold=json.loads(GOLD.read_text())
    old={r[0] for r in json.loads((ROOT/"research"/"dialogue_graph_gold.json").read_text())["speaker_cases"]}
    candidates={}
    with (path/"graphs.jsonl").open() as f:
        for line in f:
            r=json.loads(line)
            if r["case_id"] not in old and sum(p["function"]=="reporting_clause" for p in r["graph"]["source_nodes"])==1:
                candidates[r["case_id"]]=r
    chosen=sorted(candidates,key=lambda cid:sha256(("speaker-holdout-v2:"+cid).encode()).hexdigest())[:40]
    if chosen!=[x[0] for x in gold]: raise ValueError("Holdout sample drift")
    for cid,tag_text,speaker,head_text in gold:
        r=candidates[cid];g=r["graph"];text=r["source_text"]
        tag=next(p for p in g["source_nodes"] if p["function"]=="reporting_clause" and text[p["start"]:p["end"]]==tag_text)
        np=locate(text,speaker,tag["start"],tag["end"]);head=locate(text,head_text,*np)
        attrs=[a for a in g["attributions"] if a["reporting_clause_id"]==tag["id"]]
        yield {"id":cid,"family":"natural_holdout","text":text,"gold":speaker,
               "outcomes":evaluate_attribution(g,attrs,np,head)}

def stress_cases():
    """Counterbalanced novel lexical items and contrastive discourse contexts.

    Each case specifies exact quoted span and source speaker NP independently
    of parser output. Negative examples require no attribution to the quote.
    Synthetic cases measure controlled behavior, not natural-distribution accuracy.
    """
    people=[("Nora","Felix"),("Dr. Reed","Iris"),("the young captain","Leo"),
            ("Ava and Ben","Milo"),("my sister","Owen"),("Professor Chen","Ruth")]
    def add(family,text,quotes,joined=None):
        return {"id":f"{family}:{sha256(text.encode()).hexdigest()[:12]}","family":family,
                "text":text,"quotes":quotes,"joined":joined}
    for speaker,other in people:
        head=speaker.split()[-1] # coordinated NPs scored separately below
        if " and " in speaker: head=speaker # require overlapping full NP; flag group target
        cap=speaker[0].upper()+speaker[1:]
        q='"We must leave now."'
        yield add("preposed",f'{cap} said to {other}, {q}',[(q,cap,head if cap==speaker else head.capitalize() if head==speaker else head)])
        q='"We must leave now!"'
        yield add("inverted",f'{q} exclaimed {speaker}.',[(q,speaker,head)])
        yield add("inverted_modifier",f'{q} said {speaker} quietly to {other}.',[(q,speaker,head)])
        yield add("noncanonical_speech_verb",f'{q} murmured {speaker}.',[(q,speaker,head)])
        yield add("lexical_polysemy",f'{q} returned {speaker}.',[(q,speaker,head)])
        q='"Do you agree?"'
        yield add("question_addressee",f'{q} asked {speaker} of {other}.',[(q,speaker,head)])
        q='"I expect,"';q2='"to arrive tomorrow."'
        yield add("split_control",f'{q} said {speaker}, {q2}',[(q,speaker,head),(q2,speaker,head)],True)
        q='"If it rains,"';q2='"we will stay here."'
        yield add("split_condition",f'{q} said {speaker}, {q2}',[(q,speaker,head),(q2,speaker,head)],True)
        q='"I agree."';q2='"No, I disagree."'
        yield add("two_turns",f'{q} {cap} said. {q2} {other} replied.',[(q,cap,head if head!=speaker else cap),(q2,other,other)],False)
        q='"The red door"'
        yield add("mention_not_speech",f'{cap} painted the words {q} on the wall and {other} said nothing.',[(q,None,None)],False)
        q='"Please wait."'
        yield add("unrelated_narration",f'{q} {cap} returned the book to {other}.',[(q,None,None)],False)
        q='"The word is \'yes\'."'
        yield add("embedded_quote",f'{cap} said, {q}',[(q,cap,head if head!=speaker else cap),("'yes'",None,None)])
        q='"No!"'
        yield add("passive_reporter",f'{q} was shouted by {speaker} at {other}.',[(q,speaker,head)])
        q='"We are ready."'
        yield add("relative_distractor",f'{cap}, who was looking at {other}, said, {q}',[(q,cap,head if head!=speaker else cap)])
    # Additional nested/direct and punctuational negative controls with known
    # speaker distinction. Exact quote anchors, not inferred from parse.
    yield add("nested_speaker",'"Maya said \'Go now.\'," said Omar.',
              [('"Maya said \'Go now.\',"',"Omar","Omar"),("'Go now.'",None,None)])
    yield add("separate_citations",'"Go," said Nora. "Wait!"',
              [('"Go,"',"Nora","Nora"),('"Wait!"',None,None)],False)

def global_span(text,needle,exclude=()):
    # All generated overt speaker mentions occur once outside their quotes.
    spans=[]
    start=0
    while True:
        i=text.find(needle,start)
        if i<0: break
        s=(i,i+len(needle));start=i+1
        if not any(a<=s[0]<s[1]<=b for a,b in exclude): spans.append(s)
    if len(spans)!=1: raise ValueError(f"Gold anchor not unique: {needle} in {text}")
    return spans[0]

def evaluate_stress(case, parser):
    text=case["text"]
    parsed=parser.parse_paragraph(text)
    quotes=[]
    joined=False
    for u in parsed["units"]:
        g=u.get("dialogue_graph")
        if not g: continue
        offset=u["paragraph_span"][0]
        joined |= any(v["kind"]=="resumed_speech" for v in g["views"])
        for q in g["source_nodes"]:
            if q["function"] in {"direct_speech","embedded_quotation"}:
                quotes.append((offset+q["start"],offset+q["end"],offset,q,g))
    expected_spans=[global_span(text,q) for q,_,_ in case["quotes"]]
    observed=[]
    for expected,(quote,speaker,head_text) in zip(expected_spans,case["quotes"]):
        matches=[(off,q,g) for a,b,off,q,g in quotes if (a,b)==expected]
        if len(matches)!=1:
            observed.append({"quote":quote,"gold_speaker":speaker,"quote_found":False,
                             "outcomes":{p:{"status":"missing_quote","gold_in_candidates":False} for p in POLICIES}})
            continue
        off,q,g=matches[0]
        attrs=[a for a in g["attributions"] if a["quote_id"]==q["id"]]
        if speaker is None:
            # Distinguish unsupported source attribution from a claimed speaker.
            outcomes={p:{"status":"false_attribution" if attrs else "correct_abstention",
                         "gold_in_candidates":False} for p in POLICIES}
        else:
            np=global_span(text,speaker,expected_spans);head=locate(text,head_text,*np)
            local_np=tuple(x-off for x in np);local_head=tuple(x-off for x in head)
            outcomes=evaluate_attribution(g,attrs,local_np,local_head)
        observed.append({"quote":quote,"gold_speaker":speaker,"quote_found":True,"outcomes":outcomes})
    # A previously unseen extra quote is not hidden by only scoring expected quotes.
    return {**case,"quote_results":observed,"extra_quote_count":sum((a,b) not in expected_spans for a,b,*_ in quotes),
            "join_expected":case["joined"],"join_observed":joined,
            "interface_errors":sum(u.get("whole",{}).get("status") in {"interface_error","incomplete_native_output"}
                                   for u in parsed["units"] if u.get("whole")),
            "native_statuses":[u.get("whole",{}).get("status") if u.get("whole") else u.get("status") for u in parsed["units"]]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--ace",type=Path,required=True)
    p.add_argument("--grammar",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    s=json.loads((args.baseline/"summary.json").read_text())
    if s["manifest_sha256"]!=EXPECTED_MANIFEST or s["totals"]["dialogues"]!=327: raise ValueError("Wrong frozen baseline")
    counts=defaultdict(Counter); failures=[]; n=Counter()
    def record(family, row):
        for policy,o in row["outcomes"].items():
            counts[family][policy+":"+o["status"]]+=1
            if o.get("gold_in_candidates"): counts[family][policy+":candidate_recall"]+=1
        if row["outcomes"]["baseline"]["status"] not in {"correct","correct_abstention"}:
            failures.append({"family":family,**row})
    with (args.out_dir/"natural.jsonl").open("w") as f:
        for row in holdout_rows(args.baseline):
            n["natural_passages"]+=1
            record(row["family"],row);f.write(json.dumps(row,ensure_ascii=False)+"\n")
    with (args.out_dir/"ace.stderr.log").open("w") as err, Parser(args.grammar,executable=args.ace,stderr=err) as parser, (args.out_dir/"stress.jsonl").open("w") as f:
        for case in stress_cases():
            row=evaluate_stress(case,parser)
            n["synthetic_passages"]+=1;n["synthetic_quotes"]+=len(row["quote_results"])
            n["interface_errors"]+=row["interface_errors"];n["extra_quotes"]+=row["extra_quote_count"]
            if row["join_expected"] is not None:
                n["join_targets"]+=1
                n["join_correct"]+=row["join_expected"]==row["join_observed"]
            for q in row["quote_results"]:
                record(row["family"],{"id":row["id"],"text":row["text"],**q})
                for policy,o in q["outcomes"].items():
                    counts["synthetic_all"][policy+":"+o["status"]]+=1
                    if o["gold_in_candidates"]: counts["synthetic_all"][policy+":candidate_recall"]+=1
            f.write(json.dumps(row,ensure_ascii=False)+"\n");f.flush()
            if n["synthetic_passages"]%12==0: print("STRESS_PROGRESS",dict(n),flush=True)
    report={"manifest_sha256":EXPECTED_MANIFEST,"inventory":dict(n),
            "scores":{k:dict(v) for k,v in counts.items()},
            "baseline_failures":len(failures),
            "limitations":"Synthetic contrasts and a new sample from an already used corpus, not a fully independent natural held-out corpus. No policy promoted. Coordination head overlap is permissive; speaker identity not independently resolved."}
    (args.out_dir/"summary.json").write_text(json.dumps(report,indent=2))
    (args.out_dir/"failures.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2))
    print("STRESS_FINAL",json.dumps(report),flush=True)
    if n["interface_errors"]: raise SystemExit("Native interface errors")

if __name__=="__main__": main()
