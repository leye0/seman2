"""Research-only source-grounded fragment probe for remaining failure families.

Read pinned cohort identities; DO NOT infer a full repair from fragments.
All corpus completions must later use canonical parse_corpus_case.
"""
from __future__ import annotations

import json
import signal
from pathlib import Path
from seman_parser.engine import Parser, ParserResources
from scripts.diagnose_novel_parses import select_cases

DATA = Path(__file__).resolve().parents[1] / "data"
PROBES = {
  386: (
    ("all hands", "NP"),
    ("were already congregated", "VP"),
    ("already congregated", "ADJP"),
    ("congregated", "ADJ"),
    ("There all hands were already congregated.", "CLAUSE"),
  ),
  301: (
    ("this gentle and lovely being", "NP"),
    ("lost forever", "ADJP"),
    ("lost", "ADJ"),
    ("Is this gentle and lovely being lost forever?", "CLAUSE"),
  ),
  384: (
    ("You'll find I do my duty.", "CLAUSE"),
    ("You will find I do my duty.", "CLAUSE"),
    ("I do my duty.", "CLAUSE"),
    ("find I do my duty", "VP"),
    ("find", "V"),
  ),
  175: (
    ("Elizabeth listened", "CLAUSE"),
    ("wondered", "VP"),
    ("doubted", "VP"),
    ("was impatient for more", "VP"),
    ("listened, wondered, doubted, and was impatient for more", "VP"),
    ("listened, wondered, and doubted", "VP"),
  ),
  463: (
    ("He himself", "NP"),
    ("looked somewhat paler and more stern than I was used to", "VP"),
    ("I thought", "CLAUSE"),
    ("He himself looked somewhat paler", "CLAUSE"),
  ),
  52: (
    ("Why should he go to India?", "CLAUSE"),
    ("except to harass me", "PP"),
    ("he should go to India", "CLAUSE"),
    ("go to India", "VP-NP"),
    ("to harass me", "VP-NP"),
  ),
  294: (
    ("Who could arrest a creature?", "CLAUSE"),
    ("a creature capable of scaling the overhanging sides of Mont Saleve", "NP"),
    ("capable of scaling the overhanging sides of Mont Saleve", "ADJP"),
  ),
  141: (
    ("The envelope itself", "NP"),
    ("was likewise full", "VP"),
  ),
  291: (
    ("A meeting, which he anticipated with such joy", "NP"),
    ("so strangely turned to bitterness", "VP"),
    ("which he anticipated with such joy", "REL-CLAUSE"),
  ),
}


class Deadline(Exception):
    pass


def expire(*_):
    raise Deadline()


def run():
    cases, _ = select_cases(500)
    resources = ParserResources.from_dir(DATA)
    parsers = {}
    for index, probes in PROBES.items():
        source = cases[index]["source_text"]
        print("BATCH_CASE", index, json.dumps(source), flush=True)
        for fragment, goal in probes:
            if goal not in parsers:
                parsers[goal] = Parser(resources, goal_category=goal, cache_size=12)
            parser = parsers[goal]
            lattice = parser._lattice_for_text(fragment)
            lexical = {
                token.text: list(sorted({
                    c.category+":" + str(c.features.as_dict().get("vform", ""))
                    +":" + str(c.features.as_dict().get("subcat", ""))
                    for c in lattice.candidates
                    if c.surface == token.text
                }))[:12]
                for token in lattice.tokens
            }
            signal.setitimer(signal.ITIMER_REAL, 6)
            try:
                r = parser.parse(fragment, max_items=50_000,
                                 kbest_work_limit=500_000).result
                b = r.best()
                record = {
                    "index": index, "fragment": fragment, "goal": goal,
                    "completed": r.completed, "status": ("complete" if r.completed else "incomplete"),
                    "budget_exceeded": r.stats.get("budget_exceeded"),
                    "root": b.rule_id if b else None,
                    "features": b.features.as_dict() if b else None,
                    "children": [
                        [node.rule_id,node.category,fragment[node.start:node.end],
                         node.features.as_dict()]
                        for node in b.children
                    ] if b else [],
                    "lexical": lexical,
                }
            except Deadline:
                record = {"index":index,"fragment":fragment,"goal":goal,
                          "status":"timeout","lexical":lexical}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            print("BATCH_PROBE", json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run()
