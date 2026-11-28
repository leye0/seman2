"""Evaluate source-annotated reporting speakers and selected split dependencies."""
from __future__ import annotations
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

GOLD_PATH=Path(__file__).resolve().parents[1]/"research"/"dialogue_graph_gold.json"

def locate(text, needle, start=0, end=None):
    end=len(text) if end is None else end
    pos=text.index(needle,start,end)
    if text.find(needle,pos+len(needle),end)!=-1:
        raise ValueError("Ambiguous gold anchor: "+needle)
    return pos,pos+len(needle)

def overlaps(span, target):
    return max(span[0],target[0])<min(span[1],target[1])

def assess_option(spans,np,head):
    return bool(spans and all(np[0]<=a<b<=np[1] for a,b in spans)
                and any(overlaps(s,head) for s in spans))

def speaker_result(evidence,np,head):
    groups={tuple(tuple(s) for s in e["speaker_source_spans"])
            for e in evidence if e["speaker_source_spans"]}
    if not groups: return "unresolved"
    if len(groups)>1: return "ambiguous"
    return "correct" if assess_option(next(iter(groups)),np,head) else "wrong"

def gold_evaluate(rows):
    gold=json.loads(GOLD_PATH.read_text())
    reporters=[cid for cid,row in rows.items() if any(p["function"]=="reporting_clause"
                                                 for p in row["graph"]["source_nodes"])]
    selected=sorted(reporters,key=lambda cid:sha256(("speaker-gold-v1:"+cid).encode()).hexdigest())[:20]
    if selected!=[x[0] for x in gold["speaker_cases"]]:
        raise ValueError("Speaker gold sample selection changed")
    counts=Counter()
    speakers=[]
    for cid,tag_text,speaker,head_text in gold["speaker_cases"]:
        row=rows[cid];g=row["graph"];text=row["source_text"]
        tags=[p for p in g["source_nodes"] if p["function"]=="reporting_clause" and text[p["start"]:p["end"]]==tag_text]
        if len(tags)!=1: raise ValueError("Gold reporting anchor drift "+cid)
        tag=tags[0]
        np=locate(text,speaker,tag["start"],tag["end"])
        head=locate(text,head_text,*np)
        attrs=[a for a in g["attributions"] if a["reporting_clause_id"]==tag["id"]]
        ev=attrs[0]["native_report_evidence"] if attrs else []
        whole=[e for e in ev if e["reading_id"].startswith("whole/")]
        component=[e for e in ev if e["reading_id"].startswith("component:")]
        results={"whole":speaker_result(whole,np,head),"component":speaker_result(component,np,head),
                 "combined":speaker_result(whole if any(e["speaker_source_spans"] for e in whole) else component,np,head)}
        for k,v in results.items(): counts["speaker_"+k+"_"+v]+=1
        speakers.append({"case_id":cid,"source_text":text,"gold_speaker":speaker,"gold_head":head_text,
                         "outcomes":results,"candidate_surfaces":[[text[a:b] for a,b in e["speaker_source_spans"]] for e in ev if e["speaker_source_spans"]]})
    dependencies=[]
    for cid,left,right,relation in gold["split_dependencies"]:
        row=rows[cid];g=row["graph"];text=row["source_text"]
        quotes=[p for p in g["source_nodes"] if p["function"]=="direct_speech"]
        # Match only actual quote interiors, not the reporting verb.
        def find(word):
            spans=[]
            for q in quotes:
                if word in text[q["start"]:q["end"]]:
                    a=locate(text,word,q["start"],q["end"])
                    spans.append(a)
            if len(spans)!=1: raise ValueError("Gold dependency anchor ambiguous "+cid+" "+word)
            return spans[0]
        a,b=find(left),find(right)
        def matches(e):
            sig=e["signature"]
            x,y=sig[1],sig[4]
            return ((any(overlaps(s,a) for s in x) and any(overlaps(s,b) for s in y))
                    or (any(overlaps(s,b) for s in x) and any(overlaps(s,a) for s in y)))
        rds={r["id"]:r for r in g["readings"]}
        whole=[e for e in g["native_cross_quote_links"] if e["reading_id"].startswith("whole/") and matches(e)]
        resumed=[e for e in g["native_cross_quote_links"] if not e["reading_id"].startswith("whole/") and matches(e) and not rds[e["reading_id"]]["quality_flags"]]
        counts["dependency_targets"]+=1
        counts["dependency_whole_any"]+=bool(whole)
        counts["dependency_resumed_clear_any"]+=bool(resumed)
        counts["dependency_union"]+=bool(whole or resumed)
        counts["dependency_resumed_only"]+=bool(resumed and not whole)
        dependencies.append({"case_id":cid,"source_text":text,"gold":[left,right,relation],
                             "whole":whole[:3],"resumed":resumed[:3]})
    for cid in gold["terminal_negative"]:
        g=rows[cid]["graph"]
        if any(v["kind"]=="resumed_speech" for v in g["views"]) or any(a["quote_id"]=="q1" for a in g["attributions"]):
            raise ValueError("False cross-sentence resumption "+cid)
    return {"counts":dict(counts),"speaker_cases":speakers,"dependency_cases":dependencies,
            "terminal_negative_controls_passed":len(gold["terminal_negative"]),
            "limitations":"One manual annotator; source-head agreement is not full referent identity. Split dependency endpoint matching is a permissive diagnostic, not full semantic accuracy."}
