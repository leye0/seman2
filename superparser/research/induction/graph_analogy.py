"""POC-05: partial structural analogies with lossless residuals.

The aligner operates on the selected constituent tree exposed by POC-00.  It
uses ordered tree edit alignment: unmatched branches remain explicit side
residuals, while matched nodes are generalized without semantic labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .observation_graph import ObservationGraph
from .library import root_snapshot


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class AnalogyPolicy:
    insertion_cost: float = 1.0
    deletion_cost: float = 1.0
    substitution_cost: float = 0.25
    min_shared_edges: int = 1
    min_coverage: float = 0.25
    protected_features: frozenset[str] = frozenset(
        {"case", "inversion", "modal", "mood", "negation", "stype", "voice", "wh"}
    )


@dataclass(frozen=True, slots=True)
class StructuralAnalogy:
    analogy_id: str
    left_root_id: str
    right_root_id: str
    pattern_json: str
    left_bindings_json: str
    right_bindings_json: str
    edit_cost: float
    matched_nodes: int
    matched_edges: int
    left_residual_nodes: int
    right_residual_nodes: int
    coverage: float

    @property
    def pattern(self) -> dict[str, Any]:
        value = json.loads(self.pattern_json)
        assert isinstance(value, dict)
        return value

    def bindings_for(self, side: str) -> dict[str, Any]:
        if side not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        value = json.loads(
            self.left_bindings_json if side == "left" else self.right_bindings_json
        )
        assert isinstance(value, dict)
        return value

    def instantiate(self, side: str) -> dict[str, Any]:
        bindings = self.bindings_for(side)

        def expand(node: Mapping[str, Any]) -> dict[str, Any]:
            properties = _substitute(node["properties"], bindings)
            children: list[tuple[int, dict[str, Any]]] = []
            for operation in node.get("children", ()):
                kind = operation["kind"]
                if kind == "MATCH":
                    children.append((int(operation[f"{side}_position"]), expand(operation["node"])))
                elif kind == "LEFT_ONLY" and side == "left":
                    children.append((int(operation["left_position"]), dict(operation["snapshot"])))
                elif kind == "RIGHT_ONLY" and side == "right":
                    children.append((int(operation["right_position"]), dict(operation["snapshot"])))
            properties["children"] = [child for _, child in sorted(children)]
            return properties

        return expand(self.pattern)

    def as_dict(self) -> dict[str, Any]:
        return {
            "analogy_id": self.analogy_id,
            "left_root_id": self.left_root_id,
            "right_root_id": self.right_root_id,
            "pattern": self.pattern,
            "left_bindings": self.bindings_for("left"),
            "right_bindings": self.bindings_for("right"),
            "edit_cost": self.edit_cost,
            "matched_nodes": self.matched_nodes,
            "matched_edges": self.matched_edges,
            "left_residual_nodes": self.left_residual_nodes,
            "right_residual_nodes": self.right_residual_nodes,
            "coverage": self.coverage,
        }


@dataclass(frozen=True, slots=True)
class _Plan:
    left: Mapping[str, Any]
    right: Mapping[str, Any]
    operations: tuple[tuple[str, int | None, int | None, "_Plan | Mapping[str, Any]"], ...]
    cost: float
    matched_nodes: int
    matched_edges: int
    left_residual_nodes: int
    right_residual_nodes: int


class _Generalizer:
    def __init__(self) -> None:
        self.pairs: dict[str, str] = {}
        self.left: dict[str, Any] = {}
        self.right: dict[str, Any] = {}

    def generalize(self, left: Any, right: Any) -> Any:
        if isinstance(left, Mapping) and isinstance(right, Mapping) and set(left) == set(right):
            return {str(key): self.generalize(left[key], right[key]) for key in sorted(left)}
        if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
            return [self.generalize(a, b) for a, b in zip(left, right)]
        if left == right:
            return left
        key = _json([left, right])
        name = self.pairs.get(key)
        if name is None:
            name = f"A{len(self.pairs) + 1}"
            self.pairs[key] = name
            self.left[name] = left
            self.right[name] = right
        return {"$var": name}


def align_partial(
    left: ObservationGraph,
    left_root_id: str,
    right: ObservationGraph,
    right_root_id: str,
    *,
    policy: AnalogyPolicy | None = None,
) -> StructuralAnalogy | None:
    """Find the least-cost ordered partial alignment of two constituent trees."""
    active = policy or AnalogyPolicy()
    left_tree = root_snapshot(left, left_root_id)
    right_tree = root_snapshot(right, right_root_id)
    plan = _align(left_tree, right_tree, active)
    if plan is None or plan.matched_edges < active.min_shared_edges:
        return None
    total = max(_node_count(left_tree), _node_count(right_tree))
    coverage = plan.matched_nodes / total
    if coverage < active.min_coverage:
        return None
    generalizer = _Generalizer()

    def materialize(current: _Plan) -> dict[str, Any]:
        left_props = {key: value for key, value in current.left.items() if key != "children"}
        right_props = {key: value for key, value in current.right.items() if key != "children"}
        children = []
        for kind, left_position, right_position, payload in current.operations:
            if kind == "MATCH":
                assert isinstance(payload, _Plan)
                children.append(
                    {
                        "kind": kind,
                        "left_position": left_position,
                        "right_position": right_position,
                        "node": materialize(payload),
                    }
                )
            else:
                children.append(
                    {
                        "kind": kind,
                        f"{'left' if kind == 'LEFT_ONLY' else 'right'}_position": (
                            left_position if kind == "LEFT_ONLY" else right_position
                        ),
                        "snapshot": payload,
                    }
                )
        return {
            "properties": generalizer.generalize(left_props, right_props),
            "children": children,
        }

    pattern = materialize(plan)
    body = {
        "left_root_id": left_root_id,
        "right_root_id": right_root_id,
        "pattern": pattern,
        "left_bindings": generalizer.left,
        "right_bindings": generalizer.right,
    }
    analogy_id = "analogy_" + sha256(_json(body).encode("utf-8")).hexdigest()[:24]
    return StructuralAnalogy(
        analogy_id,
        left_root_id,
        right_root_id,
        _json(pattern),
        _json(generalizer.left),
        _json(generalizer.right),
        plan.cost,
        plan.matched_nodes,
        plan.matched_edges,
        plan.left_residual_nodes,
        plan.right_residual_nodes,
        coverage,
    )


def propose_partial_analogies(
    left: ObservationGraph,
    right: ObservationGraph,
    *,
    policy: AnalogyPolicy | None = None,
    limit: int = 20,
) -> list[StructuralAnalogy]:
    """Compare compatible constituent boundaries and rank systematic matches."""
    active = policy or AnalogyPolicy()
    left_nodes = [node for node in left.nodes if node.kind == "CONSTITUENT"]
    right_nodes = [node for node in right.nodes if node.kind == "CONSTITUENT"]
    candidates: dict[str, StructuralAnalogy] = {}
    for left_node in left_nodes:
        for right_node in right_nodes:
            if left_node.properties.get("category") != right_node.properties.get("category"):
                continue
            candidate = align_partial(
                left,
                left_node.node_id,
                right,
                right_node.node_id,
                policy=active,
            )
            if candidate is not None:
                candidates[candidate.analogy_id] = candidate
    return sorted(
        candidates.values(),
        key=lambda row: (
            -row.matched_edges,
            -row.coverage,
            row.edit_cost,
            row.left_residual_nodes + row.right_residual_nodes,
            row.analogy_id,
        ),
    )[:limit]


def _align(left: Mapping[str, Any], right: Mapping[str, Any], policy: AnalogyPolicy) -> _Plan | None:
    if left.get("category") != right.get("category"):
        return None
    if left.get("origin") != right.get("origin"):
        return None
    left_features = left.get("features", {})
    right_features = right.get("features", {})
    for feature in policy.protected_features:
        if left_features.get(feature) != right_features.get(feature):
            return None

    left_children = list(left.get("children", ()))
    right_children = list(right.get("children", ()))
    rows = len(left_children) + 1
    columns = len(right_children) + 1
    dp: list[list[tuple[float, tuple[Any, ...]]]] = [
        [(float("inf"), ()) for _ in range(columns)] for _ in range(rows)
    ]
    dp[0][0] = (0.0, ())
    for i in range(1, rows):
        child = left_children[i - 1]
        cost = policy.deletion_cost * _node_count(child)
        dp[i][0] = (dp[i - 1][0][0] + cost, (*dp[i - 1][0][1], ("LEFT_ONLY", i - 1, None, child)))
    for j in range(1, columns):
        child = right_children[j - 1]
        cost = policy.insertion_cost * _node_count(child)
        dp[0][j] = (dp[0][j - 1][0] + cost, (*dp[0][j - 1][1], ("RIGHT_ONLY", None, j - 1, child)))
    for i in range(1, rows):
        for j in range(1, columns):
            left_child = left_children[i - 1]
            right_child = right_children[j - 1]
            choices = [
                (
                    dp[i - 1][j][0] + policy.deletion_cost * _node_count(left_child),
                    (*dp[i - 1][j][1], ("LEFT_ONLY", i - 1, None, left_child)),
                ),
                (
                    dp[i][j - 1][0] + policy.insertion_cost * _node_count(right_child),
                    (*dp[i][j - 1][1], ("RIGHT_ONLY", None, j - 1, right_child)),
                ),
            ]
            nested = _align(left_child, right_child, policy)
            if nested is not None:
                choices.append(
                    (
                        dp[i - 1][j - 1][0] + nested.cost,
                        (*dp[i - 1][j - 1][1], ("MATCH", i - 1, j - 1, nested)),
                    )
                )
            dp[i][j] = min(choices, key=lambda row: (row[0], _operation_key(row[1])))

    operations = dp[-1][-1][1]
    nested_plans = [operation[3] for operation in operations if operation[0] == "MATCH"]
    property_cost = policy.substitution_cost * _difference_count(
        {key: value for key, value in left.items() if key != "children"},
        {key: value for key, value in right.items() if key != "children"},
    )
    return _Plan(
        left,
        right,
        operations,
        dp[-1][-1][0] + property_cost,
        1 + sum(plan.matched_nodes for plan in nested_plans),
        len(nested_plans) + sum(plan.matched_edges for plan in nested_plans),
        sum(
            _node_count(operation[3]) if operation[0] == "LEFT_ONLY" else 0
            for operation in operations
        ) + sum(plan.left_residual_nodes for plan in nested_plans),
        sum(
            _node_count(operation[3]) if operation[0] == "RIGHT_ONLY" else 0
            for operation in operations
        ) + sum(plan.right_residual_nodes for plan in nested_plans),
    )


def _node_count(snapshot: Mapping[str, Any]) -> int:
    return 1 + sum(_node_count(child) for child in snapshot.get("children", ()))


def _difference_count(left: Any, right: Any) -> int:
    if left == right:
        return 0
    if isinstance(left, Mapping) and isinstance(right, Mapping) and set(left) == set(right):
        return sum(_difference_count(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return sum(_difference_count(a, b) for a, b in zip(left, right))
    return 1


def _operation_key(operations: Sequence[tuple[Any, ...]]) -> str:
    return "|".join(str(operation[0]) for operation in operations)


def _substitute(value: Any, bindings: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        if set(value) == {"$var"}:
            return bindings[str(value["$var"])]
        return {str(key): _substitute(child, bindings) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child, bindings) for child in value]
    return value
