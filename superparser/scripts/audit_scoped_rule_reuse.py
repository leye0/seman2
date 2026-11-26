"""Inventory repeated scoped productions without claiming semantic equivalence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
GRAMMARS = ("grammar", "dialogue_grammar", "dialogue_structural_grammar")
RELATIONS = ("RELATIVE_ANTECEDENT", "CONJUNCT", "REPORTED_CONTENT", "CONTINUED_SPEECH")


def rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def plan_of(rule):
    return rule.get("provenance", {}).get("source_plan")


def shape(rule):
    return (rule["lhs"]["category"], *(symbol["category"] for symbol in rule["rhs"]))


def relations(actions):
    for action in actions:
        links = action.get("compose", {}).get("links", [])
        if "link" in action:
            links = [*links, action["link"]]
        for link in links:
            name = link.get("relation", link.get("role", "REL"))
            if name is not None:
                yield name


def summarize_grammar(rules, semantics):
    scoped = [r for r in rules if plan_of(r)]
    shapes = defaultdict(list)
    for rule in scoped:
        shapes[shape(rule)].append(rule)
    cross = [
        {"categories": list(key),
         "productions": [{"id": r["id"], "plan": plan_of(r)} for r in members]}
        for key, members in sorted(shapes.items())
        if len({plan_of(r) for r in members}) > 1
    ]
    direct_relations = {}
    for name in RELATIONS:
        seen = [r for r in scoped if name in set(relations(semantics.get(r["id"], [])))]
        direct_relations[name] = {
            "productions": len(seen),
            "plans": len({plan_of(r) for r in seen}),
        }
    return {
        "productions": len(rules),
        "scoped_productions": len(scoped),
        "source_plans": len({plan_of(r) for r in scoped}),
        "scoped_clause_productions": sum(r["lhs"]["category"] == "CLAUSE" for r in scoped),
        "cross_scope_category_shapes": len(cross),
        "productions_in_cross_scope_category_shapes": sum(len(row["productions"]) for row in cross),
        "cross_scope_shapes": cross,
        "direct_recipe_relations": direct_relations,
    }


def summarize_replay(observations, plan_by_root):
    counts = Counter()
    statuses = Counter()
    for row in observations:
        status = row["status"]
        statuses[status] += 1
        plan = plan_by_root.get(row.get("root_rule"))
        if status == "complete" and plan:
            counts[plan] += 1
    return {
        "sources": sum(statuses.values()),
        "complete": statuses["complete"],
        "complete_with_scoped_root": sum(counts.values()),
        "selected_source_plans": len(counts),
        "plans_selected_once": sum(n == 1 for n in counts.values()),
        "selected_plan_counts": dict(sorted(counts.items())),
    }


def group_replay(paths, scoped_roots, excluded):
    candidates = sorted(p for p in paths.glob("novel-*-parses.jsonl") if p.name not in excluded)
    if not candidates:
        raise ValueError(f"No novel replay JSONL found in {paths}")
    return summarize_replay((row for p in candidates for row in rows(p)), scoped_roots)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, action="append", default=[])
    parser.add_argument("--exclude-replay-file", action="append", default=[])
    args = parser.parse_args()
    grammars = {name: list(rows(DATA / f"{name}.jsonl")) for name in GRAMMARS}
    actions = {
        row["id"]: row["semantic"]
        for name in ("semantic_rules", "dialogue_semantic_rules")
        for row in rows(DATA / f"{name}.jsonl")
    }
    roots = {r["id"]: plan_of(r) for rules in grammars.values()
             for r in rules if plan_of(r) and r["lhs"]["category"] == "CLAUSE"}
    report = {
        "grammar": {name: summarize_grammar(notations, actions)
                    for name, notations in grammars.items()},
        "replays": {str(p): group_replay(p, roots, set(args.exclude_replay_file))
                    for p in args.replay_dir},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
