#!/usr/bin/env python3
"""Select one operational memory transformation with real Soar preferences."""

from __future__ import annotations

import json
import hashlib
import re
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

import Python_sml_ClientInterface as sml


candidates = request["candidates"]
canonical_context = json.dumps(
    candidates,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
active_context_digest = hashlib.sha256(canonical_context.encode()).hexdigest()
projected_precondition_ref_count = sum(
    len(candidate["precondition_refs"]) for candidate in candidates
)
kernel = sml.Kernel.CreateKernelInNewThread()
if kernel.HadError():
    raise RuntimeError(kernel.GetLastErrorDescription())
agent = kernel.CreateAgent("seman2-ingestion-transformations")
if not agent or agent.HadError():
    kernel.Shutdown()
    raise RuntimeError("Soar agent creation failed")
try:
    input_link = agent.GetInputLink()
    context = input_link.CreateIdWME("active-context")
    transformations = context.CreateIdWME("transformations")
    for candidate in candidates:
        row = transformations.CreateIdWME("transformation")
        row.CreateStringWME("external-id", candidate["transformation_id"])
        row.CreateStringWME("kind", candidate["kind"])
        row.CreateStringWME("eligible", "yes" if candidate["eligible"] else "no")
        row.CreateStringWME("episode-ref", candidate["episode_ref"])
        row.CreateStringWME("cultural-ref", candidate["cultural_ref"])
        for precondition_ref in candidate["precondition_refs"]:
            row.CreateStringWME("precondition-ref", precondition_ref)
    agent.Commit()
    source_result = agent.ExecuteCommandLine(
        r"""
sp {seman2*propose-memory-transformation
    (state <s> ^io.input-link.active-context <context>)
    (<context> ^transformations <transformations>)
    (<transformations> ^transformation <candidate>)
    (<candidate> ^eligible yes ^external-id <id> ^kind <kind>)
-->
    (<s> ^operator <operator> +)
    (<operator> ^name ingestion-memory-transformation
                ^external-id <id> ^kind <kind>)}

sp {seman2*prefer-retain-episode
    (state <s> ^operator <preferred> + ^operator <other> +)
    (<preferred> ^name ingestion-memory-transformation ^kind retain-episode)
    (<other> ^name ingestion-memory-transformation
             ^kind { <> retain-episode })
-->
    (<s> ^operator <preferred> > <other>)}

sp {seman2*apply-memory-transformation
    (state <s> ^io.output-link <output> ^operator <operator>)
    (<operator> ^name ingestion-memory-transformation
                ^external-id <id> ^kind <kind>)
-->
    (<output> ^memory-transformation-decision <decision>)
    (<decision> ^selected-transformation <id> ^kind <kind>
                ^action consolidate-without-truth-commit)}
"""
    )
    run_result = agent.ExecuteCommandLine("run 2")
    agent.SynchronizeOutputLink()
    output_link = agent.GetOutputLink()
    if output_link is None:
        raise RuntimeError(f"Soar transformation output absent: {run_result}")
    rendered = agent.ExecuteCommandLine(
        f"print {output_link.GetIdentifierName()} --depth 8"
    )
    input_rendered = agent.ExecuteCommandLine(
        f"print {input_link.GetIdentifierName()} --depth 12"
    )
    required_refs = {
        str(value)
        for candidate in candidates
        for key in (
            "transformation_id",
            "episode_ref",
            "cultural_ref",
        )
        for value in (candidate[key],)
    } | {
        str(value)
        for candidate in candidates
        for value in candidate["precondition_refs"]
    }
    absent_refs = sorted(value for value in required_refs if value not in input_rendered)
    selected_match = re.search(
        r"\^selected-transformation (?:\|([^|]+)\||([^\s()]+))", rendered
    )
    kind_match = re.search(r"\^kind (?:\|([^|]+)\||([^\s()]+))", rendered)
    if selected_match is None or kind_match is None:
        if not any(candidate["eligible"] for candidate in candidates):
            raise RuntimeError(
                "Soar transformation output absent: no eligible operator was proposed"
            )
        raise RuntimeError(f"Soar transformation decision unreadable: {rendered}")
    selected = selected_match.group(1) or selected_match.group(2)
    kind = kind_match.group(1) or kind_match.group(2)
    json.dump(
        {
            "status": "selected",
            "selected_transformation_ref": selected,
            "transformation_kind": kind,
            "action": "consolidate-without-truth-commit",
            "candidate_count": len(candidates),
            "source_result": source_result.strip(),
            "run_result": run_result.strip(),
            "selection_is_operational": True,
            "semantic_truth_selected": False,
            "active_context_digest": active_context_digest,
            "projected_precondition_ref_count": projected_precondition_ref_count,
            "all_required_refs_observed_in_wm": not absent_refs,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
finally:
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
