"""Read-only trace of canonical #466 source/proof under original parse budgets."""
from __future__ import annotations
import json,re
from pathlib import Path
from types import MethodType
from seman_parser.engine import Parser
from scripts.diagnose_novel_parses import select_cases
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.structural_preanalysis import analyze_paragraph
DATA=Path(__file__).resolve().parents[1]/"data"
def main():
    p=Parser.from_dir(DATA,cache_size=0)
    c=p._quoted_sentence_composer
    source=select_cases(500)[0][466]["source_text"]
    print("TRACE_466_SOURCE",repr(source),flush=True)
    print("TRACE_466_COMPONENTS",json.dumps([x.to_dict() for x in analyze_paragraph(source)[0].constituents]),flush=True)
    original=c._compose_verified_dialogue_pattern
    def traced(self,parser,text,lattice,specs,expected_rule,**kwargs):
        if expected_rule!="dialogue_structural_vocative_praise_stars_reporter":
            return original(parser,text,lattice,specs,expected_rule,**kwargs)
        n=sum(kind=="phrase" for _,_,_,kind,_ in specs)
        print("TRACE_466_PROOF_ENTER",n,flush=True)
        for cat,a,b,kind,needed in specs:
            evidence=[]
            if kind=="lexical":
                for x in lattice.candidates:
                    if x.category==cat and (x.span_start,x.span_end)==(a,b):
                        f=x.features.as_dict()
                        satisfied=all(
                          v in (f.get("subcat",()) if isinstance(f.get("subcat"),(list,tuple)) else (f.get("subcat"),))
                          if k=="subcat_member" else f.get(k)==v
                          for k,v in needed.items())
                        evidence.append([satisfied,f])
            if kind=="phrase":
                frag=text[a:b]
                if cat=="CLAUSE":
                    result=parser._parse_vector_text(frag,max_items=50_000//(n+1),
                        kbest_work_limit=500_000//(n+1))
                else:
                    grammar=(parser._dialogue_vector_grammar if cat=="SPEECH-TAG"
                             else parser._vector_grammar)
                    result=grammar.parse_lattice(parser._lattice_for_text(frag),
                        goal_category=cat,max_items=50_000//(n+1),
                        kbest_work_limit=500_000//(n+1),beam=parser.beam)
                tree=result.best()
                evidence=[{"completed":result.completed,
                          "root":tree.rule_id if tree else None,
                          "features":tree.features.as_dict() if tree else None,
                          "children":[(x.category,x.rule_id,frag[x.start:x.end]) for x in tree.children] if tree else None}]
            print("TRACE_466_PIECE",json.dumps({"text":text[a:b],"cat":cat,"kind":kind,
                "needed":needed,"evidence":evidence[:5]}),flush=True)
        res=original(parser,text,lattice,specs,expected_rule,**kwargs)
        print("TRACE_466_PROOF_RESULT",bool(res),flush=True)
        return res
    c._compose_verified_dialogue_pattern=MethodType(traced,c)
    old=c._compose_vocative_praise_stars_reporter
    def wrap(self,parser,text,lattice,components,**kwargs):
        print("TRACE_466_METHOD_ENTER",[(x.get("id"),x.get("function"),x.get("start"),x.get("end")) for x in components],flush=True)
        res=old(parser,text,lattice,components,**kwargs)
        print("TRACE_466_METHOD_RESULT",bool(res),flush=True)
        return res
    c._compose_vocative_praise_stars_reporter=MethodType(wrap,c)
    case=select_cases(500)[0][466]
    _,_,r=parse_corpus_case(p,case,max_items=50_000,kbest_work_limit=500_000)
    print("TRACE_466_FINAL",r.completed,r.stats.get("structural_composition_kind"),flush=True)
if __name__=="__main__":main()
