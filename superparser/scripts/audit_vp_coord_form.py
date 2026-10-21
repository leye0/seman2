"""Paired structural trial: compatible verbal form across VP coordination.

A research-only grammar alteration. Both variants use public Parser.parse
and identical lexical lattices; production grammar and scores unchanged.
"""
from __future__ import annotations
import argparse,json,signal
from collections import Counter
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify,select_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.grammar import Grammar
from seman_parser.features import FeatureStructure

ROOT=Path(__file__).resolve().parents[1]
TARGETS=frozenset({
    "vp_coord","vp_comma_coord","vp_comma_list","vp_list3",
})

class Deadline(Exception):pass
def alarm(_s,_f):raise Deadline()

def constrained(resources):
    rules=[]
    changed=[]
    for rule in resources.grammar:
        if rule.rule_id in TARGETS:
            vp_indices=[i for i,s in enumerate(rule.rhs)
                        if s.category=="VP"]
            assert len(vp_indices)>=2,rule.rule_id
            assert "vform" not in rule.lhs.features.as_dict(),rule.rule_id
            rhs=list(rule.rhs)
            variable="?coord_form_"+rule.rule_id
            for index in vp_indices:
                s=rhs[index]
                assert "vform" not in s.features.as_dict(),rule.rule_id
                # Missing evidence is not treated as a conflicting value.
                # A concrete child form unifies with the shared variable.
                rhs[index]=replace(s,features=FeatureStructure.build({
                    **s.features.as_dict(),"vform":variable,
                }))
            rule=replace(rule,
                rhs=tuple(rhs),
                lhs=replace(rule.lhs,
                    features=FeatureStructure.build({
                        **rule.lhs.features.as_dict(),"vform":variable,
                    })),
            )
            changed.append(rule.rule_id)
        rules.append(rule)
    assert set(changed)==TARGETS,changed
    return ParserResources(
        grammar=Grammar(rules),lexicon=resources.lexicon,
        types=resources.types,metadata=resources.metadata,
    )

def signature(node):
    if node is None:return None
    return (
        node.rule_id,node.category,node.start,node.end,
        tuple(signature(c) for c in node.children),
    )

def signals(node,text):
    if node is None:return []
    result=[]
    def visit(n):
        if n.rule_id in TARGETS:
            vps=[x for x in n.children if x.category=="VP"]
            forms=[x.features.as_dict().get("vform") for x in vps]
            known=[x for x in forms if x is not None and not
                   (isinstance(x,str) and x.startswith("?"))]
            result.append({
                "rule":n.rule_id,"span":[n.start,n.end],
                "text":text[n.start:n.end],
                "forms":forms,"concrete_mismatch":len(set(known))>1,
                "child_rules":[x.rule_id for x in vps],
            })
        for c in n.children:visit(c)
    visit(node)
    return result

def run(parser,case,seconds):
    signal.setitimer(signal.ITIMER_REAL,seconds)
    t=perf_counter()
    try:
        prepared,lattice,parsed=parse_corpus_case(
            parser,case,max_items=50000,kbest_work_limit=500000,
        )
        stats=parsed.stats
        best=parsed.best()
        row={
            "status":classify(parsed.completed,stats),
            "completed":parsed.completed,
            "root_rule":best.rule_id if best else None,
            "tree":signature(best),
            "coordination":signals(best,lattice.text),
            "lexical_count":len(lattice.candidates),
            "forest_budget":bool(stats.get("budget_exceeded")),
            "dialogue_budget":bool((stats.get("dialogue_attempt") or {})
                                   .get("budget_exceeded")),
            "partial_states":stats.get("partial_states"),
        }
    except Deadline:
        row={"status":"timeout","completed":False}
    except Exception as err:
        row={"status":"error","completed":False,"error":repr(err)}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    row["elapsed_ms"]=round((perf_counter()-t)*1000,1)
    return row

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--count",type=int,default=500)
    ap.add_argument("--seconds",type=float,default=10.0)
    opts=ap.parse_args()
    source=ParserResources.from_dir(ROOT/"data",wordnet_dict=opts.wordnet_dir)
    base=Parser(source,cache_size=512,lexical_left_corner_pruning=True)
    changed=Parser(constrained(source),cache_size=512,
                   lexical_left_corner_pruning=True)
    changed._lattice_cache=base._lattice_cache
    cases,_=select_cases(500)
    original_handler=signal.signal(signal.SIGALRM,alarm)
    rows=[]
    try:
        for index,case in enumerate(cases[:opts.count]):
            original=run(base,case,opts.seconds)
            trial=run(changed,case,opts.seconds)
            if original.get("lexical_count") is not None and trial.get(
                "lexical_count") is not None:
                assert original["lexical_count"]==trial["lexical_count"],index
            row={"index":index,"book_id":case["book_id"],
                 "sentence":case["text"],"original":original,
                 "constrained":trial,
                 "changed_tree":original.get("tree")!=trial.get("tree")}
            rows.append(row)
            if (row["changed_tree"] or original["status"]!=trial["status"]
                    or index in (281,365,485)):
                print("VP_COORD_FORM_CASE",json.dumps({
                    "index":index,"text":case["text"],
                    "original":{k:v for k,v in original.items() if k!="tree"},
                    "constrained":{k:v for k,v in trial.items() if k!="tree"},
                    "changed_tree":row["changed_tree"],
                },ensure_ascii=False),flush=True)
            if index%50==49:
                print("VP_COORD_FORM_PROGRESS",index+1,flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,original_handler)
    count=lambda key:dict(Counter(r[key]["status"] for r in rows))
    summary={
        "count":len(rows),
        "baseline":count("original"),
        "trial":count("constrained"),
        "recovered":[r["index"] for r in rows if
            r["original"]["status"]!="complete"
            and r["constrained"]["status"]=="complete"],
        "lost":[r["index"] for r in rows if
            r["original"]["status"]=="complete"
            and r["constrained"]["status"]!="complete"],
        "changed_best_tree":[r["index"] for r in rows if r["changed_tree"]],
        "baseline_mixed_vform_tree_indices":[r["index"] for r in rows
          if any(c["concrete_mismatch"] for c in r["original"].get(
              "coordination",()))],
        "trial_mixed_vform_tree_indices":[r["index"] for r in rows
          if any(c["concrete_mismatch"] for c in r["constrained"].get(
              "coordination",()))],
        "production_grammar_untouched":True,
    }
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(
        json.dumps({"summary":summary,"rows":rows},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf8",
    )
    print("VP_COORD_FORM_SUMMARY",json.dumps(summary),flush=True)
    if any(r["constrained"]["status"]=="error" for r in rows):
        raise AssertionError("Parser exceptions in trial")

if __name__=="__main__":
    main()
