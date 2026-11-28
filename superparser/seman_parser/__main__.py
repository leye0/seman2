"""Analyze a single source paragraph, with native MRS and exact dialogue spans."""
import argparse
import json
import sys
from .engine import Parser

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ace",default="ace")
    p.add_argument("--grammar",required=True)
    p.add_argument("--text",help="One paragraph; otherwise read stdin")
    p.add_argument("--whole-only",action="store_true")
    p.add_argument("--knowledge",action="store_true",help="Attach independent local lexical, POS and NER observations")
    p.add_argument("--wiktionary-word",action="append",default=[],help="Explicit online Wiktionary lookup; repeat for more words")
    p.add_argument("--wsd",action="store_true",help="Run upstream contextual WSD on content-word tokens (requires local knowledge and WSD dependencies)")
    p.add_argument('--srl',action='store_true',help='Attach independent neural semantic role labels')
    args=p.parse_args()
    text=args.text if args.text is not None else sys.stdin.read().rstrip("\r\n")
    with Parser(args.grammar,executable=args.ace) as parser:
        result=parser.parse_paragraph(text,parse_components=not args.whole_only)
    if args.knowledge or args.wsd:
        from .knowledge import Knowledge
        result["external_knowledge"]=Knowledge().inspect(text)
    if args.wsd:
        from .wsd import WSD
        result["wsd"]=WSD().inspect(text,result["external_knowledge"]["tokens"])
    if args.srl:
        from .srl import SRL
        result['srl']=SRL().inspect(text)
    if args.wiktionary_word:
        from .knowledge import Wiktionary
        wiki=Wiktionary()
        result["wiktionary"]=[wiki.lookup(w) for w in args.wiktionary_word]
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
