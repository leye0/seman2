"""Paired research into discourse coordinator + parenthetical + full clause.

Use only public Parser.parse, identical lexical hypotheses and corpus input.
A previous failure was counted as full-clause coverage only if it produces
a complete validated root; no fragment-specific rules are introduced.
"""
from __future__ import annotations
import argparse,json,signal
from pathlib import Path
from dataclasses import replace
from time import perf_counter
from seman_parser.engine import Parser,ParserResources
from seman_parser.grammar import Grammar,parse_rule
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify,select_cases

ROOT=Path(__file__).resolve().parents[1]
CASES=(8,76,80,94,96,100,105,107,112,115,116,167,182,194,196,
       209,213,220,226,232,237,244,281,312,340,349,356,365,367,
       423,427,438,439,473,480,485,487,493,497)

class Deadline(Exception): pass
def _alarm(_s,_f):raise Deadline()

def candidate_resources(resources):
    score=resources.grammar.by_id("coord_clause").score
    # These are non-lexical constructions; coordination is licensed by the
    # pre-existing positive phrase-coordination feature. The complement
    # must be a fully recognized CLAUSE, not any NP or elliptical fragment.
    prefix=[{"category":"COORD",
             "features":{"nominal_coordination":"true"},
             "requires":["nominal_coordination"],
             "exports":{"referent":"discourse_link"}},
            {"category":"COMMA"}]
    suffix=[{"category":"COMMA"},
            {"category":"CLAUSE","exports":{"event":"main"}}]
    variants=(
        ("clause_discourse_coordinator_adv_incise",
         [{"category":"ADV","exports":{"referent":"parenthetical"}}]),
        ("clause_discourse_coordinator_to_inf_incise",
         [{"category":"TO"},{"category":"VP-NP","exports":{"event":"parenthetical"}}]),
    )
    new=[]
    for rule_id,middle in variants:
        new.append(parse_rule({
            "id":rule_id,
            "rhs":prefix+middle+suffix,
            "lhs":{"category":"CLAUSE"},
            "score":score,
            "provenance":{
                "construction":"sentence_initial_discourse_coordinator_with_delimited_adjunct",
                "evidence":"and, besides, it was... / and, to confess the truth, we are...",
                "restriction":"overt clause after a delimited adverbial or base infinitival adjunct",
            },
        }))
    return ParserResources(
        grammar=Grammar([*resources.grammar,*new]),
        lexicon=resources.lexicon,types=resources.types,
        metadata=resources.metadata,
    )

def tree(item,text):
    if item is None:return None
    return {"rule":item.rule_id,"category":item.category,
            "text":text[item.start:item.end],"score":item.score,
            "children":[tree(c,text) for c in item.children]}

def parse(parser,case,seconds):
    started=perf_counter()
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        prepared,lattice,result=parse_corpus_case(
            parser,case,max_items=50000,kbest_work_limit=500000,
        )
        stats=result.stats
        best=result.best()
        row={
            "status":classify(result.completed,stats),
            "completed":result.completed,
            "root_rule":best.rule_id if best else None,
            "tree":tree(best,lattice.text),
            "lexical_candidates":len(lattice.candidates),
            "forest_budget":bool(stats.get("budget_exceeded")),
            "dialogue_budget":bool((stats.get("dialogue_attempt") or {})
                                   .get("budget_exceeded")),
        }
    except Deadline:
        row={"status":"timeout","completed":False}
    except Exception as exc:
        row={"status":"error","completed":False,"error":repr(exc)}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    row["ms"]=round(1000*(perf_counter()-started),2)
    return row

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--seconds",type=float,default=9)
    p.add_argument("--count",type=int,choices=(39,500),default=39)
    options=p.parse_args()
    cases,_=select_cases(500)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=options.wordnet_dir)
    baseline=Parser(resources,cache_size=128,lexical_left_corner_pruning=True)
    trial=Parser(candidate_resources(resources),cache_size=128,
                 lexical_left_corner_pruning=True)
    trial._lattice_cache=baseline._lattice_cache
    original=signal.signal(signal.SIGALRM,_alarm)
    data=[]
    try:
        probes=(
            "We are scarcely less eager to meet her again.",
            "To confess the truth, we are scarcely less eager to meet her again.",
            "and, to confess the truth, we are scarcely less eager to meet her again.",
            "I confessed the truth.",
            "I confess the truth.",
            "and, besides, it was such a pity that Lydia should be taken.",
        )
        for text in probes:
            report=baseline.parse(text,max_items=50000)
            result=report.result
            lexical={
                token:[{"cat":candidate.category,"features":candidate.features.as_dict()}
                       for candidate in report.lattice.candidates
                       if candidate.surface.casefold()==token]
                for token in ("confess","confessed","eager","besides")
            }
            print("DISCOURSE_COMPONENT_PROBE",json.dumps({
                "sentence":text,"completed":result.completed,
                "best":result.best().rule_id if result.best() else None,
                "status":classify(result.completed,result.stats),
                "lexical":lexical,
            },ensure_ascii=False),flush=True)
        indices=range(500) if options.count==500 else CASES
        for index in indices:
            a=parse(baseline,cases[index],options.seconds)
            b=parse(trial,cases[index],options.seconds)
            if a.get("lexical_candidates") is not None and b.get("lexical_candidates") is not None:
                assert a["lexical_candidates"]==b["lexical_candidates"],index
            row={"index":index,"text":cases[index]["text"],"baseline":a,"trial":b}
            data.append(row)
            if (a["status"]!=b["status"]
                    or a.get("tree")!=b.get("tree")
                    or index in (8,94,196,244,427)):
                print("DISCOURSE_INCISE_CASE",json.dumps({
                    "index":index,"baseline_status":a["status"],
                    "trial_status":b["status"],
                    "trial_rule":b.get("root_rule"),
                    "changed_tree":a.get("tree")!=b.get("tree"),
                }),flush=True)
            if len(data)%50==0:
                print("DISCOURSE_INCISE_PROGRESS",len(data),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,original)
    summary={
        "cases":len(data),
        "baseline_complete":sum(x["baseline"]["completed"] for x in data),
        "trial_complete":sum(x["trial"]["completed"] for x in data),
        "recovered":[x["index"] for x in data if
                     not x["baseline"]["completed"] and x["trial"]["completed"]],
        "lost":[x["index"] for x in data if
                x["baseline"]["completed"] and not x["trial"]["completed"]],
        "changed_trees":[x["index"] for x in data if
                         x["baseline"].get("tree")!=x["trial"].get("tree")],
        "production_grammar_untouched":True,
        "fixed_full_500":options.count==500,
    }
    options.output.parent.mkdir(parents=True,exist_ok=True)
    options.output.write_text(json.dumps({"summary":summary,"cases":data},
                                    ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("DISCOURSE_INCISE_SUMMARY",json.dumps(summary),flush=True)
    if any(x["trial"]["status"]=="error" for x in data):
        raise AssertionError("Research parser errors")

if __name__=="__main__":main()
