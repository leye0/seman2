"""POC-01: constrained anti-unification of ObservationGraph constituents.

This first operator works on rooted constituent DAGs.  It preserves node
kind, grammatical category, rule identity, ordered CHILD edges and graph
reentrance.  Differing JSON values become variables whose two substitutions
reconstruct the original rooted analyses exactly.

Approximate alignment, insertions/deletions and variable-size subgraphs are
deliberately outside this POC-01 operator; they belong to POC-02/05.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .observation_graph import GraphEdge, GraphNode, ObservationGraph


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_object(payload: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AntiUnificationError("expected a JSON object")
    return value


class AntiUnificationError(ValueError):
    """The two rooted graphs have no valid exact structural alignment."""


@dataclass(frozen=True, slots=True)
class AlignmentPolicy:
    """Structural constraints for the POC-01 exact aligner."""

    fixed_properties: frozenset[str] = frozenset({"category", "rule_id", "origin"})
    protected_features: frozenset[str] = frozenset(
        {
            "case",
            "inversion",
            "modal",
            "mood",
            "negation",
            "stype",
            "voice",
            "wh",
        }
    )
    max_variables: int = 256
    allow_subgraph_ports: bool = False
    port_categories: frozenset[str] = frozenset(
        {"NP", "VP", "CLAUSE", "PP", "NOM", "ADJP", "ADVP"}
    )


@dataclass(frozen=True, slots=True)
class VariableBinding:
    name: str
    kind: str
    left_json: str
    right_json: str

    @property
    def left(self) -> Any:
        return json.loads(self.left_json)

    @property
    def right(self) -> Any:
        return json.loads(self.right_json)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "left": self.left,
            "right": self.right,
        }


@dataclass(frozen=True, slots=True)
class PatternNode:
    node_id: str
    kind: str
    properties_json: str

    @property
    def properties(self) -> dict[str, Any]:
        return _load_object(self.properties_json)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.node_id, "kind": self.kind, "properties": self.properties}


@dataclass(frozen=True, slots=True)
class PatternEdge:
    source: str
    target: str
    role: str
    position: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "role": self.role,
            "position": self.position,
        }


@dataclass(frozen=True, slots=True)
class ComponentTemplate:
    component_id: str
    root_id: str
    nodes: tuple[PatternNode, ...]
    edges: tuple[PatternEdge, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "root_id": self.root_id,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
        }

    def instantiate(self, bindings: Mapping[str, Any]) -> dict[str, Any]:
        """Materialize a nested structural analysis from variable bindings."""
        nodes = {node.node_id: node for node in self.nodes}
        children: dict[str, list[PatternEdge]] = {}
        for edge in self.edges:
            children.setdefault(edge.source, []).append(edge)

        def expand(node_id: str) -> dict[str, Any]:
            node = nodes[node_id]
            if node.kind == "SUBGRAPH_PORT":
                marker = node.properties.get("port")
                if not isinstance(marker, Mapping) or set(marker) != {"$var"}:
                    raise AntiUnificationError(f"invalid subgraph port: {node_id}")
                name = str(marker["$var"])
                if name not in bindings:
                    raise AntiUnificationError(f"missing binding for {name}")
                value = bindings[name]
                if not isinstance(value, Mapping):
                    raise AntiUnificationError(f"subgraph binding {name} is not an object")
                return dict(value)
            properties = _substitute(node.properties, bindings)
            ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position)
            properties["children"] = [expand(edge.target) for edge in ordered]
            return properties

        return expand(self.root_id)

    def match(self, graph: ObservationGraph, root_id: str) -> dict[str, Any] | None:
        """Match this template against another rooted constituent graph."""
        graph_nodes = {node.node_id: node for node in graph.nodes}
        if root_id not in graph_nodes:
            return None
        graph_children = _child_index(graph.edges)
        pattern_nodes = {node.node_id: node for node in self.nodes}
        pattern_children: dict[str, list[PatternEdge]] = {}
        for edge in self.edges:
            pattern_children.setdefault(edge.source, []).append(edge)
        variables: dict[str, Any] = {}
        mapped: dict[str, str] = {}

        def visit(pattern_id: str, actual_id: str) -> bool:
            previous = mapped.get(pattern_id)
            if previous is not None:
                return previous == actual_id
            mapped[pattern_id] = actual_id
            pattern_node = pattern_nodes[pattern_id]
            actual_node = graph_nodes.get(actual_id)
            if actual_node is None:
                return False
            if pattern_node.kind == "SUBGRAPH_PORT":
                props = pattern_node.properties
                if actual_node.kind != "CONSTITUENT":
                    return False
                if actual_node.properties.get("category") != props.get("accepts_category"):
                    return False
                marker = props.get("port")
                if not isinstance(marker, Mapping) or set(marker) != {"$var"}:
                    return False
                name = str(marker["$var"])
                snapshot = _root_snapshot(graph, actual_id)
                if name in variables:
                    return variables[name] == snapshot
                variables[name] = snapshot
                return True
            if actual_node.kind != pattern_node.kind:
                return False
            if not _match_value(pattern_node.properties, actual_node.properties, variables):
                return False
            expected = sorted(pattern_children.get(pattern_id, ()), key=lambda edge: edge.position)
            actual = graph_children.get(actual_id, ())
            if len(expected) != len(actual):
                return False
            for expected_edge, actual_edge in zip(expected, actual):
                if expected_edge.role != actual_edge.role or expected_edge.position != actual_edge.position:
                    return False
                if not visit(expected_edge.target, actual_edge.target):
                    return False
            return True

        return variables if visit(self.root_id, root_id) else None


@dataclass(frozen=True, slots=True)
class Alignment:
    node_mapping: tuple[tuple[str, str, str], ...]
    shared_edges: tuple[tuple[str, str, int], ...]
    residual_left: tuple[str, ...] = ()
    residual_right: tuple[str, ...] = ()
    cost: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_mapping": [
                {"left": left, "right": right, "template": template}
                for left, right, template in self.node_mapping
            ],
            "shared_edges": [
                {"source": source, "target": target, "position": position}
                for source, target, position in self.shared_edges
            ],
            "residual_left": list(self.residual_left),
            "residual_right": list(self.residual_right),
            "cost": self.cost,
        }


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    node_count: int
    edge_count: int
    variable_count: int
    residual_variable_count: int
    constant_count: int
    variable_ratio: float
    raw_description_bytes: int
    encoded_description_bytes: int
    estimated_gain_bytes: int
    trivial: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "variable_count": self.variable_count,
            "residual_variable_count": self.residual_variable_count,
            "constant_count": self.constant_count,
            "variable_ratio": self.variable_ratio,
            "raw_description_bytes": self.raw_description_bytes,
            "encoded_description_bytes": self.encoded_description_bytes,
            "estimated_gain_bytes": self.estimated_gain_bytes,
            "trivial": self.trivial,
        }


@dataclass(frozen=True, slots=True)
class ComponentCandidate:
    template: ComponentTemplate
    bindings: tuple[VariableBinding, ...]
    alignment: Alignment
    evaluation: CandidateEvaluation
    left_root_id: str
    right_root_id: str

    def bindings_for(self, side: str) -> dict[str, Any]:
        if side not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        return {
            binding.name: binding.left if side == "left" else binding.right
            for binding in self.bindings
        }

    def instantiate_left(self) -> dict[str, Any]:
        return self.template.instantiate(self.bindings_for("left"))

    def instantiate_right(self) -> dict[str, Any]:
        return self.template.instantiate(self.bindings_for("right"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "template": self.template.as_dict(),
            "bindings": [binding.as_dict() for binding in self.bindings],
            "alignment": self.alignment.as_dict(),
            "evaluation": self.evaluation.as_dict(),
            "left_root_id": self.left_root_id,
            "right_root_id": self.right_root_id,
        }


class _AntiUnifier:
    def __init__(
        self,
        left: ObservationGraph,
        right: ObservationGraph,
        policy: AlignmentPolicy,
    ) -> None:
        self.left = left
        self.right = right
        self.policy = policy
        self.left_nodes = {node.node_id: node for node in left.nodes}
        self.right_nodes = {node.node_id: node for node in right.nodes}
        self.left_children = _child_index(left.edges)
        self.right_children = _child_index(right.edges)
        self.nodes: dict[str, PatternNode] = {}
        self.edges: list[PatternEdge] = []
        self.pairs: dict[tuple[str, str], str] = {}
        self.left_mapping: dict[str, str] = {}
        self.right_mapping: dict[str, str] = {}
        self.variable_pairs: dict[str, str] = {}
        self.bindings: dict[str, VariableBinding] = {}
        self.residual_left: list[str] = []
        self.residual_right: list[str] = []

    def build(self, left_root: str, right_root: str) -> ComponentCandidate:
        root = self.align_node(left_root, right_root, allow_port=False)
        nodes = tuple(sorted(self.nodes.values(), key=lambda node: node.node_id))
        edges = tuple(
            sorted(self.edges, key=lambda edge: (edge.source, edge.position, edge.target))
        )
        template_body = {
            "root_id": root,
            "nodes": [node.as_dict() for node in nodes],
            "edges": [edge.as_dict() for edge in edges],
        }
        component_id = "component_" + sha256(_json(template_body).encode("utf-8")).hexdigest()[:24]
        template = ComponentTemplate(component_id, root, nodes, edges)
        variable_bindings = tuple(
            sorted(self.bindings.values(), key=lambda binding: int(binding.name[1:]))
        )
        mapping = tuple(
            sorted(
                (left, right, pattern)
                for (left, right), pattern in self.pairs.items()
            )
        )
        shared_edges = tuple((edge.source, edge.target, edge.position) for edge in edges)
        alignment = Alignment(
            node_mapping=mapping,
            shared_edges=shared_edges,
            residual_left=tuple(self.residual_left),
            residual_right=tuple(self.residual_right),
            cost=float(
                sum(binding.kind != "span" for binding in variable_bindings)
                + 0.1 * sum(binding.kind == "span" for binding in variable_bindings)
            ),
        )
        evaluation = _evaluate(
            template,
            variable_bindings,
            _root_snapshot(self.left, left_root),
            _root_snapshot(self.right, right_root),
        )
        return ComponentCandidate(
            template=template,
            bindings=variable_bindings,
            alignment=alignment,
            evaluation=evaluation,
            left_root_id=left_root,
            right_root_id=right_root,
        )

    def align_node(
        self,
        left_id: str,
        right_id: str,
        *,
        allow_port: bool,
    ) -> str:
        pair = (left_id, right_id)
        existing = self.pairs.get(pair)
        if existing is not None:
            return existing
        if left_id in self.left_mapping and self.left_mapping[left_id] != right_id:
            raise AntiUnificationError("left node would align with two right nodes")
        if right_id in self.right_mapping and self.right_mapping[right_id] != left_id:
            raise AntiUnificationError("right node would align with two left nodes")

        left = self.left_nodes.get(left_id)
        right = self.right_nodes.get(right_id)
        if left is None or right is None:
            raise AntiUnificationError("alignment references an unknown node")
        if left.kind != "CONSTITUENT" or right.kind != "CONSTITUENT":
            raise AntiUnificationError("POC-01 roots and children must be constituents")

        left_props = left.properties
        right_props = right.properties
        left_category = left_props.get("category")
        right_category = right_props.get("category")
        if left_category != right_category:
            raise AntiUnificationError("constituent category differs")
        self._check_protected_features(left_props, right_props)

        left_edges = self.left_children.get(left_id, ())
        right_edges = self.right_children.get(right_id, ())
        port_reason = self._port_reason(left_props, right_props, left_edges, right_edges)
        if port_reason is not None:
            if (
                allow_port
                and self.policy.allow_subgraph_ports
                and left_category in self.policy.port_categories
            ):
                return self.add_port(left_id, right_id, str(left_category))
            raise AntiUnificationError(port_reason)

        for key in self.policy.fixed_properties:
            if left_props.get(key) != right_props.get(key):
                raise AntiUnificationError(f"fixed property differs: {key}")

        template_id = f"N{len(self.pairs)}"
        self.pairs[pair] = template_id
        self.left_mapping[left_id] = right_id
        self.right_mapping[right_id] = left_id
        saved_variable_pairs = dict(self.variable_pairs)
        saved_bindings = dict(self.bindings)
        try:
            properties = self.generalize(left_props, right_props, path=())
        except AntiUnificationError as exc:
            if (
                allow_port
                and self.policy.allow_subgraph_ports
                and left_category in self.policy.port_categories
                and "protected grammatical feature" not in str(exc)
            ):
                # Undo the tentative exact mapping before replacing this pair
                # with a single opaque port.
                del self.pairs[pair]
                del self.left_mapping[left_id]
                del self.right_mapping[right_id]
                self.variable_pairs = saved_variable_pairs
                self.bindings = saved_bindings
                return self.add_port(left_id, right_id, str(left_category))
            raise
        self.nodes[template_id] = PatternNode(template_id, "CONSTITUENT", _json(properties))

        for left_edge, right_edge in zip(left_edges, right_edges):
            if left_edge.role != right_edge.role or left_edge.position != right_edge.position:
                raise AntiUnificationError("ordered child relation differs")
            child = self.align_node(
                left_edge.target,
                right_edge.target,
                allow_port=self.policy.allow_subgraph_ports,
            )
            self.edges.append(PatternEdge(template_id, child, left_edge.role, left_edge.position or 0))
        return template_id

    def _check_protected_features(
        self,
        left: Mapping[str, Any],
        right: Mapping[str, Any],
    ) -> None:
        left_features = left.get("features", {})
        right_features = right.get("features", {})
        if not isinstance(left_features, Mapping) or not isinstance(right_features, Mapping):
            return
        for key in self.policy.protected_features:
            if left_features.get(key) != right_features.get(key):
                raise AntiUnificationError(f"protected grammatical feature differs: {key}")

    def _port_reason(
        self,
        left_props: Mapping[str, Any],
        right_props: Mapping[str, Any],
        left_edges: Sequence[GraphEdge],
        right_edges: Sequence[GraphEdge],
    ) -> str | None:
        for key in self.policy.fixed_properties:
            if key == "category":
                continue
            if left_props.get(key) != right_props.get(key):
                return f"fixed property differs: {key}"
        if len(left_edges) != len(right_edges):
            return "different child arity"
        for left_edge, right_edge in zip(left_edges, right_edges):
            if left_edge.role != right_edge.role or left_edge.position != right_edge.position:
                return "ordered child relation differs"
        return None

    def add_port(self, left_id: str, right_id: str, category: str) -> str:
        pair = (left_id, right_id)
        existing = self.pairs.get(pair)
        if existing is not None:
            return existing
        if left_id in self.left_mapping and self.left_mapping[left_id] != right_id:
            raise AntiUnificationError("left node would align with two right nodes")
        if right_id in self.right_mapping and self.right_mapping[right_id] != left_id:
            raise AntiUnificationError("right node would align with two left nodes")
        template_id = f"N{len(self.pairs)}"
        self.pairs[pair] = template_id
        self.left_mapping[left_id] = right_id
        self.right_mapping[right_id] = left_id
        left_snapshot = _root_snapshot(self.left, left_id)
        right_snapshot = _root_snapshot(self.right, right_id)
        marker = self.variable(
            left_snapshot,
            right_snapshot,
            ("subgraph",),
            reuse=False,
        )
        name = str(marker["$var"])
        binding = self.bindings[name]
        self.bindings[name] = VariableBinding(
            name=name,
            kind="subgraph",
            left_json=binding.left_json,
            right_json=binding.right_json,
        )
        self.nodes[template_id] = PatternNode(
            template_id,
            "SUBGRAPH_PORT",
            _json({"port": marker, "accepts_category": category}),
        )
        self.residual_left.append(left_id)
        self.residual_right.append(right_id)
        return template_id

    def generalize(self, left: Any, right: Any, *, path: tuple[str, ...]) -> Any:
        # Character offsets are lossless instance metadata, never a learned
        # grammatical constraint.  One fresh slot per node avoids accidental
        # equality merely because two spans happen to share coordinates.
        if path and path[-1] == "span":
            return self.variable(left, right, path, reuse=False)
        if left != right and path and path[-1] in self.policy.fixed_properties:
            raise AntiUnificationError(f"fixed property differs: {path[-1]}")
        if (
            left != right
            and "features" in path
            and path
            and path[-1] in self.policy.protected_features
        ):
            raise AntiUnificationError(f"protected grammatical feature differs: {path[-1]}")
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            if set(left) != set(right):
                raise AntiUnificationError(f"object shape differs at {'.'.join(path) or '<root>'}")
            return {
                key: self.generalize(left[key], right[key], path=(*path, str(key)))
                for key in sorted(left)
            }
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                raise AntiUnificationError(f"list shape differs at {'.'.join(path) or '<root>'}")
            return [
                self.generalize(a, b, path=(*path, str(index)))
                for index, (a, b) in enumerate(zip(left, right))
            ]
        if left == right:
            return left
        return self.variable(left, right, path)

    def variable(
        self,
        left: Any,
        right: Any,
        path: tuple[str, ...],
        *,
        reuse: bool = True,
    ) -> dict[str, str]:
        pair_key = _json([left, right])
        name = self.variable_pairs.get(pair_key) if reuse else None
        if name is None:
            if len(self.bindings) >= self.policy.max_variables:
                raise AntiUnificationError("variable budget exceeded")
            name = f"V{len(self.bindings) + 1}"
            if reuse:
                self.variable_pairs[pair_key] = name
            kind = _variable_kind(path, left, right)
            self.bindings[name] = VariableBinding(name, kind, _json(left), _json(right))
        return {"$var": name}


def anti_unify(
    left: ObservationGraph,
    left_root_id: str,
    right: ObservationGraph,
    right_root_id: str,
    *,
    policy: AlignmentPolicy | None = None,
) -> ComponentCandidate:
    """Return the least general exact-shape template for two rooted DAGs."""
    return _AntiUnifier(left, right, policy or AlignmentPolicy()).build(
        left_root_id, right_root_id
    )


def anti_unify_with_ports(
    left: ObservationGraph,
    left_root_id: str,
    right: ObservationGraph,
    right_root_id: str,
    *,
    policy: AlignmentPolicy | None = None,
) -> ComponentCandidate:
    """Generalize exact shared structure and abstract mismatching child DAGs.

    Root categories/rules and protected grammatical features remain strict.
    A compatible child whose rule, arity or property shape differs can become
    one typed ``SUBGRAPH_PORT`` with lossless left/right bindings.
    """
    active = policy or AlignmentPolicy()
    if not active.allow_subgraph_ports:
        active = replace(active, allow_subgraph_ports=True)
    return _AntiUnifier(left, right, active).build(left_root_id, right_root_id)


def propose_root_generalizations(
    left: ObservationGraph,
    right: ObservationGraph,
    *,
    policy: AlignmentPolicy | None = None,
    limit: int = 20,
) -> list[ComponentCandidate]:
    """Generate ranked candidates from compatible root alternatives."""
    candidates: list[ComponentCandidate] = []
    seen: set[tuple[str, str]] = set()
    left_nodes = {node.node_id: node for node in left.nodes}
    right_nodes = {node.node_id: node for node in right.nodes}
    active_policy = policy or AlignmentPolicy()
    left_children = _child_index(left.edges)
    right_children = _child_index(right.edges)
    right_by_shape: dict[str, list[str]] = {}
    for right_root in right.root_ids:
        shape = _root_shape(
            right_root,
            right_nodes,
            right_children,
            active_policy,
        )
        right_by_shape.setdefault(shape, []).append(right_root)
    for left_root in left.root_ids:
        left_props = left_nodes[left_root].properties
        shape = _root_shape(left_root, left_nodes, left_children, active_policy)
        for right_root in right_by_shape.get(shape, ()):
            right_props = right_nodes[right_root].properties
            if _root_index_key(left_props) != _root_index_key(right_props):
                continue
            try:
                candidate = anti_unify(
                    left,
                    left_root,
                    right,
                    right_root,
                    policy=active_policy,
                )
            except AntiUnificationError:
                continue
            key = (candidate.template.component_id, _bindings_shape(candidate.bindings))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    candidates.sort(
        key=lambda candidate: (
            candidate.evaluation.trivial,
            candidate.evaluation.variable_ratio,
            -candidate.evaluation.node_count,
            candidate.template.component_id,
        )
    )
    return candidates[:limit]


def _child_index(edges: Sequence[GraphEdge]) -> dict[str, tuple[GraphEdge, ...]]:
    grouped: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        if edge.role == "CHILD":
            grouped.setdefault(edge.source, []).append(edge)
    return {
        source: tuple(sorted(rows, key=lambda edge: edge.position if edge.position is not None else -1))
        for source, rows in grouped.items()
    }


def _substitute(value: Any, bindings: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        if set(value) == {"$var"}:
            name = str(value["$var"])
            if name not in bindings:
                raise AntiUnificationError(f"missing binding for {name}")
            return bindings[name]
        return {str(key): _substitute(child, bindings) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child, bindings) for child in value]
    return value


def _match_value(pattern: Any, actual: Any, bindings: dict[str, Any]) -> bool:
    if isinstance(pattern, Mapping) and set(pattern) == {"$var"}:
        name = str(pattern["$var"])
        if name in bindings:
            return bindings[name] == actual
        bindings[name] = actual
        return True
    if isinstance(pattern, Mapping) and isinstance(actual, Mapping):
        return set(pattern) == set(actual) and all(
            _match_value(pattern[key], actual[key], bindings) for key in pattern
        )
    if isinstance(pattern, list) and isinstance(actual, list):
        return len(pattern) == len(actual) and all(
            _match_value(a, b, bindings) for a, b in zip(pattern, actual)
        )
    return pattern == actual


def _variable_kind(path: tuple[str, ...], left: Any, right: Any) -> str:
    if "span" in path:
        return "span"
    if path and path[-1] in {"lemma", "surface", "normalized"}:
        return "lexical"
    if "features" in path:
        return "feature"
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return "structure"
    return "value"


def _root_index_key(properties: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        properties.get("category"),
        properties.get("rule_id"),
        properties.get("origin"),
    )


def _root_shape(
    node_id: str,
    nodes: Mapping[str, GraphNode],
    children: Mapping[str, Sequence[GraphEdge]],
    policy: AlignmentPolicy,
) -> str:
    """Cheap invariant used to avoid the Cartesian product of parse roots."""
    memo: dict[str, int] = {}

    def value_shape(value: Any, path: tuple[str, ...]) -> Any:
        if path and path[-1] == "span":
            return "$SPAN"
        if path and path[-1] in policy.fixed_properties:
            return value
        if "features" in path and path and path[-1] in policy.protected_features:
            return value
        if isinstance(value, Mapping):
            return {
                str(key): value_shape(child, (*path, str(key)))
                for key, child in sorted(value.items())
            }
        if isinstance(value, list):
            return [value_shape(child, (*path, str(index))) for index, child in enumerate(value)]
        # Other scalar values may legitimately become variables.
        return f"${type(value).__name__}"

    def visit(current_id: str) -> Any:
        if current_id in memo:
            return {"$ref": memo[current_id]}
        node = nodes[current_id]
        memo[current_id] = len(memo)
        return {
            "kind": node.kind,
            "properties": value_shape(node.properties, ()),
            "children": [
                {
                    "role": edge.role,
                    "position": edge.position,
                    "node": visit(edge.target),
                }
                for edge in children.get(current_id, ())
            ],
        }

    return _json(visit(node_id))


def _bindings_shape(bindings: Sequence[VariableBinding]) -> str:
    return _json([(binding.kind, binding.left, binding.right) for binding in bindings])


def _root_snapshot(graph: ObservationGraph, root_id: str) -> dict[str, Any]:
    nodes = {node.node_id: node for node in graph.nodes}
    children = _child_index(graph.edges)

    def expand(node_id: str) -> dict[str, Any]:
        row = nodes[node_id].properties
        row["children"] = [expand(edge.target) for edge in children.get(node_id, ())]
        return row

    return expand(root_id)


def _count_constants(value: Any) -> int:
    if isinstance(value, Mapping):
        if set(value) == {"$var"}:
            return 0
        return sum(_count_constants(child) for child in value.values())
    if isinstance(value, list):
        return sum(_count_constants(child) for child in value)
    return 1


def _evaluate(
    template: ComponentTemplate,
    bindings: Sequence[VariableBinding],
    left_snapshot: Mapping[str, Any],
    right_snapshot: Mapping[str, Any],
) -> CandidateEvaluation:
    constant_count = sum(_count_constants(node.properties) for node in template.nodes)
    conceptual_bindings = [binding for binding in bindings if binding.kind != "span"]
    residual_bindings = [binding for binding in bindings if binding.kind == "span"]
    variable_count = len(conceptual_bindings)
    denominator = constant_count + variable_count
    raw_bytes = len(_json(left_snapshot).encode("utf-8")) + len(
        _json(right_snapshot).encode("utf-8")
    )
    encoded_bytes = len(_json(template.as_dict()).encode("utf-8")) + len(
        _json([binding.as_dict() for binding in bindings]).encode("utf-8")
    )
    # A candidate with no rule/category constants beyond the mandatory node
    # envelope is structurally legal but too weak for later promotion.
    informative_constants = sum(
        1
        for node in template.nodes
        for key, value in node.properties.items()
        if key in {"category", "rule_id"} and value is not None
    )
    return CandidateEvaluation(
        node_count=len(template.nodes),
        edge_count=len(template.edges),
        variable_count=variable_count,
        residual_variable_count=len(residual_bindings),
        constant_count=constant_count,
        variable_ratio=variable_count / denominator if denominator else 1.0,
        raw_description_bytes=raw_bytes,
        encoded_description_bytes=encoded_bytes,
        estimated_gain_bytes=raw_bytes - encoded_bytes,
        trivial=informative_constants == 0 or (denominator > 0 and variable_count / denominator > 0.8),
    )

