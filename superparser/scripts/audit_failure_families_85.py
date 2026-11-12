"""Inventory the immutable 85 failures from the pre-PR45 pinned corpus.

Run: PYTHONPATH=superparser python -m scripts.audit_failure_families_85
No reparsing, changed sampling, reslicing, or inferred grammatical success.
All labels here are observational surface signals; only selected parse trees
can prove root causes and repairs.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.audit_context_dependencies import fingerprint
from scripts.diagnose_novel_parses import select_cases

ROOT = Path(__file__).resolve().parents[2]
COHORT = ROOT / "docs" / "CURRENT_COHORT.json"
QUEUE = ROOT / "docs" / "GRAMMAR_CASE_QUEUE.json"
ORIGINAL_85 = ROOT / "superparser" / "research" / "pinned_original_failure_85.json"


def inventory() -> dict:
    queue = json.loads(QUEUE.read_text())
    pinned = json.loads(ORIGINAL_85.read_text())
    baseline = json.loads(COHORT.read_text())
    cases, _ = select_cases(500)
    actual_sha = fingerprint(cases)
    expected_sha = baseline["cohort_sha256"]
    if (actual_sha != expected_sha
            or queue["cohort_sha256"] != expected_sha
            or pinned["cohort_sha256"] != expected_sha):
        raise AssertionError("Refusing an inventory on a different cohort")
    if (pinned.get("schema") != "seman2-pinned-original-unresolved-85-v1"
            or pinned.get("baseline_completed") != 415
            or pinned.get("baseline_unresolved") != 85):
        raise AssertionError("Original 85-failure manifest is not pinned")
    failed = pinned["witnesses"]
    if len(failed) != 85 or len({x["index"] for x in failed}) != 85:
        raise AssertionError("Expected exactly 85 distinct original witnesses")
    # The active queue shrinks as grammar repairs land. Its contents must
    # remain within the ORIGINAL witness set. A newly failing previously
    # completed case is a regression and cannot be silently inventoried away.
    original_by_index = {r["index"]: r["case_id"] for r in failed}
    active = queue["unresolved"]
    if (len(active) != len({r["index"] for r in active})
            or len(active) + queue["completed_count"] != 500
            or queue["completed_count"] < pinned["baseline_completed"]):
        raise AssertionError("Active 500-case queue is internally inconsistent")
    for current in active:
        if original_by_index.get(current["index"]) != current["case_id"]:
            raise AssertionError(
                "New unresolved source or case identity drift at "
                + str(current["index"])
            )
    records = []
    for row in failed:
        index = row["index"]
        case = cases[index]
        if row["case_id"] != (
            str(case["book_id"]) + ":" + __import__("hashlib").sha256(
                case["source_text"].encode()
            ).hexdigest()[:16]
        ):
            raise AssertionError("Source identity drift at case " + str(index))
        source = case["source_text"]
        lower = source.lower()
        constituents = case.get("structural_constituents", ())
        funcs = {part["function"] for part in constituents}
        signals = []
        if "direct_speech" in funcs:
            signals.append("direct_speech")
        if "split_direct_speech_turn" in funcs:
            signals.append("intercalated_reporter")
        if "embedded_quotation" in funcs:
            signals.append("nested_quote")
        if ";" in source:
            signals.append("semicolon_interclausal")
        if "?" in source:
            signals.append("question")
        if source.count(",") >= 2:
            signals.append("multiple_comma_constituents")
        if any(" " + w + " " in " " + lower + " " for w in
               ("that", "which", "when", "although", "though", "if",
                "who", "whose", "whom", "where", "unless", "lest")):
            signals.append("subordination_surface")
        if any(" " + w + " " in " " + lower + " " for w in
               ("and", "but", "or", "nor", "yet")):
            signals.append("coordination_surface")
        if "--" in source or "—" in source or "(" in source:
            signals.append("parenthetical_punctuation")
        if row["status"] in ("forest_budget_exceeded", "timeout",
                              "kbest_budget_exceeded",
                              "both_budgets_exceeded"):
            signals.append("resource_censored")
        records.append({
            "index": index, "case_id": row["case_id"],
            "status": row["status"], "source_text": source,
            "source_book": case["book_id"], "tokens": case.get("tokens"),
            "observed_signals_not_causes": signals,
        })
    statuses = Counter(r["status"] for r in records)
    signals = Counter(s for r in records for s in r["observed_signals_not_causes"])
    return {
        "schema": "seman2-all-85-unresolved-failure-inventory-v1",
        "cohort_sha256": actual_sha,
        "baseline_completed": pinned["baseline_completed"],
        "original_unresolved": len(records),
        "active_completed": queue["completed_count"],
        "active_unresolved": len(active),
        "repaired_original_indexes": sorted(
            set(original_by_index) - {r["index"] for r in active}
        ),
        "total_unresolved": len(records),
        "exclusive_status_counts": dict(sorted(statuses.items())),
        "nonexclusive_observed_signal_counts": dict(sorted(signals.items())),
        "cases": records,
        "caution": "Surface signals are NOT verified missing grammar rules. A repair requires a selected full-span rank-one tree, exact attachments, independent contrasts and same-cohort no-regression.",
    }


def markdown(data: dict) -> str:
    lines = [
        "# Immutable inventory of the 85 original grammar failures",
        "", "All **85/85 original baseline failures** are listed below.",
        "The active unresolved queue can shrink as cases are repaired.",
        "Source texts are never regenerated with new punctuation.",
        "Observational labels are hypotheses, not established grammatical diagnoses.",
        "",
        f"**Cohort SHA:** `{data['cohort_sha256']}`",
        f"**Original baseline coverage:** {data['baseline_completed']}/500",
        f"**Current active coverage:** {data['active_completed']}/500",
        f"**Current active failures:** {data['active_unresolved']}",
        f"**Original cases now repaired:** {', '.join(map(str, data['repaired_original_indexes'])) or 'none'}",
        "", "## Original exclusive parser outcomes", "",
    ]
    for key, count in data["exclusive_status_counts"].items():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Overlapping observational signals", ""]
    for key, count in data["nonexclusive_observed_signal_counts"].items():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Exact 85 original source cases", "",
              "| # | Book | Status | Signals (not proofs) | Original source |",
              "|---:|---:|---|---|---|"]
    for row in data["cases"]:
        source = row["source_text"].replace("|", "&#124;").replace("\n", " ")
        lines.append("| {index} | {source_book} | `{status}` | {signals} | {source} |".format(
            **row,
            signals=", ".join(row["observed_signals_not_causes"]) or "unclassified",
            source=source,
        ))
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("/tmp/grammar-85"))
    args = ap.parse_args()
    audit = inventory()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "all_85.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    (args.out_dir / "all_85.md").write_text(markdown(audit))
    print("GRAMMAR_ALL_85", json.dumps({
        k: v for k, v in audit.items() if k != "cases"
    }), flush=True)


if __name__ == "__main__":
    main()
