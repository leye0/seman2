#!/usr/bin/env python3
"""STAT-01: quantitative induction signals on structured occurrences."""
from __future__ import annotations

import importlib.metadata
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from scipy.stats import pointbiserialr

P = Path(__file__).resolve().parent
OUT = P / "output"
ROOT = P.parents[1]


def load_json_with_hash(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def make_occurrences() -> list[dict]:
    rows = []
    contexts = ("work", "home", "shop")
    for session in range(120):
        context = contexts[session % len(contexts)]
        window = session // 40
        offered = session % 4 != 0
        exception = offered and session % 10 == 0
        middle = "ask" if session % 5 != 0 else "browse"
        final = "buy" if offered and not exception else "leave"
        success = final == "buy" or session % 17 == 0
        actions = ("greet", middle, final)
        for position, action in enumerate(actions):
            rows.append({
                "occurrence_id": f"s{session:03d}-e{position}",
                "session_id": f"s{session:03d}",
                "position": position,
                "time_window": window,
                "context": context,
                "cue": "offer" if offered else "none",
                "action": action,
                "outcome_success": success,
                "is_offer_counterexample": bool(offered and final != "buy"),
            })
    return rows


def rows_as_dicts(cursor) -> list[dict]:
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    occurrences = make_occurrences()
    frame = pl.DataFrame(occurrences)
    parquet = OUT / "occurrences.parquet"
    frame.write_parquet(parquet, compression="zstd")
    con = duckdb.connect()
    path_sql = str(parquet.resolve()).replace("'", "''")
    con.execute(f"CREATE VIEW occurrences AS SELECT * FROM read_parquet('{path_sql}')")
    con.execute("""
        CREATE VIEW sessions AS
        SELECT session_id, any_value(time_window) AS time_window, any_value(context) AS context,
               bool_or(cue = 'offer') AS offered, bool_or(action = 'buy') AS bought,
               bool_or(outcome_success) AS outcome_success
        FROM occurrences GROUP BY session_id
    """)

    frequency = rows_as_dicts(con.execute("SELECT action, count(*) AS count, count(*) / sum(count(*)) OVER () AS rate FROM occurrences GROUP BY action ORDER BY action"))
    conditional = con.execute("SELECT avg(bought::INT) FROM sessions WHERE offered").fetchone()[0]
    support = con.execute("SELECT avg((offered AND bought)::INT) FROM sessions").fetchone()[0]
    counterexamples = [r[0] for r in con.execute("SELECT session_id FROM sessions WHERE offered AND NOT bought ORDER BY session_id").fetchall()]
    context_distribution = rows_as_dicts(con.execute("SELECT action, context, count(*) AS count FROM occurrences GROUP BY action, context ORDER BY action, context"))
    cooccurrence = rows_as_dicts(con.execute("""
        WITH flags AS (SELECT session_id, bool_or(action='ask') AS has_ask, bool_or(action='buy') AS has_buy FROM occurrences GROUP BY session_id)
        SELECT sum((has_ask AND has_buy)::INT) AS ask_buy_count, avg((has_ask AND has_buy)::INT) AS ask_buy_rate FROM flags
    """))[0]
    transitions = rows_as_dicts(con.execute("""
        WITH ordered AS (
          SELECT action AS source, lead(action) OVER (PARTITION BY session_id ORDER BY position) AS target
          FROM occurrences
        )
        SELECT source, target, count(*) AS count FROM ordered WHERE target IS NOT NULL GROUP BY source, target ORDER BY source, target
    """))
    window_rates = rows_as_dicts(con.execute("SELECT time_window, avg(bought::INT) AS buy_rate FROM sessions GROUP BY time_window ORDER BY time_window"))
    rates = np.array([r["buy_rate"] for r in window_rates], dtype=float)
    stability = float(1.0 - np.std(rates, ddof=0) / np.mean(rates))

    session_rows = con.execute("SELECT bought::INT, outcome_success::INT FROM sessions ORDER BY session_id").fetchall()
    bought = np.array([r[0] for r in session_rows], dtype=np.int8)
    success = np.array([r[1] for r in session_rows], dtype=np.int8)
    corr = pointbiserialr(bought, success)

    # The controlled corpus above is the numerical oracle.  This second path
    # measures matter actually learned upstream instead of presenting the
    # oracle itself as evidence that the cognitive flow is connected.
    sem06_path = ROOT / "poc/sem-06/output/results.json"
    ret03_path = ROOT / "poc/ret-03/output/results.json"
    sem06, sem06_sha256 = load_json_with_hash(sem06_path)
    ret03, ret03_sha256 = load_json_with_hash(ret03_path)
    learned = sem06["learned_relation"]
    learned_supports = sem06["supports"]
    learned_contradictions = sem06["contradictions"]
    learned_total = len(learned_supports) + len(learned_contradictions)
    learned_conditional = len(learned_supports) / learned_total
    temporal_match = ret03["integrated_sem06"]["match"]
    integrated_sem06_signals = {
        "source": {
            "poc": "SEM-06",
            "results_path": str(sem06_path.relative_to(ROOT)),
            "results_sha256": sem06_sha256,
        },
        "temporal_retrieval": {
            "poc": "RET-03",
            "results_path": str(ret03_path.relative_to(ROOT)),
            "results_sha256": ret03_sha256,
            "final_constraints": temporal_match["final_constraints"],
            "cross_stage_entity_links": temporal_match["cross_stage_entity_links"],
        },
        "relation_id": learned["relation_id"],
        "learned_relation_artifact_id": sem06["learned_relation_artifact_id"],
        "support_refs": learned_supports,
        "contradiction_refs": learned_contradictions,
        "support_count": len(learned_supports),
        "contradiction_count": len(learned_contradictions),
        "conditional_probability": learned_conditional,
        "credible_interval_95": learned["credible_interval_95"],
        "heldout_prediction_correct": sem06["heldout_prediction"]["correct"],
    }

    # Independent Polars and NumPy computations prevent a single-engine false positive.
    polars_frequency = (frame.group_by("action").len().sort("action").to_dicts())
    final_rows = frame.filter(pl.col("position") == 2)
    polars_conditional = final_rows.filter(pl.col("cue") == "offer").select((pl.col("action") == "buy").mean()).item()
    actions = sorted(frame.get_column("action").unique().to_list())
    action_index = {action: i for i, action in enumerate(actions)}
    matrix = np.zeros((len(actions), len(actions)), dtype=np.int64)
    for session in range(120):
        seq = [occurrences[session * 3 + i]["action"] for i in range(3)]
        for source, target in zip(seq, seq[1:]):
            matrix[action_index[source], action_index[target]] += 1
    numpy_transitions = [
        {"source": source, "target": target, "count": int(matrix[action_index[source], action_index[target]])}
        for source in actions for target in actions if matrix[action_index[source], action_index[target]]
    ]

    expected = {
        "sessions": 120,
        "occurrences": 360,
        "offered_sessions": 90,
        "bought_sessions": 84,
        "counterexamples": 6,
    }
    validations = {
        "row_counts": len(occurrences) == expected["occurrences"] and len(session_rows) == expected["sessions"],
        "known_offer_and_buy_counts": int(final_rows.filter(pl.col("cue") == "offer").height) == expected["offered_sessions"] and int(bought.sum()) == expected["bought_sessions"],
        "known_counterexample_count": len(counterexamples) == expected["counterexamples"],
        "duckdb_polars_frequency_equal": [(r["action"], r["count"]) for r in frequency] == [(r["action"], r["len"]) for r in polars_frequency],
        "duckdb_polars_conditional_equal": abs(conditional - polars_conditional) < 1e-12,
        "duckdb_numpy_transitions_equal": transitions == sorted(numpy_transitions, key=lambda r: (r["source"], r["target"])),
        "conditional_probability_valid": abs(conditional - 84 / 90) < 1e-12,
        "support_valid": abs(support - 84 / 120) < 1e-12,
        "stability_finite_and_bounded": bool(np.isfinite(stability) and 0 <= stability <= 1),
        "outcome_correlation_finite": bool(np.isfinite(corr.statistic) and np.isfinite(corr.pvalue)),
        "sem06_support_refs_exact": learned_supports == learned["support_refs"],
        "sem06_contradiction_refs_exact": learned_contradictions == learned["contradiction_refs"],
        "sem06_conditional_recomputed": abs(learned_conditional - learned["conditional_probability"]) < 1e-12,
        "sem06_support_and_counterexample_present": len(learned_supports) > 0 and len(learned_contradictions) > 0,
        "sem06_heldout_prediction_correct": sem06["heldout_prediction"]["correct"] is True,
        "ret03_temporal_constraints_sat": temporal_match["final_constraints"] == "SAT",
        "ret03_temporal_links_preserved": all(temporal_match["cross_stage_entity_links"].values()),
        "ret03_reads_same_sem06_output": ret03["integrated_sem06"]["source_sha256"] == sem06_sha256,
    }
    assert all(validations.values()), validations
    result = {
        "dataset": expected,
        "frequency": frequency,
        "conditional_probability": {"predicate": "buy | offer", "value": conditional},
        "transition_counts": transitions,
        "transition_matrix": {"actions": actions, "counts": matrix.tolist()},
        "cooccurrence": {"ask_and_buy": cooccurrence},
        "rule_support": {"rule": "offer => buy", "support_over_all_sessions": support},
        "counterexamples": {"rule": "offer => buy", "session_ids": counterexamples},
        "context_distribution": context_distribution,
        "stability": {"definition": "1 - population_cv(buy_rate_by_window)", "window_rates": window_rates, "value": stability},
        "outcome_correlation": {"feature": "bought", "outcome": "success", "method": "SciPy point-biserial", "coefficient": float(corr.statistic), "p_value": float(corr.pvalue)},
        "integrated_sem06_signals": integrated_sem06_signals,
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "occurrences": len(occurrences), "sessions": len(session_rows), "conditional_buy_given_offer": conditional,
        "support_offer_implies_buy": support, "counterexample_count": len(counterexamples), "stability": stability,
        "outcome_correlation": float(corr.statistic), "verdict": "GO_QUANTITATIVE_SIGNALS",
        "integrated_sem06_support_count": len(learned_supports),
        "integrated_sem06_contradiction_count": len(learned_contradictions),
        "integrated_sem06_conditional_probability": learned_conditional,
        "integrated_sem06_heldout_prediction_correct": sem06["heldout_prediction"]["correct"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "duckdb": importlib.metadata.version("duckdb"), "polars": importlib.metadata.version("polars"),
        "numpy": importlib.metadata.version("numpy"), "scipy": importlib.metadata.version("scipy"),
        "stability_definition": "1 - population coefficient of variation across three equal session windows",
    }, indent=2) + "\n")
    print(f"STAT-01: {len(occurrences)} occurrences; {len(counterexamples)} counterexamples; GO")


if __name__ == "__main__":
    main()
