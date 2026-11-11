"""Generate the active grammar queue from the *current* segmented 500-case run.

The old indexed queue belongs to the pre-migration cohort and must never be
reused after the current source-unit boundaries change.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.diagnose_novel_parses import EXPECTED_500_COHORT_SHA256, STATUSES


def rebuild(rows: list[dict], summary: dict, validated_commit: str) -> dict:
    """Validate alignment first; never transfer old positions to a new cohort."""
    if len(rows) != 500 or [r.get("index") for r in rows] != list(range(500)):
        raise ValueError("Expected 500 ordered, indexed current-cohort records")
    if summary.get("cohort_sha256") != EXPECTED_500_COHORT_SHA256:
        raise ValueError("Active cohort SHA differs from the current manifest")
    if summary.get("totals", {}).get("n") != len(rows):
        raise ValueError("Summary and sentence count disagree")
    if any(r.get("status") not in STATUSES for r in rows):
        raise ValueError("Unknown parse status in diagnostic rows")
    if any(r.get("status") == "error" for r in rows):
        raise ValueError("Cannot validate a cohort with execution errors")
    completed = sum(r["status"] == "complete" for r in rows)
    if summary["totals"]["completed"] != completed:
        raise ValueError("Per-case completion does not match official summary")
    unresolved = [
        {"index": row["index"], "status": row["status"],
         "case_id": row["case_id"]}
        for row in rows if row["status"] != "complete"
    ]
    if any(not isinstance(r["case_id"], str) or not r["case_id"] for r in rows):
        raise ValueError("Every current case needs source-stable identification")
    return {
        "schema": "seman2-grammar-case-queue-v2",
        "cohort_sha256": EXPECTED_500_COHORT_SHA256,
        "validated_commit": validated_commit,
        "completed_count": completed,
        "last_attempted_index": -1,
        "unresolved": unresolved,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diagnostics", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    rows = [json.loads(x) for x in args.diagnostics.read_text(encoding="utf-8").splitlines()
            if x.strip()]
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    queue = rebuild(rows, summary, os.environ.get("GITHUB_SHA", "local-unvalidated"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("CURRENT_GRAMMAR_QUEUE", json.dumps({
        "cohort_sha256": queue["cohort_sha256"],
        "completed": queue["completed_count"],
        "remaining": len(queue["unresolved"]),
        "next_index": next((r["index"] for r in unresolved), None)
        if (unresolved := queue["unresolved"]) else None,
    }), flush=True)


if __name__ == "__main__":
    main()
