#!/usr/bin/env python3
"""SEM-06: online acquisition of an anonymous conditional semiotic relation."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import duckdb
import networkx as nx
import polars as pl
from scipy.stats import beta

from seman2_runtime.cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    thaw_json,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    IngestionRecord,
    build_foundation_modules,
    ingest_records,
    register_foundation_types,
)
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
OUTPUT = POC / "output"
BUILD = "sem-06-online-semiotic-acquisition"
INPUTS = (
    "sem-05",
    "ind-03",
    "ind-04",
    "ind-05",
    "ind-06",
    "hyp-01",
    "hyp-02",
    "hyp-03",
    "hyp-04",
    "hyp-05",
    "hyp-06",
)


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def load_inputs() -> tuple[dict[str, dict], list[dict]]:
    values = {}
    provenance = []
    for name in INPUTS:
        result_path = ROOT / "poc" / name / "output/results.json"
        summary_path = ROOT / "poc" / name / "output/summary.json"
        assert result_path.is_file() and summary_path.is_file(), name
        values[name] = {
            "result": json.loads(result_path.read_text(encoding="utf-8")),
            "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        }
        provenance.append(
            {
                "poc": name.upper(),
                "result_path": str(result_path.relative_to(ROOT)),
                "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            }
        )
    return values, provenance


def representation_clusters(sem05: dict) -> tuple[dict[str, str], dict[str, list[str]]]:
    graph = nx.Graph()
    for node in sem05["index"]["nodes"]:
        graph.add_node(node["node_id"], plane=node["plane"], value=node["value"])
    for edge in sem05["index"]["edges"]:
        graph.add_edge(edge["source"], edge["target"], relation=edge["relation"])
    by_form = {
        node["value"]: node["node_id"]
        for node in sem05["index"]["nodes"]
        if node["plane"] == "form"
    }
    cluster_by_form = {}
    members_by_cluster = {}
    for form, node_id in by_form.items():
        component = sorted(nx.node_connected_component(graph, node_id))
        cluster = "anon:" + digest(component)[:24]
        cluster_by_form[form] = cluster
        members_by_cluster[cluster] = component
    return cluster_by_form, members_by_cluster


def make_observed_rows(cluster_by_form: dict[str, str]) -> tuple[list[dict], list[dict], dict]:
    target_forms = ("io", "i/o", "Io")
    assert all(form in cluster_by_form for form in (*target_forms, "yo"))
    episodes = []
    for index in range(36):
        if index < 28:
            form = target_forms[index % len(target_forms)]
            context = "c_initial"
            outcome = "effect_e1" if index < 24 else "effect_e0"
        elif index < 32:
            form = target_forms[index % len(target_forms)]
            context = "c_other"
            outcome = "effect_e0"
        else:
            form = "unrelated-form"
            context = "c_initial"
            outcome = "effect_e0"
        row = {
            "kind": "episode",
            "episode_id": f"e{index:02d}",
            "time": index,
            "speaker": f"s{index % 6}",
            "domain": f"d{index % 4}",
            "form": form,
            "context": context,
            "observed_effect": outcome,
        }
        row["observation_sha256"] = digest(row)
        episodes.append(row)
    corrections = [
        {
            "kind": "correction",
            "correction_id": f"corr-e{index:02d}",
            "target_episode_id": f"e{index:02d}",
            "time": 40 + index,
            "replacement_effect": "effect_e1",
            "reason": "later explicit observed outcome",
            "original_observation_sha256": episodes[index]["observation_sha256"],
        }
        for index in (24, 25, 26)
    ]
    heldout = {
        "kind": "evaluation",
        "episode_id": "heldout-01",
        "time": 100,
        "speaker": "s_new",
        "domain": "d_new",
        "form": "yo",
        "context": "c_initial",
        "observed_effect": "effect_e1",
    }
    return episodes, corrections, heldout


def build_runtime(
    *,
    cluster_by_form: dict[str, str],
    members_by_cluster: dict[str, list[str]],
    minimum_support: int,
    configuration_digest: str,
) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            "semiotic-episode",
            "seman2/semiotic-episode",
            2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-observation-adapter"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {
                    "episode_id",
                    "speaker",
                    "domain",
                    "form",
                    "representation_cluster",
                    "context",
                    "observed_effect",
                    "observation_sha256",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semiotic-correction",
            "seman2/semiotic-correction",
            2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-observation-adapter"}),
            parent_types=frozenset({"observation", "semiotic-episode"}),
            required_native_fields=frozenset(
                {"correction_id", "target_episode_ref", "replacement_effect", "reason"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semiotic-heldout-occurrence",
            "seman2/semiotic-heldout-occurrence",
            2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-observation-adapter"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {"episode_id", "form", "representation_cluster", "context", "observed_effect"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semiotic-statistics",
            "seman2/semiotic-statistics",
            3,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-statistics-system"}),
            parent_types=frozenset({"semiotic-episode", "semiotic-correction"}),
            required_native_fields=frozenset(
                {"episode_count", "groups", "correction_refs", "alternatives_counted_once"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semiotic-hypothesis-family",
            "seman2/semiotic-hypothesis-family",
            4,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-hypothesis-manager"}),
            parent_types=frozenset({"semiotic-statistics"}),
            required_native_fields=frozenset(
                {"candidates", "selected_candidate_id", "factorized", "selection_reason"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "learned-semiotic-relation",
            "seman2/learned-semiotic-relation",
            5,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-induction-engine"}),
            parent_types=frozenset({"semiotic-hypothesis-family"}),
            required_native_fields=frozenset(
                {
                    "relation_id",
                    "conditions",
                    "predicted_effect",
                    "support_refs",
                    "contradiction_refs",
                    "conditional_probability",
                    "credible_interval_95",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semiotic-heldout-prediction",
            "seman2/semiotic-heldout-prediction",
            6,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"semiotic-predictor"}),
            parent_types=frozenset({"semiotic-heldout-occurrence", "learned-semiotic-relation"}),
            required_native_fields=frozenset(
                {"heldout_ref", "relation_ref", "matched_conditions", "predicted_effect"}
            ),
        )
    )
    registry.freeze()

    def cluster(form: str) -> str:
        return cluster_by_form.get(form, "anon-unlinked:" + digest(form)[:24])

    def adapt_observation(trigger, context):
        row = json.loads(str(trigger.payload_native["text"]))
        if row["kind"] == "episode":
            yield ArtifactProposal(
                artifact_type="semiotic-episode",
                producer_id="semiotic-observation-adapter",
                producer_build=BUILD,
                configuration_digest=configuration_digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id,),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    **row,
                    "representation_cluster": cluster(row["form"]),
                    "representation_members": members_by_cluster.get(cluster(row["form"]), []),
                },
                payload_projection={"asserted_taxonomy": None, "source_rewritten": False},
                justification_ids=(trigger.artifact_id,),
                idempotency_key=f"semiotic-episode:{row['episode_id']}",
            )
        elif row["kind"] == "correction":
            target = next(
                episode
                for episode in context.arena.query(
                    artifact_type="semiotic-episode", session_id=trigger.session_id
                )
                if episode.payload_native["episode_id"] == row["target_episode_id"]
            )
            assert target.payload_native["observation_sha256"] == row["original_observation_sha256"]
            yield ArtifactProposal(
                artifact_type="semiotic-correction",
                producer_id="semiotic-observation-adapter",
                producer_build=BUILD,
                configuration_digest=configuration_digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id, target.artifact_id),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    "correction_id": row["correction_id"],
                    "target_episode_ref": target.artifact_id,
                    "replacement_effect": row["replacement_effect"],
                    "reason": row["reason"],
                    "original_observation_sha256": row["original_observation_sha256"],
                },
                payload_projection={"target_mutated": False},
                justification_ids=(trigger.artifact_id, target.artifact_id),
                idempotency_key=f"semiotic-correction:{row['correction_id']}",
            )
        elif row["kind"] == "evaluation":
            yield ArtifactProposal(
                artifact_type="semiotic-heldout-occurrence",
                producer_id="semiotic-observation-adapter",
                producer_build=BUILD,
                configuration_digest=configuration_digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id,),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    **row,
                    "representation_cluster": cluster(row["form"]),
                    "representation_members": members_by_cluster.get(cluster(row["form"]), []),
                },
                payload_projection={"included_in_training": False},
                justification_ids=(trigger.artifact_id,),
                idempotency_key=f"semiotic-heldout:{row['episode_id']}",
            )

    def statistics(trigger, context):
        episodes = list(
            context.arena.query(
                artifact_type="semiotic-episode",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
        )
        corrections = list(
            context.arena.query(
                artifact_type="semiotic-correction",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
        )
        corrected = {
            row.payload_native["target_episode_ref"]: row.payload_native["replacement_effect"]
            for row in corrections
        }
        groups: dict[tuple[str, str], dict] = {}
        for episode in episodes:
            key = (
                episode.payload_native["representation_cluster"],
                episode.payload_native["context"],
            )
            group = groups.setdefault(
                key,
                {
                    "representation_cluster": key[0],
                    "context": key[1],
                    "episode_refs": [],
                    "speakers": set(),
                    "domains": set(),
                    "effect_counts": Counter(),
                },
            )
            group["episode_refs"].append(episode.artifact_id)
            group["speakers"].add(episode.payload_native["speaker"])
            group["domains"].add(episode.payload_native["domain"])
            outcome = corrected.get(episode.artifact_id, episode.payload_native["observed_effect"])
            group["effect_counts"][outcome] += 1
        serialized_groups = [
            {
                **{key: value for key, value in group.items() if key not in {"speakers", "domains", "effect_counts"}},
                "speakers": sorted(group["speakers"]),
                "domains": sorted(group["domains"]),
                "effect_counts": dict(sorted(group["effect_counts"].items())),
            }
            for _, group in sorted(groups.items())
        ]
        parents = tuple(episode.artifact_id for episode in episodes) + tuple(
            correction.artifact_id for correction in corrections
        )
        yield ArtifactProposal(
            artifact_type="semiotic-statistics",
            producer_id="semiotic-statistics-system",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=parents,
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "episode_count": len(episodes),
                "groups": serialized_groups,
                "correction_refs": [row.artifact_id for row in corrections],
                "alternatives_counted_once": True,
            },
            payload_projection={"descriptive_only": True},
            justification_ids=parents,
            idempotency_key=f"semiotic-statistics:{trigger.artifact_id}",
        )

    def hypotheses(trigger, context):
        groups = list(trigger.payload_native["groups"])
        dominant = max(
            groups,
            key=lambda row: (
                sum(row["effect_counts"].values()),
                row["representation_cluster"],
                row["context"],
            ),
        )
        target_cluster = dominant["representation_cluster"]
        target_context = dominant["context"]
        target_effect = max(
            dominant["effect_counts"], key=dominant["effect_counts"].get
        )
        episode_by_ref = {
            row.artifact_id: row
            for row in context.arena.query(
                artifact_type="semiotic-episode", session_id=trigger.session_id
            )
        }
        candidates = []
        specifications = (
            ("form-only", lambda row: row.payload_native["representation_cluster"] == target_cluster, 1),
            ("context-only", lambda row: row.payload_native["context"] == target_context, 1),
            ("joint", lambda row: row.payload_native["representation_cluster"] == target_cluster and row.payload_native["context"] == target_context, 2),
        )
        corrections = {
            row.payload_native["target_episode_ref"]: row.payload_native["replacement_effect"]
            for row in context.arena.query(
                artifact_type="semiotic-correction", session_id=trigger.session_id
            )
            if row.wave <= context.scheduled_wave
        }
        for kind, predicate, specificity in specifications:
            matching = [row for row in episode_by_ref.values() if row.wave <= context.scheduled_wave and predicate(row)]
            supports = [row.artifact_id for row in matching if corrections.get(row.artifact_id, row.payload_native["observed_effect"]) == target_effect]
            contradictions = [row.artifact_id for row in matching if corrections.get(row.artifact_id, row.payload_native["observed_effect"]) != target_effect]
            probability = len(supports) / len(matching) if matching else 0.0
            candidates.append(
                {
                    "candidate_id": f"candidate:{kind}",
                    "kind": kind,
                    "conditions": {
                        "representation_cluster": target_cluster if kind != "context-only" else None,
                        "context": target_context if kind != "form-only" else None,
                    },
                    "predicted_effect": target_effect,
                    "support_refs": supports,
                    "contradiction_refs": contradictions,
                    "conditional_probability": probability,
                    "specificity": specificity,
                    "score": probability + specificity * 0.001,
                }
            )
        eligible = [
            row
            for row in candidates
            if len(row["support_refs"]) >= minimum_support
            and row["conditional_probability"] >= 0.75
        ]
        selected = max(eligible, key=lambda row: (row["score"], row["candidate_id"])) if eligible else None
        yield ArtifactProposal(
            artifact_type="semiotic-hypothesis-family",
            producer_id="semiotic-hypothesis-manager",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "candidates": candidates,
                "selected_candidate_id": selected["candidate_id"] if selected else None,
                "factorized": True,
                "selection_reason": "evidence-threshold-and-specificity" if selected else "insufficient-evidence",
            },
            payload_projection={"cartesian_product_materialized": False, "historical_hypotheses_mutated": False},
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"semiotic-hypotheses:{trigger.artifact_id}",
        )

    def learn(trigger, context):
        selected_id = trigger.payload_native["selected_candidate_id"]
        if selected_id is None:
            return
        selected = next(
            row for row in trigger.payload_native["candidates"] if row["candidate_id"] == selected_id
        )
        if selected["kind"] != "joint":
            return
        support_count = len(selected["support_refs"])
        contradiction_count = len(selected["contradiction_refs"])
        interval = beta.interval(0.95, support_count + 1, contradiction_count + 1)
        relation_id = "anonymous-semiotic:" + digest(
            {
                "conditions": thaw_json(selected["conditions"]),
                "effect": selected["predicted_effect"],
            }
        )[:24]
        yield ArtifactProposal(
            artifact_type="learned-semiotic-relation",
            producer_id="semiotic-induction-engine",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "relation_id": relation_id,
                "conditions": selected["conditions"],
                "predicted_effect": selected["predicted_effect"],
                "support_refs": selected["support_refs"],
                "contradiction_refs": selected["contradiction_refs"],
                "conditional_probability": selected["conditional_probability"],
                "credible_interval_95": list(interval),
            },
            payload_projection={"asserted_taxonomy": None, "conditional_not_universal": True},
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"learned-semiotic-relation:{trigger.artifact_id}",
        )

    def predict(trigger, context):
        learned = context.arena.query(
            artifact_type="learned-semiotic-relation", session_id=trigger.session_id
        )
        assert learned
        relation = learned[-1]
        conditions = relation.payload_native["conditions"]
        matched = {
            "representation_cluster": trigger.payload_native["representation_cluster"] == conditions["representation_cluster"],
            "context": trigger.payload_native["context"] == conditions["context"],
        }
        yield ArtifactProposal(
            artifact_type="semiotic-heldout-prediction",
            producer_id="semiotic-predictor",
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id, relation.artifact_id),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "heldout_ref": trigger.artifact_id,
                "relation_ref": relation.artifact_id,
                "matched_conditions": matched,
                "predicted_effect": relation.payload_native["predicted_effect"] if all(matched.values()) else None,
            },
            payload_projection={"actual_effect_used_for_prediction": False},
            justification_ids=(trigger.artifact_id, relation.artifact_id),
            idempotency_key=f"semiotic-heldout-prediction:{trigger.artifact_id}",
        )

    def spec(identifier, layer, consumes, produces, handler):
        return ModuleSpec(
            module_id=identifier,
            layer=layer,
            modes=frozenset({"ingestion"}),
            consumes=frozenset(consumes),
            produces=frozenset(produces),
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            handler=handler,
        )

    policy = IngestionPolicy(max_records=64, max_text_chars=2_000)
    return CognitiveRuntime(
        registry=registry,
        modules=(
            *build_foundation_modules(policy),
            spec("semiotic-observation-adapter", 2, {"observation"}, {"semiotic-episode", "semiotic-correction", "semiotic-heldout-occurrence"}, adapt_observation),
            spec("semiotic-statistics-system", 3, {"semiotic-episode", "semiotic-correction"}, {"semiotic-statistics"}, statistics),
            spec("semiotic-hypothesis-manager", 4, {"semiotic-statistics"}, {"semiotic-hypothesis-family"}, hypotheses),
            spec("semiotic-induction-engine", 5, {"semiotic-hypothesis-family"}, {"learned-semiotic-relation"}, learn),
            spec("semiotic-predictor", 6, {"semiotic-heldout-occurrence"}, {"semiotic-heldout-prediction"}, predict),
        ),
    )


def main() -> None:
    inputs, provenance = load_inputs()
    sem05 = inputs["sem-05"]["result"]
    cluster_by_form, members_by_cluster = representation_clusters(sem05)
    episodes, corrections, heldout = make_observed_rows(cluster_by_form)
    minimum_support = inputs["ind-03"]["summary"]["winner_support"]
    assert minimum_support == 8
    assert "promote" in inputs["ind-05"]["summary"]["actions"]
    assert inputs["hyp-01"]["summary"]["historical_object_mutation_count"] == 0
    assert inputs["hyp-05"]["summary"]["target_unrequested_compositions"] == 0
    assert inputs["hyp-06"]["summary"]["shared_to_naive_ratio"] < 1
    configuration_digest = digest(
        {
            "input_hashes": provenance,
            "minimum_support": minimum_support,
            "cluster_by_form": cluster_by_form,
        }
    )
    runtime = build_runtime(
        cluster_by_form=cluster_by_form,
        members_by_cluster=members_by_cluster,
        minimum_support=minimum_support,
        configuration_digest=configuration_digest,
    )
    observed_rows = [*episodes, *corrections, heldout]
    records = tuple(
        IngestionRecord(
            record_id=f"sem-06:{index:03d}",
            discourse_id="sem-06:chronological-acquisition",
            turn_index=index,
            speaker_role=row.get("speaker", "correction-source"),
            text=canonical_json(row),
            canonical_file="poc/sem-06/generated-observations.jsonl",
            source_position=index,
            source_record_id=row.get("episode_id", row.get("correction_id")),
            raw_body_sha256=digest(row),
            channel=row.get("domain", "correction-channel"),
            source_kind=f"semiotic-{row['kind']}",
            native_structure={"schema": "sem-06-observed-event-v1"},
        )
        for index, row in enumerate(observed_rows)
    )
    report = ingest_records(
        runtime,
        records,
        policy=IngestionPolicy(max_records=64, max_text_chars=2_000),
        session_id="sem-06:integration",
    )
    assert report["pending_tasks"] == 0
    learned_versions = runtime.arena.query(artifact_type="learned-semiotic-relation")
    predictions = runtime.arena.query(artifact_type="semiotic-heldout-prediction")
    assert learned_versions and len(predictions) == 1
    relation = learned_versions[-1]
    prediction = predictions[0]
    heldout_artifact = runtime.arena.get(prediction.payload_native["heldout_ref"])
    assert all(prediction.payload_native["matched_conditions"].values())
    assert prediction.payload_native["predicted_effect"] == heldout_artifact.payload_native["observed_effect"]
    assert not prediction.payload_projection["actual_effect_used_for_prediction"]

    episode_artifacts = runtime.arena.query(artifact_type="semiotic-episode")
    correction_artifacts = runtime.arena.query(artifact_type="semiotic-correction")
    before_hashes = {row["episode_id"]: row["observation_sha256"] for row in episodes}
    after_hashes = {
        row.payload_native["episode_id"]: row.payload_native["observation_sha256"]
        for row in episode_artifacts
    }
    assert before_hashes == after_hashes
    assert all(not row.payload_projection["target_mutated"] for row in correction_artifacts)
    assert set(relation.payload_native["support_refs"]).isdisjoint(relation.payload_native["contradiction_refs"])
    assert relation.payload_native["support_refs"] and relation.payload_native["contradiction_refs"]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(episodes).write_parquet(OUTPUT / "episodes.parquet", compression="zstd")
    pl.DataFrame(corrections).write_parquet(OUTPUT / "corrections.parquet", compression="zstd")
    database = duckdb.connect()
    episode_path = str((OUTPUT / "episodes.parquet").resolve()).replace("'", "''")
    correction_path = str((OUTPUT / "corrections.parquet").resolve()).replace("'", "''")
    database.execute(f"CREATE VIEW episodes AS SELECT * FROM read_parquet('{episode_path}')")
    database.execute(f"CREATE VIEW corrections AS SELECT * FROM read_parquet('{correction_path}')")
    independent = database.execute(
        """
        SELECT context,
               count(*) observations,
               count(DISTINCT speaker) speakers,
               count(DISTINCT domain) domains,
               sum((coalesce(c.replacement_effect, e.observed_effect)='effect_e1')::INT) supports,
               sum((coalesce(c.replacement_effect, e.observed_effect)!='effect_e1')::INT) contradictions
        FROM episodes e
        LEFT JOIN corrections c ON c.target_episode_id=e.episode_id
        WHERE e.form IN ('io', 'i/o', 'Io')
        GROUP BY context ORDER BY context
        """
    ).fetchall()
    database.close()
    independent_rows = [
        {"context": row[0], "observations": row[1], "speakers": row[2], "domains": row[3], "supports": row[4], "contradictions": row[5]}
        for row in independent
    ]
    target = next(row for row in independent_rows if row["context"] == "c_initial")
    assert target["supports"] == len(relation.payload_native["support_refs"])
    assert target["contradictions"] == len(relation.payload_native["contradiction_refs"])
    assert relation.payload_native["conditional_probability"] == target["supports"] / target["observations"]

    ancestry_types = {row.artifact_type for row in runtime.arena.ancestry(prediction.artifact_id)}
    required_ancestry = {
        "source-record",
        "observation",
        "semiotic-episode",
        "semiotic-correction",
        "semiotic-statistics",
        "semiotic-hypothesis-family",
        "learned-semiotic-relation",
        "semiotic-heldout-occurrence",
        "semiotic-heldout-prediction",
    }
    assert required_ancestry <= ancestry_types
    relation_text = canonical_json(thaw_json(relation.payload_native)).lower()
    forbidden_taxonomy = ("slang", "typo", "greeting", "joke", "humor")
    validations = {
        "chronological_training_only": max(row["time"] for row in episodes) < heldout["time"],
        "heldout_not_in_training": heldout["episode_id"] not in before_hashes,
        "heldout_prediction_correct": prediction.payload_native["predicted_effect"] == heldout["observed_effect"],
        "historical_observations_unchanged": before_hashes == after_hashes,
        "corrections_append_only": all(not row.payload_projection["target_mutated"] for row in correction_artifacts),
        "multiple_speakers_domains": target["speakers"] == 6 and target["domains"] == 4,
        "supports_and_contradictions_present": target["supports"] > 0 and target["contradictions"] > 0,
        "conditional_relation_selected": relation.payload_native["conditional_probability"] > 0.75,
        "no_forbidden_taxonomy_in_model": not any(value in relation_text for value in forbidden_taxonomy),
        "factorized_hypotheses": all(row.payload_native["factorized"] for row in runtime.arena.query(artifact_type="semiotic-hypothesis-family")),
        "runtime_ancestry_complete": required_ancestry <= ancestry_types,
        "duckdb_runtime_statistics_agree": True,
        "all_required_poc_artifacts_bound": len(provenance) == len(INPUTS),
    }
    assert all(validations.values()), validations
    result = {
        "independent_episode_statistics": independent_rows,
        "learned_relation": thaw_json(relation.payload_native),
        "learned_relation_artifact_id": relation.artifact_id,
        "learned_relation_version_count": len(learned_versions),
        "final_hypothesis_family": thaw_json(runtime.arena.get(relation.parent_ids[0]).payload_native),
        "supports": list(relation.payload_native["support_refs"]),
        "contradictions": list(relation.payload_native["contradiction_refs"]),
        "exceptions": [row for row in episodes if row["context"] == "c_initial" and row["observed_effect"] == "effect_e0"],
        "corrections": corrections,
        "heldout_prediction": {
            "fixture": heldout,
            "runtime_prediction": thaw_json(prediction.payload_native),
            "correct": True,
            "fixture_was_in_training": False,
        },
        "representation_clusters": members_by_cluster,
        "provenance_inputs": provenance,
        "prediction_ancestry_types": sorted(ancestry_types),
        "validations": validations,
    }
    summary = {
        "training_episodes": len(episodes),
        "corrections": len(corrections),
        "source_observations": len(records),
        "runtime_artifacts": len(runtime.arena),
        "learned_relation_versions": len(learned_versions),
        "target_supports": target["supports"],
        "target_contradictions": target["contradictions"],
        "conditional_probability": relation.payload_native["conditional_probability"],
        "heldout_correct": True,
        "historical_mutation_count": 0,
        "verdict": "GO_BOTTOM_UP_PROGRESSIVE_ANONYMOUS_SEMIOTIC_ACQUISITION",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "duckdb": importlib.metadata.version("duckdb"),
        "polars": importlib.metadata.version("polars"),
        "scipy": importlib.metadata.version("scipy"),
        "networkx": importlib.metadata.version("networkx"),
        "minimum_support_from_ind_03": minimum_support,
        "artifact_contracts": [
            "seman2/semiotic-episode",
            "seman2/semiotic-statistics",
            "seman2/semiotic-hypothesis-family",
            "seman2/learned-semiotic-relation",
        ],
    }
    for name, value in (
        ("results.json", result),
        ("summary.json", summary),
        ("versions-and-parameters.json", versions),
    ):
        (OUTPUT / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"SEM-06: {len(records)} observations -> {len(runtime.arena)} artifacts; "
        f"p={summary['conditional_probability']:.3f}; heldout yo correct; GO"
    )


if __name__ == "__main__":
    main()
