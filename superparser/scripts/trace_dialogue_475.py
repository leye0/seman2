"""Research only: diagnose original #475 common scoped-grammar proof failure."""
from __future__ import annotations
import json
from pathlib import Path
from types import MethodType
from scripts.diagnose_novel_parses import select_cases
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser
from seman_parser.structural_preanalysis import analyze_paragraph
DATA=Path(__file__).resolve().parents[1]/"data"
def main():
    parser=Parser.from_dir(DATA,cache_size=0)
    composer=parser._quoted_sentence_composer
    original=composer._compose_verified_dialogue_pattern
    def inspect(self,parser,text,lattice,specs,expected_rule,**kwargs):
        if expected_rule!="dialogue_structural_comparative_negative_tag_sequence":
            return original(parser,text,lattice,specs,expected_rule,**kwargs)
        print("TRACE_475_ENTER",len(specs),flush=True)
        phrases=sum(kind=="phrase" for _,_,_,kind,_ in specs)
        for cat,a,b,kind,req in specs:
            candidates=[]
            if kind=="lexical":
                for c in lattice.candidates:
                    if c.category==cat and (c.span_start,c.span_end)==(a,b):
                        f=c.features.as_dict()
                        ok=all(
                            v in (f.get("subcat",()) if isinstance(f.get("subcat"),(tuple,list)) else (f.get("subcat"),))
                            if k=="subcat_member" else f.get(k)==v
                            for k,v in req.items())
                        candidates.append({"ok":ok,"score":c.score,"features":f})
            elif kind=="phrase":
                grammar=parser._vector_grammar
                part=text[a:b]
                limit=(kwargs.get("max_items") or 50_000)//(phrases+1)
                work=(kwargs.get("kbest_work_limit") or 500_000)//(phrases+1)
                if cat=="CLAUSE":
                    res=parser._parse_vector_text(part,max_items=limit,kbest_work_limit=work)
                else:
                    res=grammar.parse_lattice(parser._lattice_for_text(part),
                          goal_category=cat,max_items=limit,
                          kbest_work_limit=work,beam=parser.beam)
                node=res.best()
                candidates=[{"completed":res.completed,"rule":node.rule_id if node else None,
                             "features":node.features.as_dict() if node else None,
                             "budget":res.stats.get("budget_exceeded")}]
            print("TRACE_475_PART",json.dumps({"cat":cat,"span":text[a:b],"kind":kind,
                    "needed":req,"evidence":candidates[:6]}),flush=True)
        result=original(parser,text,lattice,specs,expected_rule,**kwargs)
        print("TRACE_475_COMPOSED",bool(result),flush=True)
        return result
    composer._compose_verified_dialogue_pattern=MethodType(inspect,composer)
    case=select_cases(500)[0][475]
    print("TRACE_475_SOURCE",case["source_text"],flush=True)
    print("TRACE_475_STRUCT",json.dumps(
        [x.to_dict() for x in analyze_paragraph(case["source_text"])[0].constituents]
        ),flush=True)
    prepared,_,res=parse_corpus_case(parser,case,max_items=50_000,
                                      kbest_work_limit=500_000)
    print("TRACE_475_RESULT",res.completed,res.stats.get("structural_composition_kind"),
          flush=True)
if __name__=="__main__":main()
