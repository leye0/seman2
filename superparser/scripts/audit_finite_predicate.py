"""Paired research: require *overtly evidenced* finite VP in ordinary NP+VP CLAUSE.

All processing goes through Parser.parse. The declarative production grammar
is unchanged; research ParserResources carries one strictly checked variant.
The full fixed corpus is used to detect coverage and selected-tree regressions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import signal
from time import perf_counter

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import classify, select_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar

ROOT = Path(__file__).resolve().parents[1]
CASES_OF_INTEREST = {64, 90, 95, 104, 108, 173, 191, 203, 223, 227,
                     243, 248, 353, 362, 367, 447, 478, 485, 496, 499}


class Deadline(Exception):
    pass


def _alarm(_sig, _frame):
    raise Deadline()


def finite_variant(
    original: ParserResources, *, propagate_head_vform: bool = False,
) -> ParserResources:
    rules = []
    revised = False
    propagated = set()
    for rule in original.grammar:
        # VP modifiers, recursively coordinated predicates and adverbial
        # extensions inherit the morphological form of their VP head.
        # Their old LHS often discarded this information entirely. A paired
        # trial must propagate it rather than claiming nonfinite grammar.
        if (propagate_head_vform and rule.lhs.category == "VP"
                and "vform" not in rule.lhs.features.as_dict()):
            head_indices = [
                i for i, sym in enumerate(rule.rhs) if sym.category == "VP"
            ]
            if head_indices:
                variable = "?head_vform_" + rule.rule_id
                rhs = list(rule.rhs)
                for idx in head_indices:
                    sym = rhs[idx]
                    rhs[idx] = replace(
                        sym,
                        features=FeatureStructure.build({
                            **sym.features.as_dict(), "vform": variable,
                        }),
                        requires=tuple(dict.fromkeys((*sym.requires, "vform"))),
                    )
                rule = replace(
                    rule, rhs=tuple(rhs),
                    lhs=replace(rule.lhs,
                        features=FeatureStructure.build({
                            **rule.lhs.features.as_dict(), "vform": variable,
                        })),
                )
                propagated.add(rule.rule_id)
        if rule.rule_id == "clause_np_vp":
            assert [s.category for s in rule.rhs] == ["NP", "VP"]
            predicate = rule.rhs[1]
            assert "vform" not in predicate.features.as_dict()
            predicate = replace(
                predicate,
                features=FeatureStructure.build({
                    **predicate.features.as_dict(),
                    "vform": "finite",
                }),
                requires=(*predicate.requires, "vform"),
            )
            rule = replace(rule, rhs=(rule.rhs[0], predicate),
                           lhs=replace(
                               rule.lhs,
                               features=FeatureStructure.build({
                                   **rule.lhs.features.as_dict(),
                                   "vform": "finite",
                               }),
                           ))
            revised = True
        rules.append(rule)
    assert revised
    if propagate_head_vform:
        assert len(propagated) >= 10, propagated
        print("FINITE_PREDICATE_PROPAGATED_VP_RULES",
              json.dumps(sorted(propagated)), flush=True)
    return ParserResources(
        grammar=Grammar(rules),
        lexicon=original.lexicon,
        types=original.types,
        metadata=original.metadata,
    )


def _walk(node):
    if node is None:
        return
    yield node
    for c in node.children:
        yield from _walk(c)


def _signature(node):
    if node is None:
        return None
    return (
        node.rule_id, node.category, node.start, node.end,
        tuple(_signature(c) for c in node.children),
    )


def _parse(parser, case, timeout):
    signal.setitimer(signal.ITIMER_REAL, timeout)
    started = perf_counter()
    try:
        _input, lattice, result = parse_corpus_case(
            parser, case, max_items=50000, kbest_work_limit=500000,
        )
        stats = result.stats
        dialogue = stats.get("dialogue_attempt") or {}
        best = result.best()
        data = {
            "status": classify(result.completed, stats),
            "completed": result.completed,
            "rule": best.rule_id if best else None,
            "topical_subfront": [
                {
                    "conj": lattice.text[n.children[0].start:n.children[0].end],
                    "subordinate": {
                        "rule": n.children[1].rule_id,
                        "text": lattice.text[n.children[1].start:n.children[1].end],
                    },
                    "matrix": {
                        "rule": n.children[2].rule_id,
                        "text": lattice.text[n.children[2].start:n.children[2].end],
                    },
                }
                for n in _walk(best)
                if n.rule_id == "clause_sub_front" and len(n.children) == 3
            ],
            "tree_signature": _signature(best),
            "lexical_count": len(lattice.candidates),
            "partial_states": stats.get("partial_states"),
            "forest_budget": bool(stats.get("budget_exceeded")),
            "dialogue_budget": bool(dialogue.get("budget_exceeded")),
        }
    except Deadline:
        data = {"status": "timeout", "completed": False}
    except Exception as exc:
        data = {"status": "error", "completed": False, "exception": repr(exc)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    data["wall_ms"] = round((perf_counter() - started) * 1000, 3)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--propagate-head-vform", action="store_true")
    args = ap.parse_args()
    cases, _ = select_cases(500)
    resources = ParserResources.from_dir(
        ROOT / "data", wordnet_dict=args.wordnet_dir,
    )
    original = Parser(
        resources, cache_size=512,
        lexical_left_corner_pruning=True,
    )
    restricted = Parser(
        finite_variant(resources, propagate_head_vform=args.propagate_head_vform),
        cache_size=512,
        lexical_left_corner_pruning=True,
    )
    # Pair each trial with exactly the same lexical lattice; do not
    # conflate lazy WordNet cache effects with grammar constraints.
    restricted._lattice_cache = original._lattice_cache
    old_alarm = signal.signal(signal.SIGALRM, _alarm)
    rows = []
    try:
        for index in range(min(args.count, 500)):
            case = cases[index]
            old = _parse(original, case, args.seconds)
            new = _parse(restricted, case, args.seconds)
            if (old.get("lexical_count") is not None
                    and new.get("lexical_count") is not None
                    and old["lexical_count"] != new["lexical_count"]):
                raise AssertionError(
                    f"Lexical lattice changed at {index}: "
                    f"{old.get('lexical_count')} / {new.get('lexical_count')}"
                )
            row = {
                "index": index,
                "text": case["text"],
                "old": old,
                "new": new,
                "changed": old["tree_signature"] != new["tree_signature"]
                if "tree_signature" in old and "tree_signature" in new else None,
            }
            rows.append(row)
            if row["changed"] or (
                old["status"] != new["status"]
            ) or index in CASES_OF_INTEREST:
                print("FINITE_PREDICATE_CASE", json.dumps({
                    "index": index,
                    "old": {k: v for k,v in old.items()
                            if k != "tree_signature"},
                    "new": {k: v for k,v in new.items()
                            if k != "tree_signature"},
                    "changed": row["changed"],
                }, ensure_ascii=False), flush=True)
            if index % 50 == 49:
                print("FINITE_PREDICATE_PROGRESS", index + 1, flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_alarm)
    summary = {
        "n": len(rows),
        "old": dict(Counter(x["old"]["status"] for x in rows)),
        "new": dict(Counter(x["new"]["status"] for x in rows)),
        "recovered": [x["index"] for x in rows if
                      x["old"]["status"] != "complete"
                      and x["new"]["status"] == "complete"],
        "lost": [x["index"] for x in rows if
                 x["old"]["status"] == "complete"
                 and x["new"]["status"] != "complete"],
        "changed_trees": [x["index"] for x in rows if x["changed"]],
        "candidate": "clause_np_vp requires independently evidenced finite VP",
        "propagated_head_vform": args.propagate_head_vform,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"summary": summary, "rows": rows},
                   ensure_ascii=False, indent=2)+"\n",
        encoding="utf8",
    )
    print("FINITE_PREDICATE_SUMMARY", json.dumps(summary), flush=True)
    if any(row["new"]["status"] == "error" for row in rows):
        raise AssertionError("Unexpected experimental parser exceptions")


if __name__ == "__main__":
    main()
