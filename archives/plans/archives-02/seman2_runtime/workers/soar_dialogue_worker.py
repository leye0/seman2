#!/usr/bin/env python3
"""Run one isolated SML decision over a bounded dialogue-operator beam."""

from __future__ import annotations

import hashlib
import json
import re
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

import Python_sml_ClientInterface as sml  # noqa: E402


kernel = sml.Kernel.CreateKernelInNewThread()
if kernel.HadError():
    raise RuntimeError(kernel.GetLastErrorDescription())
agent = kernel.CreateAgent("seman2-sys09-dialogue-control")
if not agent or agent.HadError():
    kernel.Shutdown()
    raise RuntimeError("SYS-09: création de l'agent Soar impossible")

try:
    input_link = agent.GetInputLink()
    context = input_link.CreateIdWME("dialogue-context")
    context.CreateStringWME("goal-ref", request["goal_ref"])
    context.CreateStringWME("turn-ref", request["turn_ref"])
    context.CreateStringWME("move-kind", request["move_kind"])
    context.CreateStringWME("active-qud-status", request["active_qud_status"])
    beam = context.CreateIdWME("operator-beam")
    for candidate in request["operator_beam"]:
        node = beam.CreateIdWME("candidate")
        node.CreateIntWME("rank", candidate["rank"])
        node.CreateStringWME("operator-ref", candidate["operator_ref"])
        node.CreateFloatWME("score", candidate["score"])
        node.CreateStringWME("compatible", "yes" if candidate["compatible"] else "no")

    rule = r'''
sp {sys09*select-compatible-dialogue-operator
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^dialogue-context <c>)
    (<c> ^goal-ref <goal> ^turn-ref <turn> ^operator-beam <beam>)
    (<beam> ^candidate <first> ^candidate <second>)
    (<first> ^rank 1 ^operator-ref <selected> ^compatible yes)
    (<second> ^rank 2 ^operator-ref <compared>)
-->
    (<o> ^dialogue-decision <d>)
    (<d> ^action select-dialogue-operator ^goal-ref <goal> ^turn-ref <turn>
         ^selected-operator-ref <selected>
         ^compared-operator-ref <selected>
         ^compared-operator-ref <compared>)}
'''
    agent.Commit()
    source_result = agent.ExecuteCommandLine(rule)
    cycle = agent.ExecuteCommandLine("run 1")
    agent.SynchronizeOutputLink()
    output_link = agent.GetOutputLink()
    rendered_output = agent.ExecuteCommandLine(
        f"print {output_link.GetIdentifierName()} --depth 8"
    )
    rendered_input = agent.ExecuteCommandLine(
        f"print {input_link.GetIdentifierName()} --depth 12"
    )
    if "select-dialogue-operator" not in rendered_output:
        raise RuntimeError(f"SYS-09: opérateur Soar absent: {rendered_output}")
    selected = re.search(
        r"\^selected-operator-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
    )
    compared = re.findall(
        r"\^compared-operator-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
    )
    if selected is None or len(compared) != len(request["operator_beam"]):
        raise RuntimeError(f"SYS-09: sortie Soar non décodable: {rendered_output}")
    result = {
        "action": "select-dialogue-operator",
        "goal_ref": request["goal_ref"],
        "turn_ref": request["turn_ref"],
        "selected_operator_ref": selected.group(1) or selected.group(2),
        "compared_operator_refs": sorted(left or right for left, right in compared),
        "cycle_trace": cycle.strip(),
        "output": rendered_output,
        "working_memory": rendered_input,
        "working_memory_sha256": hashlib.sha256(rendered_input.encode()).hexdigest(),
        "soar_version": agent.ExecuteCommandLine("version").strip(),
        "source_result": source_result.strip(),
    }
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
finally:
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
