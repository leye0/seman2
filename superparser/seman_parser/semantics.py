"""Semantic composition graph.

Nodes and relations are generic containers. Labels such as ``AGENT`` or
``OPEN`` come from lexical and grammatical data, never from coded classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from .semantic_rules import SemanticAction
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
    matched_span: tuple[int, int] | None = None,
    syntax_children: Sequence[Any] = (),
) -> SemanticPackage:
    """Apply one generic semantic action.

    Supported kinds are data-driven verbs of composition, not linguistic
    phenomena: ``link``, ``introduce``, ``bind``, ``classify``, ``copy``, ``compose``.

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
            span=matched_span if args.get("anchor_to_match") is True else None,
            node_id=graph.fresh_id("e"),
        )
        name = str(args.get("name", "head"))
        handles[name] = node.node_id
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind == "bind":
        for handle, ref in args.items():
            resolved = _resolve_ref(ref, handles, child_handles)
            if resolved is not None:
                handles[handle] = resolved
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind == "classify":
        # Refine the graph's contextual type without changing the selected
        # lexical sense, its source span, or any original lattice alternative.
        if _matches_choice(args, graph, handles, child_handles, syntax_children):
            target = _resolve_ref(args.get("target"), handles, child_handles)
            type_name = args.get("type")
            if target in graph.nodes and isinstance(type_name, str):
                graph.nodes[target] = replace(graph.nodes[target], type_name=type_name)
        return SemanticPackage(graph=graph, handles=handles)

    if action.kind in {"link", "compose"}:
        links = (args,) if action.kind == "link" else args.get("links", ())
        for link in links:
            relation = link.get("relation", link.get("role", "REL"))
            for choice in link.get("choices", ()):
                if _matches_choice(choice, graph, handles, child_handles, syntax_children):
                    relation = choice["relation"]
                    break
            if relation is None:
                continue
            source = _resolve_ref(link.get("source", "event" if action.kind == "link" else None), handles, child_handles)
            target = _resolve_ref(link.get("target", "referent" if action.kind == "link" else None), handles, child_handles)
            if source is not None and target is not None:
                graph.add_relation(str(relation), source, target)
        return SemanticPackage(graph=graph, handles=handles)

    # Unknown action: keep merged children. Data may add new action kinds
    # without engine changes beyond this generic fallback.
    return SemanticPackage(graph=graph, handles=handles)


def _matches_choice(
    choice: Mapping[str, Any],
    graph: SemanticGraph,
    handles: Mapping[str, str],
    child_handles: Sequence[Mapping[str, str]],
    syntax_children: Sequence[Any],
) -> bool:
    """Match rank-one rule paths or selected lexical nodes, not corpus identity.

    A dotted child path refers to zero-based RHS positions. A form
    condition checks the written inflection of a selected lexical node.
    The first matching choice wins.
    """
    for path, expected in choice.get("child_rules", {}).items():
        children = syntax_children
        node = None
        for segment in path.split("."):
            i = int(segment)
            if not 0 <= i < len(children):
                return False
            node = children[i]
            children = node.children
        if node is None or node.rule_id not in expected:
            return False
    for field in ("lemmas", "forms"):
        for condition in choice.get(field, ()):
            node_id = _resolve_ref(condition["ref"], handles, child_handles)
            node = graph.nodes.get(node_id) if node_id is not None else None
            if node is None:
                return False
            value = node.surface if field == "forms" else node.attributes.get("lemma")
            if not isinstance(value, str) or value.casefold() not in condition["in"]:
                return False
    return True


def _resolve_ref(
    ref: object,
    handles: Mapping[str, str],
    child_handles: Sequence[Mapping[str, str]],
) -> str | None:
    if ref is None:
        return None
    if isinstance(ref, Mapping):
        i = ref.get("child")
        key = ref.get("handle")
        if isinstance(i, int) and 0 <= i < len(child_handles) and isinstance(key, str):
            return child_handles[i].get(key)
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


class SemanticInterpreter:
    """Rebuild semantic graphs from one already selected syntax tree."""

    def __init__(
        self,
        grammar: Any,
        actions: Mapping[str, Sequence[SemanticAction]] | None = None,
        lexicon: Any | None = None,
    ) -> None:
        self.grammar = grammar
        self.actions = actions or {}
        self.lexicon = lexicon

    def interpret(
        self,
        item: Any,
        *,
        sense_selection: Mapping[str, str] | None = None,
    ) -> SemanticPackage:
        """Interpret ``item`` without changing it or its shared forest."""
        self.sense_selection = sense_selection or {}
        return self._walk(item)

    def _walk(self, item: Any) -> SemanticPackage:
        if not item.children:
            candidate = getattr(item, "lexical_candidate", None)
            if candidate is None:
                # Compatibility for externally constructed syntax fixtures.
                return SemanticPackage(SemanticGraph(), {})
            # Structural dialogue punctuation is not an event or entity.
            if candidate.source == "dialogue-delimiter":
                return SemanticPackage(SemanticGraph(), {})
            graph = SemanticGraph()
            anchor = item.syntax.anchors.get("head", "")
            selected_id = self.sense_selection.get(anchor)
            options = getattr(candidate, "interpretations", ())
            selected = next(
                (option for option in options if option.sense_id == selected_id),
                options[0] if options else None,
            )
            lemma = selected.lemma if selected is not None else candidate.lemma
            sense = self._resolve_sense(selected) if selected is not None else None
            semantic_type = sense.semantic_type if sense is not None else self._generated_type(candidate)
            kind = "event" if candidate.category.upper().startswith("V") else "entity"
            if candidate.category in {"AUX", "AUX-BE", "COPULA", "MODAL"}:
                kind = "event"
            node = graph.add_node(
                kind=kind,
                type_name=semantic_type or lemma.upper(),
                span=(item.start, item.end),
                surface=candidate.surface,
                lemma=lemma,
                sense_ids=list(getattr(candidate, "sense_ids", (candidate.sense_id,) if candidate.sense_id else ())),
            )
            handles = {"head": node.node_id, "referent": node.node_id}
            if kind == "event":
                handles["event"] = node.node_id
            return SemanticPackage(graph, handles)

        children = tuple(self._walk(child) for child in item.children)
        if item.rule_id == "segment_interface" and len(children) == 1:
            package = children[0]
            if item.category == "CLAUSE" and "event" not in package.handles:
                graph = package.graph.copy()
                node = graph.add_node(
                    kind="event", type_name="CLAUSE",
                    span=(item.start, item.end), surface=None,
                )
                handles = dict(package.handles)
                handles["event"] = node.node_id
                return SemanticPackage(graph, handles)
            return package

        try:
            rule = self.grammar.by_id(item.rule_id) if item.rule_id else None
        except KeyError:
            rule = None
        child_graphs = [child.graph for child in children]
        child_handles = [child.handles for child in children]
        aliases: dict[str, str] = {}
        if rule is not None:
            for symbol, package in zip(rule.rhs, children):
                for child_name, rule_name in symbol.exports.items():
                    resolved = package.handles.get(child_name)
                    if resolved:
                        aliases[rule_name] = resolved
                for name in ("referent", "event", "head"):
                    resolved = package.handles.get(name)
                    if resolved:
                        aliases.setdefault(name, resolved)
            if any("head" in symbol.exports.values() for symbol in rule.rhs) and "head" in aliases:
                aliases["referent"] = aliases["head"]
        graph = SemanticGraph.merge_all(child_graphs)
        actions = self.actions.get(rule.rule_id, ()) if rule is not None else ()
        if not actions:
            handles = dict(aliases)
            for package in children:
                for key, value in package.handles.items():
                    handles.setdefault(key, value)
            return SemanticPackage(graph, handles)
        package = SemanticPackage(graph, dict(aliases))
        for action in actions:
            package = apply_action(
                action,
                package=package,
                child_handles=child_handles,
                child_graphs=child_graphs,
                aliases=aliases,
                matched_span=(item.start, item.end),
                syntax_children=item.children,
            )
        return package

    def _resolve_sense(self, reference: Any) -> Any | None:
        if self.lexicon is None or reference.sense_id is None:
            return None
        for entry in self.lexicon.entries_for_lemma(reference.lemma):
            for sense in entry.senses:
                if sense.sense_id == reference.sense_id:
                    return sense
        return None

    @staticmethod
    def _generated_type(candidate: Any) -> str | None:
        if candidate.source == "proper-noun":
            return "PERSON"
        if candidate.source == "number":
            return "NUMBER"
        if candidate.source == "unknown":
            return "REFERENTIAL"
        return None
