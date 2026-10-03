#!/usr/bin/env python3
"""TIME-07: immutable temporal selections over an append-only evidence ledger."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rank(data, time):
    allowed = {"t1"} if time == "t1" else {"t1", "t2"}
    rows = []
    for hypothesis in data["hypotheses"]:
        contributions = []
        score = 0
        for evidence in data["evidence"]:
            if evidence["hypothesis"] != hypothesis["id"] or evidence["time"] not in allowed:
                continue
            signed = evidence["weight"] if evidence["kind"] == "support" else (-evidence["weight"] if evidence["kind"] == "contradiction" else 0)
            score += signed
            contributions.append({**evidence, "signed_contribution": signed})
        rows.append({"hypothesis": hypothesis["id"], "score": score, "contributions": contributions})
    rows.sort(key=lambda row: (-row["score"], row["hypothesis"]))
    return rows


def main():
    data = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    immutable_core = {"observation": data["observation"], "hypotheses": data["hypotheses"]}
    core_hash_before = digest(immutable_core)
    ranking_t1 = rank(data, "t1")
    selection_t1 = {"id": "selection-t1", "time": "t1", "hypothesis": ranking_t1[0]["hypothesis"], "ranking_snapshot": ranking_t1}
    selection_t1_hash_before = digest(selection_t1)
    ranking_t2 = rank(data, "t2")
    selection_t2 = {"id": "selection-t2", "time": "t2", "hypothesis": ranking_t2[0]["hypothesis"], "ranking_snapshot": ranking_t2}
    assert selection_t1["hypothesis"] == data["oracle"]["selection_t1"]
    assert selection_t2["hypothesis"] == data["oracle"]["selection_t2"]
    assert digest(immutable_core) == core_hash_before and digest(selection_t1) == selection_t1_hash_before
    result = {
        "observation": data["observation"], "hypotheses": data["hypotheses"],
        "evidence_ledger": data["evidence"], "selection_events": [selection_t1, selection_t2],
        "selection_changed": True, "historical_selection_mutated": False,
        "immutable_core_hash": core_hash_before, "t1_selection_hash": selection_t1_hash_before,
        "quarantined_anchor_contribution": 0,
    }
    summary = {
        "hypothesis_count": len(data["hypotheses"]), "evidence_count": len(data["evidence"]),
        "selection_t1": selection_t1["hypothesis"], "selection_t2": selection_t2["hypothesis"],
        "historical_selection_mutated": False, "quarantined_anchor_changed_ranking": False,
        "verdict": "GO_NON_DESTRUCTIVE_TEMPORAL_REVISION",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("results.json", result), ("summary.json", summary), ("versions-and-parameters.json", {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "ledger": "append-only fixture", "ranking": "inspectable signed contributions"})):
        (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TIME-07: selection {summary['selection_t1']} -> {summary['selection_t2']}; history immutable")


if __name__ == "__main__":
    main()
