"""Select the next pinned unresolved grammar case, without manual triage.

    PYTHONPATH=superparser python -m scripts.next_grammar_case

The tracked queue is refreshed after each complete 500-case diagnostic. Its
cursor records the last *attempted* index, even if that case was blocked; an
unsolved case remains in the queue and is revisited after wrap-around.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_QUEUE = Path(__file__).resolve().parents[2] / "docs" / "GRAMMAR_CASE_QUEUE.json"


def select_next(queue: dict, *, after: int | None = None) -> dict:
    """Return the first unresolved index after the cursor (with wrap-around)."""
    unresolved = queue["unresolved"]
    indices = [entry["index"] for entry in unresolved]
    if indices != sorted(set(indices)) or any(not 0 <= index < 500 for index in indices):
        raise ValueError("Unresolved case indices must be unique, sorted and in [0, 500)")
    if queue["completed_count"] + len(indices) != 500:
        raise ValueError("The tracked 500-case coverage and unresolved queue disagree")
    if not unresolved:
        raise ValueError("No unresolved case remains in the pinned cohort")
    cursor = queue["last_attempted_index"] if after is None else after
    if not -1 <= cursor < 500:
        raise ValueError("Cursor must be between -1 and 499")
    return next((entry for entry in unresolved if entry["index"] > cursor),
                unresolved[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--after", type=int, help="Override the last attempted index")
    options = parser.parse_args()

    queue = json.loads(options.queue.read_text(encoding="utf-8"))
    from scripts.diagnose_novel_parses import EXPECTED_500_COHORT_SHA256, select_cases

    if queue["cohort_sha256"] != EXPECTED_500_COHORT_SHA256:
        raise SystemExit("The queue does not match the immutable 500-case corpus")
    chosen = select_next(queue, after=options.after)
    cases, _ = select_cases(500)
    case = cases[chosen["index"]]
    print(json.dumps({
        "index": chosen["index"],
        "status": chosen["status"],
        "book_id": case["book_id"],
        "sentence": case["text"],
        "after": queue["last_attempted_index"] if options.after is None else options.after,
        "validated_commit": queue["validated_commit"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
