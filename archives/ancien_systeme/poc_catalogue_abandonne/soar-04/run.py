#!/usr/bin/env python3
"""SOAR-04: learn, inspect, reuse, and falsify a real Soar chunk."""
from __future__ import annotations

import json
import hashlib
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import Python_sml_ClientInterface as sml


POC = Path(__file__).resolve().parent
OUT = POC / "output"
ROOT = POC.parents[1]
sys.path.insert(0, str(ROOT))

from seman2_runtime.cognitive_checkpoint_inspection import (
    artifact_index,
    artifacts_of_type,
    load_verified_session_checkpoint,
)


def firing_count(rendered: str) -> int:
    match = re.search(r"(\d+):\s+", rendered)
    assert match, rendered
    return int(match.group(1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run01 = json.loads((ROOT / "poc/run-01/output/results.json").read_text())
    cognitive_checkpoint = (
        ROOT / "poc/run-01/output/checkpoint-epoch-0/cognitive-session.json"
    )
    checkpoint_hash = hashlib.sha256(cognitive_checkpoint.read_bytes()).hexdigest()
    cognitive_payload = load_verified_session_checkpoint(cognitive_checkpoint)
    cognitive_artifacts = artifact_index(cognitive_payload)
    cognitive_decision = artifacts_of_type(
        cognitive_payload, "soar-transformation-decision"
    )[0]
    cognitive_candidates = [
        cognitive_artifacts[ref] for ref in cognitive_decision["parent_ids"]
    ]
    candidate_by_kind = {
        row["payload_native"]["kind"]: row for row in cognitive_candidates
    }
    assert set(candidate_by_kind) == {"retain-episode", "defer-consolidation"}
    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("soar04")
    assert agent is not None and not agent.HadError()
    version = agent.ExecuteCommandLine("version")

    input_link = agent.GetInputLink()
    input_link.CreateStringWME("task", "choose-transformation")
    signal = input_link.CreateStringWME("signal", "retain-episode")
    case_id = input_link.CreateStringWME(
        "case-id", cognitive_decision["artifact_id"]
    )
    for candidate in cognitive_candidates:
        row = input_link.CreateIdWME("candidate")
        row.CreateStringWME("kind", candidate["payload_native"]["kind"])
        row.CreateStringWME("external-id", candidate["artifact_id"])
        row.CreateStringWME("episode-ref", candidate["payload_native"]["episode_ref"])
    agent.Commit()

    chunk_mode = agent.ExecuteCommandLine("chunk always")
    explain_mode = agent.ExecuteCommandLine("explain all on")
    productions = r"""
sp {soar04*propose*cognitive-transformation
   (state <s> ^io.input-link <input>)
   (<input> ^task choose-transformation ^candidate <candidate>)
   (<candidate> ^kind <kind> ^external-id <id> ^episode-ref <episode>)
-->
   (<s> ^operator <o> +)
   (<o> ^name cognitive-transformation ^kind <kind>
        ^external-id <id> ^episode-ref <episode>)}

sp {soar04*substate*derive-supported-candidate
   (state <sub> ^superstate <top> ^impasse tie ^item <candidate>)
   (<top> ^io.input-link <input>)
   (<input> ^signal <kind>)
   (<candidate> ^kind <kind>)
-->
   (<sub> ^supported <candidate>)}

sp {soar04*substate*return-required-candidate
   (state <sub> ^superstate <top> ^supported <candidate>)
-->
   (<top> ^operator <candidate> !)}

sp {soar04*apply
   (state <s> ^operator <operator>)
   (<operator> ^kind <kind> ^external-id <id>)
-->
   (<s> ^last-applied-kind <kind> ^last-applied-id <id>)}
"""
    source_result = agent.ExecuteCommandLine(productions)

    training_tie_run = agent.ExecuteCommandLine("run 1")
    training_tie_stack = agent.ExecuteCommandLine("print --stack")
    training_substate = agent.ExecuteCommandLine("print S2 --depth 4")
    training_resolution_run = agent.ExecuteCommandLine("run 2")
    training_resolved_stack = agent.ExecuteCommandLine("print --stack")

    chunk_names = agent.ExecuteCommandLine("print --chunks").split()
    assert len(chunk_names) == 1, chunk_names
    chunk_name = chunk_names[0]
    chunk_rule = agent.ExecuteCommandLine(f"print {chunk_name}")
    explain_selection = agent.ExecuteCommandLine(f"explain chunk {chunk_name}")
    explain_formation = agent.ExecuteCommandLine("explain formation")
    learning_stats = agent.ExecuteCommandLine("chunk stats")
    count_after_training = firing_count(
        agent.ExecuteCommandLine(f"production firing-counts {chunk_name}")
    )

    # Même problème relationnel, autre transformation cognitive : le chunk
    # généralisé doit sélectionner directement sans recréer de sous-état.
    signal.Update("defer-consolidation")
    case_id.Update("ISOMORPHIC-02")
    agent.Commit()
    isomorphic_run = agent.ExecuteCommandLine("run 1")
    isomorphic_stack = agent.ExecuteCommandLine("print --stack")
    isomorphic_top = agent.ExecuteCommandLine("print S1 --depth 4")
    count_after_isomorphic = firing_count(
        agent.ExecuteCommandLine(f"production firing-counts {chunk_name}")
    )

    # No candidate has kind=causal. The learned rule must not invent a choice.
    signal.Update("activate-unobserved-pattern")
    case_id.Update("COUNTEREXAMPLE-03")
    agent.Commit()
    counterexample_run = agent.ExecuteCommandLine("run 1")
    counterexample_stack = agent.ExecuteCommandLine("print --stack")
    counterexample_state = agent.ExecuteCommandLine("print S4 --depth 4")
    count_after_counterexample = firing_count(
        agent.ExecuteCommandLine(f"production firing-counts {chunk_name}")
    )

    validations = {
        "real_sml_kernel_and_agent": not kernel.HadError(),
        "training_required_tie_substate": (
            "(operator tie)" in training_tie_stack
            and "^impasse tie" in training_substate
            and "^item-count 2" in training_substate
        ),
        "one_real_chunk_learned": len(chunk_names) == 1 and "Rules learned" in learning_stats,
        "chunk_conditions_and_action_inspectable": all(
            token in chunk_rule
            for token in ("^signal <s2>", "^operator <o1> +", "^kind <s2>", "^operator <o1> !")
        ),
        "chunk_generalized_not_case_memorized": (
            "case-id" not in chunk_rule
            and cognitive_decision["artifact_id"] not in chunk_rule
            and "retain-episode" not in chunk_rule
        ),
        "dependency_trace_names_both_reasoning_rules": (
            "soar04*substate*derive-supported-candidate" in explain_formation
            and "soar04*substate*return-required-candidate" in explain_formation
            and "summarizes the problem-solving" in explain_formation
        ),
        "training_selected_actual_retain_episode": (
            "O: " in training_resolved_stack
            and candidate_by_kind["retain-episode"]["artifact_id"]
            in agent.ExecuteCommandLine("print S1 --depth 5")
        ),
        "isomorphic_case_reuses_chunk_directly": (
            "(cognitive-transformation)" in isomorphic_stack
            and "operator tie" not in isomorphic_stack
            and "^signal defer-consolidation" in isomorphic_top
            and "^kind defer-consolidation ^name cognitive-transformation"
            in isomorphic_top
            and count_after_isomorphic > count_after_training
        ),
        "counterexample_does_not_fire_chunk": count_after_counterexample == count_after_isomorphic,
        "counterexample_remains_explicit_impasse": (
            "(operator tie)" in counterexample_stack
            and "^impasse tie" in counterexample_state
            and "^signal activate-unobserved-pattern" not in chunk_rule
        ),
        "actual_checkpoint_matches_run01": (
            checkpoint_hash == run01["cognitive_ingestion"]["checkpoint_sha256"]
        ),
        "actual_candidate_ids_and_episode_refs_projected": all(
            candidate["artifact_id"] in isomorphic_top
            and candidate["payload_native"]["episode_ref"] in isomorphic_top
            for candidate in cognitive_candidates
        ),
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "configuration": {"chunk": chunk_mode, "explain": explain_mode},
        "source_result": source_result,
        "integrated_cognitive_source": {
            "checkpoint_sha256": checkpoint_hash,
            "decision_artifact_id": cognitive_decision["artifact_id"],
            "candidate_artifact_ids": {
                kind: row["artifact_id"] for kind, row in candidate_by_kind.items()
            },
        },
        "training": {
            "tie_run": training_tie_run,
            "tie_stack": training_tie_stack,
            "substate": training_substate,
            "resolution_run": training_resolution_run,
            "resolved_stack": training_resolved_stack,
        },
        "learned_chunk": {
            "name": chunk_name,
            "rule": chunk_rule,
            "explain_selection": explain_selection,
            "formation": explain_formation,
            "stats": learning_stats,
            "firing_count_after_training": count_after_training,
        },
        "isomorphic_case": {
            "run": isomorphic_run,
            "stack": isomorphic_stack,
            "top_state": isomorphic_top,
            "chunk_firing_count": count_after_isomorphic,
        },
        "counterexample": {
            "run": counterexample_run,
            "stack": counterexample_stack,
            "state": counterexample_state,
            "chunk_firing_count": count_after_counterexample,
        },
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "learned-chunk.soar").write_text(chunk_rule + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "learned_chunks": 1,
                "chunk_name": chunk_name,
                "training_choice": "retain-episode",
                "isomorphic_choice": "defer-consolidation",
                "counterexample": "operator tie retained",
                "chunk_firings_after_training": count_after_training,
                "chunk_firings_after_isomorphic": count_after_isomorphic,
                "chunk_firings_after_counterexample": count_after_counterexample,
                "verdict": "GO_REAL_SOAR_CHUNK_INSPECTABLE_AND_REUSED",
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "versions-and-parameters.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "platform": platform.platform(),
                "soar_version_output": version,
                "sml_module": sml.__file__,
                "pythonpath": os.environ.get("PYTHONPATH"),
                "chunk_mode": "always",
                "explainer": "all on",
            },
            indent=2,
        )
        + "\n"
    )
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("SOAR-04: chunk learned and reused on actual cognitive transformations; GO")


if __name__ == "__main__":
    main()
