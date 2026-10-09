#!/usr/bin/env python3
"""One isolated, bounded SML cycle for conceptual structure selection."""

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
agent = kernel.CreateAgent("seman2-sys08-concept-control")
if not agent or agent.HadError():
    kernel.Shutdown()
    raise RuntimeError("SYS-08: création de l'agent Soar impossible")

try:
    input_link = agent.GetInputLink()
    context = input_link.CreateIdWME("active-context")
    context.CreateStringWME("phase", request["phase"])
    context.CreateStringWME("goal-ref", request["goal_ref"])
    context.CreateStringWME("selection-status", "unresolved")
    beam = context.CreateIdWME("beam")
    for candidate in request["active_candidates"]:
        node = beam.CreateIdWME("candidate")
        node.CreateIntWME("rank", candidate["rank"])
        node.CreateStringWME("candidate-ref", candidate["candidate_ref"])
        node.CreateStringWME("content-ref", candidate["content_ref"])
        node.CreateFloatWME("score", candidate["score"])

    if request["phase"] == "initial":
        rule = r'''
sp {sys08*request-concept-retrieval
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^phase initial ^goal-ref <goal> ^selection-status unresolved ^beam <beam>)
    (<beam> ^candidate <first> ^candidate <second>)
    (<first> ^rank 1)
    (<second> ^rank 2)
-->
    (<o> ^retrieval-request <d>)
    (<d> ^action request-concept-retrieval ^goal-ref <goal> ^next-depth 1)}
'''
    elif request["phase"] == "retrieved":
        retrieval = context.CreateIdWME("retrieval")
        retrieval.CreateStringWME("result-ref", request["retrieval"]["result_ref"])
        for hit in request["retrieval"]["hits"]:
            node = retrieval.CreateIdWME("hit")
            node.CreateIntWME("rank", hit["rank"])
            node.CreateStringWME("content-ref", hit["content_ref"])
            node.CreateFloatWME("score", hit["score"])
        rule = r'''
sp {sys08*select-concept-after-retrieval
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^phase retrieved ^goal-ref <goal> ^beam <beam> ^retrieval <retrieval>)
    (<beam> ^candidate <first> ^candidate <second> ^candidate <selected>)
    (<first> ^rank 1 ^candidate-ref <first-ref>)
    (<second> ^rank 2 ^candidate-ref <second-ref>)
    (<selected> ^candidate-ref <selected-ref> ^content-ref <winner>)
    (<retrieval> ^result-ref <result-ref> ^hit <hit>)
    (<hit> ^rank 1 ^content-ref <winner>)
-->
    (<o> ^control-decision <d>)
    (<d> ^action select-concept ^goal-ref <goal>
         ^selected-candidate-ref <selected-ref>
         ^compared-candidate-ref <first-ref>
         ^compared-candidate-ref <second-ref>
         ^retrieval-result-ref <result-ref>)}
'''
    else:
        raise RuntimeError("SYS-08: phase SML inconnue")

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
    expected = (
        "request-concept-retrieval"
        if request["phase"] == "initial"
        else "select-concept"
    )
    if expected not in rendered_output:
        raise RuntimeError(f"SYS-08: opérateur Soar absent: {rendered_output}")
    result = {
        "action": expected,
        "goal_ref": request["goal_ref"],
        "cycle_trace": cycle.strip(),
        "output": rendered_output,
        "working_memory": rendered_input,
        "working_memory_sha256": hashlib.sha256(rendered_input.encode()).hexdigest(),
        "soar_version": agent.ExecuteCommandLine("version").strip(),
        "source_result": source_result.strip(),
    }
    if request["phase"] == "initial":
        result["next_depth"] = 1
    else:
        selected = re.search(
            r"\^selected-candidate-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
        )
        compared = re.findall(
            r"\^compared-candidate-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
        )
        if selected is None or len(compared) != len(request["active_candidates"]):
            raise RuntimeError(f"SYS-08: sortie Soar non décodable: {rendered_output}")
        result["selected_candidate_ref"] = selected.group(1) or selected.group(2)
        result["compared_candidate_refs"] = sorted(left or right for left, right in compared)
        result["retrieval_result_ref"] = request["retrieval"]["result_ref"]
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
finally:
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
