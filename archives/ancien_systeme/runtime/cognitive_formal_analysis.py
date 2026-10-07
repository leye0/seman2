"""Première branche L2 réelle : segmentation, ACE/ERG et Dynamic Syntax."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from delphin.codecs import simplemrs
import z3

from .cognitive_artifacts import (
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    thaw_json,
)
from .cognitive_ingestion import (
    BUILD as FOUNDATION_BUILD,
    IngestionPolicy,
    build_foundation_modules,
    register_foundation_types,
)
from .cognitive_runtime import CognitiveRuntime
from .cognitive_scheduler import ModuleSpec
from .control_state import ControlState, SafetyLimits
from .contracts import ContractError, canonical_json


BUILD = "formal-analysis-foundation"
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])(?:[\"”’']*)\s+")


@dataclass(frozen=True)
class FormalAnalysisPolicy:
    max_units_per_observation: int = 2
    max_unit_chars: int = 240
    max_candidates: int = 3
    max_linkages: int = 8
    max_lexical_forms: int = 32
    max_lexical_candidates: int = 4
    worker_timeout_seconds: int = 20
    worker_memory_mib: int = 1_024

    def __post_init__(self) -> None:
        if not 1 <= self.max_units_per_observation <= 32:
            raise ContractError("formal analysis: max_units_per_observation hors borne")
        if not 32 <= self.max_unit_chars <= 2_000:
            raise ContractError("formal analysis: max_unit_chars hors borne")
        if not 1 <= self.max_candidates <= 10:
            raise ContractError("formal analysis: max_candidates hors borne")
        if not 1 <= self.max_linkages <= 32:
            raise ContractError("formal analysis: max_linkages hors borne")
        if not 1 <= self.max_lexical_forms <= 128:
            raise ContractError("formal analysis: max_lexical_forms hors borne")
        if not 1 <= self.max_lexical_candidates <= 16:
            raise ContractError("formal analysis: max_lexical_candidates hors borne")
        if not 1 <= self.worker_timeout_seconds <= 120:
            raise ContractError("formal analysis: timeout hors borne")
        if not 256 <= self.worker_memory_mib <= 4_096:
            raise ContractError("formal analysis: mémoire worker hors borne")

    @property
    def configuration_digest(self) -> str:
        return hashlib.sha256(canonical_json(self.__dict__).encode()).hexdigest()


def build_formal_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            "observable-unit",
            "seman2/observable-unit",
            1,
            allowed_producers=frozenset({"sentence-segmenter"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset({"text", "start", "end"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "graph-fragment",
            "seman2/graph-fragment",
            3,
            allowed_producers=frozenset({"mrs-graph-adapter"}),
            parent_types=frozenset({"native-analysis-ledger-entry", "mrs-analysis"}),
            required_native_fields=frozenset(
                {"formalism", "candidate_id", "variables", "relations", "role_edges"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "graph-adaptation-failure",
            "seman2/graph-adaptation-failure",
            3,
            allowed_producers=frozenset({"mrs-graph-adapter"}),
            parent_types=frozenset({"native-analysis-ledger-entry", "mrs-analysis"}),
            required_native_fields=frozenset({"candidate_id", "error"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "semantic-structure",
            "seman2/semantic-structure",
            4,
            allowed_producers=frozenset({"semantic-composer"}),
            parent_types=frozenset(
                {"graph-fragment", "cross-representation-hypothesis"}
            ),
            required_native_fields=frozenset(
                {"entities", "events", "predicates", "mrs_index", "index_properties"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "cross-representation-hypothesis",
            "seman2/cross-representation-hypothesis",
            3,
            allowed_producers=frozenset({"cross-representation-linker"}),
            parent_types=frozenset(
                {"native-analysis-ledger-entry", "analysis-routing-state"}
            ),
            required_native_fields=frozenset(
                {
                    "unit_ref",
                    "routing_ref",
                    "analysis_refs",
                    "alignments",
                    "selection_performed",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "temporal-constraint-network",
            "seman2/temporal-constraint-network",
            4,
            allowed_producers=frozenset({"temporal-relation-system"}),
            parent_types=frozenset({"semantic-structure"}),
            required_native_fields=frozenset(
                {"formalism", "roles", "constraints", "tense"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "constraint-solution",
            "seman2/constraint-solution",
            4,
            allowed_producers=frozenset({"constraint-engine"}),
            parent_types=frozenset(
                {"temporal-constraint-network", "cross-representation-hypothesis"}
            ),
            required_native_fields=frozenset(
                {"status", "temporal_ref", "alignment_ref", "bindings", "unsat_core"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "reference-state-candidate",
            "seman2/reference-state-candidate",
            4,
            allowed_producers=frozenset({"semantic-reference-state"}),
            parent_types=frozenset({"semantic-structure"}),
            required_native_fields=frozenset(
                {"unit_ref", "mentions", "prior_candidate_refs", "identity_asserted"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "hypothesis-candidate",
            "seman2/hypothesis-candidate",
            5,
            allowed_producers=frozenset({"factorized-hypothesis-manager"}),
            parent_types=frozenset(
                {
                    "semantic-structure",
                    "temporal-constraint-network",
                    "reference-state-candidate",
                    "constraint-solution",
                }
            ),
            required_native_fields=frozenset(
                {
                    "semantic_ref",
                    "temporal_ref",
                    "reference_ref",
                    "unit_ref",
                    "selected",
                    "factorized",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "hypothesis-family",
            "seman2/hypothesis-family",
            5,
            allowed_producers=frozenset({"hypothesis-family-builder"}),
            parent_types=frozenset({"hypothesis-candidate"}),
            required_native_fields=frozenset(
                {"member_refs", "active_refs", "selected_ref", "factorized"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "situation-branch-set",
            "seman2/situation-branch-set",
            7,
            allowed_producers=frozenset({"situation-episode-system"}),
            parent_types=frozenset({"hypothesis-family", "dialogue-state-candidate"}),
            required_native_fields=frozenset({"family_ref", "branches", "committed_ref"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "episode-candidate",
            "seman2/episode-candidate",
            7,
            allowed_producers=frozenset({"situation-episode-system"}),
            parent_types=frozenset({"hypothesis-family", "dialogue-state-candidate"}),
            required_native_fields=frozenset(
                {"family_ref", "observation_refs", "branch_count", "committed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "discourse-state-candidate",
            "seman2/discourse-state-candidate",
            6,
            allowed_producers=frozenset({"formal-discourse-system"}),
            parent_types=frozenset({"hypothesis-family", "soar-control-state"}),
            required_native_fields=frozenset(
                {"family_ref", "discourse_id", "prior_family_refs", "observed_order"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "dialogue-state-candidate",
            "seman2/dialogue-state-candidate",
            7,
            allowed_producers=frozenset({"formal-dialogue-system"}),
            parent_types=frozenset(
                {"discourse-state-candidate", "hypothesis-family"}
            ),
            required_native_fields=frozenset(
                {
                    "family_ref",
                    "discourse_ref",
                    "dialogue_act_candidates",
                    "prior_dialogue_refs",
                    "qud_candidate_refs",
                    "grounding_committed",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-control-state",
            "seman2/soar-control-state",
            6,
            allowed_producers=frozenset({"soar-control"}),
            parent_types=frozenset({"hypothesis-family"}),
            required_native_fields=frozenset(
                {
                    "status",
                    "family_ref",
                    "active_refs",
                    "inactive_refs",
                    "action",
                    "selection_policy",
                    "active_context_digest",
                    "projected_justification_ref_count",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "retrieval-index-entry",
            "seman2/retrieval-index-entry",
            8,
            allowed_producers=frozenset({"structural-retrieval"}),
            parent_types=frozenset({"episode-candidate"}),
            required_native_fields=frozenset({"episode_ref", "keys", "target_refs"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "statistics-snapshot",
            "seman2/statistics-snapshot",
            8,
            allowed_producers=frozenset({"statistics-system"}),
            parent_types=frozenset({"episode-candidate"}),
            required_native_fields=frozenset(
                {"episode_count", "feature_support", "alternatives_counted_once"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "induction-state",
            "seman2/induction-state",
            8,
            allowed_producers=frozenset({"induction-engine"}),
            parent_types=frozenset({"statistics-snapshot"}),
            required_native_fields=frozenset(
                {"pattern_candidates", "promotion_threshold", "promoted_patterns"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "cultural-learning-state",
            "seman2/cultural-learning-state",
            9,
            allowed_producers=frozenset({"cultural-concept-system"}),
            parent_types=frozenset({"induction-state"}),
            required_native_fields=frozenset(
                {"status", "supporting_pattern_refs", "concepts_asserted"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "learned-concept-candidate",
            "seman2/learned-concept-candidate",
            9,
            allowed_producers=frozenset({"cultural-concept-system"}),
            parent_types=frozenset({"induction-state"}),
            required_native_fields=frozenset(
                {"anonymous_pattern", "support", "asserted", "meaning_assigned"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "state-transformation-candidate",
            "seman2/state-transformation-candidate",
            10,
            allowed_producers=frozenset({"candidate-transformation-system"}),
            parent_types=frozenset(
                {
                    "cultural-learning-state",
                    "episode-candidate",
                    "retrieval-index-entry",
                    "learned-concept-candidate",
                }
            ),
            required_native_fields=frozenset(
                {
                    "cultural_ref",
                    "episode_ref",
                    "kind",
                    "eligible",
                    "precondition_refs",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "soar-transformation-decision",
            "seman2/soar-transformation-decision",
            10,
            allowed_producers=frozenset({"soar-transformation-control"}),
            parent_types=frozenset({"state-transformation-candidate"}),
            required_native_fields=frozenset(
                {
                    "status",
                    "selected_transformation_ref",
                    "transformation_kind",
                    "action",
                    "active_context_digest",
                    "projected_precondition_ref_count",
                    "all_required_refs_observed_in_wm",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "memory-consolidation-state",
            "seman2/memory-consolidation-state",
            10,
            allowed_producers=frozenset({"ingestion-state-consolidator"}),
            parent_types=frozenset(
                {"soar-transformation-decision", "state-transformation-candidate"}
            ),
            required_native_fields=frozenset(
                {"episode_ref", "operation", "applied", "truth_committed"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "native-analysis-ledger-entry",
            "seman2/native-analysis-ledger-entry",
            3,
            allowed_producers=frozenset({"native-analysis-ledger"}),
            parent_types=frozenset(
                {
                    "mrs-analysis",
                    "dynamic-syntax-analysis",
                    "linkage-analysis",
                    "lexical-analysis",
                    "form-phonology-analysis",
                    "code-analysis",
                }
            ),
            required_native_fields=frozenset(
                {"analysis_type", "analysis_status", "alternative_count"}
            ),
        )
    )
    for job_type in (
        "analysis-job-erg",
        "analysis-job-dynamic-syntax",
        "analysis-job-link-grammar",
        "analysis-job-lexical",
        "analysis-job-form-phonology",
        "analysis-job-code",
    ):
        registry.register(
            ArtifactTypeSpec(
                job_type,
                f"seman2/{job_type}",
                2,
                allowed_producers=frozenset({"formal-analysis-dispatch"}),
                parent_types=frozenset({"observable-unit"}),
                required_native_fields=frozenset({"text", "analyzer"}),
            )
        )
    registry.register(
        ArtifactTypeSpec(
            "analysis-routing-state",
            "seman2/analysis-routing-state",
            2,
            allowed_producers=frozenset({"formal-analysis-dispatch"}),
            parent_types=frozenset({"observable-unit"}),
            required_native_fields=frozenset(
                {"unit_ref", "routed_analyzers", "skipped_analyzers"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "mrs-analysis",
            "seman2/mrs-analysis",
            2,
            allowed_producers=frozenset({"erg-worker"}),
            parent_types=frozenset({"analysis-job-erg"}),
            required_native_fields=frozenset({"status", "candidate_count", "candidates"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "lexical-analysis",
            "seman2/lexical-analysis",
            2,
            allowed_producers=frozenset({"lexical-resource-worker"}),
            parent_types=frozenset({"analysis-job-lexical"}),
            required_native_fields=frozenset(
                {"status"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "form-phonology-analysis",
            "seman2/form-phonology-analysis",
            2,
            allowed_producers=frozenset({"form-phonology-worker"}),
            parent_types=frozenset({"analysis-job-form-phonology"}),
            required_native_fields=frozenset({"status"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "code-analysis",
            "seman2/code-analysis",
            2,
            allowed_producers=frozenset({"code-analysis-worker"}),
            parent_types=frozenset({"analysis-job-code"}),
            required_native_fields=frozenset(
                {"status", "language", "has_error", "source_reconstructed", "cst"}
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "linkage-analysis",
            "seman2/linkage-analysis",
            2,
            allowed_producers=frozenset({"link-grammar-worker"}),
            parent_types=frozenset({"analysis-job-link-grammar"}),
            required_native_fields=frozenset({"status", "linkage_count", "linkages"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "dynamic-syntax-analysis",
            "seman2/dynamic-syntax-analysis",
            2,
            allowed_producers=frozenset({"dynamic-syntax-worker"}),
            parent_types=frozenset({"analysis-job-dynamic-syntax"}),
            required_native_fields=frozenset({"status", "action_count", "actions"}),
        )
    )
    registry.freeze()
    return registry


def build_formal_modules(
    root: Path,
    ingestion_policy: IngestionPolicy,
    formal_policy: FormalAnalysisPolicy,
) -> tuple[ModuleSpec, ...]:
    digest = formal_policy.configuration_digest

    def unit_ref_for(artifact_id: str, context) -> str:
        artifact = context.arena.get(artifact_id)
        if artifact.artifact_type == "observable-unit":
            return artifact.artifact_id
        return next(
            row.artifact_id
            for row in context.arena.ancestry(artifact_id)
            if row.artifact_type == "observable-unit"
        )

    def segment(trigger, context):
        text = str(trigger.payload_native["text"])
        cursor = 0
        count = 0
        for boundary in (*SENTENCE_BOUNDARY.finditer(text), None):
            end = boundary.start() if boundary is not None else len(text)
            unit = text[cursor:end].strip()
            start = cursor + len(text[cursor:end]) - len(text[cursor:end].lstrip())
            cursor = boundary.end() if boundary is not None else len(text)
            if not unit or len(unit) > formal_policy.max_unit_chars:
                continue
            count += 1
            yield ArtifactProposal(
                artifact_type="observable-unit",
                producer_id="sentence-segmenter",
                producer_build=BUILD,
                configuration_digest=digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id,),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={"text": unit, "start": start, "end": start + len(unit)},
                payload_projection={"unit_kind": "sentence"},
                idempotency_key=f"sentence:{trigger.artifact_id}:{start}:{start + len(unit)}",
            )
            if count >= formal_policy.max_units_per_observation:
                break

    def dispatch(trigger, context):
        observation = next(
            row
            for row in context.arena.ancestry(trigger.artifact_id)
            if row.artifact_type == "observation"
        )
        native_structure = observation.payload_native["native_structure"]
        language = native_structure.get("programming_language")
        code_input = observation.payload_native["source_kind"] == "code"
        if code_input and not language:
            raise ContractError("dispatch code: programming_language requis")
        analyzers = (
            ("code",)
            if code_input
            else (
                "erg",
                "dynamic-syntax",
                "link-grammar",
                "lexical",
                "form-phonology",
            )
        )
        skipped = []
        for analyzer, reason in (
            ("code", "source modality is not code"),
            (
                "temporal-surface",
                "no attributed external calendar context on the source observation",
            ),
            (
                "rst",
                "sentence units do not satisfy the multi-EDU discourse-span contract",
            ),
        ):
            if analyzer not in analyzers:
                skipped.append({"analyzer": analyzer, "reason": reason})
        if code_input:
            skipped.extend(
                {"analyzer": analyzer, "reason": "source modality is code"}
                for analyzer in (
                    "erg",
                    "dynamic-syntax",
                    "link-grammar",
                    "lexical",
                    "form-phonology",
                )
            )
        yield ArtifactProposal(
            artifact_type="analysis-routing-state",
            producer_id="formal-analysis-dispatch",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "unit_ref": trigger.artifact_id,
                "routed_analyzers": list(analyzers),
                "skipped_analyzers": skipped,
            },
            payload_projection={"routing_is_explicit": True},
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"analysis-routing:{trigger.artifact_id}",
        )
        for analyzer in analyzers:
            yield ArtifactProposal(
                artifact_type=f"analysis-job-{analyzer}",
                producer_id="formal-analysis-dispatch",
                producer_build=BUILD,
                configuration_digest=digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id,),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    "text": trigger.payload_native["text"],
                    "analyzer": analyzer,
                    "language": language if analyzer == "code" else None,
                },
                payload_projection={"bounded": True},
                idempotency_key=f"job:{analyzer}:{trigger.artifact_id}",
            )

    def erg(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv-dialogue/bin/python",
            root / "seman2_runtime/workers/erg_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
        )
        yield _analysis_proposal(
            trigger, context, "mrs-analysis", "erg-worker", native, status, losses, digest
        )

    def dynamic_syntax(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv-dialogue/bin/python",
            root / "seman2_runtime/workers/dynamic_syntax_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
        )
        yield _analysis_proposal(
            trigger,
            context,
            "dynamic-syntax-analysis",
            "dynamic-syntax-worker",
            native,
            status,
            losses,
            digest,
        )

    def link_grammar(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv/bin/python",
            root / "seman2_runtime/workers/link_grammar_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
        )
        yield _analysis_proposal(
            trigger,
            context,
            "linkage-analysis",
            "link-grammar-worker",
            native,
            status,
            losses,
            digest,
        )

    def ledger(trigger, context):
        native = trigger.payload_native
        if trigger.artifact_type == "mrs-analysis":
            alternative_count = native["candidate_count"]
        elif trigger.artifact_type == "linkage-analysis":
            alternative_count = native["linkage_count"]
        elif trigger.artifact_type == "dynamic-syntax-analysis":
            alternative_count = 1 if native["status"] == "parsed" else 0
        else:
            alternative_count = native.get("occurrence_count", 0)
        yield ArtifactProposal(
            artifact_type="native-analysis-ledger-entry",
            producer_id="native-analysis-ledger",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "analysis_type": trigger.artifact_type,
                "analysis_status": native["status"],
                "alternative_count": alternative_count,
            },
            payload_projection={
                "native_analysis_ref": trigger.artifact_id,
                "failure_is_matter": native["status"] != "parsed",
                "cross_producer_ranking_performed": False,
            },
            status=trigger.status,
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"ledger:{trigger.artifact_id}",
        )

    def link_representations(trigger, context):
        unit_ref = unit_ref_for(trigger.artifact_id, context)
        ledgers = [
            row
            for row in context.arena.query(
                artifact_type="native-analysis-ledger-entry",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if unit_ref_for(row.artifact_id, context) == unit_ref
        ]
        ledgers.sort(key=lambda row: (row.payload_native["analysis_type"], row.artifact_id))
        routing = next(
            row
            for row in context.arena.query(
                artifact_type="analysis-routing-state",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.payload_native["unit_ref"] == unit_ref
        )
        native_by_type = {
            row.payload_native["analysis_type"]: context.arena.get(row.parent_ids[0])
            for row in ledgers
        }
        lexical = native_by_type.get("lexical-analysis")
        form = native_by_type.get("form-phonology-analysis")
        alignments = []
        if lexical is not None and form is not None:
            form_rows = {
                (tuple(row["charspan"]), row["form"]): row
                for row in form.payload_native.get("occurrences", ())
            }
            for occurrence in lexical.payload_native.get("occurrences", ()):
                key = (tuple(occurrence["charspan"]), occurrence["form"])
                if key not in form_rows:
                    continue
                phonology = form_rows[key]
                alignments.append(
                    {
                        "kind": "same-source-occurrence",
                        "form": occurrence["form"],
                        "charspan": occurrence["charspan"],
                        "lexical_candidate_count": sum(
                            len(occurrence.get(name, ()))
                            for name in ("wordnet", "verbnet", "propbank")
                        ),
                        "ipa": phonology.get("ipa"),
                        "identity_asserted": False,
                    }
                )
        lexical_rows = (
            list(lexical.payload_native.get("occurrences", ()))
            if lexical is not None
            else []
        )
        linkage = native_by_type.get("linkage-analysis")
        if linkage is not None:
            for linkage_index, candidate in enumerate(
                linkage.payload_native.get("linkages", ())
            ):
                for token in candidate.get("tokens", ()):
                    for occurrence in lexical_rows:
                        if tuple(token["charspan"]) == tuple(occurrence["charspan"]):
                            alignments.append(
                                {
                                    "kind": "link-token-to-lexical-occurrence",
                                    "linkage_index": linkage_index,
                                    "token_index": token["index"],
                                    "form": occurrence["form"],
                                    "charspan": occurrence["charspan"],
                                    "identity_asserted": False,
                                }
                            )
        mrs = native_by_type.get("mrs-analysis")
        if mrs is not None:
            for candidate in mrs.payload_native.get("candidates", ()):
                try:
                    decoded = simplemrs.decode(candidate["mrs"])
                except Exception:
                    continue
                for relation_index, relation in enumerate(decoded.rels):
                    if relation.lnk is None or relation.lnk.type != "charspan":
                        continue
                    span = tuple(relation.lnk.data)
                    for occurrence in lexical_rows:
                        occurrence_span = tuple(occurrence["charspan"])
                        if max(span[0], occurrence_span[0]) >= min(
                            span[1], occurrence_span[1]
                        ):
                            continue
                        alignments.append(
                            {
                                "kind": "mrs-relation-to-lexical-occurrence",
                                "mrs_result_id": candidate["result_id"],
                                "relation_index": relation_index,
                                "predicate": relation.predicate,
                                "form": occurrence["form"],
                                "relation_charspan": span,
                                "occurrence_charspan": occurrence_span,
                                "identity_asserted": False,
                            }
                        )
        failures = [
            {
                "analysis_ref": row.artifact_id,
                "analysis_type": row.payload_native["analysis_type"],
                "status": row.payload_native["analysis_status"],
            }
            for row in ledgers
            if row.payload_native["analysis_status"] not in {"parsed", "analyzed"}
        ]
        yield ArtifactProposal(
            artifact_type="cross-representation-hypothesis",
            producer_id="cross-representation-linker",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(routing.artifact_id, *(row.artifact_id for row in ledgers)),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "unit_ref": unit_ref,
                "routing_ref": routing.artifact_id,
                "analysis_refs": [row.artifact_id for row in ledgers],
                "alignments": alignments,
                "failures": failures,
                "selection_performed": False,
            },
            payload_projection={
                "represented_analysis_types": sorted(native_by_type),
                "alignment_count": len(alignments),
                "failed_analyses_retained": len(failures),
            },
            justification_ids=tuple(row.artifact_id for row in ledgers),
            idempotency_key=f"cross-representation:{unit_ref}",
        )

    def adapt_mrs(trigger, context):
        if trigger.payload_native["analysis_type"] != "mrs-analysis":
            return
        analysis = context.arena.get(trigger.parent_ids[0])
        if analysis.artifact_type != "mrs-analysis":
            raise ContractError("ledger MRS sans parent mrs-analysis")
        for candidate in analysis.payload_native["candidates"]:
            candidate_id = str(candidate["result_id"])
            try:
                decoded = simplemrs.decode(candidate["mrs"])
                variables = [
                    {
                        "id": variable,
                        "sort": variable[0],
                        "properties": dict(properties),
                    }
                    for variable, properties in sorted(decoded.variables.items())
                ]
                relations = []
                role_edges = []
                for index, relation in enumerate(decoded.rels):
                    relation_id = f"relation:{candidate_id}:{index}"
                    relations.append(
                        {
                            "id": relation_id,
                            "predicate": relation.predicate,
                            "label": relation.label,
                            "surface": list(relation.lnk.data)
                            if relation.lnk and relation.lnk.type == "charspan"
                            else None,
                            "constant": relation.carg,
                        }
                    )
                    for role, target in sorted(relation.args.items()):
                        role_edges.append(
                            {"source": relation_id, "role": role, "target": target}
                        )
                native = {
                    "formalism": "MRS",
                    "candidate_id": candidate_id,
                    "top": decoded.top,
                    "index": decoded.index,
                    "variables": variables,
                    "relations": relations,
                    "role_edges": role_edges,
                    "handle_constraints": [
                        {"high": row.hi, "relation": row.relation, "low": row.lo}
                        for row in decoded.hcons
                    ],
                    "individual_constraints": [
                        {"left": row.left, "relation": row.relation, "right": row.right}
                        for row in decoded.icons
                    ],
                }
                artifact_type = "graph-fragment"
                status = ArtifactStatus.SUCCESS
                losses = ()
            except Exception as exc:
                native = {
                    "candidate_id": candidate_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                artifact_type = "graph-adaptation-failure"
                status = ArtifactStatus.FAILURE
                losses = ("mrs-decode-failure",)
            yield ArtifactProposal(
                artifact_type=artifact_type,
                producer_id="mrs-graph-adapter",
                producer_build=BUILD,
                configuration_digest=digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id, analysis.artifact_id),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native=native,
                payload_projection={
                    "native_mrs_ref": analysis.artifact_id,
                    "candidate_selection_performed": False,
                },
                status=status,
                justification_ids=(trigger.artifact_id,),
                losses=losses,
                idempotency_key=f"mrs-graph:{analysis.artifact_id}:{candidate_id}",
            )

    def lexical_resources(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv/bin/python",
            root / "seman2_runtime/workers/lexical_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
        )
        yield _analysis_proposal(
            trigger,
            context,
            "lexical-analysis",
            "lexical-resource-worker",
            native,
            status,
            losses,
            digest,
        )

    def form_phonology(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv-semiotic/bin/python",
            root / "seman2_runtime/workers/form_phonology_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
        )
        yield _analysis_proposal(
            trigger,
            context,
            "form-phonology-analysis",
            "form-phonology-worker",
            native,
            status,
            losses,
            digest,
        )

    def analyze_code(trigger, context):
        native, status, losses = _run_worker(
            root / ".venv/bin/python",
            root / "seman2_runtime/workers/code_worker.py",
            trigger.payload_native["text"],
            root,
            formal_policy,
            extra_request={"language": trigger.payload_native["language"]},
        )
        yield _analysis_proposal(
            trigger,
            context,
            "code-analysis",
            "code-analysis-worker",
            native,
            status,
            losses,
            digest,
        )

    def compose_semantics(trigger, context):
        native = trigger.payload_native
        variables = {row["id"]: row for row in native["variables"]}
        predicates = []
        edges_by_relation: dict[str, dict[str, str]] = {}
        for edge in native["role_edges"]:
            edges_by_relation.setdefault(edge["source"], {})[edge["role"]] = edge["target"]
        for relation in native["relations"]:
            predicates.append(
                {
                    "predicate": relation["predicate"],
                    "label": relation["label"],
                    "surface": relation["surface"],
                    "constant": relation["constant"],
                    "arguments": edges_by_relation.get(relation["id"], {}),
                }
            )
        index = native["index"]
        unit_ref = next(
            row.artifact_id
            for row in context.arena.ancestry(trigger.artifact_id)
            if row.artifact_type == "observable-unit"
        )
        cross_representation = next(
            row
            for row in context.arena.query(
                artifact_type="cross-representation-hypothesis",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.payload_native["unit_ref"] == unit_ref
        )
        yield ArtifactProposal(
            artifact_type="semantic-structure",
            producer_id="semantic-composer",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id, cross_representation.artifact_id),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "entities": [row for row in native["variables"] if row["sort"] == "x"],
                "events": [row for row in native["variables"] if row["sort"] == "e"],
                "predicates": predicates,
                "mrs_top": native["top"],
                "mrs_index": index,
                "index_properties": variables.get(index, {}).get("properties", {}),
                "unit_ref": unit_ref,
                "cross_representation_ref": cross_representation.artifact_id,
            },
            payload_projection={
                "candidate_id": native["candidate_id"],
                "identity_resolution_performed": False,
                "truth_asserted": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"semantics:{trigger.artifact_id}",
        )

    def build_reference_state(trigger, context):
        mentions = [
            {
                "predicate": row["predicate"],
                "name": row["constant"],
                "entity_ref": row["arguments"].get("ARG0"),
            }
            for row in trigger.payload_native["predicates"]
            if row.get("constant")
        ]
        names = {row["name"].casefold() for row in mentions if row["name"]}
        prior_refs = []
        if names:
            for prior in context.arena.query(
                artifact_type="semantic-structure",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            ):
                if prior.created_sequence >= trigger.created_sequence:
                    continue
                if prior.payload_native["unit_ref"] == trigger.payload_native["unit_ref"]:
                    continue
                prior_names = {
                    row["constant"].casefold()
                    for row in prior.payload_native["predicates"]
                    if row.get("constant")
                }
                if names & prior_names:
                    prior_refs.append(prior.artifact_id)
        yield ArtifactProposal(
            artifact_type="reference-state-candidate",
            producer_id="semantic-reference-state",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "unit_ref": trigger.payload_native["unit_ref"],
                "mentions": mentions,
                "prior_candidate_refs": prior_refs,
                "identity_asserted": False,
            },
            payload_projection={
                "status": "candidate-continuity" if prior_refs else "new-mention",
                "factorized_prior_count": len(prior_refs),
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"reference-state:{trigger.artifact_id}",
        )

    def build_temporal_network(trigger, context):
        properties = trigger.payload_native["index_properties"]
        tense = properties.get("TENSE", "unknown")
        event = trigger.payload_native["mrs_index"]
        reference = f"R:{trigger.artifact_id}"
        speech = f"S:{trigger.observation_refs[0]}"
        constraints: list[dict[str, str]] = []
        if tense == "past":
            constraints = [
                {"left": event, "operator": "=", "right": reference},
                {"left": reference, "operator": "<", "right": speech},
            ]
        elif tense == "pres":
            constraints = [
                {"left": event, "operator": "=", "right": reference},
                {"left": reference, "operator": "=", "right": speech},
            ]
        elif tense == "fut":
            constraints = [
                {"left": speech, "operator": "<", "right": reference},
                {"left": reference, "operator": "=", "right": event},
            ]
        yield ArtifactProposal(
            artifact_type="temporal-constraint-network",
            producer_id="temporal-relation-system",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "formalism": "Reichenbach E/R/S",
                "roles": {"E": event, "R": reference, "S": speech},
                "constraints": constraints,
                "tense": tense,
                "absolute_coordinate": None,
            },
            payload_projection={
                "status": "constrained" if constraints else "underspecified",
                "absolute_coordinate_invented": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"temporal:{trigger.artifact_id}",
        )

    def solve_constraints(trigger, context):
        semantic = context.arena.get(trigger.parent_ids[0])
        alignment = context.arena.get(
            semantic.payload_native["cross_representation_ref"]
        )
        symbols = sorted(
            {
                constraint[side]
                for constraint in trigger.payload_native["constraints"]
                for side in ("left", "right")
            }
        )
        variables = {name: z3.Int(f"temporal_{index}") for index, name in enumerate(symbols)}
        solver = z3.Solver()
        solver.set(timeout=min(formal_policy.worker_timeout_seconds * 1_000, 5_000))
        labels: dict[str, dict[str, str]] = {}
        for index, constraint in enumerate(trigger.payload_native["constraints"]):
            label_name = f"constraint_{index}"
            label = z3.Bool(label_name)
            labels[label_name] = dict(constraint)
            left = variables[constraint["left"]]
            right = variables[constraint["right"]]
            if constraint["operator"] == "=":
                expression = left == right
            elif constraint["operator"] == "<":
                expression = left < right
            else:
                raise ContractError(
                    f"constraint-engine: opérateur inconnu {constraint['operator']}"
                )
            solver.assert_and_track(expression, label)
        result = solver.check()
        result_name = str(result).upper()
        bindings: dict[str, int] = {}
        unsat_core: list[dict[str, str]] = []
        reason_unknown = None
        if result == z3.sat:
            model = solver.model()
            bindings = {
                name: model.eval(variable, model_completion=True).as_long()
                for name, variable in variables.items()
            }
        elif result == z3.unsat:
            unsat_core = [labels[str(label)] for label in solver.unsat_core()]
        else:
            reason_unknown = solver.reason_unknown()
        yield ArtifactProposal(
            artifact_type="constraint-solution",
            producer_id="constraint-engine",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id, alignment.artifact_id),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "status": result_name,
                "temporal_ref": trigger.artifact_id,
                "alignment_ref": alignment.artifact_id,
                "bindings": bindings,
                "unsat_core": unsat_core,
                "reason_unknown": reason_unknown,
                "constraint_count": len(trigger.payload_native["constraints"]),
            },
            payload_projection={
                "solver": "Z3",
                "underdetermined": result == z3.sat and not bool(symbols),
                "external_analysis_selected": False,
            },
            status=(
                ArtifactStatus.SUCCESS
                if result == z3.sat
                else ArtifactStatus.FAILURE
                if result == z3.unsat
                else ArtifactStatus.UNKNOWN
            ),
            justification_ids=(trigger.artifact_id, alignment.artifact_id),
            contradiction_ids=tuple(
                trigger.artifact_id for _ in unsat_core[:1]
            ),
            idempotency_key=f"constraint-solution:{trigger.artifact_id}",
        )

    def create_hypothesis(trigger, context):
        temporal = context.arena.get(trigger.payload_native["temporal_ref"])
        semantic_id = temporal.parent_ids[0]
        semantic = context.arena.get(semantic_id)
        unit_ref = next(
            row.artifact_id
            for row in context.arena.ancestry(semantic.artifact_id)
            if row.artifact_type == "observable-unit"
        )
        reference = next(
            row
            for row in context.arena.query(
                artifact_type="reference-state-candidate",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.parent_ids == (semantic.artifact_id,)
        )
        yield ArtifactProposal(
            artifact_type="hypothesis-candidate",
            producer_id="factorized-hypothesis-manager",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(
                semantic.artifact_id,
                temporal.artifact_id,
                reference.artifact_id,
                trigger.artifact_id,
            ),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "semantic_ref": semantic.artifact_id,
                "temporal_ref": temporal.artifact_id,
                "reference_ref": reference.artifact_id,
                "constraint_solution_ref": trigger.artifact_id,
                "unit_ref": unit_ref,
                "selected": False,
                "factorized": True,
            },
            payload_projection={
                "cross_candidate_product_materialized": False,
                "selection_deferred": True,
            },
            justification_ids=(
                semantic.artifact_id,
                temporal.artifact_id,
                reference.artifact_id,
                trigger.artifact_id,
            ),
            idempotency_key=(
                f"hypothesis:{semantic.artifact_id}:{temporal.artifact_id}:"
                f"{reference.artifact_id}"
            ),
        )

    def build_hypothesis_family(trigger, context):
        unit_ref = trigger.payload_native["unit_ref"]
        members = [
            row
            for row in context.arena.query(
                artifact_type="hypothesis-candidate",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.payload_native["unit_ref"] == unit_ref
        ]
        member_refs = tuple(row.artifact_id for row in members)
        yield ArtifactProposal(
            artifact_type="hypothesis-family",
            producer_id="hypothesis-family-builder",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=member_refs,
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "member_refs": member_refs,
                "active_refs": member_refs,
                "selected_ref": None,
                "factorized": True,
            },
            payload_projection={
                "member_count": len(member_refs),
                "joint_products_materialized": 0,
                "selection_deferred": True,
            },
            justification_ids=member_refs,
            idempotency_key=f"hypothesis-family:{unit_ref}",
        )

    def control_with_soar(trigger, context):
        candidate_projections = []
        for member_ref in trigger.payload_native["member_refs"]:
            member = context.arena.get(member_ref)
            semantic = context.arena.get(member.payload_native["semantic_ref"])
            temporal = context.arena.get(member.payload_native["temporal_ref"])
            reference = context.arena.get(member.payload_native["reference_ref"])
            structural_features = sorted(
                {
                    *(
                        f"predicate:{canonical_json(thaw_json(predicate))}"
                        for predicate in semantic.payload_native["predicates"]
                    ),
                    *(
                        f"temporal:{canonical_json(thaw_json(constraint))}"
                        for constraint in temporal.payload_native["constraints"]
                    ),
                    f"reference-count:{len(reference.payload_native['mentions'])}",
                }
            )
            candidate_projections.append(
                {
                    "hypothesis_ref": member.artifact_id,
                    "semantic_ref": semantic.artifact_id,
                    "temporal_ref": temporal.artifact_id,
                    "reference_ref": reference.artifact_id,
                    "constraint_solution_ref": member.payload_native[
                        "constraint_solution_ref"
                    ],
                    "unit_ref": member.payload_native["unit_ref"],
                    "observation_refs": list(member.observation_refs),
                    "justification_refs": list(member.justification_ids),
                    "structural_features": structural_features,
                }
            )
        native, status, losses = _run_soar_worker(
            root / ".venv/bin/python",
            root / "seman2_runtime/workers/soar_control_worker.py",
            family_ref=trigger.artifact_id,
            candidates=candidate_projections,
            beam_bound=context.control.parameters.hypothesis_beam_width,
            timeout_seconds=formal_policy.worker_timeout_seconds,
            memory_mib=formal_policy.worker_memory_mib,
        )
        yield ArtifactProposal(
            artifact_type="soar-control-state",
            producer_id="soar-control",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native=native,
            payload_projection={
                "native_soar_used": status is ArtifactStatus.SUCCESS,
                "selection_performed": False,
                "working_memory_bounded": True,
                "persistent_store_copied_to_soar": False,
                "rich_active_context_projected": True,
            },
            status=status,
            losses=losses,
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"soar-control:{trigger.artifact_id}",
        )

    def build_discourse_state(trigger, context):
        family = context.arena.get(trigger.payload_native["family_ref"])
        observation = next(
            row
            for row in context.arena.ancestry(family.artifact_id)
            if row.artifact_type == "observation"
        )
        discourse_id = observation.payload_native["discourse_id"]
        prior_families = []
        for prior in context.arena.query(
            artifact_type="hypothesis-family",
            session_id=trigger.session_id,
            wave_at_most=context.scheduled_wave,
        ):
            if (
                prior.artifact_id == family.artifact_id
                or prior.created_sequence >= trigger.created_sequence
            ):
                continue
            prior_observation = next(
                row
                for row in context.arena.ancestry(prior.artifact_id)
                if row.artifact_type == "observation"
            )
            if prior_observation.payload_native["discourse_id"] == discourse_id:
                prior_families.append(prior.artifact_id)
        yield ArtifactProposal(
            artifact_type="discourse-state-candidate",
            producer_id="formal-discourse-system",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(
                family.artifact_id,
                trigger.artifact_id,
                *tuple(prior_families),
            ),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "family_ref": family.artifact_id,
                "discourse_id": discourse_id,
                "prior_family_refs": prior_families,
                "observed_order": observation.payload_native["turn_index"],
                "soar_control_ref": trigger.artifact_id,
            },
            payload_projection={
                "sequence_link_count": len(prior_families),
                "rhetorical_relation_asserted": False,
            },
            justification_ids=(
                family.artifact_id,
                trigger.artifact_id,
                *tuple(prior_families),
            ),
            idempotency_key=f"discourse-state:{family.artifact_id}",
        )

    def build_dialogue_state(trigger, context):
        family = context.arena.get(trigger.payload_native["family_ref"])
        dialogue_acts = []
        for hypothesis_ref in family.payload_native["member_refs"]:
            hypothesis = context.arena.get(hypothesis_ref)
            semantic = context.arena.get(hypothesis.payload_native["semantic_ref"])
            sentence_force = str(
                semantic.payload_native["index_properties"].get("SF", "unknown")
            ).casefold()
            dialogue_act = {
                "ques": "question-candidate",
                "prop": "inform-candidate",
                "comm": "directive-candidate",
            }.get(sentence_force, "underspecified-act-candidate")
            dialogue_acts.append(
                {
                    "hypothesis_ref": hypothesis_ref,
                    "semantic_ref": semantic.artifact_id,
                    "sentence_force": sentence_force,
                    "dialogue_act": dialogue_act,
                    "committed": False,
                }
            )
        prior_dialogues = [
            row
            for row in context.arena.query(
                artifact_type="dialogue-state-candidate",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.created_sequence < trigger.created_sequence
            and row.payload_native["discourse_id"]
            == trigger.payload_native["discourse_id"]
        ]
        qud_candidates = [
            {
                "dialogue_ref": row.artifact_id,
                "act_index": index,
            }
            for row in prior_dialogues
            for index, act in enumerate(row.payload_native["dialogue_act_candidates"])
            if act["dialogue_act"] == "question-candidate"
        ]
        yield ArtifactProposal(
            artifact_type="dialogue-state-candidate",
            producer_id="formal-dialogue-system",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id, family.artifact_id),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "family_ref": family.artifact_id,
                "discourse_ref": trigger.artifact_id,
                "discourse_id": trigger.payload_native["discourse_id"],
                "dialogue_act_candidates": dialogue_acts,
                "prior_dialogue_refs": [row.artifact_id for row in prior_dialogues],
                "qud_candidate_refs": qud_candidates,
                "grounding_committed": False,
            },
            payload_projection={
                "formal_sentence_force_used": True,
                "dialogue_act_selected": False,
                "answer_truth_asserted": False,
                "raw_source_read": False,
            },
            justification_ids=(trigger.artifact_id, family.artifact_id),
            idempotency_key=f"dialogue-state:{family.artifact_id}",
        )

    def index_episode(trigger, context):
        family = context.arena.get(trigger.payload_native["family_ref"])
        keys: set[str] = set()
        targets: list[str] = []
        for hypothesis_id in family.payload_native["member_refs"]:
            hypothesis = context.arena.get(hypothesis_id)
            semantic = context.arena.get(hypothesis.payload_native["semantic_ref"])
            targets.append(semantic.artifact_id)
            for predicate in semantic.payload_native["predicates"]:
                keys.add(f"predicate:{predicate['predicate']}")
                if predicate.get("constant"):
                    keys.add(f"constant:{predicate['constant'].casefold()}")
        yield ArtifactProposal(
            artifact_type="retrieval-index-entry",
            producer_id="structural-retrieval",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "episode_ref": trigger.artifact_id,
                "keys": sorted(keys),
                "target_refs": targets,
            },
            payload_projection={
                "internal_references_only": True,
                "source_corpus_query_performed": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"retrieval-index:{trigger.artifact_id}",
        )

    def update_statistics(trigger, context):
        episodes = context.arena.query(
            artifact_type="episode-candidate",
            session_id=trigger.session_id,
            wave_at_most=context.scheduled_wave,
        )
        support: dict[str, int] = {}
        for episode in episodes:
            family = context.arena.get(episode.payload_native["family_ref"])
            episode_features: set[str] = set()
            for hypothesis_id in family.payload_native["member_refs"]:
                hypothesis = context.arena.get(hypothesis_id)
                semantic = context.arena.get(hypothesis.payload_native["semantic_ref"])
                for predicate in semantic.payload_native["predicates"]:
                    episode_features.add(f"predicate:{predicate['predicate']}")
                    if predicate.get("constant"):
                        episode_features.add(
                            f"constant:{predicate['constant'].casefold()}"
                        )
            for feature in episode_features:
                support[feature] = support.get(feature, 0) + 1
        yield ArtifactProposal(
            artifact_type="statistics-snapshot",
            producer_id="statistics-system",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "episode_count": len(episodes),
                "feature_support": support,
                "alternatives_counted_once": True,
            },
            payload_projection={"statistics_are_descriptive": True},
            justification_ids=tuple(row.artifact_id for row in episodes),
            idempotency_key=f"statistics:{trigger.artifact_id}",
        )

    def induce_patterns(trigger, context):
        support = trigger.payload_native["feature_support"]
        candidates = [
            {"feature": feature, "support": count, "promoted": False}
            for feature, count in sorted(support.items())
            if count >= 2
        ]
        threshold = context.control.parameters.induction_trigger
        yield ArtifactProposal(
            artifact_type="induction-state",
            producer_id="induction-engine",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "pattern_candidates": candidates,
                "promotion_threshold": threshold,
                "promoted_patterns": [
                    row for row in candidates if row["support"] >= threshold
                ],
            },
            payload_projection={
                "minimum_observed_support": 2,
                "causality_inferred": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"induction:{trigger.artifact_id}",
        )

    def update_cultural_state(trigger, context):
        promoted = trigger.payload_native["promoted_patterns"]
        for row in promoted:
            anonymous_pattern = hashlib.sha256(
                canonical_json(
                    {
                        "feature": row["feature"],
                        "support": row["support"],
                        "source": trigger.artifact_id,
                    }
                ).encode()
            ).hexdigest()
            yield ArtifactProposal(
                artifact_type="learned-concept-candidate",
                producer_id="cultural-concept-system",
                producer_build=BUILD,
                configuration_digest=digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=(trigger.artifact_id,),
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    "anonymous_pattern": anonymous_pattern,
                    "source_feature": row["feature"],
                    "support": row["support"],
                    "asserted": False,
                    "meaning_assigned": False,
                },
                payload_projection={
                    "candidate_only": True,
                    "taxonomy_imposed": False,
                },
                justification_ids=(trigger.artifact_id,),
                idempotency_key=(
                    f"learned-concept-candidate:{trigger.artifact_id}:"
                    f"{anonymous_pattern}"
                ),
            )
        yield ArtifactProposal(
            artifact_type="cultural-learning-state",
            producer_id="cultural-concept-system",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "status": (
                    "anonymous-candidates-created" if promoted else "insufficient-support"
                ),
                "supporting_pattern_refs": [trigger.artifact_id] if promoted else [],
                "concepts_asserted": [],
            },
            payload_projection={
                "nonliteral_interpretation_performed": False,
                "culture_invented_from_sparse_input": False,
                "anonymous_candidate_count": len(promoted),
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"cultural-state:{trigger.artifact_id}",
        )

    def build_state_transformations(trigger, context):
        episode = next(
            row
            for row in context.arena.ancestry(trigger.artifact_id)
            if row.artifact_type == "episode-candidate"
        )
        retrieval = next(
            row
            for row in context.arena.query(
                artifact_type="retrieval-index-entry",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.payload_native["episode_ref"] == episode.artifact_id
        )
        learned = [
            row
            for row in context.arena.query(
                artifact_type="learned-concept-candidate",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.parent_ids == trigger.parent_ids
        ]
        candidates = [
            {
                "kind": "retain-episode",
                "eligible": True,
                "parents": (trigger.artifact_id, episode.artifact_id, retrieval.artifact_id),
                "preconditions": (episode.artifact_id, retrieval.artifact_id),
            },
            {
                "kind": "defer-consolidation",
                "eligible": True,
                "parents": (trigger.artifact_id, episode.artifact_id),
                "preconditions": (trigger.artifact_id,),
            },
        ]
        if learned:
            candidates.append(
                {
                    "kind": "activate-pattern-candidates",
                    "eligible": True,
                    "parents": (
                        trigger.artifact_id,
                        episode.artifact_id,
                        retrieval.artifact_id,
                        *(row.artifact_id for row in learned),
                    ),
                    "preconditions": tuple(row.artifact_id for row in learned),
                }
            )
        for candidate in candidates:
            yield ArtifactProposal(
                artifact_type="state-transformation-candidate",
                producer_id="candidate-transformation-system",
                producer_build=BUILD,
                configuration_digest=digest,
                mode=trigger.mode,
                session_id=trigger.session_id,
                wave=context.scheduled_wave,
                parent_ids=candidate["parents"],
                observation_refs=trigger.observation_refs,
                source_anchors=trigger.source_anchors,
                payload_native={
                    "cultural_ref": trigger.artifact_id,
                    "episode_ref": episode.artifact_id,
                    "kind": candidate["kind"],
                    "eligible": candidate["eligible"],
                    "precondition_refs": candidate["preconditions"],
                },
                payload_projection={
                    "uses_raw_source": False,
                    "uses_corpus_label": False,
                    "world_commit_requested": False,
                },
                justification_ids=candidate["preconditions"],
                idempotency_key=(
                    f"state-transformation:{trigger.artifact_id}:{candidate['kind']}"
                ),
            )

    def choose_state_transformation(trigger, context):
        cultural_ref = trigger.payload_native["cultural_ref"]
        candidates = [
            row
            for row in context.arena.query(
                artifact_type="state-transformation-candidate",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
            )
            if row.payload_native["cultural_ref"] == cultural_ref
        ]
        native, status, losses = _run_transformation_worker(
            root / ".venv/bin/python",
            root / "seman2_runtime/workers/soar_transformation_worker.py",
            candidates=candidates,
            timeout_seconds=formal_policy.worker_timeout_seconds,
            memory_mib=formal_policy.worker_memory_mib,
        )
        yield ArtifactProposal(
            artifact_type="soar-transformation-decision",
            producer_id="soar-transformation-control",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=tuple(row.artifact_id for row in candidates),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native=native,
            payload_projection={
                "native_soar_used": status is ArtifactStatus.SUCCESS,
                "semantic_truth_selected": False,
            },
            status=status,
            losses=losses,
            justification_ids=tuple(row.artifact_id for row in candidates),
            idempotency_key=f"soar-transformation-decision:{cultural_ref}",
        )

    def apply_state_transformation(trigger, context):
        selected = context.arena.get(
            trigger.payload_native["selected_transformation_ref"]
        )
        if selected.artifact_id not in trigger.parent_ids:
            raise ContractError(
                "consolidation: transformation sélectionnée absente des parents"
            )
        yield ArtifactProposal(
            artifact_type="memory-consolidation-state",
            producer_id="ingestion-state-consolidator",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id, selected.artifact_id),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "episode_ref": selected.payload_native["episode_ref"],
                "operation": selected.payload_native["kind"],
                "applied": trigger.status is ArtifactStatus.SUCCESS,
                "truth_committed": False,
            },
            payload_projection={
                "operational_memory_update_only": True,
                "source_text_copied": False,
            },
            status=trigger.status,
            justification_ids=(trigger.artifact_id, selected.artifact_id),
            idempotency_key=f"memory-consolidation:{trigger.artifact_id}",
        )

    def build_situation_and_episode(trigger, context):
        family = context.arena.get(trigger.payload_native["family_ref"])
        branches = []
        for hypothesis_id in family.payload_native["member_refs"]:
            hypothesis = context.arena.get(hypothesis_id)
            branches.append(
                {
                    "hypothesis_ref": hypothesis.artifact_id,
                    "semantic_ref": hypothesis.payload_native["semantic_ref"],
                    "temporal_ref": hypothesis.payload_native["temporal_ref"],
                    "committed": False,
                }
            )
        common = {
            "producer_id": "situation-episode-system",
            "producer_build": BUILD,
            "configuration_digest": digest,
            "mode": trigger.mode,
            "session_id": trigger.session_id,
            "wave": context.scheduled_wave,
            "parent_ids": (family.artifact_id, trigger.artifact_id),
            "observation_refs": trigger.observation_refs,
            "source_anchors": trigger.source_anchors,
            "justification_ids": (family.artifact_id, trigger.artifact_id),
        }
        yield ArtifactProposal(
            artifact_type="situation-branch-set",
            payload_native={
                "family_ref": family.artifact_id,
                "branches": branches,
                "committed_ref": None,
            },
            payload_projection={
                "branch_count": len(branches),
                "world_update_performed": False,
            },
            idempotency_key=f"situation-branches:{family.artifact_id}",
            **common,
        )
        yield ArtifactProposal(
            artifact_type="episode-candidate",
            payload_native={
                "family_ref": family.artifact_id,
                "observation_refs": trigger.observation_refs,
                "branch_count": len(branches),
                "committed": False,
            },
            payload_projection={
                "episodic_indexable": True,
                "asserted_as_fact": False,
            },
            idempotency_key=f"episode:{family.artifact_id}",
            **common,
        )

    def spec(
        module_id,
        layer,
        consumes,
        produces,
        handler,
        build=BUILD,
        parallel_safe=False,
    ):
        return ModuleSpec(
            module_id=module_id,
            layer=layer,
            modes=frozenset({"ingestion"}),
            consumes=frozenset(consumes),
            produces=frozenset(produces),
            producer_build=build,
            configuration_digest=(
                ingestion_policy.configuration_digest
                if build == FOUNDATION_BUILD
                else digest
            ),
            handler=handler,
            parallel_safe=parallel_safe,
        )

    foundation = build_foundation_modules(ingestion_policy)
    return foundation + (
        spec("sentence-segmenter", 1, {"observation"}, {"observable-unit"}, segment),
        spec(
            "formal-analysis-dispatch",
            2,
            {"observable-unit"},
            {
                "analysis-routing-state",
                "analysis-job-erg",
                "analysis-job-dynamic-syntax",
                "analysis-job-link-grammar",
                "analysis-job-lexical",
                "analysis-job-form-phonology",
                "analysis-job-code",
            },
            dispatch,
        ),
        spec(
            "erg-worker",
            2,
            {"analysis-job-erg"},
            {"mrs-analysis"},
            erg,
            parallel_safe=True,
        ),
        spec(
            "native-analysis-ledger",
            3,
            {
                "mrs-analysis",
                "dynamic-syntax-analysis",
                "linkage-analysis",
                "lexical-analysis",
                "form-phonology-analysis",
                "code-analysis",
            },
            {"native-analysis-ledger-entry"},
            ledger,
        ),
        spec(
            "cross-representation-linker",
            3,
            {"native-analysis-ledger-entry"},
            {"cross-representation-hypothesis"},
            link_representations,
        ),
        spec(
            "mrs-graph-adapter",
            3,
            {"native-analysis-ledger-entry"},
            {"graph-fragment", "graph-adaptation-failure"},
            adapt_mrs,
        ),
        spec(
            "semantic-composer",
            4,
            {"graph-fragment"},
            {"semantic-structure"},
            compose_semantics,
        ),
        spec(
            "temporal-relation-system",
            4,
            {"semantic-structure"},
            {"temporal-constraint-network"},
            build_temporal_network,
        ),
        spec(
            "constraint-engine",
            4,
            {"temporal-constraint-network"},
            {"constraint-solution"},
            solve_constraints,
        ),
        spec(
            "semantic-reference-state",
            4,
            {"semantic-structure"},
            {"reference-state-candidate"},
            build_reference_state,
        ),
        spec(
            "factorized-hypothesis-manager",
            5,
            {"constraint-solution"},
            {"hypothesis-candidate"},
            create_hypothesis,
        ),
        spec(
            "hypothesis-family-builder",
            5,
            {"hypothesis-candidate"},
            {"hypothesis-family"},
            build_hypothesis_family,
        ),
        spec(
            "soar-control",
            6,
            {"hypothesis-family"},
            {"soar-control-state"},
            control_with_soar,
        ),
        spec(
            "formal-discourse-system",
            6,
            {"soar-control-state"},
            {"discourse-state-candidate"},
            build_discourse_state,
        ),
        spec(
            "formal-dialogue-system",
            7,
            {"discourse-state-candidate"},
            {"dialogue-state-candidate"},
            build_dialogue_state,
        ),
        spec(
            "situation-episode-system",
            7,
            {"dialogue-state-candidate"},
            {"situation-branch-set", "episode-candidate"},
            build_situation_and_episode,
        ),
        spec(
            "structural-retrieval",
            8,
            {"episode-candidate"},
            {"retrieval-index-entry"},
            index_episode,
        ),
        spec(
            "statistics-system",
            8,
            {"episode-candidate"},
            {"statistics-snapshot"},
            update_statistics,
        ),
        spec(
            "induction-engine",
            8,
            {"statistics-snapshot"},
            {"induction-state"},
            induce_patterns,
        ),
        spec(
            "cultural-concept-system",
            9,
            {"induction-state"},
            {"cultural-learning-state", "learned-concept-candidate"},
            update_cultural_state,
        ),
        spec(
            "candidate-transformation-system",
            10,
            {"cultural-learning-state"},
            {"state-transformation-candidate"},
            build_state_transformations,
        ),
        spec(
            "soar-transformation-control",
            10,
            {"state-transformation-candidate"},
            {"soar-transformation-decision"},
            choose_state_transformation,
        ),
        spec(
            "ingestion-state-consolidator",
            10,
            {"soar-transformation-decision"},
            {"memory-consolidation-state"},
            apply_state_transformation,
        ),
        spec(
            "link-grammar-worker",
            2,
            {"analysis-job-link-grammar"},
            {"linkage-analysis"},
            link_grammar,
            parallel_safe=True,
        ),
        spec(
            "lexical-resource-worker",
            2,
            {"analysis-job-lexical"},
            {"lexical-analysis"},
            lexical_resources,
            parallel_safe=True,
        ),
        spec(
            "form-phonology-worker",
            2,
            {"analysis-job-form-phonology"},
            {"form-phonology-analysis"},
            form_phonology,
            parallel_safe=True,
        ),
        spec(
            "code-analysis-worker",
            2,
            {"analysis-job-code"},
            {"code-analysis"},
            analyze_code,
            parallel_safe=True,
        ),
        spec(
            "dynamic-syntax-worker",
            2,
            {"analysis-job-dynamic-syntax"},
            {"dynamic-syntax-analysis"},
            dynamic_syntax,
            parallel_safe=True,
        ),
    )


def _run_worker(python, worker, text, root, policy, *, extra_request=None):
    request = {
        "root": str(root),
        "text": text,
        "max_candidates": policy.max_candidates,
        "max_linkages": policy.max_linkages,
        "max_lexical_forms": policy.max_lexical_forms,
        "max_lexical_candidates": policy.max_lexical_candidates,
        "max_form_occurrences": min(policy.max_lexical_forms, 16),
        "parse_timeout_seconds": min(policy.worker_timeout_seconds, 10),
        "memory_limit_mib": policy.worker_memory_mib,
    }
    request.update(extra_request or {})
    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    try:
        process = subprocess.run(
            [str(python), str(worker)],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=policy.worker_timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return (
            {"status": "timeout", "candidate_count": 0, "candidates": [], "action_count": 0, "actions": []},
            ArtifactStatus.FAILURE,
            ("worker-timeout",),
        )
    if process.returncode:
        return (
            {"status": "failure", "candidate_count": 0, "candidates": [], "action_count": 0, "actions": [], "diagnostic": process.stderr[-1000:]},
            ArtifactStatus.FAILURE,
            ("worker-process-failure",),
        )
    try:
        native = json.loads(process.stdout)
    except json.JSONDecodeError:
        return (
            {"status": "failure", "candidate_count": 0, "candidates": [], "action_count": 0, "actions": []},
            ArtifactStatus.FAILURE,
            ("worker-invalid-json",),
        )
    status = (
        ArtifactStatus.SUCCESS
        if native.get("status") in {"parsed", "analyzed"}
        else ArtifactStatus.FAILURE
    )
    return native, status, ()


def _run_soar_worker(
    python,
    worker,
    *,
    family_ref,
    candidates,
    beam_bound,
    timeout_seconds,
    memory_mib,
):
    active_candidates, inactive_candidates = _select_diverse_active_candidates(
        candidates, beam_bound
    )
    bounded_refs = [row["hypothesis_ref"] for row in active_candidates]
    inactive_refs = [row["hypothesis_ref"] for row in inactive_candidates]
    active_context_digest = hashlib.sha256(
        canonical_json(active_candidates).encode()
    ).hexdigest()
    justification_count = sum(
        len(row["justification_refs"]) for row in active_candidates
    )
    failure = {
        "status": "failure",
        "family_ref": family_ref,
        "active_refs": bounded_refs,
        "inactive_refs": inactive_refs,
        "action": "preserve-family-without-native-control",
        "beam_bound": beam_bound,
        "candidate_count": len(candidates),
        "selection_policy": "greedy-structural-diversity-stable",
        "active_context_digest": active_context_digest,
        "projected_justification_ref_count": justification_count,
        "working_memory_verified": False,
        "selection_performed": False,
    }
    environment = os.environ.copy()
    try:
        process = subprocess.run(
            [str(python), str(worker)],
            input=json.dumps(
                {
                    "family_ref": family_ref,
                    "active_candidates": active_candidates,
                    "inactive_refs": inactive_refs,
                    "beam_bound": beam_bound,
                    "memory_limit_mib": memory_mib,
                },
                ensure_ascii=False,
            ),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return failure, ArtifactStatus.FAILURE, ("soar-worker-timeout",)
    if process.returncode:
        return (
            {**failure, "diagnostic": process.stderr[-1_000:]},
            ArtifactStatus.FAILURE,
            ("soar-worker-process-failure",),
        )
    try:
        native = json.loads(process.stdout)
    except json.JSONDecodeError:
        return failure, ArtifactStatus.FAILURE, ("soar-worker-invalid-json",)
    if native.get("status") != "controlled" or not native.get(
        "working_memory_verified"
    ):
        return native, ArtifactStatus.FAILURE, ("soar-control-unverified",)
    if (
        native.get("active_refs") != bounded_refs
        or native.get("inactive_refs") != inactive_refs
        or native.get("active_context_digest") != active_context_digest
        or native.get("projected_justification_ref_count") != justification_count
    ):
        return native, ArtifactStatus.FAILURE, ("soar-control-projection-mismatch",)
    return native, ArtifactStatus.SUCCESS, ()


def _select_diverse_active_candidates(candidates, beam_bound):
    """Sélection déterministe avec réserve structurelle, sans score de vérité."""

    remaining = [dict(row) for row in candidates]
    selected = []
    while remaining and len(selected) < beam_bound:
        if not selected:
            winner = remaining[0]
        else:
            selected_features = [set(row["structural_features"]) for row in selected]

            def diversity_key(candidate):
                features = set(candidate["structural_features"])
                maximum_similarity = max(
                    (
                        len(features & prior) / len(features | prior)
                        if features | prior
                        else 1.0
                        for prior in selected_features
                    ),
                    default=0.0,
                )
                return (1.0 - maximum_similarity, candidate["hypothesis_ref"])

            winner = max(remaining, key=diversity_key)
        selected.append(winner)
        remaining.remove(winner)
    return selected, remaining


def _run_transformation_worker(
    python,
    worker,
    *,
    candidates,
    timeout_seconds,
    memory_mib,
):
    rows = [
        {
            "transformation_id": row.artifact_id,
            "kind": row.payload_native["kind"],
            "eligible": row.payload_native["eligible"],
            "episode_ref": row.payload_native["episode_ref"],
            "cultural_ref": row.payload_native["cultural_ref"],
            "precondition_refs": list(row.payload_native["precondition_refs"]),
        }
        for row in candidates
    ]
    eligible = [row for row in rows if row["eligible"]]
    if not eligible:
        raise ContractError("Soar transformations: aucun candidat admissible")
    active_context_digest = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
    projected_precondition_ref_count = sum(
        len(row["precondition_refs"]) for row in rows
    )
    fallback = {
        "status": "failure",
        "selected_transformation_ref": eligible[0]["transformation_id"],
        "transformation_kind": eligible[0]["kind"],
        "action": "defer-after-native-control-failure",
        "candidate_count": len(rows),
        "selection_is_operational": True,
        "semantic_truth_selected": False,
        "active_context_digest": active_context_digest,
        "projected_precondition_ref_count": projected_precondition_ref_count,
        "all_required_refs_observed_in_wm": False,
    }
    try:
        process = subprocess.run(
            [str(python), str(worker)],
            input=json.dumps(
                {
                    "candidates": rows,
                    "memory_limit_mib": memory_mib,
                },
                ensure_ascii=False,
            ),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return fallback, ArtifactStatus.FAILURE, ("soar-transformation-timeout",)
    if process.returncode:
        return (
            {**fallback, "diagnostic": process.stderr[-1_000:]},
            ArtifactStatus.FAILURE,
            ("soar-transformation-process-failure",),
        )
    try:
        native = json.loads(process.stdout)
    except json.JSONDecodeError:
        return fallback, ArtifactStatus.FAILURE, ("soar-transformation-invalid-json",)
    selected = native.get("selected_transformation_ref")
    if native.get("status") != "selected" or selected not in {
        row["transformation_id"] for row in eligible
    }:
        return native, ArtifactStatus.FAILURE, ("soar-transformation-unverified",)
    if (
        native.get("active_context_digest") != active_context_digest
        or native.get("projected_precondition_ref_count")
        != projected_precondition_ref_count
        or not native.get("all_required_refs_observed_in_wm")
    ):
        return native, ArtifactStatus.FAILURE, (
            "soar-transformation-projection-mismatch",
        )
    return native, ArtifactStatus.SUCCESS, ()


def _analysis_proposal(trigger, context, artifact_type, producer, native, status, losses, digest):
    return ArtifactProposal(
        artifact_type=artifact_type,
        producer_id=producer,
        producer_build=BUILD,
        configuration_digest=digest,
        mode=trigger.mode,
        session_id=trigger.session_id,
        wave=context.scheduled_wave,
        parent_ids=(trigger.artifact_id,),
        observation_refs=trigger.observation_refs,
        source_anchors=trigger.source_anchors,
        payload_native=native,
        payload_projection={"native_preserved": True, "fusion_performed": False},
        status=status,
        losses=losses,
        idempotency_key=f"analysis:{artifact_type}:{trigger.artifact_id}",
    )


def build_formal_runtime(
    root: Path,
    *,
    ingestion_policy: IngestionPolicy | None = None,
    formal_policy: FormalAnalysisPolicy | None = None,
    control: ControlState | None = None,
) -> CognitiveRuntime:
    ingestion = ingestion_policy or IngestionPolicy()
    formal = formal_policy or FormalAnalysisPolicy()
    return CognitiveRuntime(
        registry=build_formal_registry(),
        modules=build_formal_modules(root.resolve(), ingestion, formal),
        control=control or ControlState(limits=SafetyLimits(max_worker_count=4)),
    )
