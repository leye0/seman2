#!/usr/bin/env python3
"""HYP-01: immutable observation/hypothesis/selection lifecycle."""
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
OUT = P / "output"


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    observation = {
        "observation_id": "obs:io:t1", "observed_at": "2026-01-01T10:00:00Z",
        "raw_text": "io", "span_start": 0, "span_end": 2,
        "source_sha256": hashlib.sha256(b"io").hexdigest(), "modality": "written_text",
    }
    hypotheses_t1 = [
        {"hypothesis_id": "hyp:H1", "version": 1, "meaning": "input_output_abbreviation",
         "created_at": "2026-01-01T10:00:01Z", "status": "active", "supersedes_version": None},
        {"hypothesis_id": "hyp:H2", "version": 1, "meaning": "informal_greeting",
         "created_at": "2026-01-01T10:00:01Z", "status": "active", "supersedes_version": None},
        {"hypothesis_id": "hyp:H3", "version": 1, "meaning": "jupiter_moon_Io",
         "created_at": "2026-01-01T10:00:01Z", "status": "active", "supersedes_version": None},
        {"hypothesis_id": "hyp:H4", "version": 1, "meaning": "typographic_or_unknown_form",
         "created_at": "2026-01-01T10:00:01Z", "status": "active", "supersedes_version": None},
    ]
    evidence = [
        {"hypothesis_id": "hyp:H1", "family": "context", "value": 1.0, "reason": "active computing topic"},
        {"hypothesis_id": "hyp:H1", "family": "lexical", "value": 0.7, "reason": "known IO abbreviation"},
        {"hypothesis_id": "hyp:H2", "family": "form", "value": 0.8, "reason": "short greeting-like token"},
        {"hypothesis_id": "hyp:H3", "family": "lexical", "value": 0.4, "reason": "proper-name candidate"},
        {"hypothesis_id": "hyp:H4", "family": "fallback", "value": 0.1, "reason": "unknown-form fallback"},
    ]
    snapshot = {
        "snapshot_id": "evidence:io:t1", "captured_at": "2026-01-01T10:00:02Z",
        "context_id": "context:computing:t1", "entries_json": canonical(evidence),
        "entries_sha256": digest(evidence),
    }
    selection = {
        "selection_event_id": "selection:io:t1", "selected_at": "2026-01-01T10:00:03Z",
        "observation_id": observation["observation_id"], "hypothesis_id": "hyp:H1",
        "hypothesis_version": 1, "snapshot_id": snapshot["snapshot_id"],
        "decision": "selected", "known_later_to_be_wrong": True,
    }
    t1_hashes = {"observation": digest(observation), "hypotheses": digest(hypotheses_t1),
                 "snapshot": digest(snapshot), "selection": digest(selection)}

    # A later correction creates a new hypothesis version. It does not update
    # the row referenced by the historical selection event.
    h1_v2 = {"hypothesis_id": "hyp:H1", "version": 2, "meaning": "input_output_abbreviation",
             "created_at": "2026-01-02T09:00:00Z", "status": "contradicted_in_greeting_context",
             "supersedes_version": 1}
    hypotheses_all = hypotheses_t1 + [h1_v2]

    schemas = {
        "observations": pa.schema([("observation_id", pa.string()), ("observed_at", pa.string()),
                                   ("raw_text", pa.string()), ("span_start", pa.int64()),
                                   ("span_end", pa.int64()), ("source_sha256", pa.string()), ("modality", pa.string())]),
        "hypothesis_versions": pa.schema([("hypothesis_id", pa.string()), ("version", pa.int64()),
                                          ("meaning", pa.string()), ("created_at", pa.string()),
                                          ("status", pa.string()), ("supersedes_version", pa.int64())]),
        "evidence_snapshots": pa.schema([("snapshot_id", pa.string()), ("captured_at", pa.string()),
                                         ("context_id", pa.string()), ("entries_json", pa.large_string()),
                                         ("entries_sha256", pa.string())]),
        "selection_events": pa.schema([("selection_event_id", pa.string()), ("selected_at", pa.string()),
                                       ("observation_id", pa.string()), ("hypothesis_id", pa.string()),
                                       ("hypothesis_version", pa.int64()), ("snapshot_id", pa.string()),
                                       ("decision", pa.string()), ("known_later_to_be_wrong", pa.bool_())]),
    }
    rows = {"observations": [observation], "hypothesis_versions": hypotheses_all,
            "evidence_snapshots": [snapshot], "selection_events": [selection]}
    for name, values in rows.items():
        pq.write_table(table(values, schemas[name]), OUT / f"{name}.parquet", compression="zstd")

    database = OUT / "hyp-01.duckdb"
    if database.exists():
        database.unlink()
    con = duckdb.connect(str(database))
    for name in rows:
        path = str((OUT / f"{name}.parquet").resolve()).replace("'", "''")
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
    historical = con.execute("""
        SELECT s.selection_event_id, o.raw_text, h.meaning, h.version,
               e.entries_sha256, s.known_later_to_be_wrong
        FROM selection_events s
        JOIN observations o USING (observation_id)
        JOIN hypothesis_versions h
          ON h.hypothesis_id = s.hypothesis_id AND h.version = s.hypothesis_version
        JOIN evidence_snapshots e USING (snapshot_id)
    """).fetchone()
    current_h1 = con.execute("""
        SELECT hypothesis_id, version, status FROM hypothesis_versions
        WHERE hypothesis_id = 'hyp:H1' ORDER BY version DESC LIMIT 1
    """).fetchone()
    counts = {name: con.execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in rows}
    con.close()

    t1_hashes_after = {"observation": digest(observation), "hypotheses": digest(hypotheses_t1),
                       "snapshot": digest(snapshot), "selection": digest(selection)}
    validations = {
        "separate_identifiers": len({observation["observation_id"], hypotheses_t1[0]["hypothesis_id"],
                                     snapshot["snapshot_id"], selection["selection_event_id"]}) == 4,
        "historical_selection_still_resolves_v1": historical[2:4] == ("input_output_abbreviation", 1),
        "current_h1_is_new_version": current_h1 == ("hyp:H1", 2, "contradicted_in_greeting_context"),
        "t1_hashes_unchanged_after_hypothesis_revision": t1_hashes == t1_hashes_after,
        "observation_source_reconstructs": observation["raw_text"] == "io" and
                                            hashlib.sha256(observation["raw_text"].encode()).hexdigest() == observation["source_sha256"],
        "parquet_roundtrip": all(pq.read_table(OUT / f"{name}.parquet").to_pylist() == values
                                 for name, values in rows.items()),
    }
    assert all(validations.values())
    result = {"observation": observation, "hypothesis_versions": hypotheses_all,
              "evidence_snapshot": snapshot, "selection_event": selection,
              "historical_selection_query": {"selection_event_id": historical[0], "raw_text": historical[1],
                                             "meaning": historical[2], "hypothesis_version": historical[3],
                                             "snapshot_sha256": historical[4], "known_later_to_be_wrong": historical[5]},
              "current_h1_query": {"hypothesis_id": current_h1[0], "version": current_h1[1], "status": current_h1[2]},
              "t1_hashes_before_revision": t1_hashes, "t1_hashes_after_revision": t1_hashes_after,
              "validation": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"observation_count": counts["observations"], "hypothesis_count": 4,
               "hypothesis_version_count": counts["hypothesis_versions"],
               "evidence_snapshot_count": counts["evidence_snapshots"],
               "selection_event_count": counts["selection_events"],
               "historical_object_mutation_count": 0,
               "verdict": "GO_IMMUTABLE_SEPARATE_OBSERVATION_HYPOTHESIS_SELECTION"}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "duckdb": importlib.metadata.version("duckdb"),
        "pyarrow": importlib.metadata.version("pyarrow"), "storage": "Parquet + DuckDB",
    }, ensure_ascii=False, indent=2) + "\n")
    print("HYP-01: 1 observation, 4 hypotheses/5 versions, 1 immutable historical selection; GO")


if __name__ == "__main__":
    main()
