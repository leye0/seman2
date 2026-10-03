#!/usr/bin/env python3
"""SOAR-02: inspect a real operator-tie impasse and its resolution through SML."""
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


def operator_names(rendered: str) -> set[str]:
    return set(re.findall(r"\^name ([^\s()]+)", rendered))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("soar02")
    assert agent is not None and not agent.HadError()

    version = agent.ExecuteCommandLine("version")
    input_link = agent.GetInputLink()
    input_link.CreateStringWME("task", "choose-analysis")
    resolution_gate = input_link.CreateStringWME("resolve", "no")
    agent.Commit()

    productions = r"""
sp {soar02*propose*structural-analysis
   (state <s> ^io.input-link.task choose-analysis)
-->
   (<s> ^operator <o> +)
   (<o> ^name structural-analysis ^external-id OP-STRUCT)}

sp {soar02*propose*temporal-analysis
   (state <s> ^io.input-link.task choose-analysis)
-->
   (<s> ^operator <o> +)
   (<o> ^name temporal-analysis ^external-id OP-TEMP)}

sp {soar02*resolve*tie-in-substate
   (state <sub> ^superstate <top> ^impasse tie
                ^attribute operator ^item <candidate>)
   (<top> ^io.input-link <input>)
   (<input> ^resolve yes)
   (<candidate> ^name temporal-analysis)
-->
   (<top> ^operator <candidate> !)}

sp {soar02*apply*temporal-analysis
   (state <s> ^operator <o>)
   (<o> ^name temporal-analysis ^external-id <external-id>)
-->
   (<s> ^selected-operator <external-id>)}
"""
    source_result = agent.ExecuteCommandLine(productions)
    trace_configuration = agent.ExecuteCommandLine("watch 5")

    tie_run = agent.ExecuteCommandLine("run 1")
    tie_decision_count = agent.GetDecisionCycleCounter()
    tie_stack = agent.ExecuteCommandLine("print --stack")
    tie_state = agent.ExecuteCommandLine("print S2 --depth 3")
    top_during_tie = agent.ExecuteCommandLine("print S1 --depth 3")
    preferences_during_tie = agent.ExecuteCommandLine("preferences S1 ^operator")

    resolution_gate.Update("yes")
    agent.Commit()
    resolution_run = agent.ExecuteCommandLine("run 2")
    resolved_decision_count = agent.GetDecisionCycleCounter()
    resolved_stack = agent.ExecuteCommandLine("print --stack")
    resolved_top = agent.ExecuteCommandLine("print S1 --depth 3")
    resolved_preferences = agent.ExecuteCommandLine("preferences S1 ^operator")
    production_firings = agent.ExecuteCommandLine("stats")

    validations = {
        "real_sml_kernel_and_agent": not kernel.HadError(),
        "two_operators_proposed": operator_names(top_during_tie)
        >= {"structural-analysis", "temporal-analysis"},
        "concurrent_acceptable_preferences_visible": (
            "acceptables:" in preferences_during_tie
            and "structural-analysis" in preferences_during_tie
            and "temporal-analysis" in preferences_during_tie
        ),
        "operator_tie_impasse_visible": (
            "^impasse tie" in tie_state
            and "^attribute operator" in tie_state
            and "^item-count 2" in tie_state
            and "(operator tie)" in tie_stack
        ),
        "substate_and_superstate_visible": "^superstate S1" in tie_state and "==>S: S2" in tie_stack,
        "impasse_items_keep_operator_identity": (
            "OP-STRUCT" in tie_state and "OP-TEMP" in tie_state
        ),
        "substate_result_preference_visible": (
            "requires:" in resolved_preferences
            and "temporal-analysis" in resolved_preferences
        ),
        "operator_selected": (
            "O: " in resolved_stack
            and "(temporal-analysis)" in resolved_stack
            and "^selected-operator OP-TEMP" in resolved_top
        ),
        "tie_substate_removed_after_resolution": "(operator tie)" not in resolved_stack,
        "decision_trace_progresses": resolved_decision_count > tie_decision_count >= 1,
        "productions_fired": "4 rules fired" in resolution_run or "rules fired" in resolution_run,
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "source_result": source_result,
        "trace_configuration": trace_configuration,
        "tie_snapshot": {
            "run": tie_run,
            "decision_count": tie_decision_count,
            "stack": tie_stack,
            "state": tie_state,
            "top_state": top_during_tie,
            "preferences": preferences_during_tie,
        },
        "resolved_snapshot": {
            "run": resolution_run,
            "decision_count": resolved_decision_count,
            "stack": resolved_stack,
            "top_state": resolved_top,
            "preferences": resolved_preferences,
        },
        "stats": production_firings,
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "proposed_operators": ["OP-STRUCT", "OP-TEMP"],
                "observed_impasse": "operator tie",
                "substate": "S2",
                "selected_operator": "OP-TEMP",
                "decision_count_before_resolution": tie_decision_count,
                "decision_count_after_resolution": resolved_decision_count,
                "verdict": "GO_REAL_SOAR_DECISION_DATA_ACCESSIBLE",
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
                "initial_resolution_gate": "no",
                "final_resolution_gate": "yes",
                "tie_run_decisions": 1,
                "resolution_run_decisions": 2,
            },
            indent=2,
        )
        + "\n"
    )
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("SOAR-02: tie impasse, substate, preferences and selected operator verified; GO")


if __name__ == "__main__":
    main()
