#!/usr/bin/env python3
"""Un cycle SML isolé pour le contrôle exécutif SYS-07."""

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
agent = kernel.CreateAgent("seman2-sys07-control")
if not agent or agent.HadError():
    kernel.Shutdown()
    raise RuntimeError("SYS-07: création de l'agent Soar impossible")

try:
    input_link = agent.GetInputLink()
    context = input_link.CreateIdWME("active-context")
    context.CreateStringWME("phase", request["phase"])
    context.CreateStringWME("goal-ref", request["goal_ref"])
    context.CreateStringWME("resolution-status", request["resolution_status"])
    context.CreateIntWME("beam-bound", request["beam_bound"])
    beam = context.CreateIdWME("beam")
    for candidate in request["active_candidates"]:
        node = beam.CreateIdWME("candidate")
        node.CreateIntWME("rank", candidate["rank"])
        node.CreateStringWME("candidate-ref", candidate["candidate_ref"])
        node.CreateStringWME("identity-ref", candidate["identity_ref"])
        node.CreateFloatWME("score", candidate["score"])

    if request["phase"] == "initial":
        rule = r'''
sp {sys07*request-retrieval-on-impasse
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^phase initial ^goal-ref <goal> ^resolution-status ambiguous ^beam <beam>)
    (<beam> ^candidate <first> ^candidate <second>)
    (<first> ^rank 1)
    (<second> ^rank 2)
-->
    (<o> ^retrieval-request <d>)
    (<d> ^action request-retrieval ^goal-ref <goal> ^next-depth 1)}
'''
    elif request["phase"] == "retrieved":
        retrieval = request["retrieval"]
        retrieval_node = context.CreateIdWME("retrieval")
        retrieval_node.CreateStringWME("result-ref", retrieval["result_ref"])
        retrieval_node.CreateIntWME("depth", retrieval["depth"])
        for hit in retrieval["hits"]:
            node = retrieval_node.CreateIdWME("hit")
            node.CreateIntWME("rank", hit["rank"])
            node.CreateStringWME("content-ref", hit["content_ref"])
            node.CreateFloatWME("score", hit["score"])
        rule = r'''
sp {sys07*select-after-retrieval
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^phase retrieved ^goal-ref <goal> ^beam <beam>
         ^retrieval <retrieval>)
    (<beam> ^candidate <first> ^candidate <second>)
    (<first> ^rank 1 ^candidate-ref <first-ref> ^identity-ref <winner>)
    (<second> ^rank 2 ^candidate-ref <second-ref>)
    (<retrieval> ^result-ref <result-ref> ^hit <hit>)
    (<hit> ^rank 1 ^content-ref <winner>)
-->
    (<o> ^control-decision <d>)
    (<d> ^action select-candidate ^goal-ref <goal>
         ^selected-candidate-ref <first-ref>
         ^compared-candidate-ref <first-ref>
         ^compared-candidate-ref <second-ref>
         ^retrieval-result-ref <result-ref>)}
'''
    else:
        raise RuntimeError("SYS-07: phase SML inconnue")

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
    expected = "request-retrieval" if request["phase"] == "initial" else "select-candidate"
    if expected not in rendered_output:
        raise RuntimeError(f"SYS-07: opérateur Soar absent: {rendered_output}")
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
        active = request["active_candidates"]
        selected_match = re.search(
            r"\^selected-candidate-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
        )
        compared_matches = re.findall(
            r"\^compared-candidate-ref (?:\|([^|]+)\||([^\s()]+))", rendered_output
        )
        if selected_match is None or len(compared_matches) != len(active):
            raise RuntimeError(f"SYS-07: sortie Soar non décodable: {rendered_output}")
        result.update(
            selected_candidate_ref=selected_match.group(1) or selected_match.group(2),
            compared_candidate_refs=sorted(left or right for left, right in compared_matches),
            retrieval_result_ref=request["retrieval"]["result_ref"],
        )
        decoded_compared = {left or right for left, right in compared_matches}
        if any(row["candidate_ref"] not in decoded_compared for row in active):
            raise RuntimeError("SYS-07: candidats comparés absents de la sortie Soar")
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
finally:
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
