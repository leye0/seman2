#!/usr/bin/env python3
"""SOAR-05: real SML output-command bridge to a DuckDB/Parquet store."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import Python_sml_ClientInterface as sml


POC = Path(__file__).resolve().parent
OUT = POC / "output"
ROOT = POC.parents[1]
RET03 = ROOT / "poc" / "ret-03" / "output"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_command(
    agent: sml.Agent, output_link_name: str, name: str, attributes: list[str]
) -> tuple[dict[str, str], str]:
    rendered = agent.ExecuteCommandLine(
        f"print {output_link_name} --depth 4"
    )
    assert rendered.count(f"^{name} ") == 1, rendered
    values = {}
    for attribute in attributes:
        match = re.search(rf"\^{re.escape(attribute)} (?:\|([^|]+)\||([^\s()]+))", rendered)
        assert match, (attribute, rendered)
        values[attribute] = match.group(1) if match.group(1) is not None else match.group(2)
    return values, rendered


def execute_retrieval(store: Path, meaning: str, top_k: int, excluded: list[str]) -> list[dict]:
    connection = duckdb.connect()
    sql = "SELECT * FROM read_parquet(?) WHERE meaning = ?"
    parameters: list[object] = [str(store), meaning]
    if excluded:
        sql += " AND hypothesis_id NOT IN (SELECT unnest(?))"
        parameters.append(excluded)
    sql += " ORDER BY score DESC, hypothesis_id LIMIT ?"
    parameters.append(top_k)
    relation = connection.execute(sql, parameters)
    columns = [column[0] for column in relation.description]
    rows = [dict(zip(columns, values)) for values in relation.fetchall()]
    connection.close()
    return rows


def inject_batch(input_link: sml.Identifier, query_id: str, rows: list[dict], source_hash: str) -> None:
    batch = input_link.CreateIdWME("retrieval-batch")
    batch.CreateStringWME("query-id", query_id)
    batch.CreateIntWME("count", len(rows))
    for rank, row in enumerate(rows, start=1):
        result = batch.CreateIdWME("result")
        result.CreateIntWME("rank", rank)
        result.CreateStringWME("hypothesis-id", row["hypothesis_id"])
        result.CreateStringWME("episode-id", row["episode_id"])
        result.CreateStringWME("family", row["family"])
        result.CreateFloatWME("score", row["score"])
        result.CreateStringWME("source-artifact", "RET-03/episodes.parquet")
        result.CreateStringWME("source-sha256", source_hash)


def destroy_batch(agent: sml.Agent, input_link: sml.Identifier) -> None:
    batch_wme = input_link.FindByAttribute("retrieval-batch", 0)
    assert batch_wme is not None
    assert agent.DestroyWME(batch_wme)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ret_results_path = RET03 / "results.json"
    ret_episodes_path = RET03 / "episodes.parquet"
    assert ret_results_path.exists() and ret_episodes_path.exists(), "Run RET-03 first"
    ret_results = json.loads(ret_results_path.read_text())
    assert {row["episode_id"] for row in ret_results["matches"]} == {
        "episode:match-A",
        "episode:match-E",
    }
    ret_results_hash = sha256(ret_results_path)
    ret_episodes_hash = sha256(ret_episodes_path)

    candidates = [
        {
            "hypothesis_id": "H-MATCH-A",
            "episode_id": "episode:match-A",
            "meaning": "greeting",
            "family": "validated-sequence",
            "score": 0.96,
            "ret03_status": "matched",
        },
        {
            "hypothesis_id": "H-MATCH-E",
            "episode_id": "episode:match-E",
            "meaning": "greeting",
            "family": "validated-sequence",
            "score": 0.92,
            "ret03_status": "matched",
        },
        {
            "hypothesis_id": "H-DISTRACTOR-F",
            "episode_id": "episode:distractor",
            "meaning": "greeting",
            "family": "rejected-outcome",
            "score": 0.61,
            "ret03_status": "rejected",
        },
        {
            "hypothesis_id": "H-OUT-OF-ORDER-D",
            "episode_id": "episode:out-of-order",
            "meaning": "greeting",
            "family": "rejected-order",
            "score": 0.55,
            "ret03_status": "rejected",
        },
        {
            "hypothesis_id": "H-WRONG-C",
            "episode_id": "episode:wrong-meaning",
            "meaning": "input_output",
            "family": "wrong-meaning",
            "score": 0.80,
            "ret03_status": "rejected",
        },
    ]
    candidate_store = OUT / "candidate-store.parquet"
    pq.write_table(pa.Table.from_pylist(candidates), candidate_store, compression="zstd")

    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("soar05")
    assert agent is not None and not agent.HadError()
    version = agent.ExecuteCommandLine("version")
    input_link = agent.GetInputLink()
    input_link_name = input_link.GetIdentifierName()
    phase = input_link.CreateStringWME("bridge-phase", "request-initial")
    input_link.CreateStringWME("active-goal", "interpret-greeting")
    agent.Commit()

    productions = r"""
sp {soar05*request*initial
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^bridge-phase request-initial ^active-goal interpret-greeting)
-->
   (<output> ^retrieval-request <request>)
   (<request> ^query-id Q-INITIAL ^meaning greeting ^top-k 2)}

sp {soar05*consume*initial
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^bridge-phase results-initial ^retrieval-batch <batch>)
   (<batch> ^query-id Q-INITIAL ^result <result>)
   (<result> ^rank 1 ^hypothesis-id <hypothesis> ^episode-id <episode>
             ^source-sha256 <source>)
-->
   (<output> ^activation-ack <ack>)
   (<ack> ^query-id Q-INITIAL ^selected-hypothesis <hypothesis>
          ^episode-id <episode> ^source-sha256 <source>)}

sp {soar05*request*next
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^bridge-phase request-next ^active-goal interpret-greeting)
-->
   (<output> ^retrieval-request <request>)
   (<request> ^query-id Q-NEXT ^meaning greeting ^top-k 1)}

sp {soar05*consume*next
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^bridge-phase results-next ^retrieval-batch <batch>)
   (<batch> ^query-id Q-NEXT ^result <result>)
   (<result> ^rank 1 ^hypothesis-id <hypothesis> ^episode-id <episode>
             ^source-sha256 <source>)
-->
   (<output> ^activation-ack <ack>)
   (<ack> ^query-id Q-NEXT ^selected-hypothesis <hypothesis>
          ^episode-id <episode> ^source-sha256 <source>)}
"""
    source_result = agent.ExecuteCommandLine(productions)

    initial_request_run = agent.ExecuteCommandLine("run 1")
    top_state = agent.ExecuteCommandLine("print S1 --depth 2")
    output_link_match = re.search(r"\^output-link ([A-Z]\d+)", top_state)
    assert output_link_match, top_state
    output_link_name = output_link_match.group(1)
    request1_values, request1_output = output_command(
        agent, output_link_name, "retrieval-request", ["query-id", "meaning", "top-k"]
    )
    request1_data = {
        "query_id": request1_values["query-id"],
        "meaning": request1_values["meaning"],
        "top_k": int(request1_values["top-k"]),
    }
    first_rows = execute_retrieval(
        candidate_store, request1_data["meaning"], request1_data["top_k"], []
    )
    inject_batch(input_link, request1_data["query_id"], first_rows, ret_episodes_hash)
    phase.Update("results-initial")
    agent.Commit()
    initial_consume_run = agent.ExecuteCommandLine("run 1")
    initial_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 8")
    ack1_values, ack1_output = output_command(
        agent,
        output_link_name,
        "activation-ack",
        ["query-id", "selected-hypothesis", "episode-id", "source-sha256"],
    )
    ack1_data = {
        "query_id": ack1_values["query-id"],
        "selected_hypothesis": ack1_values["selected-hypothesis"],
        "episode_id": ack1_values["episode-id"],
        "source_sha256": ack1_values["source-sha256"],
    }

    destroy_batch(agent, input_link)
    phase.Update("clean")
    agent.Commit()
    cleanup_run = agent.ExecuteCommandLine("run 1")
    cleaned_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 8")

    excluded = [row["hypothesis_id"] for row in first_rows]
    phase.Update("request-next")
    agent.Commit()
    next_request_run = agent.ExecuteCommandLine("run 1")
    request2_values, request2_output = output_command(
        agent, output_link_name, "retrieval-request", ["query-id", "meaning", "top-k"]
    )
    request2_data = {
        "query_id": request2_values["query-id"],
        "meaning": request2_values["meaning"],
        "top_k": int(request2_values["top-k"]),
        "excluded_by_adapter": excluded,
    }
    next_rows = execute_retrieval(
        candidate_store, request2_data["meaning"], request2_data["top_k"], excluded
    )
    inject_batch(input_link, request2_data["query_id"], next_rows, ret_episodes_hash)
    phase.Update("results-next")
    agent.Commit()
    next_consume_run = agent.ExecuteCommandLine("run 1")
    next_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 8")
    ack2_values, ack2_output = output_command(
        agent,
        output_link_name,
        "activation-ack",
        ["query-id", "selected-hypothesis", "episode-id", "source-sha256"],
    )
    ack2_data = {
        "query_id": ack2_values["query-id"],
        "selected_hypothesis": ack2_values["selected-hypothesis"],
        "episode_id": ack2_values["episode-id"],
        "source_sha256": ack2_values["source-sha256"],
    }
    final_output = agent.ExecuteCommandLine(f"print {output_link_name} --depth 6")

    first_ids = [row["hypothesis_id"] for row in first_rows]
    next_ids = [row["hypothesis_id"] for row in next_rows]
    store_ids = {row["hypothesis_id"] for row in candidates}
    validations = {
        "real_sml_output_command_received": request1_data
        == {"query_id": "Q-INITIAL", "meaning": "greeting", "top_k": 2},
        "duckdb_top_k_is_exact": first_ids == ["H-MATCH-A", "H-MATCH-E"],
        "only_beam_injected_into_soar": (
            all(identifier in initial_input for identifier in first_ids)
            and "H-DISTRACTOR-F" not in initial_input
            and "H-OUT-OF-ORDER-D" not in initial_input
        ),
        "external_ids_and_provenance_preserved": all(
            row["episode_id"] in initial_input for row in first_rows
        )
        and ret_episodes_hash in initial_input,
        "soar_consumed_rank_one": ack1_data["selected_hypothesis"] == "H-MATCH-A",
        "batch_wmes_removed": (
            "retrieval-batch" not in cleaned_input
            and not any(identifier in cleaned_input for identifier in store_ids)
        ),
        "outside_beam_remained_persistent": set(excluded) < store_ids,
        "later_request_reactivates_outside_beam": (
            next_ids == ["H-DISTRACTOR-F"]
            and "H-DISTRACTOR-F" in next_input
            and ack2_data["selected_hypothesis"] == "H-DISTRACTOR-F"
        ),
        "second_activation_keeps_source_hash": ack2_data["source_sha256"] == ret_episodes_hash,
        "ret03_artifacts_cryptographically_linked": len(ret_results_hash) == 64
        and len(ret_episodes_hash) == 64,
        "persistent_store_never_bulk_copied": len(store_ids) == 5
        and len(first_ids) == 2
        and len(next_ids) == 1,
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "source_result": source_result,
        "ret03_provenance": {
            "results_sha256": ret_results_hash,
            "episodes_sha256": ret_episodes_hash,
            "ret03_verdict": ret_results["validation"],
        },
        "persistent_candidates": candidates,
        "initial_cycle": {
            "request_run": initial_request_run,
            "request": request1_data,
            "request_output": request1_output,
            "duckdb_rows": first_rows,
            "input_wmes": initial_input,
            "consume_run": initial_consume_run,
            "ack": ack1_data,
            "ack_output": ack1_output,
        },
        "cleanup": {"run": cleanup_run, "input_wmes": cleaned_input},
        "later_cycle": {
            "request_run": next_request_run,
            "request": request2_data,
            "request_output": request2_output,
            "duckdb_rows": next_rows,
            "input_wmes": next_input,
            "consume_run": next_consume_run,
            "ack": ack2_data,
            "ack_output": ack2_output,
        },
        "final_output": final_output,
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "persistent_candidates": len(candidates),
                "initial_beam": first_ids,
                "initial_selected": ack1_data["selected_hypothesis"],
                "removed_from_working_memory": first_ids,
                "later_reactivated": next_ids,
                "ret03_episodes_sha256": ret_episodes_hash,
                "verdict": "GO_REAL_SML_DUCKDB_RETRIEVAL_BRIDGE",
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
                "duckdb": importlib.metadata.version("duckdb"),
                "pyarrow": importlib.metadata.version("pyarrow"),
                "pythonpath": os.environ.get("PYTHONPATH"),
                "initial_top_k": 2,
                "later_top_k": 1,
            },
            indent=2,
        )
        + "\n"
    )
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("SOAR-05: SML request, DuckDB top-k, WME cleanup and later reactivation verified; GO")


if __name__ == "__main__":
    main()
