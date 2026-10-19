"""Reproducible, bounded, one-pass diagnosis of cleaned novel sentences.

The forest state budget and k-best WORK budget are independent. Neither a
timed-out parse nor a saturated search proves lack of grammatical coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import signal
from time import perf_counter

from scripts.corpus_samples import BANDS, choose_cases, sample_spread
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]
STATUSES = (
    "complete", "both_budgets_exceeded", "forest_budget_exceeded",
    "kbest_budget_exceeded", "no_structural_root",
    "roots_without_valid_analysis", "timeout", "error",
)
MEANINGS = {
    "complete": "Best grammatical analysis certified",
    "both_budgets_exceeded": "Recognition and k-best both saturated",
    "forest_budget_exceeded": "Recognition stopped at forest item ceiling",
    "kbest_budget_exceeded": "Extraction stopped at k-best work ceiling",
    "no_structural_root": "No full-span clause found without saturation",
    "roots_without_valid_analysis": "Roots exist, but none unifies to a valid analysis",
    "timeout": "Deadline reached (no coverage conclusion)",
    "error": "Execution error (no coverage conclusion)",
}


class SentenceDeadline(Exception):
    pass


def _deadline(_signum, _frame):
    raise SentenceDeadline()


def select_cases(count: int):
    """Exactly count sentences, deterministically spread over 4 books x 4 bands."""
    if count < 1:
        raise ValueError("count must be positive")
    per_book_band = math.ceil(count / (4 * len(BANDS)))
    pool, sources = choose_cases(per_book_band)
    if len(pool) < count:
        raise ValueError(f"Only {len(pool)} eligible sentences for {count} requested")
    return sample_spread(pool, count), sources


def classify(completed: bool, stats: dict) -> str:
    """Exclusive headline; independent budget flags remain in the JSONL."""
    if completed:
        return "complete"
    forest = bool(stats.get("budget_exceeded"))
    kbest = bool(stats.get("kbest_budget_exceeded"))
    if forest and kbest:
        return "both_budgets_exceeded"
    if forest:
        return "forest_budget_exceeded"
    if kbest:
        return "kbest_budget_exceeded"
    if int(stats.get("structural_root_nodes", 0)) == 0:
        return "no_structural_root"
    return "roots_without_valid_analysis"


def compact_stats(stats: dict) -> dict:
    names = (
        "engine", "structural_root_nodes", "forest_nodes", "partial_states",
        "structural_derivations", "partial_derivations", "partial_proposals",
        "recognition_operations", "recognition_ms", "best_ms",
        "combinations_visited_for_best", "combinations_visited_total",
        "kbest_work_units", "unification_attempts", "unification_rejections",
        "hint_unification_attempts", "hint_unification_rejections",
    )
    return {key: stats.get(key, 0) for key in names}


def tally(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "completed": sum(r["status"] == "complete" for r in rows),
        "statuses": {s: sum(r["status"] == s for r in rows) for s in STATUSES},
        "forest_budget_flag": sum(bool(r.get("forest_budget_exceeded")) for r in rows),
        "kbest_budget_flag": sum(bool(r.get("kbest_budget_exceeded")) for r in rows),
        "structural_roots_present": sum(r.get("structural_root_nodes", 0) > 0 for r in rows),
        "complete_with_forest_saturation": sum(
            r["status"] == "complete" and bool(r.get("forest_budget_exceeded"))
            for r in rows
        ),
    }


def render_markdown(summary: dict, rows: list[dict]) -> str:
    total = summary["totals"]
    limits = summary["limits"]
    output = [
        "# Seman2 — diagnostic des phrases de romans",
        "",
        f"Analyses certifiées : {total['completed']}/{total['n']} "
        f"({summary['coverage_percent']:.1f} %).",
        "",
        f"Reconnaissance : {limits['max_items']} états ; k-best : "
        f"{limits['kbest_work_limit']} unités de travail ; délai : "
        f"{limits['deadline_seconds']} s / phrase.",
        "",
        "ATTENTION : les unités k-best ne sont pas les combinaisons visitées. "
        "Les deux mesures figurent dans per_sentence.jsonl.",
        "",
        "## Cause principale (catégories exclusives)",
        "",
        "| Cause | Phrases | Interprétation |",
        "|---|---:|---|",
    ]
    for status in STATUSES:
        output.append(
            f"| {status} | {total['statuses'][status]} | {MEANINGS[status]} |"
        )
    output.extend([
        "",
        "## Drapeaux indépendants, même sur des analyses complètes",
        "",
        f"- Forêt saturée : {total['forest_budget_flag']}",
        f"- K-best saturé : {total['kbest_budget_flag']}",
        f"- Racines structurelles présentes : {total['structural_roots_present']}",
        f"- Complètes mais forêt saturée : {total['complete_with_forest_saturation']}",
        "",
        "## Par longueur de phrase",
        "",
        "| Tokens | n | Complètes | Forêt saturée | K-best saturé |",
        "|---|---:|---:|---:|---:|",
    ])
    for band, row in summary["by_band"].items():
        output.append(
            f"| {band} | {row['n']} | {row['completed']} | "
            f"{row['forest_budget_flag']} | {row['kbest_budget_flag']} |"
        )
    output.extend([
        "",
        "## Premières phrases non complètes (maximum 15)",
        "",
        "| Index | Livre | Tokens | Cause | Racines | Unités k-best | Temps (ms) |",
        "|---:|---:|---:|---|---:|---:|---:|",
    ])
    for row in [r for r in rows if r["status"] != "complete"][:15]:
        output.append(
            f"| {row['index'] + 1} | {row['book_id']} | {row['tokens']} | "
            f"{row['status']} | {row.get('structural_root_nodes', '-')} | "
            f"{row.get('kbest_work_units', '-')} | {row['wall_ms']} |"
        )
    output.extend([
        "",
        "Le fichier per_sentence.jsonl conserve aussi toutes les phrases, "
        "les compteurs de combinaisons et d'unification et les erreurs.",
        "Une saturation, un délai ou une racine structurelle invalide ne "
        "doivent pas être confondus avec une absence certaine de grammaire.",
        "",
    ])
    return "\n".join(output)


def run(args: argparse.Namespace) -> dict:
    if args.max_items < 1 or args.kbest_work_limit < 1 or args.deadline_seconds <= 0:
        raise ValueError("Budgets and deadline must be positive")
    selected, sources = select_cases(args.count)
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=args.max_items)
    # Warm lexical lookup before any per-sentence deadline.
    build_lattice("John opened the box.", resources.lexicon, multiword_max=1)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    started = perf_counter()
    try:
        with (args.out_dir / "per_sentence.jsonl").open(
            "w", encoding="utf8", buffering=1
        ) as stream:
            for index, case in enumerate(selected):
                row = {
                    "index": index, "book_id": case["book_id"],
                    "ordinal": case["ordinal"], "band": case["band"],
                    "tokens": case["tokens"], "sentence": case["text"],
                    "sha256": sha256(case["text"].encode("utf8")).hexdigest(),
                }
                began = perf_counter()
                signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
                try:
                    lattice = build_lattice(
                        case["text"], resources.lexicon, multiword_max=1
                    )
                    result = parser.parse_grammar_lattice(
                        lattice, max_items=args.max_items,
                        kbest_work_limit=args.kbest_work_limit,
                    )
                    stats = result.stats
                    row.update(compact_stats(stats))
                    row.update({
                        "status": classify(result.completed, stats),
                        "completed": bool(result.completed),
                        "lexical_candidates": len(lattice.candidates),
                        "forest_budget_exceeded": bool(stats.get("budget_exceeded")),
                        "kbest_budget_exceeded": bool(stats.get("kbest_budget_exceeded")),
                        "root_rule": result.best().rule_id if result.completed else None,
                        "dialogue_scoped": bool(stats.get("dialogue_scoped")),
                        "complexity_route": stats.get("complexity_route", "canonical"),
                    })
                except SentenceDeadline:
                    row.update({"status": "timeout", "completed": False})
                except Exception as exc:
                    row.update({
                        "status": "error", "completed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                row["wall_ms"] = round((perf_counter() - began) * 1000, 2)
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                if (index + 1) % 5 == 0 or index + 1 == len(selected):
                    progress = tally(rows)
                    print("NOVEL_DIAGNOSTIC_PROGRESS", json.dumps({
                        "seen": index + 1, "complete": progress["completed"],
                        "statuses": progress["statuses"], "last_ms": row["wall_ms"],
                    }), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

    totals = tally(rows)
    by_band = {band: tally([r for r in rows if r["band"] == band])
               for band, _, _ in BANDS}
    by_book = {
        str(book_id): tally([r for r in rows if r["book_id"] == book_id])
        for book_id in sorted({r["book_id"] for r in rows})
    }
    summary = {
        "schema": "seman2-novel-parse-diagnostics-v1",
        "selection": "deterministic four-book/four-band cleaned Gutenberg sample",
        "sources": sources,
        "limits": {
            "count": args.count, "max_items": args.max_items,
            "kbest_work_limit": args.kbest_work_limit,
            "deadline_seconds": args.deadline_seconds,
        },
        "totals": totals, "by_band": by_band, "by_book": by_book,
        "coverage_percent": round(100 * totals["completed"] / len(rows), 2),
        "elapsed_seconds": round(perf_counter() - started, 2),
        "notes": [
            "Exclusive statuses; independent search-saturation flags.",
            "A structural root does not guarantee a unified valid analysis.",
            "Timeouts and errors are not grammatical coverage failures.",
            "A completed parse can still have an interrupted forest.",
            "Each sentence is parsed once, without A/B comparisons.",
        ],
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "report.md").write_text(
        render_markdown(summary, rows), encoding="utf8"
    )
    print("NOVEL_DIAGNOSTIC_FINAL", json.dumps({
        "counts": totals, "coverage_percent": summary["coverage_percent"],
        "by_band": by_band, "elapsed_seconds": summary["elapsed_seconds"],
    }, ensure_ascii=False), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--max-items", type=int, default=50_000)
    p.add_argument("--kbest-work-limit", type=int, default=500_000)
    p.add_argument("--deadline-seconds", type=float, default=10.0)
    p.add_argument("--out-dir", type=Path, required=True)
    run(p.parse_args())


if __name__ == "__main__":
    main()
