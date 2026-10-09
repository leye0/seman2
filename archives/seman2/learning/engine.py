"""Coupled level-3 runtime: observe, align, consolidate, reprocess, generate."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

from ..adapters.atomspace import AtomSpaceAdapter
from ..adapters.discodop import DiscoDopAdapter
from ..adapters.miner import MinerAdapter
from ..evidence.model import EvidenceUnit
from ..evidence.store import canonical_json, utc_now
from ..interpretation.model import AnalysisBundle, Projection
from .alignments import propose_alignments
from .generation import GenerationCandidate, Generator
from .growth import GrowthInducer, RecurrenceIndex
from .model import Derivation, LearnedRelation, LearnedStructure, Support
from .patterns import induce_pattern, match_pattern
from .retro import (
    binding_rows,
    coverage_revision_proposals,
    coverage_weights,
    match_identity,
    match_payload,
    match_fragments_on_tree,
    retro_derivation,
)
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
        max_fragment_depth: int = 3,
        discourse_window: int = 4,
        max_fragments_per_run: int = 2000,
        min_fragment_nodes: int = 3,
        max_matches_per_tree: int = 64,
        sample_size: int = 24,
        seed: int | None = None,
    ) -> None:
        self.store = store
        self.atomspace = atomspace or AtomSpaceAdapter()
        self.discodop = discodop or DiscoDopAdapter()
        self.miner = miner or MinerAdapter()
        self.max_fragment_depth = max_fragment_depth
        self.discourse_window = discourse_window
        self.max_fragments_per_run = max_fragments_per_run
        self.min_fragment_nodes = min_fragment_nodes
        self.max_matches_per_tree = max_matches_per_tree
        self.sample_size = sample_size
        self.seed = seed
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

            # Node-level and fragment-level expansion is deferred to
            # consolidation: the projection payload already carries the
            # complete graph, and the awake cycle must stay cheap.

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
                produced.extend(
                    self._retro_match_tree(
                        treebank[0],
                        treebank[1],
                        tree_structure_id=tree_structure.structure_id,
                        analysis_id=bundle.analysis_id,
                        hypothesis_id=hypothesis.hypothesis_id,
                        evidence_id=evidence.evidence_id,
                    )
                )

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
            rows = self.store.structures_for_evidence_in_memory(evidence_id)
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

    def _dop_fragment_sources(self) -> tuple[tuple[str, LearnedStructure], ...]:
        self.store.load_family("dop-fragment")
        rows: list[tuple[str, LearnedStructure]] = []
        for row in self.store.structures_in_memory(family="dop-fragment"):
            source = row.payload.get("fragment")
            if isinstance(source, str) and source:
                rows.append((source, row))
        return tuple(rows)

    def _fragment_is_worth_storing(self, source: str) -> bool:
        """Bound the fragment lattice: no trivial terminals, no tiny stubs."""
        if source.count("(") < self.min_fragment_nodes:
            return False
        if len(source) < 12:
            return False
        return True

    def _rng(self) -> random.Random:
        """Per-run RNG: stochastic induction keeps each pass bounded.

        Stable patterns reappear across samples and solidify over time;
        one-off combinations get filtered out by the long-term repetition.
        """
        return random.Random(self.seed if self.seed is not None else None)

    @staticmethod
    def _sample(rows: Sequence[Any], size: int, rng: random.Random) -> tuple[Any, ...]:
        if size < 1:
            return ()
        if len(rows) <= size:
            return tuple(rows)
        return tuple(rng.sample(list(rows), size))

    @staticmethod
    def _fragment_root_label(source: str) -> str:
        cursor = source.find("(")
        if cursor < 0:
            return ""
        cursor += 1
        end = cursor
        while end < len(source) and not source[end].isspace() and source[end] != ")":
            end += 1
        return source[cursor:end]

    @staticmethod
    def _tree_labels(tree_source: str) -> set[str]:
        labels: set[str] = set()
        cursor = 0
        while True:
            cursor = tree_source.find("(", cursor)
            if cursor < 0:
                break
            cursor += 1
            end = cursor
            while end < len(tree_source) and not tree_source[end].isspace() and tree_source[end] != ")":
                end += 1
            if end > cursor:
                labels.add(tree_source[cursor:end])
        return labels

    @staticmethod
    def _fragment_neighbors(
        index: RecurrenceIndex,
        payloads: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, list[str]]:
        """Map each frequent motif to motifs actually observed alongside it.

        Co-occurrence on the same support is the only edge: growth never
        invents connections the data did not show.
        """
        supports_to_keys: dict[str, list[str]] = {}
        for key in index.keys():
            for support_id in index.supports(key):
                supports_to_keys.setdefault(support_id, []).append(key)
        neighbors: dict[str, set[str]] = {}
        for keys in supports_to_keys.values():
            for key in keys:
                bucket = neighbors.setdefault(key, set())
                for other in keys:
                    if other != key:
                        bucket.add(other)
        return {key: sorted(values) for key, values in neighbors.items()}

    def _retro_match_tree(
        self,
        tree_source: str,
        sentence: Sequence[str],
        *,
        tree_structure_id: str,
        analysis_id: str | None,
        hypothesis_id: str | None,
        evidence_id: str | None,
        fragment_rows: Sequence[tuple[str, LearnedStructure]] | None = None,
    ) -> tuple[str, ...]:
        """Send known complex segments back against one observed tree."""
        produced: list[str] = []
        fragments = (
            tuple(fragment_rows)
            if fragment_rows is not None
            else self._dop_fragment_sources()
        )
        if not fragments:
            return ()
        # Index by root label: a fragment can only match inside a tree that
        # contains that label. This replaces the O(fragments × trees) scan.
        root_labels = {
            self._fragment_root_label(source)
            for source, _ in fragments
        }
        host_labels = self._tree_labels(tree_source)
        candidates = [
            (source, row)
            for source, row in fragments
            if self._fragment_root_label(source) in host_labels
        ]
        # Bound the work per tree: sample candidates instead of scanning all.
        rng = self._rng()
        candidates = list(self._sample(candidates, self.max_matches_per_tree * 4, rng))
        candidates.sort(key=lambda item: -len(item[0]))
        matched = match_fragments_on_tree(
            [source for source, _ in candidates], tree_source, sentence
        )
        by_source = {source: row for source, row in candidates}
        stored_matches = 0
        for fragment_source, match in matched:
            if stored_matches >= self.max_matches_per_tree:
                break
            fragment_row = by_source.get(fragment_source)
            if fragment_row is None:
                continue
            payload = match_payload(
                fragment_id=fragment_row.structure_id,
                fragment_source=fragment_source,
                tree_structure_id=tree_structure_id,
                analysis_id=analysis_id,
                hypothesis_id=hypothesis_id,
                match=match,
            )
            derivation = retro_derivation(
                parameters={
                    "fragment_fingerprint": fragment_row.fingerprint,
                    "tree_structure_id": tree_structure_id,
                },
                inputs=(fragment_row.structure_id, tree_structure_id),
            )
            structure = self._structure(
                "fragment-match",
                payload,
                derivation,
                identity=match_identity(payload),
                fingerprint=exact_fingerprint(
                    {
                        "fragment": fragment_source,
                        "root_path": match.root_path,
                        "bindings": dict(match.bindings),
                    }
                ),
                parent_id=fragment_row.structure_id,
            )
            self.store.put_structure(structure)
            if evidence_id:
                self.store.add_support(
                    Support(
                        structure_id=structure.structure_id,
                        evidence_id=evidence_id,
                        analysis_id=analysis_id,
                        hypothesis_id=hypothesis_id,
                        span=None,
                        weight=1.0,
                    )
                )
            self.store.put_relation(
                self._relation(
                    fragment_row.structure_id,
                    structure.structure_id,
                    "instantiated-by",
                    derivation,
                )
            )
            self.store.put_relation(
                self._relation(
                    tree_structure_id,
                    structure.structure_id,
                    "exhibits",
                    derivation,
                )
            )
            for binding_id, binding_payload in binding_rows(
                fragment_id=fragment_row.structure_id,
                tree_structure_id=tree_structure_id,
                match=match,
            ):
                self.store.put_binding(
                    binding_id,
                    fragment_row.structure_id,
                    tree_structure_id,
                    binding_payload,
                    derivation,
                )
            produced.append(structure.structure_id)
            stored_matches += 1
        return tuple(produced)

    def retro(
        self,
        *,
        evidence_id: str | None = None,
        algorithm: str = "dop-fragment-retro-match",
        fragment_rows: Sequence[tuple[str, LearnedStructure]] | None = None,
    ) -> dict[str, Any]:
        """Match known complex segments against stored trees (indexed)."""
        fragments = (
            tuple(fragment_rows)
            if fragment_rows is not None
            else self._dop_fragment_sources()
        )
        rng = self._rng()
        fragments = self._sample(fragments, self.max_fragments_per_run, rng)
        trees = self.store.structures(family="treebank-observation")
        trees = self._sample(trees, max(self.sample_size, 1) * 2, rng)
        matches: list[tuple[str, Mapping[str, Any]]] = []
        produced: list[str] = []
        with self.store.batch():
            for tree_row in trees:
                tree_source = tree_row.payload.get("tree")
                sentence = tree_row.payload.get("sentence") or ()
                if not isinstance(tree_source, str) or not tree_source:
                    continue
                support_rows = self.store.supports(tree_row.structure_id)
                linked_evidence = evidence_id or (
                    support_rows[0]["evidence_id"] if support_rows else None
                )
                created = self._retro_match_tree(
                    tree_source,
                    tuple(str(item) for item in sentence),
                    tree_structure_id=tree_row.structure_id,
                    analysis_id=tree_row.payload.get("analysis_id"),
                    hypothesis_id=tree_row.payload.get("hypothesis_id"),
                    evidence_id=linked_evidence,
                    fragment_rows=fragments,
                )
                for structure_id in created:
                    structure = self.store.get_structure(structure_id)
                    matches.append((structure_id, structure.payload))
                    produced.append(structure_id)
        weights = coverage_weights(matches)
        prior_scores = {
            str(row.payload.get("hypothesis_id")): float(row.payload.get("score") or 0.0)
            for row in self.store.structures(family="hypothesis-reference")
            if row.payload.get("hypothesis_id")
        }
        proposals = coverage_revision_proposals(
            evidence_id=evidence_id or "",
            weights=weights,
            prior_scores=prior_scores,
            algorithm=algorithm,
        )
        if self.atomspace.available:
            self.atomspace.synchronize(self.store)
        return {
            "fragments": len(fragments),
            "trees": len(trees),
            "matches": len(produced),
            "match_structure_ids": sorted(set(produced)),
            "coverage_weights": weights,
            "revision_proposals": list(proposals),
        }

    def consolidate(
        self,
        *,
        minimum_support: int = 2,
        use_discodop: bool = True,
        synchronize: bool = True,
    ) -> dict[str, Any]:
        if minimum_support < 2:
            raise ValueError("minimum support must be at least two")
        rng = self._rng()
        # One durable transaction for the whole run: the outbox is useless
        # while AtomSpace is absent, and per-object SQLite writes dominate.
        self.store.outbox_enabled = self.atomspace.available
        inputs: list[str] = []
        outputs: list[str] = []
        families = (
            "semantic-observation",
            "structural-observation",
            "alignment",
            "context-sequence",
        )
        with self.store.batch():
            # Recurrence to select, local growth to explore, scoring to
            # solidify. Never "all possible combinations".
            inducer = GrowthInducer(minimum_support=minimum_support)
            index = RecurrenceIndex()
            payloads: dict[str, dict[str, Any]] = {}
            alignment_counts: dict[str, int] = {}
            observation_keys: list[str] = []
            for family in families:
                rows = self.store.structures_in_memory(family=family)
                if not rows:
                    self.store.load_family(family)
                    rows = self.store.structures_in_memory(family=family)
                for row in rows:
                    index.add(row.fingerprint, row.structure_id)
                    payloads[row.fingerprint] = dict(row.payload)
                    if family == "alignment":
                        alignment_counts[row.fingerprint] = (
                            alignment_counts.get(row.fingerprint, 0) + 1
                        )
                    if family in ("semantic-observation", "structural-observation"):
                        observation_keys.append(row.fingerprint)

            selected = inducer.select(index, payloads)
            grown: list[Any] = []
            neighbors = self._fragment_neighbors(index, payloads)
            for candidate in selected:
                grown.extend(
                    inducer.grow(candidate, neighbors, index, payloads, rng=rng)
                )
            candidates = [*selected, *grown]
            solidified = inducer.solidify(
                candidates,
                payloads=payloads,
                observations=observation_keys,
                alignment_counts=alignment_counts,
            )
            for candidate in solidified:
                derivation = Derivation(
                    algorithm="growth-induction",
                    version="1",
                    parameters={
                        "minimum_support": minimum_support,
                        "score": candidate.score,
                    },
                    inputs=candidate.supports,
                )
                pattern = LearnedStructure(
                    structure_id=digest("pattern", {"key": candidate.key}),
                    family="pattern",
                    fingerprint=candidate.key,
                    payload={"tree": dict(candidate.tree), "growth": candidate.as_dict()},
                    derivation=derivation,
                    score=candidate.score,
                )
                self.store.put_structure(pattern)
                outputs.append(pattern.structure_id)
                for support_id in candidate.supports:
                    inputs.append(support_id)
                    self.store.put_relation(
                        self._relation(
                            support_id, pattern.structure_id, "generalized-into", derivation
                        )
                    )

            dop_outputs: list[str] = []
            if use_discodop and self.discodop.available:
                treebank = self.store.structures(family="treebank-observation")
                if len(treebank) >= minimum_support:
                    fragments = self.discodop.recurring(
                        [str(row.payload["tree"]) for row in treebank],
                        [tuple(row.payload["sentence"]) for row in treebank],
                        max_depth=self.max_fragment_depth,
                    )
                    kept = 0
                    for fragment in fragments:
                        if kept >= self.max_fragments_per_run:
                            break
                        if fragment["support"] < minimum_support:
                            continue
                        if not self._fragment_is_worth_storing(fragment["fragment"]):
                            continue
                        derivation = Derivation(
                            algorithm="disco-dop-recurringfragments",
                            version="local",
                            parameters={
                                "max_depth": self.max_fragment_depth,
                                "min_nodes": self.min_fragment_nodes,
                            },
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
                        kept += 1

            retro_report = (
                self.retro(
                    fragment_rows=tuple(
                        (row.payload["fragment"], row)
                        for row in (
                            self.store.get_structure(sid) for sid in dop_outputs
                        )
                        if isinstance(row.payload.get("fragment"), str)
                    )
                )
                if dop_outputs
                else {
                    "fragments": 0,
                    "trees": 0,
                    "matches": 0,
                    "match_structure_ids": [],
                    "coverage_weights": {},
                    "revision_proposals": [],
                }
            )
            outputs.extend(retro_report.get("match_structure_ids", ()))

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
            "patterns": len(set(outputs) - set(dop_outputs) - set(retro_report.get("match_structure_ids", ()))),
            "dop_fragments": len(set(dop_outputs)),
            "retro": retro_report,
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
        retro_report = self.retro()
        if self.atomspace.available:
            self.atomspace.synchronize(self.store)
        return {
            "patterns": len(patterns),
            "observations": len(observations),
            "new_bindings": len(created),
            "retro": retro_report,
        }

    def generate(
        self,
        target: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
        bindings: Mapping[str, Any] | None = None,
        limit: int = 10,
        modes: Sequence[str] = ("retrieve", "instantiate"),
    ) -> tuple[GenerationCandidate, ...]:
        return self.generator.generate(
            target, context=context, bindings=bindings, limit=limit, modes=modes
        )

    def status(self) -> dict[str, Any]:
        return {
            "counts": self.store.counts(),
            "atomspace": self.atomspace.status,
            "discodop": self.discodop.status,
            "miner": self.miner.status,
        }
