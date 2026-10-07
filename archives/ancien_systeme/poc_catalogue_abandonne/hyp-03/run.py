#!/usr/bin/env python3
"""HYP-03: append-only temporal revision of the io lifecycle."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
OUT = P / "output"


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def main() -> None:
    hyp01_path = ROOT / "poc/hyp-01/output/results.json"
    hyp02_path = ROOT / "poc/hyp-02/output/results.json"
    hyp04_path = ROOT / "poc/hyp-04/output/results.json"
    hyp01 = json.loads(hyp01_path.read_text())
    hyp02 = json.loads(hyp02_path.read_text())
    hyp04 = json.loads(hyp04_path.read_text())
    assert hyp02["upstream"]["result_sha256"] == hashlib.sha256(hyp01_path.read_bytes()).hexdigest()
    assert hyp04["validation"]["different_contexts_prefer_different_hypotheses"] is True
    observation_t1 = hyp01["observation"]
    selection_t1 = hyp01["selection_event"]
    snapshot_t1 = hyp01["evidence_snapshot"]
    immutable_before = {"observation": digest(observation_t1), "selection": digest(selection_t1),
                        "snapshot": digest(snapshot_t1)}

    observations = [
        {"observation_id": "obs:io:t1", "observed_at": "2026-01-01T10:00:00Z", "raw_text": "io"},
        {"observation_id": "obs:io:t2", "observed_at": "2026-01-05T09:00:00Z", "raw_text": "io"},
    ]
    ledger = [
        {"entry_id": "ev:001", "recorded_at": "2026-01-01T10:00:01Z", "available_from": "2026-01-01T10:00:01Z",
         "hypothesis_id": "hyp:H1", "observation_id": "obs:io:t1", "family": "context", "contribution": 1.3,
         "kind": "support", "reason": "computing context at t1", "retrospective": False},
        {"entry_id": "ev:002", "recorded_at": "2026-01-01T10:00:01Z", "available_from": "2026-01-01T10:00:01Z",
         "hypothesis_id": "hyp:H1", "observation_id": "obs:io:t1", "family": "lexical", "contribution": 0.7,
         "kind": "support", "reason": "IO abbreviation candidate", "retrospective": False},
        {"entry_id": "ev:003", "recorded_at": "2026-01-01T10:00:01Z", "available_from": "2026-01-01T10:00:01Z",
         "hypothesis_id": "hyp:H2", "observation_id": "obs:io:t1", "family": "form", "contribution": 0.5,
         "kind": "support", "reason": "short greeting-like form", "retrospective": False},
        {"entry_id": "ev:004", "recorded_at": "2026-01-02T12:00:00Z", "available_from": "2026-01-02T12:00:00Z",
         "hypothesis_id": "hyp:H2", "observation_id": "episode:greeting:1", "family": "episodic", "contribution": 1.4,
         "kind": "support", "reason": "same speaker uses io as greeting", "retrospective": False},
        {"entry_id": "ev:005", "recorded_at": "2026-01-03T12:00:00Z", "available_from": "2026-01-03T12:00:00Z",
         "hypothesis_id": "hyp:H3", "observation_id": "episode:astronomy:1", "family": "episodic", "contribution": 0.8,
         "kind": "support", "reason": "Io occurs in astronomy episode", "retrospective": False},
        {"entry_id": "ev:006", "recorded_at": "2026-01-04T15:00:00Z", "available_from": "2026-01-04T15:00:00Z",
         "hypothesis_id": "hyp:H1", "observation_id": "correction:1", "family": "explicit_correction", "contribution": -2.4,
         "kind": "contradiction", "reason": "speaker says previous io meant hello", "retrospective": False},
        {"entry_id": "ev:007", "recorded_at": "2026-01-04T15:00:00Z", "available_from": "2026-01-04T15:00:00Z",
         "hypothesis_id": "hyp:H2", "observation_id": "correction:1", "family": "explicit_correction", "contribution": 2.5,
         "kind": "support", "reason": "speaker confirms greeting reading", "retrospective": False},
        {"entry_id": "ev:008", "recorded_at": "2026-01-04T15:00:01Z", "available_from": "2026-01-04T15:00:01Z",
         "hypothesis_id": "hyp:H2", "observation_id": "obs:io:t1", "family": "retrospective_link", "contribution": 0.0,
         "kind": "link", "reason": "later correction linked back to t1", "retrospective": True},
        {"entry_id": "ev:009", "recorded_at": "2026-01-05T09:00:01Z", "available_from": "2026-01-05T09:00:01Z",
         "hypothesis_id": "hyp:H2", "observation_id": "obs:io:t2", "family": "current_context", "contribution": 1.2,
         "kind": "support", "reason": "dialogue opening at t2", "retrospective": False},
        {"entry_id": "ev:010", "recorded_at": "2026-01-05T09:00:01Z", "available_from": "2026-01-05T09:00:01Z",
         "hypothesis_id": "hyp:H1", "observation_id": "obs:io:t2", "family": "current_context", "contribution": 0.2,
         "kind": "support", "reason": "weak computing residue", "retrospective": False},
    ]
    selection_events = [selection_t1, {
        "selection_event_id": "selection:io:t2", "selected_at": "2026-01-05T09:00:03Z",
        "observation_id": "obs:io:t2", "hypothesis_id": "hyp:H2", "hypothesis_version": 1,
        "snapshot_id": "evidence:io:t2", "decision": "selected", "known_later_to_be_wrong": False,
    }]
    ledger_schema = pa.schema([(key, kind) for key, kind in (
        ("entry_id", pa.string()), ("recorded_at", pa.string()), ("available_from", pa.string()),
        ("hypothesis_id", pa.string()), ("observation_id", pa.string()), ("family", pa.string()),
        ("contribution", pa.float64()), ("kind", pa.string()), ("reason", pa.string()), ("retrospective", pa.bool_()))])
    OUT.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(ledger, schema=ledger_schema), OUT / "evidence-ledger.parquet", compression="zstd")
    db = OUT / "hyp-03.duckdb"
    if db.exists(): db.unlink()
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE ledger AS SELECT * FROM read_parquet(?)", [str((OUT / "evidence-ledger.parquet").resolve())])
    candidates = sorted(hyp02["explanations"])
    assert candidates == ["hyp:H1", "hyp:H2", "hyp:H3", "hyp:H4"]
    con.execute("CREATE TABLE candidates(id VARCHAR)")
    con.executemany("INSERT INTO candidates VALUES (?)", [(x,) for x in candidates])

    def ranking(cutoff: str):
        rows = con.execute("""
            SELECT c.id, coalesce(sum(l.contribution), 0.0) score,
                   list(l.entry_id ORDER BY l.recorded_at) FILTER (WHERE l.entry_id IS NOT NULL) entries
            FROM candidates c LEFT JOIN ledger l ON c.id=l.hypothesis_id AND l.available_from <= ?
            GROUP BY c.id ORDER BY score DESC, c.id
        """, [cutoff]).fetchall()
        return [{"hypothesis_id": row[0], "score": row[1], "entry_ids": row[2] or []} for row in rows]

    rank_t1 = ranking("2026-01-01T10:00:03Z")
    rank_t2 = ranking("2026-01-05T09:00:03Z")
    con.close()
    snapshot_t2 = {"snapshot_id": "evidence:io:t2", "captured_at": "2026-01-05T09:00:02Z",
                   "ranking": rank_t2, "ledger_prefix_sha256": digest(ledger)}
    immutable_after = {"observation": digest(observation_t1), "selection": digest(selection_t1),
                       "snapshot": digest(snapshot_t1)}
    retrospective = [row for row in ledger if row["retrospective"]]
    validations = {
        "t1_selection_is_H1": selection_t1["hypothesis_id"] == "hyp:H1" and rank_t1[0]["hypothesis_id"] == "hyp:H1",
        "t2_selection_is_H2": selection_events[1]["hypothesis_id"] == "hyp:H2" and rank_t2[0]["hypothesis_id"] == "hyp:H2",
        "t1_objects_unchanged": immutable_before == immutable_after,
        "retrospective_links_recorded_after_t1": all(row["recorded_at"] > selection_t1["selected_at"] for row in retrospective),
        "ledger_append_only_ids_unique": len({row["entry_id"] for row in ledger}) == len(ledger),
        "h2_and_h3_receive_intermediate_support": all(any(row["hypothesis_id"] == h and row["family"] == "episodic" for row in ledger)
                                                      for h in ("hyp:H2", "hyp:H3")),
        "parquet_roundtrip": pq.read_table(OUT / "evidence-ledger.parquet").to_pylist() == ledger,
        "contextual_ranker_confirms_t1_computing_winner": hyp04["winners"]["computing"] == "hyp:H1",
        "contextual_ranker_confirms_t2_greeting_winner": hyp04["winners"]["greeting"] == "hyp:H2",
        "hyp02_candidate_set_reused": candidates == sorted(hyp02["explanations"]),
    }
    assert all(validations.values())
    result = {"observations": observations, "ledger": ledger, "ranking_t1": rank_t1, "ranking_t2": rank_t2,
              "selection_events": selection_events, "snapshot_t1": snapshot_t1, "snapshot_t2": snapshot_t2,
              "immutable_hashes_before": immutable_before, "immutable_hashes_after": immutable_after,
              "upstream": {
                  "hyp01_result_sha256": hashlib.sha256(hyp01_path.read_bytes()).hexdigest(),
                  "hyp02_result_sha256": hashlib.sha256(hyp02_path.read_bytes()).hexdigest(),
                  "hyp04_result_sha256": hashlib.sha256(hyp04_path.read_bytes()).hexdigest(),
                  "t1_selection_cognitive_artifact_id": hyp01["runtime"]["selection_event_id"],
                  "candidate_cognitive_artifact_ids": hyp02["upstream"]["hypothesis_artifact_ids"],
                  "contextual_ranker_winners": hyp04["winners"],
              },
              "validation": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"ledger_entry_count": len(ledger), "retrospective_link_count": len(retrospective),
               "t1_winner": rank_t1[0]["hypothesis_id"], "t2_winner": rank_t2[0]["hypothesis_id"],
               "historical_mutation_count": 0, "ranking_changed": rank_t1[0]["hypothesis_id"] != rank_t2[0]["hypothesis_id"],
               "upstream_poc_count": 3,
               "cognitive_artifact_refs_preserved": True,
               "verdict": "GO_NON_DESTRUCTIVE_TEMPORAL_REVISION"}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "duckdb": importlib.metadata.version("duckdb"),
        "pyarrow": importlib.metadata.version("pyarrow"), "ranking": "sum of available ledger contributions at cutoff"}, indent=2) + "\n")
    print("HYP-03: winner H1 at t1 -> H2 at t2; 0 historical mutations; GO")


if __name__ == "__main__": main()
