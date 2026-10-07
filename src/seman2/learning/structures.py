"""Generic graph canonicalization and structural-fragment extraction."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Sequence

from ..evidence.model import EvidenceUnit
from ..evidence.store import canonical_json
from ..interpretation.model import Projection, ProjectionNode


def digest(kind: str, value: Any, *, length: int = 32) -> str:
    material = canonical_json(value).encode("utf-8")
    return f"{kind}_" + hashlib.sha256(material).hexdigest()[:length]


def shape(value: Any) -> Any:
    """Erase values but retain recursively observable topology and field names."""
    if isinstance(value, Mapping):
        return {str(key): shape(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [shape(item) for item in value]
    if value is None:
        return None
    if isinstance(value, bool):
        return {"atom_type": "boolean"}
    if isinstance(value, (int, float)):
        return {"atom_type": "number"}
    return {"atom_type": "symbol"}


def projection_fingerprint(projection: Projection) -> str:
    node_categories = sorted(node.category for node in projection.nodes)
    relations = sorted(edge.relation for edge in projection.edges)
    topology = {
        "family": projection.family,
        "node_categories": node_categories,
        "relations": relations,
        "roots": len(projection.roots),
    }
    return hashlib.sha256(canonical_json(topology).encode()).hexdigest()


def exact_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def observable_context(
    evidence: EvidenceUnit,
    *,
    context_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Create unlabeled observable dimensions; no pragmatic category is inferred."""
    text = evidence.raw
    return {
        "stream_id": evidence.stream_id,
        "sequence": evidence.sequence,
        "kind": evidence.kind,
        "source": dict(evidence.source),
        "declared_context": dict(evidence.context),
        "metadata": dict(evidence.metadata),
        "prior_evidence_ids": list(context_ids),
        "surface_measurements": {
            "unicode_length": len(text),
            "line_count": text.count("\n") + 1,
            "whitespace_runs": sum(
                1
                for index, char in enumerate(text)
                if char.isspace() and (index == 0 or not text[index - 1].isspace())
            ),
            "punctuation_codepoints": [
                {"offset": index, "value": char}
                for index, char in enumerate(text)
                if not char.isalnum() and not char.isspace()
            ],
        },
    }


def _edge_position(attributes: Mapping[str, Any]) -> int:
    try:
        return int(attributes.get("position", 0))
    except (TypeError, ValueError):
        return 0


def structural_fragments(
    projection: Projection,
    *,
    max_depth: int = 5,
    include_lexicalized: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Enumerate rooted DOP-style subtrees at every observed granularity."""
    if max_depth < 1:
        raise ValueError("fragment depth must be positive")
    node_by_id = {node.node_id: node for node in projection.nodes}
    children: dict[str, list[tuple[int, str, str]]] = {}
    for edge in projection.edges:
        if edge.relation == "contains":
            children.setdefault(edge.source_id, []).append(
                (_edge_position(edge.attributes), edge.target_id, edge.relation)
            )
    for rows in children.values():
        rows.sort()

    def encode(node_id: str, depth: int, lexicalized: bool) -> dict[str, Any]:
        node = node_by_id[node_id]
        attributes: dict[str, Any] = {
            "category": node.category,
            "native_category": node.attributes.get("native_category"),
        }
        if lexicalized:
            for key in ("native_word", "surface"):
                if key in node.attributes:
                    attributes[key] = node.attributes[key]
        rows = children.get(node_id, [])
        if depth <= 1 and rows:
            return {**attributes, "frontier": len(rows)}
        return {
            **attributes,
            "children": [
                {"relation": relation, "node": encode(target, depth - 1, lexicalized)}
                for _, target, relation in rows
                if target in node_by_id
            ],
        }

    fragments: list[dict[str, Any]] = []
    tree_nodes = [node for node in projection.nodes if node.category == "tree-node"]
    for node in tree_nodes:
        for depth in range(1, max_depth + 1):
            generalized = encode(node.node_id, depth, False)
            fragments.append(
                {
                    "root_node_id": node.node_id,
                    "depth": depth,
                    "lexicalized": False,
                    "tree": generalized,
                    "fingerprint": exact_fingerprint(generalized),
                }
            )
            if include_lexicalized:
                lexical = encode(node.node_id, depth, True)
                fragments.append(
                    {
                        "root_node_id": node.node_id,
                        "depth": depth,
                        "lexicalized": True,
                        "tree": lexical,
                        "fingerprint": exact_fingerprint(lexical),
                    }
                )
            if not children.get(node.node_id):
                break
    unique = {canonical_json(row): row for row in fragments}
    return tuple(unique[key] for key in sorted(unique))


def linearized_words(projection: Projection) -> tuple[str, ...]:
    rows: list[tuple[int, str]] = []
    for node in projection.nodes:
        if node.category != "parser-word":
            continue
        try:
            position = int(node.attributes.get("position", len(rows)))
        except (TypeError, ValueError):
            position = len(rows)
        surface = node.attributes.get("surface")
        if not isinstance(surface, str):
            surface = str(node.attributes.get("value", ""))
        rows.append((position, surface))
    return tuple(value for _, value in sorted(rows) if value)


def discodop_tree(projection: Projection) -> tuple[str, tuple[str, ...]] | None:
    """Convert a native structural projection to indexed disco-dop input."""
    nodes = {node.node_id: node for node in projection.nodes}
    children: dict[str, list[tuple[int, str]]] = {}
    token_for_leaf: dict[str, int] = {}
    for edge in projection.edges:
        if edge.relation == "contains":
            children.setdefault(edge.source_id, []).append(
                (_edge_position(edge.attributes), edge.target_id)
            )
        elif edge.relation == "realizes-token":
            try:
                token_for_leaf[edge.source_id] = int(edge.attributes.get("position", 0))
            except (TypeError, ValueError):
                pass
    for rows in children.values():
        rows.sort()

    def label(node_id: str) -> str:
        node = nodes[node_id]
        raw = node.attributes.get("native_category", node.category)
        return str(raw).replace("(", "[").replace(")", "]").replace(" ", "_")

    def walk(node_id: str) -> str:
        rows = children.get(node_id, [])
        if not rows:
            token = token_for_leaf.get(node_id)
            if token is None:
                return f"({label(node_id)} )"
            return f"({label(node_id)} {token})"
        return f"({label(node_id)} {' '.join(walk(target) for _, target in rows)})"

    roots = [root for root in projection.roots if root in nodes]
    if not roots:
        return None
    tree = walk(roots[0]) if len(roots) == 1 else f"(ROOT {' '.join(walk(root) for root in roots)})"
    return tree, linearized_words(projection)


def projection_node_payload(node: ProjectionNode) -> dict[str, Any]:
    return {
        "category": node.category,
        "attributes": dict(node.attributes),
        "span": node.span.as_dict() if node.span else None,
        "native_path": node.native_path,
    }
