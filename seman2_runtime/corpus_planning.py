"""Chaîne de planification appuyée sur l'échantillon Parquet réel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from delphin.codecs import simplemrs

from .contracts import ContractError, Envelope, ServiceSpec, output_envelope, require_fields
from .corpus import CorpusSamplingService, sampling_request


class CorpusObservationService:
    spec = ServiceSpec(
        "corpus-observation", "corpus-sample-set", "observation-batch", ("corpus-sampling",)
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "samples", "sampling_policy")
        observations = []
        for sample in source.payload["samples"]:
            observations.append({
                "observation_id": f"observation:stackoverflow:{sample['question_id']}:title",
                "text": sample["title"],
                "modality": "text",
                "role": "question-title",
                "sample_id": sample["sample_id"],
                "criterion": sample["criterion"],
                "source": {
                    "canonical_file": sample["canonical_file"],
                    "source_file": sample["source_file"],
                    "source_position": sample["source_position"],
                    "source_record_id": sample["source_record_id"],
                    "raw_question_sha256": sample["raw_body_sha256"],
                    "answer_ids": [answer["answer_id"] for answer in sample["answers"]],
                },
            })
        if len(observations) != 3:
            raise ContractError(f"corpus-observation: attendu 3 observations, reçu {len(observations)}")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"observation-batch:{source.correlation_id}",
            payload={
                "observations": observations,
                "selection_is_derived": True,
                "raw_records_preserved_in_parent": True,
            },
        )


class LiveExternalAnalysisService:
    spec = ServiceSpec(
        "live-external-analysis", "observation-batch", "analyzed-corpus-batch", ("corpus-observation",)
    )

    def __init__(self, root: Path, timeout_seconds: int = 60) -> None:
        self.root = root.resolve()
        self.timeout_seconds = timeout_seconds

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "observations", "raw_records_preserved_in_parent")
        python = self.root / ".venv-dialogue/bin/python"
        worker = self.root / "seman2_runtime/dialogue_analysis_worker.py"
        for dependency in (python, worker, self.root / ".local/bin/ace", self.root / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"):
            if not dependency.is_file():
                raise ContractError(f"live-external-analysis: dépendance absente: {dependency}")
        request = {
            "root": str(self.root),
            "observations": source.payload["observations"],
        }
        environment = os.environ.copy()
        environment.update({
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TOKENIZERS_PARALLELISM": "false",
        })
        try:
            process = subprocess.run(
                [str(python), str(worker)],
                input=json.dumps(request, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContractError(f"live-external-analysis: délai de {self.timeout_seconds}s dépassé") from exc
        if process.returncode:
            raise ContractError(
                f"live-external-analysis: worker en échec: {process.stderr.strip()[-1000:]}"
            )
        try:
            rows = json.loads(process.stdout)["rows"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise ContractError("live-external-analysis: réponse worker invalide") from exc
        expected = {row["observation_id"] for row in source.payload["observations"]}
        received = {row["observation_id"] for row in rows}
        if received != expected:
            raise ContractError("live-external-analysis: observations perdues ou ajoutées")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"external-analysis:{source.correlation_id}",
            payload={
                "rows": rows,
                "worker_limits": {"batch_max": 16, "timeout_seconds": self.timeout_seconds, "threads": 1},
                "stderr_diagnostics": process.stderr.strip().splitlines()[-8:],
            },
            provenance=(str(worker.relative_to(self.root)),),
        )


class AnalysisLedgerService:
    """Enregistre succès et échecs sans exiger l'accord des producteurs."""

    spec = ServiceSpec(
        "analysis-ledger", "analyzed-corpus-batch", "analysis-ledger", ("live-external-analysis",)
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "rows", "worker_limits")
        entries = []
        for row in source.payload["rows"]:
            for analysis in row["analyses"]:
                producer = analysis["producer"]
                status = analysis["status"]
                candidate_count = analysis.get("candidate_count", 1 if status == "parsed" else 0)
                entries.append({
                    "entry_id": f"analysis-ledger:{row['observation_id']}:{producer}",
                    "observation_id": row["observation_id"],
                    "producer": producer,
                    "status": status,
                    "candidate_count": candidate_count,
                    "failure_is_evidence": status != "parsed",
                    "native_analysis": analysis,
                })
        expected = len(source.payload["rows"]) * 2
        if len(entries) != expected:
            raise ContractError(f"analysis-ledger: attendu {expected} entrées, reçu {len(entries)}")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"analysis-ledger:{source.correlation_id}",
            payload={
                "entries": entries,
                "observation_count": len(source.payload["rows"]),
                "success_count": sum(row["status"] == "parsed" for row in entries),
                "failure_count": sum(row["status"] != "parsed" for row in entries),
                "failures_preserved": True,
            },
        )


class MRSGraphAdapterService:
    """Convertit chaque MRS en fragment générique sans choisir un candidat."""

    spec = ServiceSpec(
        "mrs-graph-adapter", "analysis-ledger", "semantic-fragment-batch", ("analysis-ledger",)
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "entries", "failures_preserved")
        fragments = []
        unresolved = []
        for entry in source.payload["entries"]:
            if entry["producer"] != "ACE_ERG":
                if entry["status"] != "parsed":
                    unresolved.append({
                        "entry_id": entry["entry_id"],
                        "reason": "producer-failure-preserved",
                    })
                continue
            for candidate in entry["native_analysis"].get("candidates", []):
                mrs_text = candidate.get("mrs")
                if not mrs_text:
                    unresolved.append({
                        "entry_id": entry["entry_id"],
                        "reason": "missing-mrs",
                    })
                    continue
                try:
                    mrs = simplemrs.decode(mrs_text)
                except Exception as exc:
                    unresolved.append({
                        "entry_id": entry["entry_id"],
                        "reason": f"mrs-decode-failure:{type(exc).__name__}",
                    })
                    continue
                result_id = candidate.get("result_id")
                fragment_id = f"fragment:{entry['observation_id']}:erg:{result_id}"
                variables = [
                    {
                        "id": variable,
                        "sort": variable[0],
                        "properties": dict(properties),
                    }
                    for variable, properties in sorted(mrs.variables.items())
                ]
                relations = []
                role_edges = []
                for index, relation in enumerate(mrs.rels):
                    relation_id = f"{fragment_id}:relation:{index}"
                    relations.append({
                        "id": relation_id,
                        "predicate": relation.predicate,
                        "label": relation.label,
                        "surface": [relation.lnk.data[0], relation.lnk.data[1]]
                        if relation.lnk and relation.lnk.type == "charspan" else None,
                    })
                    for role, target in sorted(relation.args.items()):
                        role_edges.append({
                            "source": relation_id,
                            "role": role,
                            "target": target,
                        })
                fragments.append({
                    "fragment_id": fragment_id,
                    "observation_id": entry["observation_id"],
                    "producer": "ACE_ERG",
                    "formalism": "MRS",
                    "candidate_id": str(result_id),
                    "top": mrs.top,
                    "index": mrs.index,
                    "variables": variables,
                    "relations": relations,
                    "role_edges": role_edges,
                    "handle_constraints": [
                        {"high": constraint.hi, "relation": constraint.relation, "low": constraint.lo}
                        for constraint in mrs.hcons
                    ],
                    "individual_constraints": [
                        {"left": constraint.left, "relation": constraint.relation, "right": constraint.right}
                        for constraint in mrs.icons
                    ],
                    "native_mrs": mrs_text,
                    "selected": False,
                })
        if not fragments:
            raise ContractError("mrs-graph-adapter: aucun fragment MRS décodable")
        if len({row["fragment_id"] for row in fragments}) != len(fragments):
            raise ContractError("mrs-graph-adapter: identifiants de fragment dupliqués")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"semantic-fragments:{source.correlation_id}",
            payload={
                "fragments": fragments,
                "unresolved": unresolved,
                "ledger": source.payload["entries"],
                "candidate_selection_performed": False,
                "native_values_preserved": True,
            },
        )


class MRSFeatureProjectionService:
    """Projette fonction d'énoncé et candidats E/R/S sans combler les absences."""

    spec = ServiceSpec(
        "mrs-feature-projection",
        "semantic-fragment-batch",
        "semantic-feature-batch",
        ("mrs-graph-adapter",),
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "fragments", "unresolved", "ledger")
        projected = []
        temporal_unresolved = []
        for fragment in source.payload["fragments"]:
            index_variable = next(
                (row for row in fragment["variables"] if row["id"] == fragment["index"]),
                None,
            )
            properties = index_variable["properties"] if index_variable else {}
            sentence_force = properties.get("SF")
            tense = properties.get("TENSE")
            event = f"event:{fragment['fragment_id']}"
            reference = f"reference:{fragment['observation_id']}"
            speech = f"utterance:{fragment['observation_id']}"
            if tense == "pres":
                temporal = {
                    "status": "candidate",
                    "formalism": "Reichenbach E/R/S",
                    "roles": {"E": event, "R": reference, "S": speech},
                    "constraints": [
                        {"left": event, "operator": "=", "right": reference},
                        {"left": reference, "operator": "=", "right": speech},
                    ],
                    "absolute_coordinate": None,
                }
            else:
                temporal = {
                    "status": "underspecified",
                    "formalism": "Reichenbach E/R/S",
                    "roles": {"E": event, "R": reference, "S": speech},
                    "constraints": [],
                    "absolute_coordinate": None,
                    "reason": "MRS tense is untensed or absent",
                }
                temporal_unresolved.append({
                    "fragment_id": fragment["fragment_id"],
                    "observed_tense": tense,
                    "reason": temporal["reason"],
                })
            projected.append({
                **fragment,
                "external_grammatical_features": {
                    "sentence_force": sentence_force,
                    "tense": tense,
                    "mood": properties.get("MOOD"),
                    "progressive": properties.get("PROG"),
                    "perfect": properties.get("PERF"),
                    "promoted_to_cognitive_primitive": False,
                },
                "temporal_candidate": temporal,
            })
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"semantic-features:{source.correlation_id}",
            payload={
                "fragments": projected,
                "analysis_unresolved": source.payload["unresolved"],
                "temporal_unresolved": temporal_unresolved,
                "ledger": source.payload["ledger"],
                "candidate_selection_performed": False,
                "absolute_coordinate_invented": False,
            },
        )


class CandidateHypothesisLedgerService:
    """Crée une hypothèse par candidat MRS, sans produit cartésien temporel."""

    spec = ServiceSpec(
        "candidate-hypothesis-ledger",
        "semantic-feature-batch",
        "corpus-hypothesis-ledger",
        ("mrs-feature-projection",),
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(
            source,
            "fragments",
            "analysis_unresolved",
            "temporal_unresolved",
            "ledger",
        )
        hypotheses = []
        for fragment in source.payload["fragments"]:
            temporal = fragment["temporal_candidate"]
            temporal_id = f"temporal:{fragment['fragment_id']}"
            hypotheses.append({
                "hypothesis_id": f"hypothesis:{fragment['fragment_id']}",
                "observation_id": fragment["observation_id"],
                "content_ref": fragment["fragment_id"],
                "producer": fragment["producer"],
                "producer_candidate_id": fragment["candidate_id"],
                "producer_rank": int(fragment["candidate_id"]) + 1,
                "status": "persistent-alternative",
                "selected": False,
                "justification_ids": [
                    f"analysis-ledger:{fragment['observation_id']}:ACE_ERG",
                    temporal_id,
                ],
                "temporal": {
                    "candidate_id": temporal_id,
                    "status": temporal["status"],
                    "constraint_count": len(temporal["constraints"]),
                },
                "contradiction_ids": [],
            })
        if len(hypotheses) != len(source.payload["fragments"]):
            raise ContractError("candidate-hypothesis-ledger: perte de candidats")
        by_observation: dict[str, list[str]] = {}
        for hypothesis in hypotheses:
            by_observation.setdefault(hypothesis["observation_id"], []).append(hypothesis["hypothesis_id"])
        families = [
            {
                "observation_id": observation_id,
                "hypothesis_ids": identifiers,
                "active_ids": identifiers,
                "active_bound": len(identifiers),
                "selection_deferred": True,
            }
            for observation_id, identifiers in sorted(by_observation.items())
        ]
        theoretical_temporal_product = 1
        for family in families:
            theoretical_temporal_product *= len(family["hypothesis_ids"])
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"corpus-hypotheses:{source.correlation_id}",
            payload={
                "hypotheses": hypotheses,
                "families": families,
                "selection_events": [],
                "feature_batch": dict(source.payload),
                "persistent_count": len(hypotheses),
                "materialized_joint_interpretations": 0,
                "theoretical_cross_observation_product": theoretical_temporal_product,
                "cross_observation_product_materialized": False,
            },
        )


class ProtoServicePlanningService:
    spec = ServiceSpec(
        "proto-service-planning",
        "corpus-hypothesis-ledger",
        "proto-service-plan",
        ("candidate-hypothesis-ledger",),
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "hypotheses", "families", "feature_batch")
        feature_batch = source.payload["feature_batch"]
        fragments = feature_batch["fragments"]
        ledger = feature_batch["ledger"]
        readiness = []
        observation_ids = sorted({entry["observation_id"] for entry in ledger})
        for observation_id in observation_ids:
            producers = {
                entry["producer"]: entry
                for entry in ledger
                if entry["observation_id"] == observation_id
            }
            erg = producers["ACE_ERG"]["native_analysis"]
            ds = producers["dynamicsyntax-python"]["native_analysis"]
            fragment_count = sum(row["observation_id"] == observation_id for row in fragments)
            readiness.append({
                "observation_id": observation_id,
                "erg_status": erg["status"],
                "erg_candidates": erg["candidate_count"],
                "mrs_fragments": fragment_count,
                "formal_temporal_candidates": sum(
                    row["observation_id"] == observation_id
                    and row["temporal_candidate"]["status"] == "candidate"
                    for row in fragments
                ),
                "temporally_underspecified_candidates": sum(
                    row["observation_id"] == observation_id
                    and row["temporal_candidate"]["status"] == "underspecified"
                    for row in fragments
                ),
                "dynamic_syntax_status": ds["status"],
                "dynamic_syntax_actions_before_stop": ds["action_count"],
                "can_enter_existing_narrow_semantic_projection": (
                    erg["candidate_count"] == 1 and ds["status"] == "parsed"
                ),
            })
        if not all(row["erg_status"] == "parsed" for row in readiness):
            status = "NO-GO-ANALYSIS"
        elif all(row["can_enter_existing_narrow_semantic_projection"] for row in readiness):
            status = "GO-CURRENT-CHAIN"
        else:
            status = "GO-INGESTION-ERG-MRS-HYPOTHESES; NO-GO-DYNAMIC-SYNTAX-COVERAGE"
        services = [
            {"name": "corpus-catalog", "state": "next", "contract": "dataset -> immutable shard descriptors"},
            {"name": "corpus-sampling", "state": "implemented", "contract": "sampling-request -> corpus-sample-set"},
            {"name": "corpus-observation", "state": "implemented", "contract": "corpus-sample-set -> observation-batch"},
            {"name": "live-external-analysis", "state": "implemented", "contract": "observation-batch -> attributed native analyses"},
            {"name": "analysis-ledger", "state": "implemented", "contract": "native analyses -> successes, failures, alternatives"},
            {"name": "mrs-graph-adapter", "state": "implemented", "contract": "arbitrary MRS candidates -> attributed graph fragments"},
            {"name": "mrs-feature-projection", "state": "implemented", "contract": "MRS fragments -> external utterance features and E/R/S candidates"},
            {"name": "candidate-hypothesis-ledger", "state": "implemented", "contract": "candidate fragments -> persistent factorized hypotheses"},
            {"name": "ttr-adapter", "state": "blocked-by-observed-coverage", "contract": "partial DS parse -> partial attributed fragment"},
            {"name": "cross-representation-linker", "state": "after-adapters", "contract": "fragments -> correspondences, never implicit identity"},
            {"name": "temporal-context", "state": "implemented-for-simple-tense", "contract": "event candidates -> E/R/S constraints"},
            {"name": "hypothesis-and-state-chain", "state": "implemented-for-narrow-declarative", "contract": "linked fragments -> bounded active reasoning"},
        ]
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"proto-service-plan:{source.correlation_id}",
            payload={
                "status": status,
                "readiness": readiness,
                "services": services,
                "decision": {
                    "preserve_current_declarative_chain": True,
                    "do_not_force_dynamic_syntax_success": True,
                    "next_implementation_boundary": "question-answer observation sequence and interrogative dialogue-state candidates",
                    "evidence": "nine MRS hypotheses persist independently; no 3x3x3 cross-observation product is materialized; three have explicit present E/R/S candidates and six remain temporally underspecified; none completed by Dynamic Syntax",
                },
            },
        )


def run_corpus_planning(root: Path) -> tuple[Envelope, tuple[Envelope, ...]]:
    request = sampling_request("phase3:representative-corpus")
    sampling = CorpusSamplingService(root).handle(request)
    observations = CorpusObservationService().handle(sampling)
    analyses = LiveExternalAnalysisService(root).handle(observations)
    ledger = AnalysisLedgerService().handle(analyses)
    fragments = MRSGraphAdapterService().handle(ledger)
    features = MRSFeatureProjectionService().handle(fragments)
    hypotheses = CandidateHypothesisLedgerService().handle(features)
    plan = ProtoServicePlanningService().handle(hypotheses)
    return plan, (request, sampling, observations, analyses, ledger, fragments, features, hypotheses, plan)
