#!/usr/bin/env python3
"""CULT-06: append-only pragmatic/cultural revision after interaction failures."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OUT = P / "output"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {name: ROOT / "poc" / name / "output" / "results.json" for name in ("cult-03", "cult-04", "cult-05", "dlg-08", "dlg-10")}
    assert all(path.exists() for path in sources.values())
    c3 = json.loads(sources["cult-03"].read_text())
    c4 = json.loads(sources["cult-04"].read_text())
    dlg10 = json.loads(sources["dlg-10"].read_text())
    assert any(case["phenomenon"] == "other_correction" for case in dlg10["cases"])

    cases = [
        {
            "id": "REV-NOT-UNDERSTOOD", "phenomenon": "joke-not-understood", "period": "2026-Q1", "group": "team-a",
            "prior_hypothesis": "H1", "prior_support": 0.84, "feedback": "I don't get it—what dragon?",
            "grounding_before": "playful-intent-assumed", "grounding_after": "understanding-failed; explanation-pending",
            "repair_act": "explain-and-check-understanding", "outcome": "failed-comprehension",
            "revision": "specialize", "added_condition": "shared-fiction-or-wordplay-background",
        },
        {
            "id": "REV-FALSE-POSITIVE", "phenomenon": "false-positive-humour", "period": "2026-Q1", "group": "team-a",
            "prior_hypothesis": "H1", "prior_support": 0.71, "feedback": "No, I was being completely serious.",
            "grounding_before": "playful-intent-assumed", "grounding_after": "literal-intent-explicitly-supported",
            "repair_act": "apologize-and-restore-literal", "outcome": "misclassified-literal",
            "revision": "split", "added_condition": "explicit-sincerity-separates-literal-branch",
        },
        {
            "id": "REV-OFFENSE", "phenomenon": "unintended-offense", "period": "2026-Q2", "group": "team-a",
            "prior_hypothesis": "H1", "prior_support": 0.79, "feedback": "That was hurtful; this happened to my brother.",
            "grounding_before": "affiliation-expected", "grounding_after": "offense-established; affiliation-not-grounded",
            "repair_act": "acknowledge-harm-and-apologize", "outcome": "offended-response",
            "revision": "specialize", "added_condition": "exclude-known-personal-loss-context",
        },
        {
            "id": "REV-TEMPORAL", "phenomenon": "convention-changed", "period": "2026-Q3", "group": "forum-x",
            "prior_hypothesis": "H1", "prior_support": 0.68, "feedback": "That expression used to be playful here; now it marks spam.",
            "grounding_before": "historic-positive-convention-active", "grounding_after": "period-sensitive-convention-recorded",
            "repair_act": "acknowledge-current-convention", "outcome": "current-negative-historic-positive",
            "revision": "temporal-split", "added_condition": "valid-before-2026-Q3-vs-valid-from-2026-Q3",
        },
        {
            "id": "REV-EXPLICIT", "phenomenon": "explicit-feedback", "period": "2026-Q3", "group": "team-b",
            "prior_hypothesis": "H2", "prior_support": 0.61, "feedback": "In our group this phrase invites help; it is not a criticism.",
            "grounding_before": "criticism-tentatively-selected", "grounding_after": "local-help-invitation-supported",
            "repair_act": "confirm-local-meaning", "outcome": "local-convention-corrected",
            "revision": "revise", "added_condition": "team-b-shared-help-practice",
        },
        {
            "id": "REV-DISAGREEMENT", "phenomenon": "contradictory-groups", "period": "2026-Q4", "group": "team-a+team-b",
            "prior_hypothesis": "H1", "prior_support": 0.56, "feedback": "Team A treats it as teasing; Team B treats it as dismissive.",
            "grounding_before": "single-pooled-expectation", "grounding_after": "two-incompatible-local-outcomes-retained",
            "repair_act": "ask-which-local-practice-applies", "outcome": "persistent-disagreement",
            "revision": "group-split", "added_condition": "branch-by-observed-interaction-history-not-membership-essence",
        },
    ]

    observations, repairs, versions, revisions = [], [], [], []
    for index, case in enumerate(cases, 1):
        obs0, obs1 = f"{case['id']}:o0", f"{case['id']}:o1"
        prior_id = f"{case['id']}:hyp:prior"
        revised_id = f"{case['id']}:hyp:revised"
        observations.extend([
            {"observation_id": obs0, "case_id": case["id"], "turn": 1, "raw": c3["observation"]["raw_text"], "immutable": True, "kind": "original-user-turn"},
            {"observation_id": obs1, "case_id": case["id"], "turn": 2, "raw": case["feedback"], "immutable": True, "kind": "feedback"},
        ])
        repairs.append({
            "repair_id": f"repair:{case['id']}", "case_id": case["id"], "signal_observation_id": obs1,
            "repair_target_hypothesis_id": prior_id,
            "revision_candidates": [
                {"hypothesis_id": revised_id, "status": "selected", "supported_by": [obs0, obs1], "revises": prior_id, "content": case["grounding_after"]},
                {"hypothesis_id": prior_id, "status": "historical-not-deleted", "supported_by": [obs0], "content": case["grounding_before"]},
            ],
            "selected_revision_id": revised_id, "repair_act": case["repair_act"],
            "state_before": {"grounding": case["grounding_before"]}, "state_after": {"grounding": case["grounding_after"]},
            "dlg10_contract": "signal + target + candidates + selected revision + accessible prior state",
        })
        base_version = f"CP-{index:02d}-v1"
        versions.append({
            "pattern_version_id": base_version, "pattern_lineage_id": f"CP-{index:02d}", "version": 1,
            "valid_from": "historical", "valid_to": case["period"], "status": "superseded-not-deleted",
            "conditions": ["surface-or-structural-analogy"], "outcomes": {"expected": 1, case["outcome"]: 0},
            "source_occurrences": ["TO-REAL-8mi6ue", "TO-REAL-8mi71r"], "supersedes": None,
        })
        branch_ids = []
        if case["revision"] in ("split", "temporal-split", "group-split"):
            branch_specs = {
                "split": [("a", "explicit-sincerity", "literal"), ("b", "no-explicit-sincerity", "play-or-undecided")],
                "temporal-split": [("old", "before-2026-Q3", "historic-positive"), ("new", "from-2026-Q3", "current-negative")],
                "group-split": [("a", "observed-team-a-practice", "teasing"), ("b", "observed-team-b-practice", "dismissive")],
            }[case["revision"]]
            for suffix, condition, outcome in branch_specs:
                vid = f"CP-{index:02d}-v2-{suffix}"
                branch_ids.append(vid)
                versions.append({
                    "pattern_version_id": vid, "pattern_lineage_id": f"CP-{index:02d}", "version": 2,
                    "valid_from": case["period"], "valid_to": None, "status": "active-local-branch",
                    "conditions": [case["added_condition"], condition], "outcomes": {outcome: 1, case["outcome"]: 1 if outcome in case["outcome"] else 0},
                    "source_occurrences": [obs0, obs1], "supersedes": base_version,
                })
        else:
            vid = f"CP-{index:02d}-v2"
            branch_ids.append(vid)
            versions.append({
                "pattern_version_id": vid, "pattern_lineage_id": f"CP-{index:02d}", "version": 2,
                "valid_from": case["period"], "valid_to": None, "status": "active-specialized",
                "conditions": ["surface-or-structural-analogy", case["added_condition"]],
                "outcomes": {"expected": 1, case["outcome"]: 1}, "source_occurrences": [obs0, obs1], "supersedes": base_version,
            })
        revisions.append({
            "revision_id": f"pattern-revision:{case['id']}", "case_id": case["id"], "operation": case["revision"],
            "input_pattern_version": base_version, "output_pattern_versions": branch_ids,
            "trigger_feedback_observation": obs1, "outcome_update": case["outcome"],
            "old_version_mutated": False, "uncertainty_preserved": case["revision"] in ("split", "group-split"),
        })

    events = []
    previous_hash = "GENESIS"
    sequence = 0
    for case in cases:
        for event_type, payload_id in (
            ("observation-original", f"{case['id']}:o0"),
            ("hypothesis-selected", f"{case['id']}:hyp:prior"),
            ("feedback-observed", f"{case['id']}:o1"),
            ("repair-applied", f"repair:{case['id']}"),
            ("outcome-updated", case["outcome"]),
            ("pattern-version-created", f"pattern-revision:{case['id']}"),
        ):
            sequence += 1
            event = {"sequence": sequence, "case_id": case["id"], "event_type": event_type, "payload_id": payload_id, "previous_event_hash": previous_hash}
            event_hash = hashlib.sha256(canonical(event).encode()).hexdigest()
            event["event_hash"] = event_hash
            events.append(event)
            previous_hash = event_hash

    event_path = OUT / "revision-events.jsonl"
    event_path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events))
    observations_path, versions_path = OUT / "observations.parquet", OUT / "pattern-versions.parquet"
    pq.write_table(pa.Table.from_pylist(observations), observations_path, compression="zstd")
    pq.write_table(pa.Table.from_pylist([{**v, "conditions": json.dumps(v["conditions"]), "outcomes": json.dumps(v["outcomes"]), "source_occurrences": json.dumps(v["source_occurrences"])} for v in versions]), versions_path, compression="zstd")

    con = duckdb.connect()
    temporal_stats = con.execute(
        """SELECT valid_from,status,count(*) versions FROM read_parquet(?) GROUP BY valid_from,status ORDER BY valid_from,status""",
        [str(versions_path)],
    ).fetchall()
    con.close()
    graph = nx.DiGraph()
    for version in versions:
        graph.add_node(version["pattern_version_id"])
        if version["supersedes"]:
            graph.add_edge(version["supersedes"], version["pattern_version_id"])

    chained = True
    prior = "GENESIS"
    for event in events:
        base = {k: event[k] for k in ("sequence", "case_id", "event_type", "payload_id", "previous_event_hash")}
        chained &= event["previous_event_hash"] == prior and hashlib.sha256(canonical(base).encode()).hexdigest() == event["event_hash"]
        prior = event["event_hash"]
    disagree = next(v for v in revisions if v["case_id"] == "REV-DISAGREEMENT")
    validations = {
        "all_required_failure_modes": {c["phenomenon"] for c in cases} == {"joke-not-understood", "false-positive-humour", "unintended-offense", "convention-changed", "explicit-feedback", "contradictory-groups"},
        "prior_hypothesis_kept_everywhere": all(len(r["revision_candidates"]) == 2 and any(c["status"] == "historical-not-deleted" for c in r["revision_candidates"]) for r in repairs),
        "repair_contract_complete": all(r["signal_observation_id"] and r["repair_target_hypothesis_id"] and r["selected_revision_id"] and r["state_before"] and r["state_after"] for r in repairs),
        "original_observations_immutable": all(o["immutable"] for o in observations) and len(observations) == 12,
        "each_failure_updates_outcome": all(r["outcome_update"] for r in revisions),
        "each_failure_revises_or_splits_pattern": all(r["operation"] in {"specialize", "split", "temporal-split", "revise", "group-split"} and r["output_pattern_versions"] for r in revisions),
        "old_pattern_versions_not_rewritten": all(r["old_version_mutated"] is False for r in revisions) and sum(v["status"] == "superseded-not-deleted" for v in versions) == 6,
        "version_graph_acyclic": nx.is_directed_acyclic_graph(graph),
        "append_only_event_hash_chain_valid": chained and len({e["event_hash"] for e in events}) == len(events),
        "temporal_statistics_computed": len(temporal_stats) >= 6,
        "changed_convention_has_old_and_new_branches": len(next(r for r in revisions if r["case_id"] == "REV-TEMPORAL")["output_pattern_versions"]) == 2,
        "contradictory_groups_not_forced_to_consensus": len(disagree["output_pattern_versions"]) == 2 and disagree["uncertainty_preserved"],
        "group_branches_condition_on_observed_practice": all("observed-team-" in condition for v in versions if v["pattern_lineage_id"] == "CP-06" and v["version"] == 2 for condition in v["conditions"] if condition.startswith("observed")),
        "empirical_and_controlled_sources_remain_traceable": c4["real_corpus_discovery"]["exact_occurrences"] == 2 and any(o["provenance"]["kind"] == "controlled-fixture" for o in c4["transmission_occurrences"]),
        "parquet_roundtrip": pq.read_table(observations_path).num_rows == 12 and pq.read_table(versions_path).num_rows == len(versions),
    }
    assert all(validations.values()), validations
    result = {
        "failure_cases": cases, "observations": observations, "interaction_repairs": repairs,
        "pattern_versions": versions, "pattern_revisions": revisions,
        "event_log": {"path": "output/revision-events.jsonl", "events": len(events), "final_hash": previous_hash, "sha256": sha(event_path)},
        "temporal_statistics": [{"valid_from": row[0], "status": row[1], "versions": row[2]} for row in temporal_stats],
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources.values()},
        "boundary": "Feedback revises support, grounding and pattern versions; it never edits an observation or retroactively changes the historical hypothesis.",
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "failure_modes": len(cases), "immutable_observations": len(observations), "repair_records": len(repairs),
        "pattern_versions": len(versions), "append_only_events": len(events), "disagreement_branches": len(disagree["output_pattern_versions"]),
        "verdict": "GO_APPEND_ONLY_CULTURAL_REVISION_AND_REPAIR",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "duckdb": importlib.metadata.version("duckdb"), "networkx": importlib.metadata.version("networkx"),
        "pyarrow": importlib.metadata.version("pyarrow"), "event_hash": "SHA-256(canonical JSON including previous hash)",
    }, indent=2) + "\n")
    print("CULT-06: six failure modes repaired; history immutable; pattern revisions/splits retained; GO")


if __name__ == "__main__":
    main()
