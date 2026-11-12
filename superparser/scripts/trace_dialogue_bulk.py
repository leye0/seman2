"""Print bounded source-pattern proof blockers for current dialogue batch."""
from __future__ import annotations
from types import MethodType
from scripts.diagnose_novel_parses import select_cases
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser
from pathlib import Path

def main():
    p=Parser.from_dir(Path(__file__).resolve().parents[1]/"data",cache_size=0)
    composer=p._quoted_sentence_composer
    original=composer._compose_verified_dialogue_pattern
    invoked=[]
    def traced(self,parser,text,lattice,specs,expected_rule,**kwargs):
        invoked.append(expected_rule)
        print("BULK_TRACE_RULE",expected_rule,flush=True)
        for category,a,b,kind,needed in specs:
            surface=text[a:b]
            if kind=="lexical":
                opts=[c for c in lattice.candidates
                      if c.category==category
                      and (c.span_start,c.span_end)==(a,b)]
                valid=[c for c in opts if all(c.features.as_dict().get(k)==v
                                          for k,v in needed.items())]
                print("BULK_TRACE_LEX",category,repr(surface),"valid",len(valid),
                      "seen",[(c.features.as_dict(),c.score) for c in opts][:2],
                      flush=True)
            elif kind=="phrase":
                grammar=(parser._dialogue_vector_grammar
                         if category=="SPEECH-TAG" else parser._vector_grammar)
                try:
                    pr=grammar.parse_lattice(
                        parser._lattice_for_text(surface),
                        goal_category=category,beam=parser.beam,
                        max_items=9000,kbest_work_limit=90000)
                    best=pr.best()
                    print("BULK_TRACE_PHRASE",category,repr(surface),
                          "completed",pr.completed,
                          "rule",best.rule_id if best else None,
                          "features",best.features.as_dict() if best else None,
                          flush=True)
                except Exception as e:
                    print("BULK_TRACE_PHRASE_ERROR",type(e).__name__,str(e),flush=True)
        result=original(parser,text,lattice,specs,expected_rule,**kwargs)
        print("BULK_TRACE_ASSEMBLY",expected_rule,bool(result),flush=True)
        return result
    composer._compose_verified_dialogue_pattern=MethodType(traced,composer)
    cases,_=select_cases(500)
    for i in [157,200,445]:
        print("BULK_TRACE_CASE",i,cases[i]["source_text"],flush=True)
        prepared,lattice,result=parse_corpus_case(
            p,cases[i],max_items=50000,kbest_work_limit=500000)
        print("BULK_TRACE_RESULT",i,result.completed,
              result.best().rule_id if result.best() else None,
              "invocations",list(invoked),flush=True)

if __name__=="__main__":main()
