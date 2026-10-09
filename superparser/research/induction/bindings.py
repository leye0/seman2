"""POC-02: named reference ports and preservation of candidate links.

Reference edges are observations about grammatical licensing.  In particular,
``MAYBE_REF`` remains an open alternative: this module generalizes its source
and target mention shapes but never commits identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .anti_unification import VariableBinding
from .observation_graph import GraphEdge, GraphNode, ObservationGraph


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ReferencePortPattern:
    pattern_id: str
    source_port: str
    target_port: str
    reference_kind: str
    rule_id: str
    source_json: str
    target_json: str
    bindings: tuple[VariableBinding, ...]

    @property
    def source_template(self) -> dict[str, Any]:
        value = json.loads(self.source_json)
        assert isinstance(value, dict)
        return value

    @property
    def target_template(self) -> dict[str, Any]:
        value = json.loads(self.target_json)
        assert isinstance(value, dict)
        return value

    @property
    def is_open_candidate(self) -> bool:
        return self.reference_kind == "MAYBE_REF"

    def bindings_for(self, side: str) -> dict[str, Any]:
        if side not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        return {
            binding.name: binding.left if side == "left" else binding.right
            for binding in self.bindings
        }

    def instantiate(self, side: str) -> dict[str, Any]:
        bindings = self.bindings_for(side)
        return {
            "source_port": self.source_port,
            "target_port": self.target_port,
            "kind": self.reference_kind,
            "rule_id": self.rule_id,
            "source": _substitute(self.source_template, bindings),
            "target": _substitute(self.target_template, bindings),
        }

    def match_graph(self, graph: ObservationGraph) -> list[dict[str, Any]]:
        """Return bindings for every compatible observed reference edge."""
        nodes = {node.node_id: node for node in graph.nodes}
        matches: list[dict[str, Any]] = []
        for edge in graph.edges:
            if edge.role != "REFERENCE":
                continue
            properties = edge.properties
            if properties.get("kind") != self.reference_kind:
                continue
            if properties.get("rule_id") != self.rule_id:
                continue
            source = nodes.get(edge.source)
            target = nodes.get(edge.target)
            if source is None or target is None:
                continue
            if source.kind != "MENTION" or target.kind != "MENTION":
                continue
            env: dict[str, Any] = {}
            if not _match(self.source_template, source.properties, env):
                continue
            if not _match(self.target_template, target.properties, env):
                continue
            matches.append(env)
        return matches

    def as_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "source_port": self.source_port,
            "target_port": self.target_port,
            "reference_kind": self.reference_kind,
            "rule_id": self.rule_id,
            "source_template": self.source_template,
            "target_template": self.target_template,
            "bindings": [binding.as_dict() for binding in self.bindings],
            "is_open_candidate": self.is_open_candidate,
        }


class _MentionGeneralizer:
    def __init__(self) -> None:
        self.pairs: dict[str, str] = {}
        self.bindings: dict[str, VariableBinding] = {}

    def generalize(self, left: Any, right: Any, path: tuple[str, ...] = ()) -> Any:
        if path and path[-1] == "span":
            return self.variable(left, right, "span", reuse=False)
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            if set(left) != set(right):
                raise ValueError("mention property shape differs")
            return {
                str(key): self.generalize(left[key], right[key], (*path, str(key)))
                for key in sorted(left)
            }
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                raise ValueError("mention list shape differs")
            return [
                self.generalize(a, b, (*path, str(index)))
                for index, (a, b) in enumerate(zip(left, right))
            ]
        if left == right:
            return left
        kind = "referential"
        if path and path[-1] in {"surface", "head_lemma"}:
            kind = "lexical"
        elif "features" in path:
            kind = "reference_feature"
        elif path and path[-1] == "sentence":
            kind = "discourse_position"
        return self.variable(left, right, kind)

    def variable(
        self,
        left: Any,
        right: Any,
        kind: str,
        *,
        reuse: bool = True,
    ) -> dict[str, str]:
        key = _json([left, right])
        name = self.pairs.get(key) if reuse else None
        if name is None:
            name = f"R{len(self.bindings) + 1}"
            if reuse:
                self.pairs[key] = name
            self.bindings[name] = VariableBinding(name, kind, _json(left), _json(right))
        return {"$var": name}


def generalize_reference_candidates(
    left: ObservationGraph,
    right: ObservationGraph,
    *,
    limit: int = 100,
) -> list[ReferencePortPattern]:
    """Generalize compatible REFERENCE alternatives without resolving them."""
    left_nodes = {node.node_id: node for node in left.nodes}
    right_nodes = {node.node_id: node for node in right.nodes}
    left_rows = _reference_rows(left, left_nodes)
    right_rows = _reference_rows(right, right_nodes)
    right_index: dict[tuple[str, ...], list[tuple[GraphEdge, GraphNode, GraphNode]]] = {}
    for row in right_rows:
        right_index.setdefault(_reference_key(*row), []).append(row)

    patterns: list[ReferencePortPattern] = []
    seen: set[str] = set()
    for left_row in left_rows:
        for right_row in right_index.get(_reference_key(*left_row), ()):
            left_edge, left_source, left_target = left_row
            right_edge, right_source, right_target = right_row
            generalizer = _MentionGeneralizer()
            try:
                source = generalizer.generalize(
                    left_source.properties, right_source.properties
                )
                target = generalizer.generalize(
                    left_target.properties, right_target.properties
                )
            except ValueError:
                continue
            kind = str(left_edge.properties["kind"])
            rule_id = str(left_edge.properties["rule_id"])
            body = {
                "source_port": "REF_SOURCE",
                "target_port": "REF_TARGET",
                "reference_kind": kind,
                "rule_id": rule_id,
                "source_template": source,
                "target_template": target,
            }
            pattern_id = "refpattern_" + sha256(_json(body).encode("utf-8")).hexdigest()[:24]
            bindings = tuple(
                sorted(
                    generalizer.bindings.values(),
                    key=lambda binding: int(binding.name[1:]),
                )
            )
            signature = _json(
                {
                    "body": body,
                    "bindings": [binding.as_dict() for binding in bindings],
                }
            )
            if signature in seen:
                continue
            seen.add(signature)
            patterns.append(
                ReferencePortPattern(
                    pattern_id=pattern_id,
                    source_port="REF_SOURCE",
                    target_port="REF_TARGET",
                    reference_kind=kind,
                    rule_id=rule_id,
                    source_json=_json(source),
                    target_json=_json(target),
                    bindings=bindings,
                )
            )
    patterns.sort(
        key=lambda pattern: (
            pattern.reference_kind,
            pattern.rule_id,
            len(pattern.bindings),
            pattern.pattern_id,
        )
    )
    return patterns[:limit]


def _reference_rows(
    graph: ObservationGraph,
    nodes: Mapping[str, GraphNode],
) -> list[tuple[GraphEdge, GraphNode, GraphNode]]:
    rows: list[tuple[GraphEdge, GraphNode, GraphNode]] = []
    for edge in graph.edges:
        if edge.role != "REFERENCE":
            continue
        source = nodes.get(edge.source)
        target = nodes.get(edge.target)
        if source is None or target is None:
            continue
        if source.kind == "MENTION" and target.kind == "MENTION":
            rows.append((edge, source, target))
    return rows


def _reference_key(
    edge: GraphEdge,
    source: GraphNode,
    target: GraphNode,
) -> tuple[str, ...]:
    return (
        str(edge.properties.get("kind")),
        str(edge.properties.get("rule_id")),
        str(source.properties.get("kind")),
        str(target.properties.get("kind")),
    )


def _substitute(value: Any, bindings: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        if set(value) == {"$var"}:
            return bindings[str(value["$var"])]
        return {str(key): _substitute(child, bindings) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child, bindings) for child in value]
    return value


def _match(pattern: Any, actual: Any, bindings: dict[str, Any]) -> bool:
    if isinstance(pattern, Mapping) and set(pattern) == {"$var"}:
        name = str(pattern["$var"])
        if name in bindings:
            return bindings[name] == actual
        bindings[name] = actual
        return True
    if isinstance(pattern, Mapping) and isinstance(actual, Mapping):
        return set(pattern) == set(actual) and all(
            _match(pattern[key], actual[key], bindings) for key in pattern
        )
    if isinstance(pattern, list) and isinstance(actual, list):
        return len(pattern) == len(actual) and all(
            _match(a, b, bindings) for a, b in zip(pattern, actual)
        )
    return pattern == actual

