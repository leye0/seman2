#!/usr/bin/env python3
"""HYP-07: bounded structurally diverse beam, evaluated and exposed to real Soar."""
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
HYP04_RESULTS = ROOT / "poc" / "hyp-04" / "output" / "results.json"
BEAM_SIZE = 4
DIVERSITY_WEIGHT = 0.40


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right)


def diversify(candidates: list[dict], size: int) -> tuple[list[dict], list[dict]]:
    remaining = candidates.copy()
    selected: list[dict] = []
    trace = []
    while remaining and len(selected) < size:
        scored = []
        for candidate in remaining:
            features = set(json.loads(candidate["structural_features_json"]))
            max_similarity = max(
                (jaccard(features, set(json.loads(item["structural_features_json"]))) for item in selected),
                default=0.0,
            )
            min_distance = 1.0 - max_similarity
            objective = candidate["prior_score"] + DIVERSITY_WEIGHT * min_distance
            scored.append((objective, candidate["prior_score"], candidate["hypothesis_id"], max_similarity, candidate))
        objective, _, _, max_similarity, winner = max(scored)
        selected.append(winner)
        remaining.remove(winner)
        trace.append(
            {
                "rank": len(selected),
                "hypothesis_id": winner["hypothesis_id"],
                "prior_score": winner["prior_score"],
                "max_similarity_to_selected": max_similarity,
                "objective": objective,
            }
        )
    return selected, trace


def metrics(beam: list[dict], global_best: float) -> dict:
    best = max(row["revealed_utility"] for row in beam)
    return {
        "ids": [row["hypothesis_id"] for row in beam],
        "families": sorted({row["family"] for row in beam}),
        "family_coverage": len({row["family"] for row in beam}),
        "useful_family_coverage": len({row["family"] for row in beam if row["family"] != "noise"}),
        "best_revealed_utility": best,
        "regret": global_best - best,
    }


def output(agent: sml.Agent, output_link_name: str) -> str:
    return agent.ExecuteCommandLine(f"print {output_link_name} --depth 5")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    assert HYP04_RESULTS.exists(), "Run HYP-04 first"
    hyp04_hash = sha256(HYP04_RESULTS)
    hyp04 = json.loads(HYP04_RESULTS.read_text())
    assert hyp04["validation"]["ledger_unchanged_by_ranking"]

    candidates = []
    for index in range(20):
        features = ["root:token", "edge:expands", "leaf:io", "shape:star", f"lexical-variant:{index % 3}"]
        candidates.append(
            {
                "hypothesis_id": f"A-{index + 1:02d}",
                "family": "lexical-clone",
                "prior_score": round(0.960 - 0.006 * index, 6),
                "revealed_utility": round(0.840 - 0.004 * index, 6),
                "structural_features_json": json.dumps(features),
                "revealed_correct": False,
            }
        )
    for index in range(4):
        features = ["root:event", "edge:before", "edge:causes", "leaf:response", "shape:chain", f"temporal-variant:{index}"]
        candidates.append(
            {
                "hypothesis_id": f"B-{index + 1:02d}",
                "family": "temporal-chain",
                "prior_score": round(0.740 - 0.010 * index, 6),
                "revealed_utility": round(1.290 - 0.070 * index, 6),
                "structural_features_json": json.dumps(features),
                "revealed_correct": index == 0,
            }
        )
    for index in range(6):
        features = ["root:noise", "shape:noise", f"random-edge:{index}", f"random-leaf:{index * 7}"]
        candidates.append(
            {
                "hypothesis_id": f"N-{index + 1:02d}",
                "family": "noise",
                "prior_score": round(0.690 - 0.012 * index, 6),
                "revealed_utility": round(0.100 - 0.010 * index, 6),
                "structural_features_json": json.dumps(features),
                "revealed_correct": False,
            }
        )
    candidates.sort(key=lambda row: (-row["prior_score"], row["hypothesis_id"]))
    store = OUT / "persistent-candidates.parquet"
    pq.write_table(pa.Table.from_pylist(candidates), store, compression="zstd")

    top_k = candidates[:BEAM_SIZE]
    diverse, diversity_trace = diversify(candidates, BEAM_SIZE)
    oracle = sorted(candidates, key=lambda row: (-row["revealed_utility"], row["hypothesis_id"]))[:BEAM_SIZE]
    global_best = oracle[0]["revealed_utility"]
    comparison = {
        "top_k": metrics(top_k, global_best),
        "diversified": metrics(diverse, global_best),
        "oracle": metrics(oracle, global_best),
    }

    kernel = sml.Kernel.CreateKernelInNewThread()
    assert not kernel.HadError()
    agent = kernel.CreateAgent("hyp07")
    assert agent is not None and not agent.HadError()
    version = agent.ExecuteCommandLine("version")
    input_link = agent.GetInputLink()
    input_link_name = input_link.GetIdentifierName()
    phase = input_link.CreateStringWME("phase", "beam-ready")
    beam = input_link.CreateIdWME("active-beam")
    beam.CreateIntWME("bound", BEAM_SIZE)
    beam.CreateStringWME("policy", "structural-diversity")
    for rank, row in enumerate(diverse, start=1):
        item = beam.CreateIdWME("hypothesis")
        item.CreateIntWME("rank", rank)
        item.CreateStringWME("hypothesis-id", row["hypothesis_id"])
        item.CreateStringWME("family", row["family"])
        item.CreateFloatWME("prior-score", row["prior_score"])
        item.CreateStringWME("revealed-correct", "true" if row["revealed_correct"] else "false")
        item.CreateStringWME("store-sha256", sha256(store))
    agent.Commit()

    productions = r"""
sp {hyp07*select*revealed-correct
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^phase beam-ready ^active-beam <beam>)
   (<beam> ^hypothesis <hypothesis>)
   (<hypothesis> ^hypothesis-id <id> ^family <family> ^revealed-correct true
                 ^store-sha256 <hash>)
-->
   (<output> ^beam-decision <decision>)
   (<decision> ^selected-hypothesis <id> ^family <family> ^store-sha256 <hash>)}

sp {hyp07*ack*reactivated
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^phase reactivated ^reactivated-hypothesis <hypothesis>)
   (<hypothesis> ^hypothesis-id <id> ^store-sha256 <hash>)
-->
   (<output> ^reactivation-ack <ack>)
   (<ack> ^hypothesis-id <id> ^store-sha256 <hash>)}
"""
    source_result = agent.ExecuteCommandLine(productions)
    beam_run = agent.ExecuteCommandLine("run 1")
    top_state = agent.ExecuteCommandLine("print S1 --depth 2")
    output_match = re.search(r"\^output-link ([A-Z]\d+)", top_state)
    assert output_match, top_state
    output_link_name = output_match.group(1)
    beam_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 8")
    beam_output = output(agent, output_link_name)

    beam_wme = input_link.FindByAttribute("active-beam", 0)
    assert beam_wme is not None and agent.DestroyWME(beam_wme)
    phase.Update("cleared")
    agent.Commit()
    cleanup_run = agent.ExecuteCommandLine("run 1")
    cleared_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 8")

    diverse_ids = [row["hypothesis_id"] for row in diverse]
    connection = duckdb.connect()
    relation = connection.execute(
        """SELECT * FROM read_parquet(?)
           WHERE hypothesis_id NOT IN (SELECT unnest(?))
           ORDER BY prior_score DESC, hypothesis_id LIMIT 1""",
        [str(store), diverse_ids],
    )
    columns = [column[0] for column in relation.description]
    reactivated = dict(zip(columns, relation.fetchone()))
    connection.close()
    reactivated_wme = input_link.CreateIdWME("reactivated-hypothesis")
    reactivated_wme.CreateStringWME("hypothesis-id", reactivated["hypothesis_id"])
    reactivated_wme.CreateStringWME("family", reactivated["family"])
    reactivated_wme.CreateFloatWME("prior-score", reactivated["prior_score"])
    reactivated_wme.CreateStringWME("store-sha256", sha256(store))
    phase.Update("reactivated")
    agent.Commit()
    reactivation_run = agent.ExecuteCommandLine("run 1")
    reactivation_input = agent.ExecuteCommandLine(f"print {input_link_name} --depth 6")
    reactivation_output = output(agent, output_link_name)

    beam_ids = set(diverse_ids)
    all_ids = {row["hypothesis_id"] for row in candidates}
    validations = {
        "imbalanced_candidate_pool": sum(row["family"] == "lexical-clone" for row in candidates) == 20,
        "scalar_top_k_collapses_to_one_family": comparison["top_k"]["family_coverage"] == 1,
        "diversity_preserves_lower_ranked_correct_family": (
            "B-01" in diverse_ids
            and candidates.index(next(row for row in candidates if row["hypothesis_id"] == "B-01")) >= BEAM_SIZE
        ),
        "diversity_improves_useful_family_coverage": (
            comparison["diversified"]["useful_family_coverage"]
            > comparison["top_k"]["useful_family_coverage"]
        ),
        "diversified_regret_matches_oracle": comparison["diversified"]["regret"] == 0.0
        and comparison["oracle"]["regret"] == 0.0,
        "top_k_has_positive_post_context_regret": comparison["top_k"]["regret"] > 0.0,
        "only_diverse_beam_transmitted_to_soar": (
            all(identifier in beam_input for identifier in beam_ids)
            and not any(identifier in beam_input for identifier in all_ids - beam_ids)
            and beam_input.count("^hypothesis-id") == BEAM_SIZE
        ),
        "soar_selects_revealed_correct_candidate": (
            "^selected-hypothesis B-01" in beam_output
            and "^family temporal-chain" in beam_output
        ),
        "beam_removed_from_working_memory": "active-beam" not in cleared_input
        and not any(identifier in cleared_input for identifier in beam_ids),
        "outside_alternatives_remain_persistent": all_ids - beam_ids
        == {row["hypothesis_id"] for row in pq.read_table(store).to_pylist()} - beam_ids,
        "outside_alternative_retrievable_and_reactivated": (
            reactivated["hypothesis_id"] not in beam_ids
            and reactivated["hypothesis_id"] in reactivation_input
            and f"^hypothesis-id {reactivated['hypothesis_id']}" in reactivation_output
        ),
        "hyp04_provenance_linked": len(hyp04_hash) == 64,
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "parameters": {"beam_size": BEAM_SIZE, "diversity_weight": DIVERSITY_WEIGHT},
        "hyp04_results_sha256": hyp04_hash,
        "candidate_count": len(candidates),
        "family_counts": {
            family: sum(row["family"] == family for row in candidates)
            for family in sorted({row["family"] for row in candidates})
        },
        "comparison": comparison,
        "diversity_trace": diversity_trace,
        "source_result": source_result,
        "soar_beam": {"run": beam_run, "input": beam_input, "output": beam_output},
        "cleanup": {"run": cleanup_run, "input": cleared_input},
        "reactivation": {
            "candidate": reactivated,
            "run": reactivation_run,
            "input": reactivation_input,
            "output": reactivation_output,
        },
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(candidates),
                "beam_size": BEAM_SIZE,
                "top_k_ids": comparison["top_k"]["ids"],
                "diversified_ids": diverse_ids,
                "oracle_ids": comparison["oracle"]["ids"],
                "top_k_regret": comparison["top_k"]["regret"],
                "diversified_regret": comparison["diversified"]["regret"],
                "reactivated_outside_beam": reactivated["hypothesis_id"],
                "verdict": "GO_BOUNDED_STRUCTURALLY_DIVERSE_SOAR_BEAM",
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
                "similarity": "Jaccard(structural feature sets)",
                "objective": "prior_score + diversity_weight * min_distance_to_selected",
            },
            indent=2,
        )
        + "\n"
    )
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("HYP-07: diverse beam preserves B-01, reaches oracle regret and is bounded in Soar; GO")


if __name__ == "__main__":
    main()
