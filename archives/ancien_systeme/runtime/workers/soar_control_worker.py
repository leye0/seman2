#!/usr/bin/env python3
"""Project a bounded hypothesis family into a real Soar working memory."""

from __future__ import annotations

import json
import hashlib
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

import Python_sml_ClientInterface as sml


family_ref = str(request["family_ref"])
active_candidates = request["active_candidates"]
inactive_refs = [str(value) for value in request["inactive_refs"]]
beam_bound = int(request["beam_bound"])
active_refs = [str(row["hypothesis_ref"]) for row in active_candidates]
candidate_count = len(active_refs) + len(inactive_refs)
canonical_context = json.dumps(
    active_candidates,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
active_context_digest = hashlib.sha256(canonical_context.encode()).hexdigest()
justification_count = sum(
    len(row["justification_refs"]) for row in active_candidates
)

kernel = sml.Kernel.CreateKernelInNewThread()
if kernel.HadError():
    raise RuntimeError(kernel.GetLastErrorDescription())
agent = kernel.CreateAgent("seman2-ingestion-control")
if not agent or agent.HadError():
    kernel.Shutdown()
    raise RuntimeError("Soar agent creation failed")

try:
    input_link = agent.GetInputLink()
    context = input_link.CreateIdWME("active-context")
    context.CreateStringWME("family-ref", family_ref)
    context.CreateStringWME("mode", "ingestion")
    context.CreateStringWME("ready", "yes")
    context.CreateStringWME("goal", "maintain-factorized-alternatives")
    context.CreateStringWME("selection-policy", "greedy-structural-diversity-stable")
    context.CreateStringWME("active-context-digest", active_context_digest)
    context.CreateIntWME("candidate-count", candidate_count)
    context.CreateIntWME("beam-bound", beam_bound)
    active = context.CreateIdWME("active-hypotheses")
    for rank, candidate in enumerate(active_candidates, start=1):
        hypothesis = active.CreateIdWME("hypothesis")
        hypothesis.CreateIntWME("rank", rank)
        hypothesis.CreateStringWME("external-id", candidate["hypothesis_ref"])
        hypothesis.CreateStringWME("semantic-ref", candidate["semantic_ref"])
        hypothesis.CreateStringWME("temporal-ref", candidate["temporal_ref"])
        hypothesis.CreateStringWME("reference-ref", candidate["reference_ref"])
        hypothesis.CreateStringWME(
            "constraint-solution-ref", candidate["constraint_solution_ref"]
        )
        hypothesis.CreateStringWME("unit-ref", candidate["unit_ref"])
        for observation_ref in candidate["observation_refs"]:
            hypothesis.CreateStringWME("observation-ref", observation_ref)
        for justification_ref in candidate["justification_refs"]:
            hypothesis.CreateStringWME("justification-ref", justification_ref)
        for feature in candidate["structural_features"]:
            hypothesis.CreateStringWME("structural-feature", feature)
    agent.Commit()
    source_result = agent.ExecuteCommandLine(
        r"""
sp {seman2*maintain-ingestion-alternatives
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^mode ingestion ^ready yes ^family-ref <family>
         ^candidate-count <count> ^beam-bound <bound>
         ^active-hypotheses <active>)
    (<active> ^hypothesis <hypothesis>)
-->
    (<o> ^control-decision <decision>)
    (<decision> ^action maintain-factorized-alternatives
                ^family-ref <family> ^candidate-count <count>
                ^beam-bound <bound>)}
"""
    )
    run_result = agent.ExecuteCommandLine("run 1")
    agent.SynchronizeOutputLink()
    output_link = agent.GetOutputLink()
    if output_link is None:
        raise RuntimeError(f"Soar output link unavailable: {run_result}")
    rendered = agent.ExecuteCommandLine(
        f"print {output_link.GetIdentifierName()} --depth 8"
    )
    if "maintain-factorized-alternatives" not in rendered:
        raise RuntimeError(f"Soar control decision absent: {rendered}")
    input_rendered = agent.ExecuteCommandLine(
        f"print {input_link.GetIdentifierName()} --depth 12"
    )
    required_refs = {
        value
        for candidate in active_candidates
        for key in (
            "hypothesis_ref",
            "semantic_ref",
            "temporal_ref",
            "reference_ref",
            "constraint_solution_ref",
            "unit_ref",
        )
        for value in (str(candidate[key]),)
    } | {
        str(value)
        for candidate in active_candidates
        for key in ("observation_refs", "justification_refs")
        for value in candidate[key]
    }
    absent_refs = sorted(value for value in required_refs if value not in input_rendered)
    leaked_inactive_refs = sorted(
        value for value in inactive_refs if value in input_rendered
    )
    if absent_refs or leaked_inactive_refs:
        raise RuntimeError(
            f"projection WME invalide: absents={absent_refs}; inactifs={leaked_inactive_refs}"
        )
    version = agent.ExecuteCommandLine("version").strip()
    result = {
        "status": "controlled",
        "family_ref": family_ref,
        "active_refs": active_refs,
        "inactive_refs": inactive_refs,
        "action": "maintain-factorized-alternatives",
        "beam_bound": beam_bound,
        "candidate_count": candidate_count,
        "selection_policy": "greedy-structural-diversity-stable",
        "active_context_digest": active_context_digest,
        "projected_justification_ref_count": justification_count,
        "projected_hypothesis_count": len(active_candidates),
        "all_required_refs_observed_in_wm": not absent_refs,
        "inactive_refs_absent_from_wm": not leaked_inactive_refs,
        "soar_version": version,
        "source_result": source_result.strip(),
        "run_result": run_result.strip(),
        "working_memory_verified": True,
        "selection_performed": False,
    }
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
finally:
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
