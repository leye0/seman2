"""POC-12: incremental structural index and versioned consolidation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .observation_graph import ObservationGraph


PROTECTED = frozenset({"case", "inversion", "modal", "mood", "negation", "stype", "voice", "wh"})


@dataclass(frozen=True, slots=True)
class ComponentRevisionRecord:
    component_id: str
    signature: str
    version: int
    status: str
    member_ids: tuple[str, ...]
    parent_version: int | None


@dataclass(frozen=True, slots=True)
class IngestionResult:
    observation_id: str
    signature: str
    neighbor_ids: tuple[str, ...]
    comparisons: int
    component_id: str | None


class IncrementalStructuralIndex:
    def __init__(self, *, min_support: int = 4) -> None:
        self.min_support = min_support
        self.signatures: dict[str, str] = {}
        self.buckets: dict[str, list[str]] = {}
        self.invalidated: set[str] = set()
        self.revisions: list[ComponentRevisionRecord] = []
        self.comparison_cache: set[tuple[str, str]] = set()

    def ingest(self, graph: ObservationGraph) -> IngestionResult:
        observation_id = graph.observation_id
        if observation_id in self.signatures:
            raise ValueError(f"duplicate observation: {observation_id}")
        signature = structural_signature(graph)
        neighbors = tuple(self.buckets.get(signature, ()))
        for neighbor in neighbors:
            self.comparison_cache.add(tuple(sorted((observation_id, neighbor))))
        self.signatures[observation_id] = signature
        self.buckets.setdefault(signature, []).append(observation_id)
        component = self._consolidate(signature)
        return IngestionResult(
            observation_id,
            signature,
            neighbors,
            len(neighbors),
            None if component is None else component.component_id,
        )

    def invalidate(self, observation_id: str) -> ComponentRevisionRecord | None:
        if observation_id not in self.signatures:
            raise KeyError(observation_id)
        self.invalidated.add(observation_id)
        return self._consolidate(self.signatures[observation_id])

    @property
    def active_components(self) -> tuple[ComponentRevisionRecord, ...]:
        ids = {row.component_id for row in self.revisions}
        latest = [max((row for row in self.revisions if row.component_id == component_id), key=lambda row: row.version) for component_id in ids]
        return tuple(sorted((row for row in latest if row.status == "active"), key=lambda row: row.component_id))

    def _consolidate(self, signature: str) -> ComponentRevisionRecord | None:
        members = tuple(sorted(row for row in self.buckets.get(signature, ()) if row not in self.invalidated))
        component_id = "incremental_component_" + signature[:20]
        previous = [row for row in self.revisions if row.component_id == component_id]
        status = "active" if len(members) >= self.min_support else "retired"
        if not previous and status == "retired":
            return None
        if previous and previous[-1].member_ids == members and previous[-1].status == status:
            return previous[-1]
        version = len(previous) + 1
        revision = ComponentRevisionRecord(
            component_id,
            signature,
            version,
            status,
            members,
            None if not previous else previous[-1].version,
        )
        self.revisions.append(revision)
        return revision

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "incremental-index/0.1",
            "min_support": self.min_support,
            "signatures": dict(sorted(self.signatures.items())),
            "buckets": {key: list(value) for key, value in sorted(self.buckets.items())},
            "invalidated": sorted(self.invalidated),
            "revisions": [row.__dict__ if hasattr(row, "__dict__") else {
                "component_id": row.component_id,
                "signature": row.signature,
                "version": row.version,
                "status": row.status,
                "member_ids": list(row.member_ids),
                "parent_version": row.parent_version,
            } for row in self.revisions],
            "comparison_cache": [list(row) for row in sorted(self.comparison_cache)],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IncrementalStructuralIndex":
        if payload.get("schema_version") != "incremental-index/0.1":
            raise ValueError("unsupported incremental index schema")
        index = cls(min_support=int(payload["min_support"]))
        index.signatures = {str(key): str(value) for key, value in payload["signatures"].items()}
        index.buckets = {str(key): [str(row) for row in value] for key, value in payload["buckets"].items()}
        index.invalidated = {str(row) for row in payload["invalidated"]}
        index.revisions = [
            ComponentRevisionRecord(
                str(row["component_id"]), str(row["signature"]), int(row["version"]),
                str(row["status"]), tuple(str(value) for value in row["member_ids"]),
                None if row["parent_version"] is None else int(row["parent_version"]),
            )
            for row in payload["revisions"]
        ]
        index.comparison_cache = {tuple(sorted((str(row[0]), str(row[1])))) for row in payload["comparison_cache"]}
        return index


def structural_signature(graph: ObservationGraph) -> str:
    if not graph.root_ids:
        return sha256(b"no-root").hexdigest()
    nodes = {node.node_id: node for node in graph.nodes}
    children: dict[str, list[Any]] = {}
    for edge in graph.edges:
        if edge.role == "CHILD":
            children.setdefault(edge.source, []).append(edge)

    def shape(node_id: str) -> dict[str, Any]:
        node = nodes[node_id]
        props = node.properties
        features = props.get("features", {})
        ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
        return {
            "category": props.get("category"),
            "rule_id": props.get("rule_id"),
            "origin": props.get("origin"),
            "protected": {key: features[key] for key in sorted(features) if key in PROTECTED},
            "children": [shape(edge.target) for edge in ordered],
        }

    payload = json.dumps(shape(graph.root_ids[0]), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


def batch_signature_groups(graphs: Sequence[ObservationGraph], *, min_support: int = 4) -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {}
    for graph in graphs:
        buckets.setdefault(structural_signature(graph), []).append(graph.observation_id)
    return {
        signature: tuple(sorted(members))
        for signature, members in buckets.items()
        if len(members) >= min_support
    }
