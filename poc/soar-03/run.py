#!/usr/bin/env python3
"""SOAR-03: exercise native semantic and episodic memory through real SML."""
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


def stat(rendered: str, label: str) -> int:
    match = re.search(rf"^{re.escape(label)}:\s+(\d+)\s*$", rendered, re.MULTILINE)
    assert match, (label, rendered)
    return int(match.group(1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    semantic_export = OUT / "semantic-memory.soar"
    episodic_backup = OUT / "episodic-memory.sqlite"

    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("soar03")
    assert agent is not None and not agent.HadError()
    version = agent.ExecuteCommandLine("version")

    input_link = agent.GetInputLink()
    mode = input_link.CreateStringWME("memory-mode", "idle")
    event = input_link.CreateIdWME("event")
    event.CreateStringWME("actor", "agent-A")
    event.CreateStringWME("channel", "dialogue")
    action = event.CreateStringWME("action", "observe")
    sequence = event.CreateIntWME("sequence", 1)
    payload = event.CreateStringWME("payload", "claim-17")
    agent.Commit()

    configuration = {
        "smem_learning": agent.ExecuteCommandLine("smem --set learning on"),
        "smem_activation": agent.ExecuteCommandLine("smem --set activation-mode base-level"),
        "epmem_learning": agent.ExecuteCommandLine("epmem --set learning on"),
        "epmem_trigger": agent.ExecuteCommandLine("epmem --set trigger dc"),
        "epmem_phase": agent.ExecuteCommandLine("epmem --set phase output"),
    }
    semantic_add = agent.ExecuteCommandLine(
        """smem --add {
          (@observe ^kind event ^actor agent-A ^channel dialogue ^action observe ^next @compare)
          (@compare ^kind event ^actor agent-A ^channel dialogue ^action compare ^next @answer)
          (@answer ^kind event ^actor agent-A ^channel dialogue ^action answer)
        }"""
    )
    semantic_contents = agent.ExecuteCommandLine("print @ --depth 5")
    semantic_ranked_query = agent.ExecuteCommandLine(
        "smem --query {(<cue> ^kind event ^actor agent-A ^channel dialogue)} 3"
    )

    productions = r"""
sp {soar03*epmem*query-compare
   (state <s> ^io.input-link <input> ^epmem.command <command>)
   (<input> ^memory-mode ep-query)
-->
   (<command> ^query <cue>)
   (<cue> ^io.input-link.event.action compare)}

sp {soar03*epmem*next
   (state <s> ^io.input-link <input> ^epmem.command <command>)
   (<input> ^memory-mode ep-next)
-->
   (<command> ^next <request>)}

sp {soar03*epmem*previous
   (state <s> ^io.input-link <input> ^epmem.command <command>)
   (<input> ^memory-mode ep-previous)
-->
   (<command> ^previous <request>)}

sp {soar03*smem*query-compare
   (state <s> ^io.input-link <input> ^smem.command <command>)
   (<input> ^memory-mode sm-query)
-->
   (<command> ^query <cue>)
   (<cue> ^action compare)}
"""
    source_result = agent.ExecuteCommandLine(productions)

    encoded_events = []
    for index, (event_action, event_payload) in enumerate(
        [("observe", "claim-17"), ("compare", "claim-17"), ("answer", "response-17")],
        start=1,
    ):
        if index > 1:
            action.Update(event_action)
            sequence.Update(index)
            payload.Update(event_payload)
            agent.Commit()
        run_result = agent.ExecuteCommandLine("run 1")
        encoded_events.append(
            {"sequence": index, "action": event_action, "payload": event_payload, "run": run_result}
        )
    # Epmem's reported time is the next episode id; one extra output phase seals episode 3.
    flush_run = agent.ExecuteCommandLine("run 1")
    episodes = {str(i): agent.ExecuteCommandLine(f"epmem --print {i}") for i in range(1, 4)}
    agent.ExecuteCommandLine("epmem --set trigger none")

    mode.Update("ep-query")
    agent.Commit()
    ep_query_run = agent.ExecuteCommandLine("run 2")
    ep_query_result = agent.ExecuteCommandLine("print E1 --depth 12")
    ep_query_stats = agent.ExecuteCommandLine("epmem --stats")

    mode.Update("ep-next")
    agent.Commit()
    ep_next_run = agent.ExecuteCommandLine("run 2")
    ep_next_result = agent.ExecuteCommandLine("print E1 --depth 12")
    ep_next_stats = agent.ExecuteCommandLine("epmem --stats")

    mode.Update("ep-previous")
    agent.Commit()
    ep_previous_run = agent.ExecuteCommandLine("run 2")
    ep_previous_result = agent.ExecuteCommandLine("print E1 --depth 12")
    ep_previous_stats = agent.ExecuteCommandLine("epmem --stats")

    mode.Update("sm-query")
    agent.Commit()
    sm_query_run = agent.ExecuteCommandLine("run 2")
    sm_query_result = agent.ExecuteCommandLine("print L1 --depth 10")
    sm_query_stats = agent.ExecuteCommandLine("smem --stats")
    semantic_history = agent.ExecuteCommandLine("smem --history @compare")

    smem_help = agent.ExecuteCommandLine("smem ?")
    epmem_help = agent.ExecuteCommandLine("help epmem")
    semantic_export_result = agent.ExecuteCommandLine(f"smem --export {semantic_export}")
    episodic_backup_result = agent.ExecuteCommandLine(f"epmem --backup {episodic_backup}")

    validations = {
        "real_sml_kernel_and_agent": not kernel.HadError(),
        "three_semantic_ltis_with_links": (
            semantic_contents.count("^kind event") == 3
            and "^next @2" in semantic_contents
            and "^next @3" in semantic_contents
        ),
        "semantic_ranked_activation_exposed": (
            semantic_ranked_query.count("[+1.000]") == 3
            and all(action_name in semantic_ranked_query for action_name in ("observe", "compare", "answer"))
        ),
        "semantic_agent_query_returns_lti": (
            "^retrieved" in sm_query_result
            and "(@2)" in sm_query_result
            and "^action compare" in sm_query_result
            and "^next" in sm_query_result
        ),
        "semantic_query_and_activation_counted": (
            stat(sm_query_stats, "Queries") == 1
            and stat(sm_query_stats, "Activation Updates") >= 1
        ),
        "three_distinct_episodes_encoded": all(
            f"^action {name}" in episodes[str(i)] and f"^sequence {i}" in episodes[str(i)]
            for i, name in enumerate(("observe", "compare", "answer"), start=1)
        ),
        "shared_episode_properties_preserved": all(
            "^actor agent-A" in episode and "^channel dialogue" in episode
            for episode in episodes.values()
        ),
        "episodic_cue_query_returns_episode_2_with_scores": all(
            token in ep_query_result
            for token in ("^memory-id 2", "^action compare", "^match-score 1.000000", "^normalized-match-score 1.000000")
        ),
        "episodic_next_returns_episode_3": (
            "^memory-id 3" in ep_next_result
            and "^action answer" in ep_next_result
            and stat(ep_next_stats, "Nexts") == 1
        ),
        "episodic_previous_returns_episode_2": (
            "^memory-id 2" in ep_previous_result
            and "^action compare" in ep_previous_result
            and stat(ep_previous_stats, "Prevs") == 1
        ),
        "episodic_query_statistics_exposed": (
            stat(ep_query_stats, "Queries") == 1
            and stat(ep_query_stats, "Last Query Retrieved") == 2
            and stat(ep_query_stats, "Last Query Positive") > 0
        ),
        "native_export_limits_observed": (
            "smem --export" in smem_help
            and "--export" not in epmem_help
            and "--backup" in epmem_help
            and "--print" in epmem_help
            and "--viz" in epmem_help
        ),
        "native_artifacts_written": (
            semantic_export.exists()
            and semantic_export.stat().st_size > 0
            and episodic_backup.exists()
            and episodic_backup.stat().st_size > 0
        ),
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "configuration": configuration,
        "source_result": source_result,
        "semantic_memory": {
            "add_result": semantic_add,
            "contents": semantic_contents,
            "ranked_cli_query": semantic_ranked_query,
            "agent_query_run": sm_query_run,
            "agent_query_result": sm_query_result,
            "activation_history": semantic_history,
            "stats": sm_query_stats,
            "export_result": semantic_export_result,
        },
        "episodic_memory": {
            "encoded_events": encoded_events,
            "flush_run": flush_run,
            "episodes": episodes,
            "cue_query": {"run": ep_query_run, "result": ep_query_result, "stats": ep_query_stats},
            "next": {"run": ep_next_run, "result": ep_next_result, "stats": ep_next_stats},
            "previous": {
                "run": ep_previous_run,
                "result": ep_previous_result,
                "stats": ep_previous_stats,
            },
            "backup_result": episodic_backup_result,
        },
        "export_capabilities": {
            "semantic": "native text export of the whole store",
            "episodic": "native SQLite backup plus per-episode print/viz; no native whole-store text export",
            "smem_help_evidence": smem_help,
            "epmem_help_evidence": epmem_help,
        },
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "semantic_ltis": 3,
                "semantic_agent_queries": stat(sm_query_stats, "Queries"),
                "episodes": 3,
                "cue_retrieved_episode": 2,
                "next_episode": 3,
                "previous_episode": 2,
                "semantic_export": semantic_export.name,
                "episodic_backup": episodic_backup.name,
                "verdict": "GO_NATIVE_SOAR_SEMANTIC_AND_EPISODIC_MEMORY",
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
                "smem_activation_mode": "base-level",
                "epmem_trigger_while_encoding": "dc",
                "epmem_phase": "output",
                "event_count": 3,
            },
            indent=2,
        )
        + "\n"
    )
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("SOAR-03: semantic retrieval, episodic cue/next/previous and exports verified; GO")


if __name__ == "__main__":
    main()
