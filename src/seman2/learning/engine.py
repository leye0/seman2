"""Coupled level-3 runtime: observe, align, consolidate, reprocess, generate."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..adapters.atomspace import AtomSpaceAdapter
from ..adapters.discodop import DiscoDopAdapter
from ..adapters.miner import MinerAdapter
from ..evidence.model import EvidenceUnit
from ..evidence.store import canonical_json, utc_now
from ..interpretation.model import AnalysisBundle, Projection
from .alignments import propose_alignments
from .generation import GenerationCandidate, Generator
from .model import Derivation, LearnedRelation, LearnedStructure, Support
from .patterns import induce_pattern, match_pattern
from .store import LearningStore
from .structures import (
    digest,
    discodop_tree,
    exact_fingerprint,
    observable_context,
    projection_fingerprint,
    structural_fragments,
)


class CoupledLearningRuntime:
    """Generic level-3 mechanics; all discovered knowledge remains data."""

    def __init__(
        self,
        store: LearningStore,
        *,
        atomspace: AtomSpaceAdapter | None = None,
        discodop: DiscoDopAdapter | None = None,
        miner: MinerAdapter | None = None,
        max_fragment_depth: int = 5,
        discourse_window: int = 4,
    ) -> None:
        self.store = store
        self.atomspace = atomspace or AtomSpaceAdapter()
        self.discodop = discodop or DiscoDopAdapter()
        self.miner = miner or MinerAdapter()
        self.max_fragment_depth = max_fragment_depth
        self.discourse_window = discourse_window
        self.generator = Generator(store)

    @classmethod
    def open(cls, database: str | Path, **kwargs: Any) -> "CoupledLearningRuntime":
        return cls(LearningStore(database), **kwargs)

    def close(self) -> None:
        self.store.close()

    @staticmethod
    def _structure(
        family: str,
        payload: Mapping[str, Any],
        derivation: Derivation,
        *,
        identity: Mapping[str, Any] | None = None,
        fingerprint: str | None = None,
        score: float | None = None,
        parent_id: str | None = None,
    ) -> LearnedStructure:
        identity_value = identity or {"family": family, "payload": payload}
        return LearnedStructure(
            structure_id=digest("structure", identity_value),
            family=family,
            fingerprint=fingerprint or exact_fingerprint(payload),
            payload=payload,
            derivation=derivation,
            score=score,
            parent_id=parent_id,
        )

    @staticmethod
    def _relation(
        source: str,
        target: str,
        relation: str,
        derivation: Derivation,
        payload: Mapping[str, Any] | None = None,
    ) -> LearnedRelation:
        data = dict(payload or {})
        identity = {"source": source, "target": target, "relation": relation, "payload": data}
        return LearnedRelation(
            relation_id=digest("relation", identity),
            source_id=source,
            target_id=target,
            relation=relation,
            payload=data,
            derivation=derivation,
        )

    def _put_supported(
        self,
        structure: LearnedStructure,
        evidence: EvidenceUnit,
        bundle: AnalysisBundle,
        *,
        hypothesis_id: str | None = None,
        span: Mapping[str, Any] | None = None,
        weight: float = 1.0,
    ) -> str:
        self.store.put_structure(structure)
        self.store.add_support(
            Support(
                structure_id=structure.structure_id,
                evidence_id=evidence.evidence_id,
                analysis_id=bundle.analysis_id,
                hypothesis_id=hypothesis_id,
                span=span,
                weight=weight,
            )
        )
        return structure.structure_id

    def observe(self, evidence: EvidenceUnit, bundle: AnalysisBundle) -> tuple[str, ...]:
        imported = Derivation(
            algorithm="trips-projection-import",
            version="1",
            parameters={"analyzer": bundle.analyzer, "configuration": dict(bundle.analyzer_configuration)},
            inputs=(evidence.evidence_id, bundle.analysis_id),
        )
        evidence_ref = self._structure(
            "evidence-reference",
            {
                "evidence_id": evidence.evidence_id,
                "stream_id": evidence.stream_id,
                "sequence": evidence.sequence,
                "raw_sha256": evidence.raw_sha256,
            },
            Derivation("evidence-reference", "1", inputs=(evidence.evidence_id,)),
            identity={"evidence_id": evidence.evidence_id},
        )
        analysis_ref = self._structure(
            "analysis-reference",
            {
                "analysis_id": bundle.analysis_id,
                "evidence_id": evidence.evidence_id,
                "raw_sha256": bundle.raw_sha256,
            },
            imported,
            identity={"analysis_id": bundle.analysis_id},
        )
        produced: list[str] = [evidence_ref.structure_id, analysis_ref.structure_id]
        self._put_supported(evidence_ref, evidence, bundle)
        self._put_supported(analysis_ref, evidence, bundle)
        self.store.put_relation(
            self._relation(evidence_ref.structure_id, analysis_ref.structure_id, "supports", imported)
        )
        context = observable_context(evidence, context_ids=bundle.context_evidence_ids)
        context_fingerprint = exact_fingerprint(context)

        for hypothesis in bundle.hypotheses:
            hypothesis_ref = self._structure(
                "hypothesis-reference",
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "rank": hypothesis.rank,
                    "score": hypothesis.score,
                    "analysis_id": bundle.analysis_id,
                },
                imported,
                identity={"hypothesis_id": hypothesis.hypothesis_id},
                score=hypothesis.score,
            )
            self._put_supported(
                hypothesis_ref, evidence, bundle, hypothesis_id=hypothesis.hypothesis_id
            )
            self.store.put_relation(
                self._relation(
                    analysis_ref.structure_id,
                    hypothesis_ref.structure_id,
                    "contains",
                    imported,
                )
            )
            produced.append(hypothesis_ref.structure_id)
            projection_ids: dict[str, str] = {}
            for projection in (hypothesis.semantic, hypothesis.structural):
                payload = {
                    "analysis_id": bundle.analysis_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "projection": projection.as_dict(),
                    "context": context,
                }
                structure = self._structure(
                    f"{projection.family}-observation",
                    payload,
                    imported,
                    identity={
                        "analysis_id": bundle.analysis_id,
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "projection": projection.family,
                    },
                    fingerprint=projection_fingerprint(projection),
                    score=hypothesis.score,
                    parent_id=hypothesis_ref.structure_id,
                )
                self._put_supported(
                    structure,
                    evidence,
                    bundle,
                    hypothesis_id=hypothesis.hypothesis_id,
                    span=self._projection_span(projection),
                )
                self.store.put_relation(
                    self._relation(
                        hypothesis_ref.structure_id,
                        structure.structure_id,
                        "projects-to",
                        imported,
                        {"family": projection.family},
                    )
                )
                self._record_context(
                    structure.structure_id,
                    context_fingerprint,
                    context,
                    evidence.evidence_id,
                )
                projection_ids[projection.family] = structure.structure_id
                produced.append(structure.structure_id)
                self._observe_nodes(structure, projection, evidence, bundle, hypothesis.hypothesis_id, imported)

            for fragment in structural_fragments(
                hypothesis.structural, max_depth=self.max_fragment_depth
            ):
                fragment_derivation = Derivation(
                    algorithm="incremental-dop-subtree-enumeration",
                    version="1",
                    parameters={"max_depth": self.max_fragment_depth},
                    inputs=(projection_ids["structural"],),
                )
                fragment_structure = self._structure(
                    "structural-fragment",
                    fragment,
                    fragment_derivation,
                    identity={
                        "family": "structural-fragment",
                        "fingerprint": fragment["fingerprint"],
                        "lexicalized": fragment["lexicalized"],
                        "depth": fragment["depth"],
                    },
                    fingerprint=fragment["fingerprint"],
                    parent_id=projection_ids["structural"],
                )
                self._put_supported(
                    fragment_structure,
                    evidence,
                    bundle,
                    hypothesis_id=hypothesis.hypothesis_id,
                )
                self.store.put_relation(
                    self._relation(
                        projection_ids["structural"],
                        fragment_structure.structure_id,
                        "exhibits",
                        fragment_derivation,
                    )
                )
                self._record_context(
                    fragment_structure.structure_id,
                    context_fingerprint,
                    context,
                    evidence.evidence_id,
                )
                produced.append(fragment_structure.structure_id)

            treebank = discodop_tree(hypothesis.structural)
            if treebank is not None:
                tree_payload = {
                    "tree": treebank[0],
                    "sentence": list(treebank[1]),
                    "analysis_id": bundle.analysis_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                }
                tree_structure = self._structure(
                    "treebank-observation",
                    tree_payload,
                    imported,
                    identity={
                        "analysis_id": bundle.analysis_id,
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "treebank": True,
                    },
                    fingerprint=exact_fingerprint({"tree": treebank[0]}),
                )
                self._put_supported(
                    tree_structure, evidence, bundle, hypothesis_id=hypothesis.hypothesis_id
                )
                produced.append(tree_structure.structure_id)

            for proposal in propose_alignments(hypothesis):
                alignment_derivation = Derivation(
                    algorithm="shared-span-alignment",
                    version="1",
                    inputs=(projection_ids["structural"], projection_ids["semantic"]),
                )
                alignment = self._structure(
                    "alignment",
                    proposal["payload"],
                    alignment_derivation,
                    identity={"alignment_id": proposal["alignment_id"]},
                    fingerprint=exact_fingerprint(
                        {
                            "structural_path": proposal["payload"]["structural_path"],
                            "semantic_path": proposal["payload"]["semantic_path"],
                        }
                    ),
                    score=proposal["score"],
                )
                self._put_supported(
                    alignment,
                    evidence,
                    bundle,
                    hypothesis_id=hypothesis.hypothesis_id,
                    span=proposal["payload"]["span_overlap"],
                    weight=proposal["score"],
                )
                self.store.put_relation(
                    self._relation(
                        projection_ids["structural"],
                        alignment.structure_id,
                        "aligned-by",
                        alignment_derivation,
                    )
                )
                self.store.put_relation(
                    self._relation(
                        alignment.structure_id,
                        projection_ids["semantic"],
                        "aligns-to",
                        alignment_derivation,
                    )
                )
                self._record_context(
                    alignment.structure_id,
                    context_fingerprint,
                    context,
                    evidence.evidence_id,
                )
                produced.append(alignment.structure_id)

        sequence_id = self._observe_sequence(evidence, bundle, imported)
        if sequence_id is not None:
            produced.append(sequence_id)
        if self.atomspace.available:
            self.atomspace.synchronize(self.store)
        return tuple(dict.fromkeys(produced))

    def _observe_nodes(
        self,
        parent: LearnedStructure,
        projection: Projection,
        evidence: EvidenceUnit,
        bundle: AnalysisBundle,
        hypothesis_id: str,
        derivation: Derivation,
    ) -> None:
        node_ids: dict[str, str] = {}
        for node in projection.nodes:
            payload = {
                "projection_structure_id": parent.structure_id,
                "native_node_id": node.node_id,
                "category": node.category,
                "attributes": dict(node.attributes),
                "span": node.span.as_dict() if node.span else None,
                "native_path": node.native_path,
            }
            row = self._structure(
                "projection-node",
                payload,
                derivation,
                identity={"parent": parent.structure_id, "native_node_id": node.node_id},
                fingerprint=exact_fingerprint(
                    {"projection_family": projection.family, "category": node.category, "shape": payload["native_path"]}
                ),
                parent_id=parent.structure_id,
            )
            self._put_supported(
                row,
                evidence,
                bundle,
                hypothesis_id=hypothesis_id,
                span=payload["span"],
            )
            self.store.put_relation(
                self._relation(parent.structure_id, row.structure_id, "contains", derivation)
            )
            node_ids[node.node_id] = row.structure_id
        for edge in projection.edges:
            source = node_ids.get(edge.source_id)
            target = node_ids.get(edge.target_id)
            if source is not None and target is not None:
                self.store.put_relation(
                    self._relation(source, target, edge.relation, derivation, edge.attributes)
                )

    @staticmethod
    def _projection_span(projection: Projection) -> Mapping[str, Any] | None:
        spans = [node.span for node in projection.nodes if node.span is not None]
        if not spans:
            return None
        return {"start": min(span.start for span in spans), "end": max(span.end for span in spans)}

    def _record_context(
        self,
        structure_id: str,
        fingerprint: str,
        context: Mapping[str, Any],
        evidence_id: str,
    ) -> None:
        statistic_id = digest(
            "context",
            {"structure": structure_id, "fingerprint": fingerprint, "evidence": evidence_id},
        )
        self.store.put_context(statistic_id, structure_id, fingerprint, context, evidence_id)

    def _observe_sequence(
        self, evidence: EvidenceUnit, bundle: AnalysisBundle, derivation: Derivation
    ) -> str | None:
        evidence_ids = (*bundle.context_evidence_ids[-self.discourse_window :], evidence.evidence_id)
        steps: list[dict[str, Any]] = []
        for position, evidence_id in enumerate(evidence_ids):
            rows = self.store.structures_for_evidence(evidence_id)
            fingerprints = sorted(
                {
                    f"{row.family}:{row.fingerprint}"
                    for row in rows
                    if row.family in {"semantic-observation", "structural-observation", "alignment"}
                }
            )
            steps.append({"position": position, "fingerprints": fingerprints})
        if len(steps) < 2:
            return None
        payload = {"length": len(steps), "steps": steps}
        structure = self._structure(
            "context-sequence",
            payload,
            Derivation(
                algorithm="ordered-context-window",
                version="1",
                parameters={"maximum_window": self.discourse_window},
                inputs=tuple(evidence_ids),
            ),
            fingerprint=exact_fingerprint(
                {"length": len(steps), "step_widths": [len(step["fingerprints"]) for step in steps]}
            ),
        )
        self._put_supported(structure, evidence, bundle)
        return structure.structure_id

    def consolidate(
        self,
        *,
        minimum_support: int = 2,
        use_discodop: bool = True,
        synchronize: bool = True,
    ) -> dict[str, Any]:
        if minimum_support < 2:
            raise ValueError("minimum support must be at least two")
        inputs: list[str] = []
        outputs: list[str] = []
        families = (
            "semantic-observation",
            "structural-observation",
            "alignment",
            "context-sequence",
        )
        for family in families:
            groups: dict[str, list[LearnedStructure]] = defaultdict(list)
            for row in self.store.structures(family=family):
                groups[row.fingerprint].append(row)
            for fingerprint, rows in groups.items():
                if len(rows) < minimum_support:
                    continue
                instances = [row.payload for row in rows]
                induced = induce_pattern(instances)
                derivation = Derivation(
                    algorithm="generic-anti-unification-mdl",
                    version="1",
                    parameters={"minimum_support": minimum_support, "source_family": family},
                    inputs=tuple(row.structure_id for row in rows),
                )
                pattern_payload = {"source_family": family, **induced["payload"]}
                pattern = LearnedStructure(
                    structure_id=induced["pattern_id"],
                    family="pattern",
                    fingerprint=induced["fingerprint"],
                    payload=pattern_payload,
                    derivation=derivation,
                    score=float(induced["scores"]["rank"]),
                )
                self.store.put_structure(pattern)
                outputs.append(pattern.structure_id)
                for row, bindings in zip(rows, induced["bindings"]):
                    binding_id = digest(
                        "binding",
                        {"pattern": pattern.structure_id, "instance": row.structure_id, "bindings": bindings},
                    )
                    self.store.put_binding(
                        binding_id, pattern.structure_id, row.structure_id, bindings, derivation
                    )
                    self.store.put_relation(
                        self._relation(row.structure_id, pattern.structure_id, "generalized-into", derivation)
                    )
                    inputs.append(row.structure_id)

        dop_outputs: list[str] = []
        if use_discodop and self.discodop.available:
            treebank = self.store.structures(family="treebank-observation")
            if len(treebank) >= minimum_support:
                fragments = self.discodop.recurring(
                    [str(row.payload["tree"]) for row in treebank],
                    [tuple(row.payload["sentence"]) for row in treebank],
                    max_depth=self.max_fragment_depth,
                )
                for fragment in fragments:
                    if fragment["support"] < minimum_support:
                        continue
                    derivation = Derivation(
                        algorithm="disco-dop-recurringfragments",
                        version="local",
                        parameters={"max_depth": self.max_fragment_depth},
                        inputs=tuple(
                            treebank[index].structure_id for index in fragment["tree_indices"]
                        ),
                    )
                    row = self._structure(
                        "dop-fragment",
                        fragment,
                        derivation,
                        identity={"discodop_fragment": fragment["fragment"]},
                        score=float(fragment["support"]),
                    )
                    self.store.put_structure(row)
                    dop_outputs.append(row.structure_id)
                    outputs.append(row.structure_id)

        run_identity = {
            "at": utc_now(),
            "inputs": sorted(set(inputs)),
            "outputs": sorted(set(outputs)),
            "minimum_support": minimum_support,
        }
        run_id = digest("consolidation", run_identity)
        self.store.record_run(
            run_id,
            algorithm="coupled-consolidation",
            parameters={
                "minimum_support": minimum_support,
                "discodop_requested": use_discodop,
                "discodop_available": self.discodop.available,
                "miner_available": self.miner.available,
            },
            inputs=tuple(sorted(set(inputs))),
            outputs=tuple(sorted(set(outputs))),
        )
        sync = self.atomspace.synchronize(self.store) if synchronize else self.atomspace.status
        return {
            "run_id": run_id,
            "patterns": len(set(outputs) - set(dop_outputs)),
            "dop_fragments": len(set(dop_outputs)),
            "outputs": sorted(set(outputs)),
            "atomspace": sync,
            "discodop": self.discodop.status,
            "miner": self.miner.status,
        }

    def reprocess(self, *, minimum_similarity: float = 0.0) -> dict[str, Any]:
        patterns = self.store.structures(family="pattern")
        observations = tuple(
            row
            for family in ("semantic-observation", "structural-observation", "alignment", "context-sequence")
            for row in self.store.structures(family=family)
        )
        created: list[str] = []
        for pattern in patterns:
            generalized = pattern.payload.get("generalized")
            source_family = pattern.payload.get("source_family")
            for observation in observations:
                if observation.family != source_family:
                    continue
                bindings = match_pattern(generalized, observation.payload)
                if bindings is None:
                    continue
                derivation = Derivation(
                    algorithm="pattern-reprocessing",
                    version="1",
                    parameters={"minimum_similarity": minimum_similarity},
                    inputs=(pattern.structure_id, observation.structure_id),
                )
                binding_id = digest(
                    "binding",
                    {"pattern": pattern.structure_id, "instance": observation.structure_id, "bindings": bindings},
                )
                if self.store.put_binding(
                    binding_id, pattern.structure_id, observation.structure_id, bindings, derivation
                ):
                    created.append(binding_id)
                self.store.put_relation(
                    self._relation(observation.structure_id, pattern.structure_id, "matches", derivation)
                )
        if self.atomspace.available:
            self.atomspace.synchronize(self.store)
        return {"patterns": len(patterns), "observations": len(observations), "new_bindings": len(created)}

    def generate(
        self,
        target: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
        bindings: Mapping[str, Any] | None = None,
        limit: int = 10,
    ) -> tuple[GenerationCandidate, ...]:
        return self.generator.generate(
            target, context=context, bindings=bindings, limit=limit
        )

    def status(self) -> dict[str, Any]:
        return {
            "counts": self.store.counts(),
            "atomspace": self.atomspace.status,
            "discodop": self.discodop.status,
            "miner": self.miner.status,
        }
