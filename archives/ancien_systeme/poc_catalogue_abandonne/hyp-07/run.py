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
HYP06_RESULTS = ROOT / "poc" / "hyp-06" / "output" / "results.json"
HYP08_RESULTS = ROOT / "poc" / "hyp-08" / "output" / "results.json"
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
    assert all(
        path.exists() for path in (HYP04_RESULTS, HYP06_RESULTS, HYP08_RESULTS)
    ), "Run HYP-04, HYP-06 and HYP-08 first"
    hyp04_hash = sha256(HYP04_RESULTS)
    hyp06_hash = sha256(HYP06_RESULTS)
    hyp08_hash = sha256(HYP08_RESULTS)
    hyp04 = json.loads(HYP04_RESULTS.read_text())
    hyp06 = json.loads(HYP06_RESULTS.read_text())
    hyp08 = json.loads(HYP08_RESULTS.read_text())
    assert hyp04["validation"]["ledger_unchanged_by_ranking"]
    integrated_sharing = hyp06["integrated_hypothesis_sharing"]
    integrated_cold = hyp08["integrated_cold_storage"]
    assert integrated_sharing["sources"]["hyp04_results_sha256"] == hyp04_hash
    assert integrated_cold["sources"]["hyp06_results_sha256"] == hyp06_hash
    assert integrated_cold["sources"]["hyp04_results_sha256"] == hyp04_hash

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

    # Trajet intégré sur les quatre vraies hypothèses HYP-04. Les fermetures
    # structurelles viennent du DAG partagé HYP-06; H4 entre depuis l'archive
    # froide HYP-08 à la suite d'un signal contextuel explicite. Ce signal est
    # un boost d'activation opérationnel, pas une sélection de vérité.
    greeting_scores = {
        row["hypothesis_id"]: row["score"] for row in hyp04["rankings"]["greeting"]
    }
    actual_candidates = []
    for hypothesis_id, cognitive_id in sorted(
        integrated_sharing["hypothesis_artifact_ids"].items()
    ):
        from_cold_store = hypothesis_id == integrated_cold["cold_hypothesis_id"]
        context_activation = 6.0 if from_cold_store else 0.0
        actual_candidates.append(
            {
                "hypothesis_id": hypothesis_id,
                "cognitive_artifact_id": cognitive_id,
                "family": "fallback-oov" if from_cold_store else "active-interpretation",
                "prior_score": greeting_scores[hypothesis_id] + context_activation,
                "evidence_score": greeting_scores[hypothesis_id],
                "context_activation": context_activation,
                "structural_features_json": json.dumps(
                    integrated_sharing["reconstructed_closures"][hypothesis_id]
                ),
                "from_cold_store": from_cold_store,
                "revealed_utility": greeting_scores[hypothesis_id] + context_activation,
                "revealed_correct": False,
            }
        )
    actual_candidates.sort(key=lambda row: (-row["prior_score"], row["hypothesis_id"]))
    actual_store = OUT / "integrated-candidates.parquet"
    pq.write_table(pa.Table.from_pylist(actual_candidates), actual_store, compression="zstd")
    actual_beam, actual_trace = diversify(actual_candidates, 3)
    actual_beam_ids = [row["hypothesis_id"] for row in actual_beam]

    actual_agent = kernel.CreateAgent("hyp07-integrated")
    assert actual_agent is not None and not actual_agent.HadError()
    actual_input = actual_agent.GetInputLink()
    actual_input_name = actual_input.GetIdentifierName()
    actual_input.CreateStringWME("phase", "integrated-beam-ready")
    actual_wme = actual_input.CreateIdWME("active-beam")
    actual_wme.CreateIntWME("bound", 3)
    actual_wme.CreateStringWME("selection-semantics", "operational-not-truth")
    for rank, row in enumerate(actual_beam, start=1):
        item = actual_wme.CreateIdWME("hypothesis")
        item.CreateIntWME("rank", rank)
        item.CreateStringWME("hypothesis-id", row["hypothesis_id"])
        item.CreateStringWME("cognitive-artifact-id", row["cognitive_artifact_id"])
        item.CreateStringWME("from-cold-store", "yes" if row["from_cold_store"] else "no")
        item.CreateFloatWME("operational-score", row["prior_score"])
        for shared_ref in json.loads(row["structural_features_json"]):
            item.CreateStringWME("shared-justification-ref", shared_ref)
    actual_agent.Commit()
    actual_source = actual_agent.ExecuteCommandLine(
        r"""
sp {hyp07-integrated*select-reactivated
   (state <s> ^io <io>)
   (<io> ^input-link <input> ^output-link <output>)
   (<input> ^phase integrated-beam-ready ^active-beam <beam>)
   (<beam> ^hypothesis <hypothesis>)
   (<hypothesis> ^hypothesis-id <id> ^cognitive-artifact-id <artifact>
                 ^from-cold-store yes)
-->
   (<output> ^beam-decision <decision>)
   (<decision> ^selected-hypothesis <id> ^cognitive-artifact-id <artifact>
               ^selection-semantics operational-not-truth)}
"""
    )
    actual_run = actual_agent.ExecuteCommandLine("run 1")
    actual_top = actual_agent.ExecuteCommandLine("print S1 --depth 2")
    actual_output_match = re.search(r"\^output-link ([A-Z]\d+)", actual_top)
    assert actual_output_match, actual_top
    actual_beam_input = actual_agent.ExecuteCommandLine(
        f"print {actual_input_name} --depth 10"
    )
    actual_beam_output = actual_agent.ExecuteCommandLine(
        f"print {actual_output_match.group(1)} --depth 5"
    )

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
        "integrated_sources_hash_chained": (
            integrated_sharing["sources"]["hyp04_results_sha256"] == hyp04_hash
            and integrated_cold["sources"]["hyp06_results_sha256"] == hyp06_hash
            and integrated_cold["sources"]["hyp04_results_sha256"] == hyp04_hash
        ),
        "integrated_candidates_preserve_cognitive_ids": {
            row["hypothesis_id"]: row["cognitive_artifact_id"]
            for row in actual_candidates
        }
        == integrated_sharing["hypothesis_artifact_ids"],
        "integrated_beam_is_bounded": len(actual_beam) == 3,
        "cold_hypothesis_reactivated_into_beam": (
            integrated_cold["cold_hypothesis_id"] in actual_beam_ids
            and integrated_cold["active_count_after_reactivation"] == 4
            and integrated_cold["expected_derived_sha256"]
            == integrated_cold["regenerated_derived_sha256"]
        ),
        "shared_justifications_transmitted_without_copy_ids": all(
            shared_ref in actual_beam_input
            for row in actual_beam
            for shared_ref in json.loads(row["structural_features_json"])
        ),
        "real_soar_selects_reactivated_actual_hypothesis_operationally": (
            "^selected-hypothesis hyp:H4" in actual_beam_output
            and integrated_cold["hypothesis_artifact_id"] in actual_beam_output
            and "^selection-semantics operational-not-truth" in actual_beam_output
            and "1 rule fired" in actual_run
        ),
    }
    assert all(validations.values()), validations

    result = {
        "soar_version": version,
        "parameters": {"beam_size": BEAM_SIZE, "diversity_weight": DIVERSITY_WEIGHT},
        "hyp04_results_sha256": hyp04_hash,
        "hyp06_results_sha256": hyp06_hash,
        "hyp08_results_sha256": hyp08_hash,
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
        "integrated_actual_flow": {
            "source_hypotheses": actual_candidates,
            "candidate_store": actual_store.name,
            "candidate_store_sha256": sha256(actual_store),
            "beam_ids": actual_beam_ids,
            "diversity_trace": actual_trace,
            "cold_reactivation": integrated_cold,
            "soar": {
                "source": actual_source,
                "run": actual_run,
                "input": actual_beam_input,
                "output": actual_beam_output,
            },
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
                "integrated_actual_beam_ids": actual_beam_ids,
                "integrated_reactivated_hypothesis": integrated_cold[
                    "cold_hypothesis_id"
                ],
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
    kernel.DestroyAgent(actual_agent)
    kernel.DestroyAgent(agent)
    kernel.Shutdown()
    print("HYP-07: diverse beam preserves B-01, reaches oracle regret and is bounded in Soar; GO")


if __name__ == "__main__":
    main()
