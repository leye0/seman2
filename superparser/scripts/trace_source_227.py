"""Research-only trace of source-faithful #227 passive-dash proof at public budgets."""
from __future__ import annotations
from pathlib import Path
from types import MethodType
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser

def main() -> None:
    parser=Parser.from_dir(Path(__file__).resolve().parents[1]/"data",cache_size=0)
    composer=parser._quoted_sentence_composer
    original=composer._compose_verified_dialogue_pattern
    def traced(self,parser,text,lattice,specs,expected_rule,**kwargs):
        if expected_rule!="structural_source_asyndetic_modal_passive_dash":
            return original(parser,text,lattice,specs,expected_rule,**kwargs)
        n=sum(x[3]=="phrase" for x in specs)
        items=kwargs.get("max_items") or parser.max_items
        work=kwargs.get("kbest_work_limit") or 500_000
        print("DASH_TRACE_PIECES",n,"alloc",items//(n+1),work//(n+1),flush=True)
        for cat,a,b,kind,needed in specs:
            fragment=text[a:b]
            if kind=="lexical":
                matches=[c for c in lattice.candidates if
                         c.category==cat and (c.span_start,c.span_end)==(a,b)]
                print("DASH_TRACE_LEX",cat,repr(fragment),needed,
                      [c.features.as_dict() for c in matches][:8],flush=True)
            elif kind=="phrase":
                g=(parser._dialogue_vector_grammar
                   if cat=="SPEECH-TAG" else parser._vector_grammar)
                try:
                    if cat=="CLAUSE":
                        result=parser._parse_vector_text(fragment,
                              max_items=items//(n+1),
                              kbest_work_limit=work//(n+1))
                    else:
                        result=g.parse_lattice(parser._lattice_for_text(fragment),
                          goal_category=cat,max_items=items//(n+1),
                          kbest_work_limit=work//(n+1),beam=parser.beam)
                    b1=result.best()
                    print("DASH_TRACE_PHRASE",cat,repr(fragment),
                          result.completed,b1.rule_id if b1 else None,
                          b1.features.as_dict() if b1 else None,
                          result.stats.get("budget_exceeded"),flush=True)
                except Exception as e:
                    print("DASH_TRACE_PHRASE_ERROR",repr(e),flush=True)
        result=original(parser,text,lattice,specs,expected_rule,**kwargs)
        print("DASH_TRACE_ASSEMBLY",bool(result),flush=True)
        return result
    composer._compose_verified_dialogue_pattern=MethodType(traced,composer)
    case=select_cases(500)[0][227]
    print("DASH_TRACE_SOURCE",case["source_text"],flush=True)
    prepared,_,result=parse_corpus_case(
        parser,case,max_items=50_000,kbest_work_limit=500_000)
    print("DASH_TRACE_RESULT",result.completed,
          result.best().rule_id if result.best() else None,flush=True)

if __name__=="__main__":
    main()
