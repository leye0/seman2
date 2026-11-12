"""One-pass, source-pinned decomposition of all 24 residual dialogues.

This script diagnoses independent subconstituent recognition; it does not
promote fragments to complete rank-one parses and does not modify source text.
The existing 500-sentence extraction and original source spans are unchanged.
"""
from __future__ import annotations
import json
import re
import signal
from pathlib import Path
from seman_parser.engine import Parser
from scripts.diagnose_novel_parses import select_cases

DATA = Path(__file__).resolve().parents[1] / "data"
INDEXES = (56,66,96,99,109,157,200,209,223,229,235,237,
           241,247,359,408,441,445,456,464,466,475,495,498)
class ProbeTimeout(Exception): pass
def alarm(*_): raise ProbeTimeout()

def main():
    cases,_ = select_cases(500)
    parser = Parser.from_dir(DATA,cache_size=24)
    signal.signal(signal.SIGALRM,alarm)
    totals = {}
    for index in INDEXES:
        case=cases[index]
        text=case["source_text"]
        parts=case.get("structural_constituents",())
        qparts=[x for x in parts if x["function"]=="spoken_clause_candidate"]
        tags=[x for x in parts if x["function"]=="reporting_clause"]
        print("DIALOGUE_CASE",json.dumps({
            "index":index,"text":text,
            "quotes":[[x["start"],x["end"],text[x["start"]:x["end"]]]
                       for x in parts if x["function"]=="direct_speech"],
            "tags":[[x["start"],x["end"],text[x["start"]:x["end"]]] for x in tags],
            "parts":len(qparts)}),flush=True)
        samples=[]
        for x in qparts:
            a,b=x["start"],x["end"]
            raw=text[a:b]
            # Source punctuation removed only from a diagnostic fragment,
            # never from a corpus parse or proposed completed analysis.
            body=raw.rstrip(".!?")
            if body:
                samples.append(("spoken",a,a+len(body),body))
            # Split multi-clause quotations by their printed stops. Retain
            # exact original character spans and punctuation metadata.
            for m in re.finditer(r"[^.!?]+[.!?]",raw):
                unit=m.group(0)
                l=len(unit)-len(unit.lstrip())
                unit=unit.strip()
                if not unit:continue
                a1=a+m.start()+l
                b1=a1+len(unit)-1
                if a1<b1:samples.append(("sentence",a1,b1,text[a1:b1]))
        for x in tags:
            a,b=x["start"],x["end"]
            samples.append(("reporter",a,b,text[a:b]))
        # Deduplicate but keep exact source ranges.
        unique={}
        for cat,a,b,s in samples:
            unique[(a,b,cat)]=(cat,a,b,s)
        for kind,a,b,s in unique.values():
            goals=("SPEECH-TAG",) if kind=="reporter" else ("CLAUSE","NP","ADVP","PP")
            out={"index":index,"role":kind,"source_span":[a,b],
                 "surface":s,"results":{}}
            for goal in goals:
                signal.setitimer(signal.ITIMER_REAL,5)
                try:
                    lattice=parser._lattice_for_text(s)
                    grammar=(parser._dialogue_vector_grammar
                             if goal=="SPEECH-TAG" else parser._vector_grammar)
                    parsed=grammar.parse_lattice(lattice,goal_category=goal,
                        max_items=12000,kbest_work_limit=100000)
                    best=parsed.best()
                    out["results"][goal]={
                        "ok":bool(parsed.completed and best),
                        "rule":best.rule_id if best else None,
                        "children":[[c.category,c.rule_id,s[c.start:c.end]]
                                    for c in best.children] if best else [],
                        "budget":parsed.stats.get("budget_exceeded"),
                    }
                except ProbeTimeout:out["results"][goal]={"timeout":True}
                finally:signal.setitimer(signal.ITIMER_REAL,0)
            print("DIALOGUE_UNIT",json.dumps(out,ensure_ascii=False),flush=True)
        totals[index]=len(unique)
    print("DIALOGUE_24_PROBED",json.dumps(totals),flush=True)
if __name__=="__main__":main()
