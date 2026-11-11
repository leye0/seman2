"""Measure direct-speech vs narration failures without quote/apostrophe guesses.

Input is the 500 aligned per-sentence outcomes of the canonical diagnostic.
All groupings are based on SOURCE-ANCHORED functions produced by the active
structural preanalyzer, not raw quotation glyph counts (which mistakenly
include don't, o'clock and possessives) or inferred tree correctness.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def analyze(rows: list[dict]) -> dict:
    if len(rows) == 0 or len({r["index"] for r in rows}) != len(rows):
        raise ValueError("Expected nonempty diagnostic with unique indexed cases")
    counts = defaultdict(Counter)
    examples = []
    for row in rows:
        functions = row.get("structural_functions")
        if not isinstance(functions, list):
            raise ValueError("Missing source-typed structural functions")
        funcs = Counter(functions)
        label = "direct_speech" if funcs["direct_speech"] else "non_direct_speech"
        failure = row["status"] != "complete"
        counts[label]["total"] += 1
        counts[label]["failed"] += int(failure)
        counts[label]["complete"] += int(not failure)
        counts[label]["status:" + row["status"]] += 1
        if not funcs["direct_speech"]:
            continue
        if funcs["split_direct_speech_turn"]:
            kind = "split_speech_with_intercalated_reporting_clause"
        elif funcs["embedded_quotation"]:
            kind = "nested_quotation"
        elif funcs["spoken_clause_candidate"] >= 2:
            kind = "multisentence_quotation"
        elif funcs["reporting_clause"]:
            kind = "single_quote_with_reporting_clause"
        else:
            kind = "unattributed_single_quotation"
        counts["speech_subtype:" + kind]["total"] += 1
        counts["speech_subtype:" + kind]["failed"] += int(failure)
        counts["speech_subtype:" + kind]["complete"] += int(not failure)
        if failure:
            examples.append({
                "index": row["index"],
                "case_id": row.get("case_id"),
                "status": row["status"],
                "subtype": kind,
                "text": row.get("source_text", row.get("sentence")),
                "functions": dict(funcs),
                "relations": row.get("structural_relations", []),
            })
    out = {k: dict(v) for k, v in sorted(counts.items())}
    return {
        "schema": "seman2-dialogue-residual-audit-v1",
        "n": len(rows),
        "counted_by_structural_quote_spans_not_apostrophes": True,
        "parse_results_unchanged": True,
        "direct_speech_is_not_the_only_possible_dialogue_context": True,
        "outcomes": out,
        "failed_direct_speech_cases": examples,
        "limitations": [
            "Some narration failures may still depend on surrounding dialogue.",
            "A quotation failure may be lexical, syntactic or resource-censored.",
            "Constituent functions are provisional; this audit does not certify parse trees.",
            "No changes to grammar rules, input text, cohort or parse budgets.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in
            args.diagnostics.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    report = analyze(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("DIALOGUE_RESIDUAL_AUDIT", json.dumps({
        key: value for key, value in report.items()
        if key != "failed_direct_speech_cases"
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
