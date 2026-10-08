"""Semantic composition graph.

Nodes and relations are generic containers. Labels such as ``AGENT`` or
``OPEN`` come from lexical and grammatical data, never from coded classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .grammar import SemanticAction
from .lexicon import LexicalSense, SenseFrame


@dataclass(frozen=True, slots=True)
class SemanticNode:
    """An event, entity, situation or any other node kind supplied by data."""

    node_id: str
    kind: str  # "event", "entity", ... — free labels from data
    type_name: str | None = None
    span: tuple[int, int] | None = None
    surface: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "type": self.type_name,
            "span": list(self.span) if self.span else None,
            "surface": self.surface,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class SemanticRelation:
    """A role or discourse relation between semantic nodes."""

    relation: str
    source: str
    target: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "source": self.source,
            "target": self.target,
            "attributes": dict(self.attributes),
        }


# Process-wide node-id source so merged graphs never collide on ids.
_NODE_COUNTER = 0


def _fresh_node_id(prefix: str = "e") -> str:
    global _NODE_COUNTER
    _NODE_COUNTER += 1
    return f"{prefix}{_NODE_COUNTER}"


@dataclass
class SemanticGraph:
    """Mutable builder for one analysis; freeze via ``as_dict``/snapshot."""

    nodes: dict[str, SemanticNode] = field(default_factory=dict)
    relations: list[SemanticRelation] = field(default_factory=list)

    def fresh_id(self, prefix: str = "n") -> str:
        return _fresh_node_id(prefix)

    def add_node(
        self,
        *,
        kind: str,
        type_name: str | None = None,
        node_id: str | None = None,
        span: tuple[int, int] | None = None,
        surface: str | None = None,
        **attributes: Any,
    ) -> SemanticNode:
        nid = node_id or self.fresh_id("e")
        node = SemanticNode(
            node_id=nid,
            kind=kind,
            type_name=type_name,
            span=span,
            surface=surface,
            attributes=dict(attributes),
        )
        self.nodes[nid] = node
        return node

    def add_relation(self, relation: str, source: str, target: str, **attributes: Any) -> SemanticRelation:
        edge = SemanticRelation(
            relation=relation,
            source=source,
            target=target,
            attributes=dict(attributes),
        )
        self.relations.append(edge)
        return edge

    def copy(self) -> "SemanticGraph":
        clone = SemanticGraph(nodes=dict(self.nodes), relations=list(self.relations))
        return clone

    def merge(self, other: "SemanticGraph") -> "SemanticGraph":
        combined = self.copy()
        for node_id, node in other.nodes.items():
            if node_id in combined.nodes:
                continue
            combined.nodes[node_id] = node
        combined.relations.extend(other.relations)
        return combined

    @staticmethod
    def merge_all(graphs: Sequence["SemanticGraph"]) -> "SemanticGraph":
        """Merge many graphs with a single pass, no intermediate copies.

        ``A.merge(B).merge(C)`` copies A twice. ``merge_all`` writes
        every node and relation once into a fresh graph.
        """
        combined = SemanticGraph()
        for graph in graphs:
            for node_id, node in graph.nodes.items():
                combined.nodes.setdefault(node_id, node)
            combined.relations.extend(graph.relations)
        return combined

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.as_dict() for node in self.nodes.values()],
            "relations": [edge.as_dict() for edge in self.relations],
        }


@dataclass(frozen=True, slots=True)
class SemanticPackage:
    """Semantic contribution of a lexical sense or grammar rule application."""

    graph: SemanticGraph
    # Named handles available to parent rules: role/export name -> node id.
    handles: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"graph": self.graph.as_dict(), "handles": dict(self.handles)}


def introduce_from_sense(
    sense: LexicalSense,
    *,
    span: tuple[int, int],
    surface: str,
    lemma: str,
) -> SemanticPackage:
    """Create the event/entity node a lexical sense contributes."""
    graph = SemanticGraph()
    kind = "event" if sense.semantic_type and sense.category.upper().startswith("V") else "entity"
    if sense.category.upper().startswith("V"):
        kind = "event"
    elif sense.category.upper().startswith("N"):
        kind = "entity"
    node = graph.add_node(
        kind=kind,
        type_name=sense.semantic_type or lemma.upper(),
        span=span,
        surface=surface,
        lemma=lemma,
    )
    handles = {"head": node.node_id, "referent": node.node_id}
    if kind == "event":
        handles["event"] = node.node_id
    return SemanticPackage(graph=graph, handles=handles)


def apply_action(
    action: SemanticAction,
    *,
    package: SemanticPackage,
    child_handles: Sequence[Mapping[str, str]],
    child_graphs: Sequence[SemanticGraph],
    aliases: Mapping[str, str] | None = None,
) -> SemanticPackage:
    """Apply one generic semantic action.

    Supported kinds are data-driven verbs of composition, not linguistic
    phenomena: ``link``, ``introduce``, ``copy``, ``compose``.

    ``aliases`` carries rule-level names (``subject``, ``object``, ``event``)
    resolved while matching RHS symbols.
    """
    graph = package.graph
    # Reuse the same handles mapping across actions of one rule instead of
    # copying it every time. The package is rebuilt per action, but the
    # dict is now shared and updated in place.
    handles = package.handles if isinstance(package.handles, dict) else dict(package.handles)
    if aliases:
        for key, value in aliases.items():
            if value:
                handles.setdefault(key, value)
    # Every action sees the children first: nodes must survive composition.
    for child in child_handles:
        for key, value in child.items():
            handles.setdefault(key, value)
    # NOTE: caller pre-merges child graphs into ``package.graph`` so this
    # function does not re-copy them once per action.
    args = action.args

    if action.kind == "copy":
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind == "introduce":
        node = graph.add_node(
            kind=str(args.get("kind", "entity")),
            type_name=args.get("type"),
            node_id=graph.fresh_id("e"),
        )
        name = str(args.get("name", "head"))
        handles[name] = node.node_id
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind == "link":
        relation = str(args.get("relation", args.get("role", "REL")))
        source_ref = args.get("source", "event")
        target_ref = args.get("target", "referent")
        source = _resolve_ref(source_ref, handles, child_handles)
        target = _resolve_ref(target_ref, handles, child_handles)
        if source is not None and target is not None:
            graph.add_relation(relation, source, target)
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind == "compose":
        for link in args.get("links", ()):
            relation = str(link.get("relation", "REL"))
            source = _resolve_ref(link.get("source"), handles, child_handles)
            target = _resolve_ref(link.get("target"), handles, child_handles)
            if source is not None and target is not None:
                graph.add_relation(relation, source, target)
        return SemanticPackage(graph=graph, handles=handles)

    # Unknown action: keep merged children. Data may add new action kinds
    # without engine changes beyond this generic fallback.
    return SemanticPackage(graph=graph, handles=handles)


def _resolve_ref(
    ref: object,
    handles: Mapping[str, str],
    child_handles: Sequence[Mapping[str, str]],
) -> str | None:
    if ref is None:
        return None
    if isinstance(ref, int):
        if 0 <= ref < len(child_handles):
            child = child_handles[ref]
            return child.get("referent") or child.get("head") or child.get("event")
        return None
    name = str(ref)
    if name in handles:
        return handles[name]
    for child in child_handles:
        if name in child:
            return child[name]
    return None


def bind_frame_roles(
    package: SemanticPackage,
    frame: SenseFrame,
    argument_nodes: Mapping[str, str],
) -> SemanticPackage:
    """Attach semantic roles of a lexical frame to resolved arguments."""
    graph = package.graph
    event_id = package.handles.get("event") or package.handles.get("head")
    if event_id is None:
        return package
    for slot in frame.slots:
        target = argument_nodes.get(slot.syntactic)
        if target is None:
            continue
        graph.add_relation(slot.semantic_role, event_id, target)
    return SemanticPackage(graph=graph, handles=package.handles)
