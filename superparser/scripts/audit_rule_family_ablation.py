"""Controlled grammar-family ablation on the SAME pinned 500-case corpus.

Research-only. The official Parser and 500-case benchmark remain unchanged.
Each ablation constructs a Grammar excluding a named family, calls the public
parse_corpus_case gateway exactly once per case and condition, and enforces
the same per-sentence time/forest limits. The result describes interactions,
not a license to overfit particular Gutenberg sentence indices.
"""
from __future__ import annotations

import argparse
import json
import signal
from pathlib import Path
from time import perf_counter

from scripts.diagnose_novel_parses import select_cases
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser, ParserResources
from seman_parser.grammar import Grammar

ROOT = Path(__file__).resolve().parents[1]
SERIAL = frozenset({
    "np_possessive_adjective_phrase_noun",
    "vp_perfect_negated_adverbial_transitive",
    "vp_perfect_negated_adverbial_intransitive",
    "np_third_person_nominal_coord_subject",
    "np_universal_third_person_nominal",
    "np_serial_third_person_nominal_coordination",
    "clause_serial_nominal_subject_comma_predicate",
})
COORD = frozenset({
    "vp_finite_comma_coord_fronted_pp",
    "vp_finite_comma_coord_fronted_adv",
})
PERFECT_GAP = frozenset({
    "vp_gap_perfect_transitive",
    "wh_bare_perfect_object_relative",
})
REPORTING = frozenset({"parenthetical_reporting_modal_bare"})
ABLATIONS = {
    "current": frozenset(),
    "without_possessive_adjp_nominal": frozenset({
        "np_possessive_adjective_phrase_noun",
    }),
    "without_perfect_negative_adverbial": frozenset({
        "vp_perfect_negated_adverbial_transitive",
        "vp_perfect_negated_adverbial_intransitive",
    }),
    "without_nominal_coordination_head": frozenset({
        "np_third_person_nominal_coord_subject",
    }),
    "without_universal_nominal_quantifier": frozenset({
        "np_universal_third_person_nominal",
    }),
    "without_serial_nominal_subject": frozenset({
        "np_serial_third_person_nominal_coordination",
        "clause_serial_nominal_subject_comma_predicate",
    }),
    "without_serial_subject_and_neg_perfect": SERIAL,
    "without_interrupted_vp_coordination": COORD,
    "without_perfect_relative_gaps": PERFECT_GAP,
    "without_new_rule_families": SERIAL | COORD | PERFECT_GAP | REPORTING,
}
# Stratified by the 500-case global signature audit: difficult interactions
# (coordinator + nonfinite / repeated coordination) AND successful controls.
# These are NOT selected solely for known failures, to expose regressions.
TARGETS = (
    58, 62, 75, 98, 104,  # matched successful controls
    96, 100, 115, 194, 209, 232, 237, 347, 349, 367, 439, 473,
)


class Deadline(Exception):
    pass


def _alarm(_signal_number, _frame):
    raise Deadline("research parse exceeded per-case deadline")


def audit(wordnet_dir: str, indices: tuple[int, ...], *,
          seconds: float = 9.0, max_items: int = 50000):
    cases, _ = select_cases(500)
    baseline = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    names = {rule.rule_id for rule in baseline.grammar}
    for name, excluded in ABLATIONS.items():
        unknown = excluded - names
        if unknown:
            raise ValueError(f"Missing rule IDs in {name}: {sorted(unknown)}")
    old_handler = signal.signal(signal.SIGALRM, _alarm)
    rows = []
    try:
        for name, excluded in ABLATIONS.items():
            grammar = Grammar(r for r in baseline.grammar if r.rule_id not in excluded)
            resources = ParserResources(
                grammar=grammar,
                lexicon=baseline.lexicon,
                types=baseline.types,
                metadata=baseline.metadata,
            )
            parser = Parser(resources, cache_size=0, max_items=max_items)
            for idx in indices:
                case = cases[idx]
                started = perf_counter()
                signal.setitimer(signal.ITIMER_REAL, seconds)
                try:
                    prepared, lattice, result = parse_corpus_case(
                        parser, case, max_items=max_items,
                        kbest_work_limit=500000,
                    )
                    row = {
                        "variant": name, "index": idx, "book_id": case["book_id"],
                        "completed": result.completed,
                        "root": result.best().rule_id if result.best() else None,
                        "forest_budget": bool(result.stats.get("budget_exceeded")),
                        "forest_nodes": result.stats.get("forest_nodes"),
                        "root_nodes": result.stats.get("structural_root_nodes"),
                        "lexical_candidates": len(lattice.candidates),
                    }
                except Deadline:
                    row = {"variant": name, "index": idx, "completed": False,
                           "status": "timeout"}
                except Exception as exc:
                    row = {"variant": name, "index": idx, "completed": False,
                           "status": f"error: {type(exc).__name__}: {exc}"}
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                row["wall_ms"] = round((perf_counter() - started) * 1000, 2)
                rows.append(row)
                print("NOVEL_RULE_FAMILY_ABLATION",
                      json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    summary = {
        name: {
            "completed": sum(x["completed"] for x in rows if x["variant"] == name),
            "timeouts": sum(x.get("status") == "timeout"
                            for x in rows if x["variant"] == name),
            "forest_limited": sum(x.get("forest_budget", False)
                                  for x in rows if x["variant"] == name),
        }
        for name in ABLATIONS
    }
    # Paired case-level deltas are more informative than raw completion
    # totals: a rule family may recover one sentence while losing another.
    baseline = {row["index"]: row for row in rows
                if row["variant"] == "current"}
    deltas = {}
    for name in ABLATIONS:
        if name == "current":
            continue
        candidate = {row["index"]: row for row in rows
                     if row["variant"] == name}
        recovered = sorted(i for i in indices
                           if not baseline[i]["completed"]
                           and candidate[i]["completed"])
        regressed = sorted(i for i in indices
                           if baseline[i]["completed"]
                           and not candidate[i]["completed"])
        deltas[name] = {
            "recovered_vs_current": recovered,
            "regressed_vs_current": regressed,
            "net_completion_change": len(recovered) - len(regressed),
            "baseline_completed": sum(baseline[i]["completed"] for i in indices),
            "variant_completed": sum(candidate[i]["completed"] for i in indices),
        }
    print("NOVEL_RULE_FAMILY_ABLATION_PAIRED",
          json.dumps({"indices": indices, "deltas": deltas}), flush=True)
    print("NOVEL_RULE_FAMILY_ABLATION_SUMMARY",
          json.dumps({"indices": indices, "groups": summary}), flush=True)
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--indices", default=",".join(map(str, TARGETS)))
    p.add_argument("--seconds", type=float, default=9.0)
    p.add_argument("--max-items", type=int, default=50000)
    opts = p.parse_args()
    audit(opts.wordnet_dir, tuple(int(x) for x in opts.indices.split(",")),
          seconds=opts.seconds, max_items=opts.max_items)


if __name__ == "__main__":
    main()
