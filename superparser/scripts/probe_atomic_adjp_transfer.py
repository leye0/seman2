"""Probe a purely grammatical adjective-phrase composition change; not a corpus repair."""
from __future__ import annotations

import json
import os
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts import novel1500_exploratory as novel
from seman_parser.engine import Parser, ParserResources

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORDNET = os.environ["WORDNET_DICT"]
LIMITS = dict(max_items=50_000, kbest_work_limit=500_000)

def snapshot(text: str, category: str = "ADJP") -> dict:
    parser = Parser(ParserResources.from_dir(DATA, wordnet_dict=WORDNET),
                    goal_category=category)
    report = parser.parse(text, **LIMITS)
    item = report.result.best()
    return {"text": text, "category": category,
            "complete": report.result.completed,
            "best_rule": item.rule_id if item else None,
            "children": [c.rule_id for c in item.children] if item else [],
            "status": "work_limit" if report.result.stats.get("kbest_budget_exceeded") else "other"}

def main() -> None:
    results = [
        snapshot("extremely averse to delay"),
        snapshot("averse to delay"),
        snapshot("extremely averse"),
        snapshot("very averse to delay"),
        snapshot("extremely pretty"),
        snapshot("sufficiently fond of music"),
        snapshot("extremely fond of music"),
        snapshot("extremely beautiful", category="ADJP"),
    ]
    _, groups = novel.prepare()
    case = groups[1400][1][5]
    assert case["transfer_id"] == "N1306", case.get("transfer_id")
    parser = Parser(ParserResources.from_dir(DATA, wordnet_dict=WORDNET))
    _, _, report = parse_corpus_case(parser, case)
    top = report.result.best()
    results.append({"text": case["text"], "case": "N1306",
                    "complete": report.result.completed,
                    "best_rule": top.rule_id if top else None,
                    "stats": {k: report.result.stats.get(k) for k in
                        ("kbest_budget_exceeded","budget_exceeded","root_count")}})
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if not results[0]["complete"]:
        raise SystemExit("No general adjective phrase composition")
    if not results[-1]["complete"]:
        raise SystemExit("N1306 is not improved by the general composition")

if __name__ == "__main__":
    main()
