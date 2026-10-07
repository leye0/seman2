#!/usr/bin/env python3
"""HYP-08: reversible hot/warm/cold pruning with provenance preservation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import zstandard as zstd

P = Path(__file__).resolve().parent
OUT = P / "output"
ROOT = P.parents[1]

METRICS = [
    ("H00", 14, 0, .95, .10, 2), ("H01", 11, 1, .83, .20, 3), ("H02", 9, 1, .72, .25, 4),
    ("H03", 7, 1, .62, .30, 4), ("H04", 6, 2, .55, .35, 5), ("H05", 5, 1, .48, .45, 5),
    ("H06", 4, 2, .42, .50, 6), ("H07", 3, 1, .35, .55, 6), ("H08", 2, 3, .25, .65, 7),
    ("H09", 2, 1, .18, .70, 8), ("H10", 5, 4, .20, .88, 9), ("H11", 1, 0, .10, .92, 10),
]


def state(support: int, contradictions: int, recency: float, redundancy: float, cost: int) -> str:
    if support >= 9 and contradictions <= 1 and recency >= .7:
        return "hot"
    if support <= 3 or redundancy >= .8 or (cost >= 8 and recency < .4):
        return "cold"
    return "warm"


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derived(hypothesis_id: str, observations: list[dict], edges: list[dict]) -> dict:
    positive = sorted(o["observation_id"] for o in observations if o["polarity"] == "support")
    negative = sorted(o["observation_id"] for o in observations if o["polarity"] == "contradict")
    return {
        "hypothesis_id": hypothesis_id,
        "support_postings": positive,
        "contradiction_postings": negative,
        "justification_edges": sorted((e["source_id"], e["target_id"], e["relation"]) for e in edges),
        "aggregate": {"support": len(positive), "contradictions": len(negative)},
    }


def write_parquet(rows: list[dict], path: Path) -> None:
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def load_json_with_hash(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def integrated_cold_storage(compressor: zstd.ZstdCompressor) -> tuple[dict, dict[str, bool]]:
    """Prune and restore one actual HYP-02/04 hypothesis via HYP-06 postings."""
    hyp06_path = ROOT / "poc/hyp-06/output/results.json"
    hyp04_path = ROOT / "poc/hyp-04/output/results.json"
    hyp06, hyp06_sha256 = load_json_with_hash(hyp06_path)
    hyp04, hyp04_sha256 = load_json_with_hash(hyp04_path)
    sharing = hyp06["integrated_hypothesis_sharing"]
    closures = sharing["reconstructed_closures"]
    artifact_ids = sharing["hypothesis_artifact_ids"]
    ledger_by_hypothesis: dict[str, list[str]] = {hypothesis_id: [] for hypothesis_id in closures}
    for entry in hyp04["ledger"]:
        ledger_by_hypothesis[entry["hypothesis_id"]].append(entry["entry_id"])

    def actual_derived(hypothesis_id: str) -> dict:
        return {
            "hypothesis_id": hypothesis_id,
            "hypothesis_artifact_id": artifact_ids[hypothesis_id],
            "shared_node_refs": sorted(closures[hypothesis_id]),
            "evidence_ledger_refs": sorted(ledger_by_hypothesis[hypothesis_id]),
        }

    actual_before = []
    for hypothesis_id in sorted(closures):
        encoded = stable_json(actual_derived(hypothesis_id))
        actual_before.append({
            "hypothesis_id": hypothesis_id,
            "state": "hot" if hypothesis_id in {"hyp:H1", "hyp:H2", "hyp:H3"} else "cold",
            "derived_json": encoded,
            "derived_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        })
    cold_hypothesis_id = "hyp:H4"
    actual_after = [row for row in actual_before if row["hypothesis_id"] != cold_hypothesis_id]
    cold_before = next(row for row in actual_before if row["hypothesis_id"] == cold_hypothesis_id)
    source_hashes_before = {
        "hyp06_results_sha256": hyp06_sha256,
        "hyp04_results_sha256": hyp04_sha256,
    }
    archive_bundle = {
        "hypothesis_id": cold_hypothesis_id,
        "hypothesis_artifact_id": artifact_ids[cold_hypothesis_id],
        "shared_node_refs": closures[cold_hypothesis_id],
        "evidence_ledger_refs": ledger_by_hypothesis[cold_hypothesis_id],
        "derived_sha256_before_pruning": cold_before["derived_sha256"],
        "source_hashes": source_hashes_before,
    }
    packed = compressor.compress(stable_json(archive_bundle).encode())
    write_parquet(actual_before, OUT / "integrated-active-before.parquet")
    write_parquet(actual_after, OUT / "integrated-active-after-pruning.parquet")
    write_parquet([{
        "hypothesis_id": cold_hypothesis_id,
        "archive_payload_zstd": packed,
        "payload_sha256": hashlib.sha256(packed).hexdigest(),
        "derived_sha256_before_pruning": cold_before["derived_sha256"],
    }], OUT / "integrated-cold-archive.parquet")

    start = time.perf_counter_ns()
    archive_row = pq.read_table(OUT / "integrated-cold-archive.parquet").to_pylist()[0]
    restored_bundle = json.loads(zstd.ZstdDecompressor().decompress(archive_row["archive_payload_zstd"]))
    hyp06_after, hyp06_sha256_after = load_json_with_hash(hyp06_path)
    hyp04_after, hyp04_sha256_after = load_json_with_hash(hyp04_path)
    restored_closure = hyp06_after["integrated_hypothesis_sharing"]["reconstructed_closures"][cold_hypothesis_id]
    restored_ledger_refs = sorted(
        entry["entry_id"] for entry in hyp04_after["ledger"]
        if entry["hypothesis_id"] == cold_hypothesis_id
    )
    regenerated = stable_json({
        "hypothesis_id": cold_hypothesis_id,
        "hypothesis_artifact_id": restored_bundle["hypothesis_artifact_id"],
        "shared_node_refs": sorted(restored_closure),
        "evidence_ledger_refs": restored_ledger_refs,
    })
    regenerated_hash = hashlib.sha256(regenerated.encode()).hexdigest()
    latency_ns = time.perf_counter_ns() - start
    actual_reactivated = actual_after + [{
        "hypothesis_id": cold_hypothesis_id,
        "state": "hot",
        "derived_json": regenerated,
        "derived_sha256": regenerated_hash,
    }]
    write_parquet(actual_reactivated, OUT / "integrated-active-reactivated.parquet")

    details = {
        "sources": source_hashes_before,
        "cold_hypothesis_id": cold_hypothesis_id,
        "hypothesis_artifact_id": restored_bundle["hypothesis_artifact_id"],
        "preserved_shared_node_refs": restored_closure,
        "preserved_evidence_ledger_refs": restored_ledger_refs,
        "active_count_before": len(actual_before),
        "active_count_after_pruning": len(actual_after),
        "active_count_after_reactivation": len(actual_reactivated),
        "expected_derived_sha256": cold_before["derived_sha256"],
        "regenerated_derived_sha256": regenerated_hash,
        "reactivation_latency_ns": latency_ns,
        "trigger": {"context": "unknown-form-context", "reason": "fallback hypothesis becomes relevant"},
        "equivalence": "bit-exact canonical JSON",
    }
    validations = {
        "actual_cold_hypothesis_removed_from_active_index": cold_hypothesis_id not in {row["hypothesis_id"] for row in actual_after},
        "actual_sources_immutable_during_pruning": hyp06_sha256_after == hyp06_sha256 and hyp04_sha256_after == hyp04_sha256,
        "actual_archive_source_hashes_preserved": restored_bundle["source_hashes"] == source_hashes_before,
        "actual_observation_and_justification_refs_preserved": restored_bundle["shared_node_refs"] == restored_closure and sorted(restored_bundle["evidence_ledger_refs"]) == restored_ledger_refs,
        "actual_artifact_identity_preserved": restored_bundle["hypothesis_artifact_id"] == artifact_ids[cold_hypothesis_id],
        "actual_reactivation_bit_exact": regenerated_hash == cold_before["derived_sha256"] == archive_row["derived_sha256_before_pruning"],
        "actual_reactivated_once": sum(row["hypothesis_id"] == cold_hypothesis_id for row in actual_reactivated) == 1,
    }
    return details, validations


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    observations, justifications, hypotheses, before_rows = [], [], [], []
    for hid, support, contradictions, recency, redundancy, cost in METRICS:
        current_state = state(support, contradictions, recency, redundancy, cost)
        hypotheses.append({"hypothesis_id": hid, "support": support, "contradictions": contradictions, "recency": recency, "redundancy": redundancy, "indexing_cost": cost, "state": current_state})
        local_obs = []
        for i in range(support + contradictions):
            row = {"observation_id": f"obs-{hid}-{i:02d}", "hypothesis_id": hid, "polarity": "support" if i < support else "contradict", "source_id": f"source-{(i * 7 + int(hid[1:])) % 23:02d}", "payload": f"immutable-evidence-{hid}-{i:02d}"}
            observations.append(row); local_obs.append(row)
        local_edges = [{"source_id": o["observation_id"], "target_id": hid, "relation": o["polarity"], "rule_id": "aggregate-v1"} for o in local_obs]
        justifications.extend(local_edges)
        data = derived(hid, local_obs, local_edges)
        encoded = stable_json(data)
        before_rows.append({"hypothesis_id": hid, "state": current_state, "derived_json": encoded, "derived_sha256": hashlib.sha256(encoded.encode()).hexdigest()})

    write_parquet(observations, OUT / "observation-ledger.parquet")
    write_parquet(justifications, OUT / "justifications.parquet")
    write_parquet(hypotheses, OUT / "hypotheses.parquet")
    write_parquet(before_rows, OUT / "active-index-before.parquet")
    cold_ids = sorted(h["hypothesis_id"] for h in hypotheses if h["state"] == "cold")
    after_rows = [r for r in before_rows if r["hypothesis_id"] not in cold_ids]
    write_parquet(after_rows, OUT / "active-index-after-pruning.parquet")

    compressor = zstd.ZstdCompressor(level=12)
    archive_rows = []
    for hid in cold_ids:
        hypothesis = next(h for h in hypotheses if h["hypothesis_id"] == hid)
        bundle = {"hypothesis": hypothesis, "observation_ids": sorted(o["observation_id"] for o in observations if o["hypothesis_id"] == hid), "justification_edge_count": sum(e["target_id"] == hid for e in justifications), "derived_sha256_before_pruning": next(r["derived_sha256"] for r in before_rows if r["hypothesis_id"] == hid)}
        packed = compressor.compress(stable_json(bundle).encode())
        archive_rows.append({"hypothesis_id": hid, "archive_payload_zstd": packed, "payload_sha256": hashlib.sha256(packed).hexdigest(), "observation_count": len(bundle["observation_ids"]), "derived_sha256_before_pruning": bundle["derived_sha256_before_pruning"]})
    write_parquet(archive_rows, OUT / "cold-archive.parquet")
    archive_path = OUT / "cold-archive.parquet"
    manifest = {
        "archive": archive_path.name, "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "cold_hypothesis_ids": cold_ids,
        "preserved": ["observation ledger", "justification ledger", "hypothesis metadata", "pre-pruning derived hash"],
        "removed_from_active_index": ["support postings", "contradiction postings", "justification adjacency", "cached aggregates"],
        "removal_policy": "only deterministic derived structures are removed",
    }
    (OUT / "archive-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    db = OUT / "hyp-08.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    for name, filename in (("observations", "observation-ledger.parquet"), ("justifications", "justifications.parquet"), ("active_after", "active-index-after-pruning.parquet"), ("archive", "cold-archive.parquet")):
        path = str((OUT / filename).resolve()).replace("'", "''")
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    trigger = {"hypothesis_id": "H09", "context": "new-context-laboratory", "reason": "new evidence makes archived structure relevant"}
    start = time.perf_counter_ns()
    obs_cols = [d[0] for d in con.execute("SELECT * FROM observations WHERE hypothesis_id=? ORDER BY observation_id", [trigger["hypothesis_id"]]).description]
    obs = [dict(zip(obs_cols, r)) for r in con.fetchall()]
    edge_cols = [d[0] for d in con.execute("SELECT * FROM justifications WHERE target_id=? ORDER BY source_id", [trigger["hypothesis_id"]]).description]
    edges = [dict(zip(edge_cols, r)) for r in con.fetchall()]
    archive_meta = con.execute("SELECT derived_sha256_before_pruning FROM archive WHERE hypothesis_id=?", [trigger["hypothesis_id"]]).fetchone()
    regenerated = stable_json(derived(trigger["hypothesis_id"], obs, edges))
    regenerated_hash = hashlib.sha256(regenerated.encode()).hexdigest()
    latency_ns = time.perf_counter_ns() - start
    reactivated = after_rows + [{"hypothesis_id": trigger["hypothesis_id"], "state": "hot", "derived_json": regenerated, "derived_sha256": regenerated_hash}]
    write_parquet(reactivated, OUT / "active-index-reactivated.parquet")
    con.close()

    before_size = (OUT / "active-index-before.parquet").stat().st_size
    after_size = (OUT / "active-index-after-pruning.parquet").stat().st_size
    before_count, after_count = len(before_rows), len(after_rows)
    preserved_obs = pq.read_table(OUT / "observation-ledger.parquet").num_rows
    preserved_edges = pq.read_table(OUT / "justifications.parquet").num_rows
    expected_records = sum(s + c for _, s, c, *_ in METRICS)
    integrated, integrated_validations = integrated_cold_storage(compressor)
    validations = {
        "all_three_states_present": {h["state"] for h in hypotheses} == {"hot", "warm", "cold"},
        "cold_absent_from_active_index": not ({r["hypothesis_id"] for r in after_rows} & set(cold_ids)),
        "hot_index_count_decreased": after_count < before_count,
        "hot_index_bytes_decreased": after_size < before_size,
        "all_observations_preserved": preserved_obs == expected_records,
        "all_justifications_preserved": preserved_edges == expected_records,
        "archive_manifest_complete": set(manifest["cold_hypothesis_ids"]) == set(cold_ids) and len(archive_rows) == len(cold_ids),
        "reactivation_bit_exact": archive_meta is not None and regenerated_hash == archive_meta[0],
        "reactivated_index_contains_target": any(r["hypothesis_id"] == trigger["hypothesis_id"] and r["state"] == "hot" for r in reactivated),
        **integrated_validations,
    }
    assert all(validations.values()), validations
    result = {"state_assignments": hypotheses, "manifest": manifest, "index_metrics": {"before_count": before_count, "after_pruning_count": after_count, "after_reactivation_count": len(reactivated), "before_bytes": before_size, "after_pruning_bytes": after_size, "byte_reduction": before_size - after_size}, "reactivation": {"trigger": trigger, "latency_ns": latency_ns, "observation_count": len(obs), "justification_count": len(edges), "expected_derived_sha256": archive_meta[0], "regenerated_derived_sha256": regenerated_hash, "equivalence": "bit-exact canonical JSON"}, "integrated_cold_storage": integrated, "validations": validations}
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    summary = {"states": {name: sum(h["state"] == name for h in hypotheses) for name in ("hot", "warm", "cold")}, "observations_preserved": preserved_obs, "index_entries_before": before_count, "index_entries_after_pruning": after_count, "index_byte_reduction": before_size - after_size, "reactivation_latency_ns": latency_ns, "reactivation_bit_exact": True, "integrated_cold_hypothesis": integrated["cold_hypothesis_id"], "integrated_artifact_id_preserved": integrated["hypothesis_artifact_id"], "integrated_reactivation_bit_exact": integrated["expected_derived_sha256"] == integrated["regenerated_derived_sha256"], "verdict": "GO_REVERSIBLE_COLD_STORAGE"}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "duckdb": importlib.metadata.version("duckdb"), "pyarrow": importlib.metadata.version("pyarrow"), "zstandard": importlib.metadata.version("zstandard"), "archive_zstd_level": 12, "hash": "SHA-256 over canonical compact sorted-key JSON"}, indent=2) + "\n")
    print(f"HYP-08: {len(cold_ids)} cold; active {before_count}->{after_count}; H09 bit-exact reactivated; GO")


if __name__ == "__main__":
    main()
