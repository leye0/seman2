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
    args=p.parse_args()
    text=args.text if args.text is not None else sys.stdin.read().rstrip("\r\n")
    with Parser(args.grammar,executable=args.ace) as parser:
        result=parser.parse_paragraph(text,parse_components=not args.whole_only)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
