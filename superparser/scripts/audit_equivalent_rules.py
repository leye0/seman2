"""Inventory and ablate candidate duplicates without editing production data.

Compared productions agree after renaming rule-local variables. They must
also have the same typed interfaces, source scope and lowered semantics.
The inventory is a review queue, not permission to remove a rule id that
another construction needs.
"""
from __future__ import annotations
import argparse,json,signal
from collections import Counter,defaultdict
from pathlib import Path
from time import perf_counter
from seman_parser.engine import Parser,ParserResources
from seman_parser.grammar import Grammar, load_grammar
from seman_parser.semantic_rules import load_semantic_rules
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases,classify

ROOT=Path(__file__).resolve().parents[1]
class Deadline(Exception):pass
def alarm(_a,_b):raise Deadline()

def equivalent_groups(grammar, semantics):
    indexed = defaultdict(list)
    for order, rule in enumerate(grammar):
        variables = {}

        def normalized(symbol):
            raw = symbol.as_dict()
            for key, value in sorted(raw["features"].items()):
                if isinstance(value, str) and value.startswith("?"):
                    raw["features"][key] = variables.setdefault(value, f"?{len(variables)}")
            # Requirements are a conjunction, not another source of order.
            raw["requires"].sort()
            return raw

        signature = {
            "rhs": [normalized(s) for s in rule.rhs],
            "lhs": normalized(rule.lhs),
            "semantic": [a.as_dict() for a in semantics.get(rule.rule_id, ())],
            "scope": {key: rule.provenance.get(key)
                      for key in ("source_plan", "usage_deviation")},
        }
        indexed[json.dumps(signature, sort_keys=True)].append((order, rule))
    groups = []
    for equal in indexed.values():
        if len(equal) < 2:
            continue
        _, kept = min(equal, key=lambda row: (-row[1].score, row[0]))
        groups.append({"keep": kept.rule_id, "score": kept.score,
                       "remove": [r.rule_id for _, r in equal if r.rule_id != kept.rule_id]})
    return groups


def inventory():
    data = ROOT / "data"
    pairs = {
        "grammar": "semantic_rules", "dialogue_grammar": "dialogue_semantic_rules",
        "dialogue_structural_grammar": "dialogue_semantic_rules",
    }
    return {grammar: equivalent_groups(load_grammar(data / f"{grammar}.jsonl"),
                                       load_semantic_rules(data / f"{semantics}.jsonl"))
            for grammar, semantics in pairs.items()}


def canonicalize(resources):
    groups = equivalent_groups(resources.grammar, resources.semantic_rules())
    omit = {rule for group in groups for rule in group["remove"]}
    filtered=[r for r in resources.grammar if r.rule_id not in omit]
    assert len(filtered)==len(resources.grammar)-len(omit)
    return ParserResources(
        grammar=Grammar(filtered),lexicon=resources.lexicon,
        types=resources.types,metadata=resources.metadata,
    ),groups

def signature(root):
    if root is None:return None
    return (root.rule_id,root.category,root.start,root.end,
            tuple(signature(c) for c in root.children))

def parse(parser,case,seconds):
    signal.setitimer(signal.ITIMER_REAL,seconds)
    started=perf_counter()
    try:
        prepared,lattice,result=parse_corpus_case(
            parser,case,max_items=50000,kbest_work_limit=500000,
        )
        stats=result.stats
        data={
            "status":classify(result.completed,stats),
            "completed":result.completed,
            "tree":signature(result.best()),
            "root_rule":result.best().rule_id if result.best() else None,
            "partial_states":stats.get("partial_states",0),
            "forest_nodes":stats.get("forest_nodes",0),
            "derivations":stats.get("structural_derivations",0),
            "lexical_count":len(lattice.candidates),
            "forest_budget":bool(stats.get("budget_exceeded")),
            "dialogue_budget":bool(
                (stats.get("dialogue_attempt") or {}).get("budget_exceeded")),
        }
    except Deadline:
        data={"status":"timeout","completed":False}
    except Exception as exc:
        data={"status":"error","completed":False,"exception":repr(exc)}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
    data["wall_ms"]=round((perf_counter()-started)*1000,1)
    return data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--count",type=int,default=105)
    ap.add_argument("--seconds",type=float,default=10.0)
    opt=ap.parse_args()
    if opt.inventory_only:
        print(json.dumps(inventory(), ensure_ascii=False, indent=2))
        return
    if opt.wordnet_dir is None or opt.output is None:
        ap.error("paired ablation requires --wordnet-dir and --output")
    cases,_=select_cases(500)
    source=ParserResources.from_dir(ROOT/"data",wordnet_dict=opt.wordnet_dir)
    filtered,groups=canonicalize(source)
    base=Parser(source,cache_size=200,lexical_left_corner_pruning=True)
    candidate=Parser(filtered,cache_size=200,lexical_left_corner_pruning=True)
    candidate._lattice_cache=base._lattice_cache
    if opt.count==500:
        # The complete corpus must not accidentally inherit the step-5
        # witness-sampling selection. Fail closed if a future edit regresses.
        indices=list(range(500))
        assert len(indices)==500 and indices[-1]==499
    else:
        indices=sorted(set(list(range(0,500,5))[:opt.count]+[
            32,75,104,168,202,281,348,365,367,485,499
        ]))
    previous=signal.signal(signal.SIGALRM,alarm)
    rows=[]
    try:
        for index in indices:
            original=parse(base,cases[index],opt.seconds)
            changed=parse(candidate,cases[index],opt.seconds)
            if original.get("lexical_count") is not None and changed.get("lexical_count") is not None:
                assert original["lexical_count"]==changed["lexical_count"],index
            row={"index":index,"text":cases[index]["text"],
                 "baseline":original,"deduplicated":changed,
                 "tree_changed":original.get("tree")!=changed.get("tree")}
            rows.append(row)
            if row["tree_changed"] or original["status"]!=changed["status"]:
                print("RULE_DEDUP_CASE",json.dumps({
                    "index":index,"text":cases[index]["text"],
                    "baseline":{k:v for k,v in original.items() if k!="tree"},
                    "deduplicated":{k:v for k,v in changed.items() if k!="tree"},
                },ensure_ascii=False),flush=True)
            if len(rows)%25==0:
                print("RULE_DEDUP_PROGRESS",len(rows),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    summary={
        "count":len(rows),"groups":groups,
        "eliminated_rules":sum(len(g["remove"]) for g in groups),
        "baseline":dict(Counter(x["baseline"]["status"] for x in rows)),
        "deduplicated":dict(Counter(x["deduplicated"]["status"] for x in rows)),
        "lost":[x["index"] for x in rows if x["baseline"]["status"]=="complete"
                and x["deduplicated"]["status"]!="complete"],
        "recovered":[x["index"] for x in rows if x["baseline"]["status"]!="complete"
                    and x["deduplicated"]["status"]=="complete"],
        "tree_changed":[x["index"] for x in rows if x["tree_changed"]],
        "baseline_partial_states":sum(x["baseline"].get("partial_states") or 0 for x in rows),
        "trial_partial_states":sum(x["deduplicated"].get("partial_states") or 0 for x in rows),
        "baseline_forest_nodes":sum(x["baseline"].get("forest_nodes") or 0 for x in rows),
        "trial_forest_nodes":sum(x["deduplicated"].get("forest_nodes") or 0 for x in rows),
        "production_grammar_untouched":True,
    }
    opt.output.parent.mkdir(parents=True,exist_ok=True)
    opt.output.write_text(json.dumps({"summary":summary,"rows":rows},
                                  ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("RULE_DEDUP_SUMMARY",json.dumps(summary),flush=True)
    if any(r["deduplicated"]["status"]=="error" for r in rows):
        raise AssertionError("Parser exception in filtered rules")

if __name__=="__main__":main()
