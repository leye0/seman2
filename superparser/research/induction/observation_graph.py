"""POC-00: compact structural projection of one selected parser analysis.

The parser currently produces both grammatical structure and imported
lexical semantics.  Induction must not see the latter.  This module therefore
implements a strict allow-list projection:

* source text, character spans and token order;
* opaque lexical anchors and grammatical categories/features;
* one selected rule tree with ordered children;
* completion status and parser/projection versions.

Semantic graphs, semantic types, WordNet sense ids/glosses, role handles,
scores and runtime bindings are intentionally absent. The packed forest and
competing roots are deliberately not serialized. Source text and parser
version remain sufficient to request a later reparse.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

from seman_parser.chart import ChartItem, ParseResult
from seman_parser.discourse import Mention
from seman_parser.reference import ReferenceLink
SCHEMA_VERSION = "poc00-observation-graph/0.2"
PROJECTION_POLICY = "selected-structure-allowlist/0.2"

# These fields are present in the parser output but forbidden in the
# induction projection.  Validation guards future adapter changes too.
FORBIDDEN_PROPERTY_KEYS = frozenset(
    {
        "bindings",
        "gloss",
        "handles",
        "lex_file",
        "offset",
        "semantic",
        "semantic_role",
        "semantic_type",
        "sense_id",
        "type_name",
    }
)


class ObservationGraphError(ValueError):
    """Raised when an observation graph violates the POC-00 contract."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _object(value: Mapping[str, Any]) -> str:
    """Freeze a JSON object as canonical text."""
    return _canonical_json(dict(value))


def _load_object(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ObservationGraphError("node/edge properties must be a JSON object")
    return loaded


def _content_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


@dataclass(frozen=True, slots=True)
class GraphNode:
    """Immutable, content-addressed node."""

    node_id: str
    kind: str
    properties_json: str = "{}"

    @classmethod
    def build(cls, *, kind: str, properties: Mapping[str, Any]) -> "GraphNode":
        body = {"kind": kind, "properties": dict(properties)}
        return cls(
            node_id=_content_id(kind.lower().replace("_", "-"), body),
            kind=kind,
            properties_json=_object(properties),
        )

    @property
    def properties(self) -> dict[str, Any]:
        return _load_object(self.properties_json)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.node_id, "kind": self.kind, "properties": self.properties}

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "GraphNode":
        return cls(
            node_id=str(row["id"]),
            kind=str(row["kind"]),
            properties_json=_object(_require_mapping(row.get("properties", {}), "node properties")),
        )


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Directed edge; ``position`` makes ordered relations explicit."""

    source: str
    target: str
    role: str
    position: int | None = None
    properties_json: str = "{}"

    @classmethod
    def build(
        cls,
        *,
        source: str,
        target: str,
        role: str,
        position: int | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> "GraphEdge":
        return cls(source, target, role, position, _object(properties or {}))

    @property
    def properties(self) -> dict[str, Any]:
        return _load_object(self.properties_json)

    def as_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "source": self.source,
            "target": self.target,
            "role": self.role,
        }
        if self.position is not None:
            row["position"] = self.position
        if self.properties:
            row["properties"] = self.properties
        return row

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "GraphEdge":
        position = row.get("position")
        return cls.build(
            source=str(row["source"]),
            target=str(row["target"]),
            role=str(row["role"]),
            position=None if position is None else int(position),
            properties=_require_mapping(row.get("properties", {}), "edge properties"),
        )


@dataclass(frozen=True, slots=True)
class ObservationGraph:
    """Canonical structural observation consumed by later induction POCs."""

    observation_id: str
    text: str
    completed: bool
    parser_version: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    root_ids: tuple[str, ...]
    forest_ids: tuple[str, ...]
    selection_policy: str
    selection_provisional: bool
    schema_version: str = SCHEMA_VERSION
    projection_policy: str = PROJECTION_POLICY

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_policy": self.projection_policy,
            "observation_id": self.observation_id,
            "text": self.text,
            "completed": self.completed,
            "parser_version": self.parser_version,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
            "root_ids": list(self.root_ids),
            "forest_ids": list(self.forest_ids),
            "selection_policy": self.selection_policy,
            "selection_provisional": self.selection_provisional,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.as_dict())

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "ObservationGraph":
        graph = cls(
            schema_version=str(row["schema_version"]),
            projection_policy=str(row["projection_policy"]),
            observation_id=str(row["observation_id"]),
            text=str(row["text"]),
            completed=bool(row["completed"]),
            parser_version=str(row["parser_version"]),
            nodes=tuple(GraphNode.from_dict(node) for node in row.get("nodes", ())),
            edges=tuple(GraphEdge.from_dict(edge) for edge in row.get("edges", ())),
            root_ids=tuple(str(node_id) for node_id in row.get("root_ids", ())),
            forest_ids=tuple(str(node_id) for node_id in row.get("forest_ids", ())),
            selection_policy=str(row["selection_policy"]),
            selection_provisional=bool(row["selection_provisional"]),
        )
        graph.validate()
        return graph

    @classmethod
    def from_json(cls, payload: str) -> "ObservationGraph":
        row = json.loads(payload)
        if not isinstance(row, dict):
            raise ObservationGraphError("observation payload must be a JSON object")
        return cls.from_dict(row)

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ObservationGraphError(f"unsupported schema version: {self.schema_version}")
        if self.projection_policy != PROJECTION_POLICY:
            raise ObservationGraphError(f"unsupported projection policy: {self.projection_policy}")
        if len(self.root_ids) > 1:
            raise ObservationGraphError("compact observation may contain at most one root")
        if self.forest_ids:
            raise ObservationGraphError("compact observation must not contain a parse forest")

        by_id = {node.node_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ObservationGraphError("duplicate node id")
        for node in self.nodes:
            _reject_forbidden_keys(node.properties, where=node.node_id)
        for edge in self.edges:
            if edge.source not in by_id or edge.target not in by_id:
                raise ObservationGraphError(f"dangling edge: {edge.source} -> {edge.target}")
            _reject_forbidden_keys(edge.properties, where=f"edge {edge.role}")
        for node_id in (*self.root_ids, *self.forest_ids):
            if node_id not in by_id:
                raise ObservationGraphError(f"unknown analysis node: {node_id}")
            if by_id[node_id].kind != "CONSTITUENT":
                raise ObservationGraphError(f"analysis id is not a constituent: {node_id}")

        child_edges: dict[str, list[GraphEdge]] = {}
        for edge in self.edges:
            if edge.role == "CHILD":
                child_edges.setdefault(edge.source, []).append(edge)
        for source, edges in child_edges.items():
            positions = sorted(edge.position for edge in edges if edge.position is not None)
            if len(positions) != len(edges) or positions != list(range(len(edges))):
                raise ObservationGraphError(f"non-contiguous child order on {source}")
        _assert_acyclic(child_edges)

        token_nodes = sorted(
            (node for node in self.nodes if node.kind == "TOKEN"),
            key=lambda node: int(node.properties["index"]),
        )
        for expected, node in enumerate(token_nodes):
            props = node.properties
            if props["index"] != expected:
                raise ObservationGraphError("token indexes must be contiguous")
            start, end = props["span"]
            if self.text[start:end] != props["text"]:
                raise ObservationGraphError(f"token span/text mismatch on {node.node_id}")

        expected_id = _observation_id(self._identity_payload())
        if self.observation_id != expected_id:
            raise ObservationGraphError("observation id does not match canonical content")

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_policy": self.projection_policy,
            "text": self.text,
            "completed": self.completed,
            "parser_version": self.parser_version,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
            "root_ids": list(self.root_ids),
            "forest_ids": list(self.forest_ids),
            "selection_policy": self.selection_policy,
            "selection_provisional": self.selection_provisional,
        }

    def structural_snapshot(self) -> dict[str, Any]:
        """Reconstruct the allow-listed parser information from the graph."""
        by_id = {node.node_id: node for node in self.nodes}
        children: dict[str, list[GraphEdge]] = {}
        for edge in self.edges:
            if edge.role == "CHILD":
                children.setdefault(edge.source, []).append(edge)

        def expand(node_id: str) -> dict[str, Any]:
            node = by_id[node_id]
            row = node.properties
            ordered = sorted(children.get(node_id, ()), key=lambda edge: edge.position or 0)
            row["children"] = [expand(edge.target) for edge in ordered]
            return row

        tokens = sorted(
            (node.properties for node in self.nodes if node.kind == "TOKEN"),
            key=lambda row: row["index"],
        )
        root_analyses = [expand(node_id) for node_id in self.root_ids]
        return {
            "text": self.text,
            "completed": self.completed,
            "selection_policy": self.selection_policy,
            "selection_provisional": self.selection_provisional,
            "tokens": tokens,
            "lexical_candidates": [],
            "root_analyses": sorted(root_analyses, key=_canonical_json),
            "forest_analyses": [],
        }


class _Builder:
    def __init__(
        self,
        result: ParseResult,
        parser_version: str,
        mentions: Sequence[Mention],
        reference_links: Sequence[ReferenceLink],
        mention_catalog: Mapping[str, Mention],
    ) -> None:
        self.result = result
        self.parser_version = parser_version
        self.mentions = mentions
        self.reference_links = reference_links
        self.mention_catalog = mention_catalog
        self.nodes: dict[str, GraphNode] = {}
        self.edges: set[GraphEdge] = set()
        self._items: dict[int, str] = {}
        self._mention_ids: dict[str, str] = {}

    def add_node(self, kind: str, properties: Mapping[str, Any]) -> str:
        node = GraphNode.build(kind=kind, properties=properties)
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ObservationGraphError(f"content-id collision: {node.node_id}")
        self.nodes[node.node_id] = node
        return node.node_id

    def build(self) -> ObservationGraph:
        token_ids: list[str] = []
        for token in self.result.lattice.tokens:
            token_ids.append(
                self.add_node(
                    "TOKEN",
                    {
                        "index": token.index,
                        "span": [token.start, token.end],
                        "text": token.text,
                    },
                )
            )
        for left, right in zip(token_ids, token_ids[1:]):
            self.edges.add(GraphEdge.build(source=left, target=right, role="NEXT_TOKEN"))

        selected, selection_policy, provisional = _select_analysis(self.result)
        root_ids = () if selected is None else (self.add_item(selected, token_ids),)
        self.add_references()

        nodes = tuple(sorted(self.nodes.values(), key=lambda node: node.node_id))
        edges = tuple(sorted(self.edges, key=_edge_sort_key))
        roots = tuple(root_ids)
        forest: tuple[str, ...] = ()
        identity = {
            "schema_version": SCHEMA_VERSION,
            "projection_policy": PROJECTION_POLICY,
            "text": self.result.text,
            "completed": self.result.completed,
            "parser_version": self.parser_version,
            "nodes": [node.as_dict() for node in nodes],
            "edges": [edge.as_dict() for edge in edges],
            "root_ids": list(roots),
            "forest_ids": list(forest),
            "selection_policy": selection_policy,
            "selection_provisional": provisional,
        }
        graph = ObservationGraph(
            observation_id=_observation_id(identity),
            text=self.result.text,
            completed=self.result.completed,
            parser_version=self.parser_version,
            nodes=nodes,
            edges=edges,
            root_ids=roots,
            forest_ids=forest,
            selection_policy=selection_policy,
            selection_provisional=provisional,
        )
        graph.validate()
        return graph

    def add_references(self) -> None:
        """Add structural mentions and qualified reference candidates.

        Runtime mention ids are used only to wire the input.  They never enter
        node properties or content ids, so renaming them cannot change the
        serialized observation.
        """
        relevant: dict[str, Mention] = dict(self.mention_catalog)
        relevant.update((mention.mention_id, mention) for mention in self.mentions)

        referenced_ids = {
            mention_id
            for link in self.reference_links
            for mention_id in (link.source, link.target)
            if mention_id is not None and mention_id in relevant
        }
        referenced_ids.update(mention.mention_id for mention in self.mentions)
        for mention_id in sorted(referenced_ids):
            self._mention_ids[mention_id] = self.add_node(
                "MENTION", _mention_properties(relevant[mention_id])
            )

        constituent_nodes = [node for node in self.nodes.values() if node.kind == "CONSTITUENT"]
        for mention in self.mentions:
            mention_node = self._mention_ids[mention.mention_id]
            for constituent in constituent_nodes:
                props = constituent.properties
                if props.get("span") == list(mention.span) and props.get("category") == "NP":
                    self.edges.add(
                        GraphEdge.build(
                            source=mention_node,
                            target=constituent.node_id,
                            role="REALIZED_BY",
                        )
                    )

        unresolved_id: str | None = None
        for link in self.reference_links:
            source = self._mention_ids.get(link.source)
            if source is None:
                raise ObservationGraphError(f"reference source has no mention: {link.source}")
            target = self._mention_ids.get(link.target or "")
            if target is None:
                if unresolved_id is None:
                    unresolved_id = self.add_node(
                        "REFERENCE_ANCHOR", {"status": "unresolved_or_external"}
                    )
                target = unresolved_id
            self.edges.add(
                GraphEdge.build(
                    source=source,
                    target=target,
                    role="REFERENCE",
                    properties={
                        "kind": link.kind.value,
                        "rule_id": link.rule_id,
                    },
                )
            )

    def add_item(self, item: ChartItem, token_ids: Sequence[str]) -> str:
        cached = self._items.get(id(item))
        if cached is not None:
            return cached

        child_ids = [self.add_item(child, token_ids) for child in item.children]
        props = _item_properties(item)
        identity = {"kind": "CONSTITUENT", "properties": props, "children": child_ids}
        node_id = _content_id("constituent", identity)
        node = GraphNode(node_id=node_id, kind="CONSTITUENT", properties_json=_object(props))
        existing = self.nodes.get(node_id)
        if existing is not None and existing != node:
            raise ObservationGraphError(f"content-id collision: {node_id}")
        self.nodes[node_id] = node
        self._items[id(item)] = node_id

        for position, child_id in enumerate(child_ids):
            self.edges.add(
                GraphEdge.build(source=node_id, target=child_id, role="CHILD", position=position)
            )
        if not child_ids:
            start, end = props["span"]
            for token, token_id in zip(self.result.lattice.tokens, token_ids):
                if start <= token.start and token.end <= end:
                    self.edges.add(
                        GraphEdge.build(
                            source=node_id,
                            target=token_id,
                            role="REALIZES_TOKEN",
                            position=token.index,
                        )
                    )
        return node_id


def parse_to_observation(
    result: ParseResult,
    *,
    parser_version: str = "unknown",
    mentions: Iterable[Mention] = (),
    reference_links: Iterable[ReferenceLink] = (),
    mention_catalog: Mapping[str, Mention] | None = None,
) -> ObservationGraph:
    """Project one parser result into the non-semantic POC-00 graph.

    ``mention_catalog`` supplies antecedents from prior sentences when a
    reference link crosses the sentence boundary.  Semantic mention types,
    semantic node ids, confidence scores and link evidence are not copied.
    """
    mention_rows = tuple(mentions)
    link_rows = tuple(reference_links)
    catalog = dict(mention_catalog or {})
    return _Builder(result, parser_version, mention_rows, link_rows, catalog).build()


def structural_snapshot_from_parse(result: ParseResult) -> dict[str, Any]:
    """Independent allow-list view used to verify graph reconstruction.

    This walks the parser objects directly rather than traversing graph edges.
    Equality with :meth:`ObservationGraph.structural_snapshot` therefore tests
    that graph construction and reconstruction preserved the selected parse
    topology.
    """
    def expand(item: ChartItem) -> dict[str, Any]:
        row = _item_properties(item)
        row["children"] = [expand(child) for child in item.children]
        return row

    selected, selection_policy, provisional = _select_analysis(result)

    return {
        "text": result.text,
        "completed": result.completed,
        "selection_policy": selection_policy,
        "selection_provisional": provisional,
        "tokens": [
            {
                "index": token.index,
                "span": [token.start, token.end],
                "text": token.text,
            }
            for token in result.lattice.tokens
        ],
        "lexical_candidates": [],
        "root_analyses": [] if selected is None else [expand(selected)],
        "forest_analyses": [],
    }


def _select_analysis(result: ParseResult) -> tuple[ChartItem | None, str, bool]:
    """Use the parser's final choice, or a deterministic structural fallback."""
    selected = result.best()
    if selected is not None:
        return selected, "parser_best", False
    candidates = {
        id(item): item
        for packed in result.packed.values()
        for item in packed.alternatives
    }
    if not candidates:
        return None, "no_analysis", True

    def key(item: ChartItem) -> tuple[Any, ...]:
        full_span = item.start == 0 and item.end == len(result.text)
        shape = _canonical_json(_item_tree(item))
        return (
            -int(full_span),
            -(item.end - item.start),
            item.start,
            item.end,
            item.category,
            item.rule_id or "",
            shape,
        )

    return min(candidates.values(), key=key), "structural_fallback", True


def _item_tree(item: ChartItem) -> dict[str, Any]:
    row = _item_properties(item)
    row["children"] = [_item_tree(child) for child in item.children]
    return row


def _item_properties(item: ChartItem) -> dict[str, Any]:
    props: dict[str, Any] = {
        "span": [item.start, item.end],
        "category": item.category,
        "features": _structural_features(item.features.as_dict()),
        "rule_id": item.rule_id,
        "origin": item.provenance.source,
    }
    if not item.children:
        detail = item.provenance.detail
        # Surface and lemma are explicit lexical anchors.  sense_id and the
        # rest of lexical provenance are deliberately not copied.
        if isinstance(detail.get("surface"), str):
            props["surface"] = detail["surface"]
        if isinstance(detail.get("lemma"), str):
            props["lemma"] = detail["lemma"]
    return props


def _mention_properties(mention: Mention) -> dict[str, Any]:
    return {
        "surface": mention.surface,
        "span": list(mention.span),
        "kind": mention.kind,
        "sentence": mention.sentence_index,
        "features": _structural_features(mention.features.as_dict()),
        "head_lemma": mention.head_lemma,
    }


def _edge_sort_key(edge: GraphEdge) -> tuple[Any, ...]:
    return (
        edge.source,
        edge.role,
        -1 if edge.position is None else edge.position,
        edge.target,
        edge.properties_json,
    )


def _observation_id(identity: Mapping[str, Any]) -> str:
    return _content_id("observation", identity)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationGraphError(f"{label} must be an object")
    return value


def _structural_features(features: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively retain feature structure while removing forbidden keys.

    Grammar constraints can copy lexical fields into nested feature
    structures.  Filtering only the top level would therefore allow imported
    semantics back into the observation through unification.
    """
    return {
        str(key): _strip_forbidden_feature_values(value)
        for key, value in features.items()
        if str(key) not in FORBIDDEN_PROPERTY_KEYS
    }


def _strip_forbidden_feature_values(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _structural_features(value)
    if isinstance(value, list | tuple):
        return [_strip_forbidden_feature_values(child) for child in value]
    return value


def _reject_forbidden_keys(value: Any, *, where: str) -> None:
    if isinstance(value, Mapping):
        forbidden = FORBIDDEN_PROPERTY_KEYS.intersection(str(key) for key in value)
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise ObservationGraphError(f"forbidden semantic fields on {where}: {names}")
        for child in value.values():
            _reject_forbidden_keys(child, where=where)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            _reject_forbidden_keys(child, where=where)


def _assert_acyclic(children: Mapping[str, Iterable[GraphEdge]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ObservationGraphError(f"cycle in constituent children at {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for edge in children.get(node_id, ()):
            visit(edge.target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in children:
        visit(node_id)

