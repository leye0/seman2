"""Explore general adjective + infinitival complements and stacked degree.

Production grammar is never edited. All tests call Parser.parse. This
exploration explicitly tracks overgeneration: an analysis that parses an
odd adjective+infinitive is not evidence of valid lexical valence.
"""
from __future__ import annotations
import argparse,json,signal
from pathlib import Path
from time import perf_counter
from seman_parser.engine import Parser,ParserResources
from seman_parser.grammar import Grammar,parse_rule
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases,classify

ROOT=Path(__file__).resolve().parents[1]
COHORT_INDICES=(8,32,58,64,75,94,95,104,115,159,168,182,194,196,
               203,209,221,223,227,244,248,281,312,349,365,367,427,
               438,449,473,480,485,496,499)
CONTRASTS=(
    ("We are eager.",True),
    ("We are less eager.",True),
    ("We are scarcely less eager.",True),
    ("We are eager to meet her again.",True),
    ("We are less eager to meet her again.",True),
    ("We are scarcely less eager to meet her again.",True),
    ("And, to confess the truth, we are scarcely less eager to meet her again.",True),
    ("To confess the truth, we are scarcely less eager to meet her again.",True),
    ("Mary is ready to leave.",True),
    ("John was anxious to help Mary.",True),
    ("The dog is quick to chase cats.",True),
    ("She was very eager to help him.",True),
    ("The box is blue to sleep.",False),
    ("The wall is green to believe.",False),
    ("John was wooden to sing.",False),
)
class Deadline(Exception):pass
def _alarm(_s,_f):raise Deadline()

def candidate_resources(resources):
    score_inf=resources.grammar.by_id("adjp_adjective_pp_infinitive").score
    score_degree=resources.grammar.by_id("adjp_degree_clausal").score
    score_link=resources.grammar.by_id("coord_clause").score
    rows=(
        {"id":"research_adjp_adjective_infinitival_complement",
         "rhs":[
            {"category":"ADJ","exports":{"referent":"property"}},
            {"category":"TO"},
            {"category":"VP-NP","exports":{"event":"infinitival_complement"}}],
         "lhs":{"category":"ADJP","features":{"clausal_complement":"true"}},
         "score":score_inf,
         "provenance":{"hypothesis":"adjective selects bare-infinitival argument",
                      "safety":"not production; lacks positive adjective valence evidence"}},
        {"id":"research_adjp_adverb_degree_phrase",
         "rhs":[{"category":"ADV"},{"category":"DEGREE"},
                {"category":"ADJP","exports":{"referent":"graded_property"}}],
         "lhs":{"category":"ADJP"},
         "score":score_degree,
         "provenance":{"hypothesis":"adverb modifies scalar degree phrase",
                      "safety":"must audit lexical degree modifiers"}},
        {"id":"research_discourse_coordinator_to_inf_incise",
         "rhs":[
            {"category":"COORD","features":{"nominal_coordination":"true"},
             "requires":["nominal_coordination"]},
            {"category":"COMMA"},{"category":"TO"},
            {"category":"VP-NP","exports":{"event":"parenthetical"}},
            {"category":"COMMA"},{"category":"CLAUSE","exports":{"event":"main"}}],
         "lhs":{"category":"CLAUSE","features":{"delimited_incise":"true"}},
         "score":score_link,
         "provenance":{"hypothesis":"discourse coordinator plus infinitival parenthetical",
                      "safety":"matrix must be independently a complete clause"}},
    )
    candidate=Grammar([*resources.grammar,*map(parse_rule,rows)])
    return ParserResources(grammar=candidate,lexicon=resources.lexicon,
                           types=resources.types,metadata=resources.metadata)

def tree(node,text):
    if node is None:return None
    return {
        "rule":node.rule_id,"category":node.category,
        "text":text[node.start:node.end],
        "children":[tree(c,text) for c in node.children],
    }

def parse(parser,text,seconds,case=None):
    before=perf_counter()
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        if case is None:
            report=parser.parse(text,max_items=50000)
            lattice,result=report.lattice,report.result
        else:
            _,lattice,result=parse_corpus_case(
                parser,case,max_items=50000,kbest_work_limit=500000)
        stats=result.stats
        row={
            "completed":result.completed,"status":classify(result.completed,stats),
            "best":tree(result.best(),lattice.text),
            "lexical_candidates":len(lattice.candidates),
            "budget":bool(stats.get("budget_exceeded")),
            "dialogue_budget":bool(
                (stats.get("dialogue_attempt") or {}).get("budget_exceeded")),
        }
    except Deadline:
        row={"completed":False,"status":"timeout"}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    row["ms"]=round((perf_counter()-before)*1000,2)
    return row

def used(node,rule_id):
    return bool(node and (node["rule"]==rule_id
             or any(used(c,rule_id) for c in node["children"])))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--seconds",type=float,default=10)
    opts=ap.parse_args()
    source=ParserResources.from_dir(ROOT/"data",wordnet_dict=opts.wordnet_dir)
    baseline=Parser(source,cache_size=256,lexical_left_corner_pruning=True)
    candidate=Parser(candidate_resources(source),cache_size=256,
                     lexical_left_corner_pruning=True)
    candidate._lattice_cache=baseline._lattice_cache
    cohort,_=select_cases(500)
    old=signal.signal(signal.SIGALRM,_alarm)
    examples=[]
    rows=[]
    try:
        for text,expect in CONTRASTS:
            a=parse(baseline,text,opts.seconds)
            b=parse(candidate,text,opts.seconds)
            examples.append({"text":text,"expected_plausible":expect,
                             "base":a,"trial":b})
            print("ADJECTIVE_INF_CONTRAST",json.dumps({
                "text":text,"expected_plausible":expect,
                "old":a["status"],"trial":b["status"],
                "new_rule":used(b.get("best"),"research_adjp_adjective_infinitival_complement"),
                "degree_rule":used(b.get("best"),"research_adjp_adverb_degree_phrase"),
            },ensure_ascii=False),flush=True)
        for index in COHORT_INDICES:
            sentence=cohort[index]
            a=parse(baseline,sentence["text"],opts.seconds,sentence)
            b=parse(candidate,sentence["text"],opts.seconds,sentence)
            if a.get("lexical_candidates") is not None and b.get("lexical_candidates") is not None:
                assert a["lexical_candidates"]==b["lexical_candidates"],index
            rows.append({"index":index,"sentence":sentence["text"],
                         "base":a,"trial":b})
            if a["status"]!=b["status"] or a.get("best")!=b.get("best"):
                print("ADJECTIVE_INF_CASE",json.dumps({
                    "index":index,"old":a["status"],"new":b["status"],
                    "new_root":b.get("best",{}).get("rule") if b.get("best") else None,
                    "changed_tree":a.get("best")!=b.get("best"),
                },ensure_ascii=False),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,old)
    summary={
        "contrast_count":len(examples),"cohort_cases":len(rows),
        "recovered":[r["index"] for r in rows if
                     not r["base"]["completed"] and r["trial"]["completed"]],
        "lost":[r["index"] for r in rows if
                r["base"]["completed"] and not r["trial"]["completed"]],
        "changed":[r["index"] for r in rows if
                   r["base"].get("best")!=r["trial"].get("best")],
        "potential_negative_overgeneration":[r["text"] for r in examples if
            not r["expected_plausible"] and
            not r["base"]["completed"] and r["trial"]["completed"]],
        # A false tree that was ALREADY accepted by the baseline remains a
        # problem even when both variants report completed=True.
        "negative_controls_with_baseline_tough_tree":[
            r["text"] for r in examples if
            not r["expected_plausible"] and
            used(r["base"].get("best"),"vp_tough")
        ],
        "positive_controls_with_baseline_tough_tree":[
            r["text"] for r in examples if
            r["expected_plausible"] and
            used(r["base"].get("best"),"vp_tough")
        ],
        "production_grammar_untouched":True,
    }
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps({"summary":summary,
                                      "contrasts":examples,"cohort":rows},
                                 ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ADJECTIVE_INF_SUMMARY",json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
