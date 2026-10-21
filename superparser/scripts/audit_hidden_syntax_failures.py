"""Research-only actual tree audit for newly surfaced grammar failures.

All examples are parsed by public Parser.parse with unmodified resources;
captures selected and alternate trees, constituent spans, lexical categories.
"""
from __future__ import annotations
import json,os
from pathlib import Path
from seman_parser import Parser

DATA=Path(__file__).resolve().parents[1]/"data"
EXAMPLES=[
    "For I longed to see my friends.",
    "For the weather was cold.",
    "For my part, I waited.",
    "For the captain, he waited.",
    "They built a sample sign with a large picture, a short name, and a smaller paragraph explaining the route.",
    "Captain Nemo arrived.",
    "Doctor Watson waited.",
    "Professor Moriarty spoke.",
    "Lady Catherine smiled.",
    "Lovely Dora smiled.",
    "River Mary smiled.",
    "Carpet Dora spoke.",
]
def tree(n,text):
    return {"category":n.category,"rule":n.rule_id,
            "text":text[n.start:n.end],
            "features":n.features.as_dict(),
            "children":[tree(c,text) for c in n.children]}
def main():
    p=Parser.from_dir(DATA,cache_size=16)
    out=[]
    for text in EXAMPLES:
        report=p.parse(text,max_items=50000)
        result=report.result
        forest=result.shared_forest
        entries=[]
        for root in result.alternatives(limit=12):
            entries.append(tree(root,text))
        candidates={}
        for c in report.lattice.candidates:
            if c.category in {"TITLE","PROPER-NOUN","COORD","PREP","NP","N"}:
                key=text[c.span_start:c.span_end]
                candidates.setdefault(key,[]).append({
                    "category":c.category,"features":c.features.as_dict(),
                    "score":c.score,"lemma":c.lemma,
                })
        item={"text":text,"completed":result.completed,
              "stats":result.stats,"best":entries[0] if entries else None,
              "alternatives":entries,"lexical":candidates}
        out.append(item)
        print("HIDDEN_SYNTAX_CASE",json.dumps({
            "text":text,"completed":item["completed"],
            "root":entries[0]["rule"] if entries else None,
            "n_alternatives":len(entries),
            "first_children":[{
                "rule":c["rule"],"cat":c["category"],"text":c["text"]}
                for c in entries[0]["children"]] if entries else [],
        },ensure_ascii=False),flush=True)
    path=Path(os.environ.get("RUNNER_TEMP","."))/"hidden-syntax-trees.json"
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
if __name__=="__main__":
    main()
