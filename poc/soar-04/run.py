#!/usr/bin/env python3
"""SOAR-04: learn, inspect, reuse, and falsify a real Soar chunk."""
from __future__ import annotations

import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import Python_sml_ClientInterface as sml


POC = Path(__file__).resolve().parent
OUT = POC / "output"


def firing_count(rendered: str) -> int:
    match = re.search(r"(\d+):\s+", rendered)
    assert match, rendered
    return int(match.group(1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("soar04")
    assert agent is not None and not agent.HadError()
    version = agent.ExecuteCommandLine("version")

    input_link = agent.GetInputLink()
    input_link.CreateStringWME("task", "choose-analysis")
    signal = input_link.CreateStringWME("signal", "temporal")
    case_id = input_link.CreateStringWME("case-id", "TRAIN-01")
    agent.Commit()

    chunk_mode = agent.ExecuteCommandLine("chunk always")
    explain_mode = agent.ExecuteCommandLine("explain all on")
    productions = r"""
sp {soar04*propose*structural
   (state <s> ^io.input-link.task choose-analysis)
-->
   (<s> ^operator <o> +)
   (<o> ^name analyze ^kind structural)}

sp {soar04*propose*temporal
   (state <s> ^io.input-link.task choose-analysis)
-->
   (<s> ^operator <o> +)
   (<o> ^name analyze ^kind temporal)}

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
   (<operator> ^kind <kind>)
-->
   (<s> ^last-applied-kind <kind>)}
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

    # Same relational problem, different signal/value: the generalized chunk
    # should select directly, without recreating a tie substate.
    signal.Update("structural")
    case_id.Update("ISOMORPHIC-02")
    agent.Commit()
    isomorphic_run = agent.ExecuteCommandLine("run 1")
    isomorphic_stack = agent.ExecuteCommandLine("print --stack")
    isomorphic_top = agent.ExecuteCommandLine("print S1 --depth 4")
    count_after_isomorphic = firing_count(
        agent.ExecuteCommandLine(f"production firing-counts {chunk_name}")
    )

    # No candidate has kind=causal. The learned rule must not invent a choice.
    signal.Update("causal")
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
            and "TRAIN-01" not in chunk_rule
            and "temporal" not in chunk_rule
        ),
        "dependency_trace_names_both_reasoning_rules": (
            "soar04*substate*derive-supported-candidate" in explain_formation
            and "soar04*substate*return-required-candidate" in explain_formation
            and "summarizes the problem-solving" in explain_formation
        ),
        "training_selected_temporal": "O: " in training_resolved_stack,
        "isomorphic_case_reuses_chunk_directly": (
            "(analyze)" in isomorphic_stack
            and "operator tie" not in isomorphic_stack
            and "^signal structural" in isomorphic_top
            and count_after_isomorphic > count_after_training
        ),
        "counterexample_does_not_fire_chunk": count_after_counterexample == count_after_isomorphic,
        "counterexample_remains_explicit_impasse": (
            "(operator tie)" in counterexample_stack
            and "^impasse tie" in counterexample_state
            and "^signal causal" not in chunk_rule
        ),
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "configuration": {"chunk": chunk_mode, "explain": explain_mode},
        "source_result": source_result,
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
                "training_choice": "temporal",
                "isomorphic_choice": "structural",
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
    print("SOAR-04: chunk learned, explained, reused and rejected on counterexample; GO")


if __name__ == "__main__":
    main()
