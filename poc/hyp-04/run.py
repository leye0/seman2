#!/usr/bin/env python3
"""HYP-04: contextual ranking over one immutable evidence ledger."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import pyarrow.parquet as pq

P = Path(__file__).resolve().parent
OUT = P / "output"


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    contexts = {
        "greeting": {"description": "dialogue opening with same speaker"},
        "computing": {"description": "technical discussion about file streams"},
        "astronomy": {"description": "discussion of Jupiter satellites"},
    }
    weights = {"direct": 1.3, "contextual": 1.0, "phonological": 0.6, "semantic": 1.1,
               "discursive": 1.2, "outcome": 1.4, "contradiction": 1.5,
               "recency": 0.4, "descriptive_cost": 1.0}
    specs = [
        ("e01", "hyp:H1", "direct", 0.8, 0.95, 5, {"greeting": .3, "computing": 1.0, "astronomy": .1}, "IO lexical expansion"),
        ("e02", "hyp:H1", "semantic", 1.0, 0.90, 4, {"greeting": .1, "computing": 1.0, "astronomy": .0}, "fits computing topic"),
        ("e03", "hyp:H1", "contradiction", -1.0, 1.00, 1, {"greeting": 1.0, "computing": .1, "astronomy": .2}, "explicit greeting correction"),
        ("e04", "hyp:H1", "descriptive_cost", -0.2, 1.00, 0, {"greeting": 1.0, "computing": 1.0, "astronomy": 1.0}, "acronym expansion cost"),
        ("e05", "hyp:H2", "phonological", 0.6, 0.75, 5, {"greeting": 1.0, "computing": .5, "astronomy": .4}, "form resembles greeting token"),
        ("e06", "hyp:H2", "discursive", 1.2, 0.95, 2, {"greeting": 1.0, "computing": .1, "astronomy": .1}, "opening move fit"),
        ("e07", "hyp:H2", "outcome", 1.4, 1.00, 1, {"greeting": 1.0, "computing": .1, "astronomy": .1}, "speaker confirmation"),
        ("e08", "hyp:H2", "descriptive_cost", -0.1, 1.00, 0, {"greeting": 1.0, "computing": 1.0, "astronomy": 1.0}, "short convention"),
        ("e09", "hyp:H3", "direct", 0.7, 0.90, 8, {"greeting": .1, "computing": .1, "astronomy": 1.0}, "Io proper-name entry"),
        ("e10", "hyp:H3", "semantic", 1.3, 0.95, 3, {"greeting": .0, "computing": .0, "astronomy": 1.0}, "Jupiter topic fit"),
        ("e11", "hyp:H3", "descriptive_cost", -0.15, 1.00, 0, {"greeting": 1.0, "computing": 1.0, "astronomy": 1.0}, "capitalization mismatch"),
        ("e12", "hyp:H4", "contextual", 0.2, 0.60, 2, {"greeting": .3, "computing": .3, "astronomy": .3}, "fallback remains possible"),
        ("e13", "hyp:H4", "descriptive_cost", -0.5, 1.00, 0, {"greeting": 1.0, "computing": 1.0, "astronomy": 1.0}, "unexplained form cost"),
    ]
    ledger = [{"entry_id": eid, "hypothesis_id": hyp, "family": family, "raw_strength": strength,
               "provenance_reliability": reliability, "age_days": age,
               "context_relevance_json": canonical(relevance), "reason": reason}
              for eid, hyp, family, strength, reliability, age, relevance, reason in specs]
    ledger_hash_before = hashlib.sha256(canonical(ledger).encode()).hexdigest()
    df = pl.DataFrame(ledger)
    OUT.mkdir(parents=True, exist_ok=True)
    df.write_parquet(OUT / "evidence-ledger.parquet", compression="zstd")
    rankings = {}
    contribution_rows = []
    half_life_days = 10.0
    for context_id in contexts:
        rows = []
        for row in ledger:
            relevance = json.loads(row["context_relevance_json"])[context_id]
            recency = float(np.exp(-row["age_days"] / half_life_days))
            contribution = (row["raw_strength"] * weights[row["family"]] *
                            row["provenance_reliability"] * relevance *
                            (1.0 + weights["recency"] * recency))
            rows.append({**row, "context_id": context_id, "context_relevance": relevance,
                         "recency_factor": recency, "family_weight": weights[row["family"]],
                         "contribution": contribution})
        contextual = pl.DataFrame(rows)
        ranked = (contextual.group_by("hypothesis_id").agg(pl.col("contribution").sum().alias("score"))
                  .sort(["score", "hypothesis_id"], descending=[True, False]))
        rankings[context_id] = ranked.to_dicts()
        contribution_rows.extend(rows)
    pl.DataFrame(contribution_rows).write_parquet(OUT / "contextual-contributions.parquet", compression="zstd")

    db = OUT / "hyp-04.duckdb"
    if db.exists(): db.unlink()
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE ledger AS SELECT * FROM read_parquet(?)", [str((OUT / "evidence-ledger.parquet").resolve())])
    con.execute("CREATE TABLE contributions AS SELECT * FROM read_parquet(?)", [str((OUT / "contextual-contributions.parquet").resolve())])
    family_explanations = con.execute("""
        SELECT context_id, hypothesis_id, family, sum(contribution) contribution
        FROM contributions GROUP BY ALL ORDER BY context_id, hypothesis_id, family
    """).fetchall()
    con.close()
    ledger_hash_after = hashlib.sha256(canonical(ledger).encode()).hexdigest()
    winners = {context: rows[0]["hypothesis_id"] for context, rows in rankings.items()}
    changes = []
    for left, right in (("greeting", "computing"), ("computing", "astronomy")):
        left_rows = {(r[0], r[1], r[2]): r[3] for r in family_explanations if r[0] == left}
        right_rows = {(r[0], r[1], r[2]): r[3] for r in family_explanations if r[0] == right}
        deltas = []
        for hypothesis in sorted({r[1] for r in family_explanations}):
            for family in sorted({r[2] for r in family_explanations}):
                a = left_rows.get((left, hypothesis, family), 0.0)
                b = right_rows.get((right, hypothesis, family), 0.0)
                if a != b:
                    deltas.append({"hypothesis_id": hypothesis, "family": family, "from": a, "to": b, "delta": b-a})
        changes.append({"from_context": left, "to_context": right, "winner_before": winners[left],
                        "winner_after": winners[right], "contribution_deltas": deltas})
    validations = {
        "different_contexts_prefer_different_hypotheses": len(set(winners.values())) == len(contexts),
        "ledger_unchanged_by_ranking": ledger_hash_before == ledger_hash_after,
        "every_score_decomposes_to_entries": all(
            abs(next(r["score"] for r in rankings[c] if r["hypothesis_id"] == h) -
                sum(x["contribution"] for x in contribution_rows if x["context_id"] == c and x["hypothesis_id"] == h)) < 1e-12
            for c in contexts for h in ("hyp:H1", "hyp:H2", "hyp:H3", "hyp:H4")),
        "no_global_probability_field": all("probability" not in row for row in ledger),
        "parquet_roundtrip": pq.read_table(OUT / "evidence-ledger.parquet").num_rows == len(ledger),
    }
    assert all(validations.values())
    result = {"ledger": ledger, "weights": weights, "half_life_days": half_life_days,
              "contexts": contexts, "rankings": rankings, "winners": winners,
              "family_contributions": [{"context_id": r[0], "hypothesis_id": r[1], "family": r[2], "contribution": r[3]}
                                       for r in family_explanations],
              "context_change_explanations": changes, "ledger_sha256_before": ledger_hash_before,
              "ledger_sha256_after": ledger_hash_after, "validation": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"ledger_entry_count": len(ledger), "context_count": len(contexts), "ranking_count": len(rankings),
               "winners": winners, "distinct_winner_count": len(set(winners.values())),
               "ledger_mutation_count": 0, "verdict": "GO_CONTEXTUAL_INSPECTABLE_EVIDENCE_LEDGER_RANKING"}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "duckdb": importlib.metadata.version("duckdb"),
        "polars": importlib.metadata.version("polars"), "numpy": importlib.metadata.version("numpy"),
        "formula": "strength * family_weight * provenance_reliability * context_relevance * (1 + recency_weight * exp(-age/half_life))"}, indent=2) + "\n")
    print(f"HYP-04: winners {winners}; one unchanged ledger; GO")


if __name__ == "__main__": main()
