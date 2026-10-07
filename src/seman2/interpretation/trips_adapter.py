"""Lossless local TRIPS adapter with generic dual projections."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping, Protocol, Sequence
import xml.etree.ElementTree as ET

from ..evidence.model import EvidenceUnit
from .model import (
    AnalysisBundle,
    InterpretationHypothesis,
    InterpretationSegment,
    Projection,
    ProjectionEdge,
    ProjectionNode,
    SourceSpan,
)
from .kqml import KqmlProtocolError, LocalTripsTransport, project_kqml


DEFAULT_OUTPUT_PARTS = (
    "debug words-lisp words-xml tags-lisp tags-xml "
    "lf-lisp lf-rdf tree-lisp tree-xml"
)


class TripsError(RuntimeError):
    """Base class for failures at the TRIPS adapter boundary."""


class TripsTransportError(TripsError):
    pass


class TripsProtocolError(TripsError):
    pass


@dataclass(frozen=True, slots=True)
class TripsResponse:
    body: bytes
    content_type: str
    status: int
    endpoint: str
    headers: Mapping[str, str]


class TripsTransport(Protocol):
    endpoint: str

    def parse(
        self, input_text: str, parameters: Mapping[str, str]
    ) -> TripsResponse: ...


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name


def _element_children(element: ET.Element) -> list[ET.Element]:
    return [child for child in element if isinstance(child.tag, str)]


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    return next(
        (child for child in _element_children(element) if _local_name(child.tag) == name),
        None,
    )


def _element_data(element: ET.Element) -> dict[str, Any]:
    """Preserve arbitrary native XML fields without assigning them meaning."""
    result: dict[str, Any] = {
        "name": _local_name(element.tag),
        "qualified_name": element.tag,
        "attributes": dict(element.attrib),
    }
    if element.text is not None and element.text.strip():
        result["text"] = element.text
    children = _element_children(element)
    if children:
        result["children"] = [_element_data(child) for child in children]
    return result


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class TripsAdapter:
    """Capture one TRIPS response and expose semantic/structural observations."""

    key = "trips"

    def __init__(
        self,
        transport: TripsTransport | None = None,
        *,
        number_parses_desired: int = 10,
        output_parts: str = DEFAULT_OUTPUT_PARTS,
        max_input_characters: int = 100_000,
    ) -> None:
        if not 1 <= number_parses_desired <= 10:
            raise ValueError("TRIPS accepts between 1 and 10 parses")
        if max_input_characters < 1:
            raise ValueError("max input characters must be positive")
        self.transport = transport or LocalTripsTransport()
        self.number_parses_desired = number_parses_desired
        self.output_parts = output_parts
        self.max_input_characters = max_input_characters

    @property
    def configuration(self) -> dict[str, Any]:
        return {
            "endpoint": self.transport.endpoint,
            "number_parses_desired": self.number_parses_desired,
            "output_parts": self.output_parts,
            "max_input_characters": self.max_input_characters,
        }

    @property
    def configuration_digest(self) -> str:
        encoded = json.dumps(
            self.configuration, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def interpret(
        self,
        evidence: EvidenceUnit,
        context: Sequence[EvidenceUnit] = (),
        *,
        request_id: str | None = None,
    ) -> AnalysisBundle:
        ordered = [item for item in context if item.evidence_id != evidence.evidence_id]
        ordered.append(evidence)
        input_text, input_spans = self._compose_input(ordered)
        if len(input_text) > self.max_input_characters:
            raise TripsProtocolError("TRIPS input exceeds configured bound")
        parameters = {
            "number-parses-desired": str(self.number_parses_desired),
            "output-parts": self.output_parts,
        }
        try:
            response = self.transport.parse(input_text, parameters)
        except TripsError:
            raise
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise TripsTransportError(str(exc)) from exc
        response_digest = hashlib.sha256(response.body).hexdigest()
        identity = json.dumps(
            {
                "evidence_id": evidence.evidence_id,
                "request_id": request_id,
                "response_sha256": response_digest,
                "configuration": self.configuration_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        analysis_id = "analysis_" + hashlib.sha256(identity.encode()).hexdigest()[:32]
        is_kqml = response.content_type.split(";", 1)[0].strip().casefold() == "application/kqml"
        if is_kqml:
            try:
                segments = project_kqml(
                    response.body,
                    analysis_id=analysis_id,
                    input_text=input_text,
                    input_spans=input_spans,
                )
            except KqmlProtocolError as exc:
                raise TripsProtocolError(str(exc)) from exc
            analyzer_version = response.headers.get("parser-version")
            root_attributes: dict[str, str] = {}
        else:
            root = self._parse_xml(response.body)
            if _local_name(root.tag) != "trips-parser-output":
                raise TripsProtocolError(
                    f"unexpected TRIPS root element {_local_name(root.tag)!r}"
                )
            segments = self._project_segments(root, analysis_id, input_spans)
            analyzer_version = root.attrib.get("parser-build-date")
            root_attributes = dict(root.attrib)
        return AnalysisBundle(
            analysis_id=analysis_id,
            evidence_id=evidence.evidence_id,
            context_evidence_ids=tuple(item.evidence_id for item in ordered[:-1]),
            analyzer="TRIPS",
            analyzer_version=analyzer_version,
            analyzer_configuration=self.configuration,
            input_text=input_text,
            input_spans=input_spans,
            raw_payload=response.body,
            raw_content_type=response.content_type,
            raw_sha256=response_digest,
            segments=segments,
            request_metadata={
                "request_id": request_id,
                "transport_status": response.status,
                "endpoint": response.endpoint,
                "response_headers": dict(response.headers),
                "root_attributes": root_attributes,
            },
        )

    @staticmethod
    def _compose_input(
        units: Sequence[EvidenceUnit],
    ) -> tuple[str, tuple[SourceSpan, ...]]:
        parts: list[str] = []
        spans: list[SourceSpan] = []
        cursor = 0
        for index, unit in enumerate(units):
            if index:
                parts.append("\n")
                cursor += 1
            start = cursor
            parts.append(unit.raw)
            cursor += len(unit.raw)
            spans.append(
                SourceSpan(
                    start=start,
                    end=cursor,
                    evidence_id=unit.evidence_id,
                    evidence_start=0,
                    evidence_end=len(unit.raw),
                )
            )
        return "".join(parts), tuple(spans)

    @staticmethod
    def _parse_xml(payload: bytes) -> ET.Element:
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            raise TripsProtocolError(f"invalid TRIPS XML: {exc}") from exc

    def _project_segments(
        self,
        root: ET.Element,
        analysis_id: str,
        input_spans: Sequence[SourceSpan],
    ) -> tuple[InterpretationSegment, ...]:
        items = list(self._top_level_parse_items(root))
        if not items:
            raise TripsProtocolError("TRIPS response contains no utterance or failure")
        segments: list[InterpretationSegment] = []
        for segment_index, item in enumerate(items):
            if _local_name(item.tag) == "failed-to-parse":
                segments.append(
                    InterpretationSegment(
                        segment_index=segment_index,
                        status="failed-to-parse",
                        hypotheses=(),
                    )
                )
                continue
            base_tags = _first_child(item, "tags")
            candidates = [item, *self._alternative_utterances(item)]
            hypotheses = tuple(
                self._project_hypothesis(
                    candidate,
                    inherited_tags=base_tags,
                    analysis_id=analysis_id,
                    segment_index=segment_index,
                    rank=rank,
                    input_spans=input_spans,
                )
                for rank, candidate in enumerate(candidates)
            )
            all_spans = [
                node.span
                for hypothesis in hypotheses
                for node in (*hypothesis.semantic.nodes, *hypothesis.structural.nodes)
                if node.span is not None
            ]
            segment_span = self._covering_span(all_spans, input_spans)
            segments.append(
                InterpretationSegment(
                    segment_index=segment_index,
                    status="parsed",
                    hypotheses=hypotheses,
                    span=segment_span,
                )
            )
        return tuple(segments)

    @classmethod
    def _top_level_parse_items(cls, root: ET.Element) -> Iterable[ET.Element]:
        for child in _element_children(root):
            name = _local_name(child.tag)
            if name in {"utt", "failed-to-parse"}:
                yield child
            elif name == "compound-communication-act":
                for nested in _element_children(child):
                    if _local_name(nested.tag) in {"utt", "failed-to-parse"}:
                        yield nested

    @classmethod
    def _alternative_utterances(cls, utterance: ET.Element) -> Iterable[ET.Element]:
        alternatives = _first_child(utterance, "alt-hyps")
        if alternatives is None:
            return ()
        rows: list[ET.Element] = []
        for child in _element_children(alternatives):
            name = _local_name(child.tag)
            if name == "utt":
                rows.append(child)
            elif name == "compound-communication-act":
                rows.extend(
                    nested
                    for nested in _element_children(child)
                    if _local_name(nested.tag) == "utt"
                )
        return tuple(rows)

    def _project_hypothesis(
        self,
        utterance: ET.Element,
        *,
        inherited_tags: ET.Element | None,
        analysis_id: str,
        segment_index: int,
        rank: int,
        input_spans: Sequence[SourceSpan],
    ) -> InterpretationHypothesis:
        prefix = f"{analysis_id}:s{segment_index}:h{rank}"
        own_tags = _first_child(utterance, "tags")
        tags = own_tags if own_tags is not None else inherited_tags
        structural = self._structural_projection(
            utterance, tags, prefix=prefix, input_spans=input_spans
        )
        semantic = self._semantic_projection(
            utterance, prefix=prefix, input_spans=input_spans
        )
        cross_links = self._cross_links(semantic, structural)
        return InterpretationHypothesis(
            hypothesis_id=f"{prefix}:hypothesis",
            rank=rank,
            score=_float_or_none(utterance.attrib.get("score")),
            semantic=semantic,
            structural=structural,
            cross_links=cross_links,
            parser_attributes={
                **dict(utterance.attrib),
                "tags_inherited_from_primary": tags is not None and own_tags is None,
            },
        )

    def _semantic_projection(
        self,
        utterance: ET.Element,
        *,
        prefix: str,
        input_spans: Sequence[SourceSpan],
    ) -> Projection:
        terms = _first_child(utterance, "terms")
        nodes: list[ProjectionNode] = []
        edges: list[ProjectionEdge] = []
        roots: list[str] = []
        metadata: dict[str, Any] = {}
        if terms is None:
            return Projection(
                projection_id=f"{prefix}:semantic",
                family="semantic",
                nodes=(),
                edges=(),
                metadata={"native_section_present": False},
            )
        metadata["native_section_present"] = True
        metadata["terms_attributes"] = dict(terms.attrib)
        lisp = _first_child(terms, "lisp")
        if lisp is not None:
            metadata["native_lisp"] = lisp.text or ""
        rdf = _first_child(terms, "RDF")
        if rdf is None:
            return Projection(
                projection_id=f"{prefix}:semantic",
                family="semantic",
                nodes=(),
                edges=(),
                metadata=metadata,
            )

        descriptions = [
            child
            for child in _element_children(rdf)
            if _local_name(child.tag) == "Description"
        ]
        native_to_projected: dict[str, str] = {}
        for index, description in enumerate(descriptions):
            native_id = self._description_id(description) or f"anonymous-{index}"
            native_to_projected[native_id] = f"{prefix}:sem:{native_id}"

        for index, description in enumerate(descriptions):
            native_id = self._description_id(description) or f"anonymous-{index}"
            node_id = native_to_projected[native_id]
            values: dict[str, Any] = {
                "native_id": native_id,
                "native_attributes": dict(description.attrib),
            }
            start: int | None = None
            end: int | None = None
            for child_index, child in enumerate(_element_children(description)):
                name = _local_name(child.tag)
                resource = next(
                    (
                        value
                        for key, value in child.attrib.items()
                        if _local_name(key) == "resource"
                    ),
                    None,
                )
                if resource:
                    native_target = resource.removeprefix("#")
                    target = native_to_projected.get(
                        native_target, f"{prefix}:sem:{native_target}"
                    )
                    edges.append(
                        ProjectionEdge(
                            source_id=node_id,
                            target_id=target,
                            relation=name,
                            attributes={
                                "native_qualified_name": child.tag,
                                "native_attributes": dict(child.attrib),
                                "position": child_index,
                            },
                        )
                    )
                    continue
                text = child.text or ""
                existing = values.get(name)
                if existing is None:
                    values[name] = text
                elif isinstance(existing, list):
                    existing.append(text)
                else:
                    values[name] = [existing, text]
                if name == "start":
                    try:
                        start = int(text)
                    except ValueError:
                        pass
                elif name == "end":
                    try:
                        end = int(text)
                    except ValueError:
                        pass
                if child.attrib or _element_children(child):
                    values.setdefault("native_children", []).append(_element_data(child))
            span = (
                self._source_span(start, end, input_spans)
                if start is not None and end is not None
                else None
            )
            nodes.append(
                ProjectionNode(
                    node_id=node_id,
                    category="lf-term",
                    attributes=values,
                    span=span,
                    native_path=f"terms/RDF/Description[{index}]",
                )
            )

        root_ref = next(
            (
                value.removeprefix("#")
                for key, value in terms.attrib.items()
                if _local_name(key) == "root"
            ),
            None,
        )
        if root_ref:
            roots.append(native_to_projected.get(root_ref, f"{prefix}:sem:{root_ref}"))
        return Projection(
            projection_id=f"{prefix}:semantic",
            family="semantic",
            nodes=tuple(nodes),
            edges=tuple(edges),
            roots=tuple(roots),
            metadata=metadata,
        )

    @staticmethod
    def _description_id(description: ET.Element) -> str | None:
        for key, value in description.attrib.items():
            if _local_name(key) in {"ID", "about"}:
                return value.removeprefix("#")
        return None

    def _structural_projection(
        self,
        utterance: ET.Element,
        tags: ET.Element | None,
        *,
        prefix: str,
        input_spans: Sequence[SourceSpan],
    ) -> Projection:
        nodes: list[ProjectionNode] = []
        edges: list[ProjectionEdge] = []
        roots: list[str] = []
        metadata: dict[str, Any] = {"native_tags_present": tags is not None}
        token_nodes: list[ProjectionNode] = []
        if tags is not None:
            lisp = _first_child(tags, "lisp")
            if lisp is not None:
                metadata["tags_native_lisp"] = lisp.text or ""
            for index, tag in enumerate(
                child
                for child in _element_children(tags)
                if _local_name(child.tag) != "lisp"
            ):
                native_kind = _local_name(tag.tag)
                start = self._integer_attribute(tag, "start")
                end = self._integer_attribute(tag, "end")
                span = (
                    self._source_span(start, end, input_spans)
                    if start is not None and end is not None
                    else None
                )
                node = ProjectionNode(
                    node_id=f"{prefix}:tag:{index}",
                    category=(
                        "parser-token"
                        if native_kind in {"word", "prefix"}
                        else "parser-tag"
                    ),
                    attributes={
                        "native_kind": native_kind,
                        "native": _element_data(tag),
                        "position": index,
                    },
                    span=span,
                    native_path=f"tags/{_local_name(tag.tag)}[{index}]",
                )
                nodes.append(node)
                if node.category == "parser-token":
                    token_nodes.append(node)

        words = _first_child(utterance, "words")
        if words is not None:
            lisp = _first_child(words, "lisp")
            if lisp is not None:
                metadata["words_native_lisp"] = lisp.text or ""
            word_index = 0
            for word in _element_children(words):
                if _local_name(word.tag) == "lisp":
                    continue
                node_id = f"{prefix}:word:{word_index}"
                nodes.append(
                    ProjectionNode(
                        node_id=node_id,
                        category="parser-word",
                        attributes={
                            "native_kind": _local_name(word.tag),
                            "value": word.text or "",
                            "native_attributes": dict(word.attrib),
                            "position": word_index,
                        },
                        span=(
                            token_nodes[word_index].span
                            if word_index < len(token_nodes)
                            else None
                        ),
                        native_path=f"words/{_local_name(word.tag)}[{word_index}]",
                    )
                )
                if word_index < len(token_nodes):
                    edges.append(
                        ProjectionEdge(
                            source_id=node_id,
                            target_id=token_nodes[word_index].node_id,
                            relation="tagged-as",
                            attributes={"position": word_index},
                        )
                    )
                word_index += 1

        tree = _first_child(utterance, "tree")
        if tree is not None:
            lisp = _first_child(tree, "lisp")
            if lisp is not None:
                metadata["tree_native_lisp"] = lisp.text or ""
            tree_roots = [
                child
                for child in _element_children(tree)
                if _local_name(child.tag) != "lisp"
            ]
            leaf_counter = [0]
            for root_index, tree_root in enumerate(tree_roots):
                root_id, _ = self._walk_tree(
                    tree_root,
                    path=(root_index,),
                    prefix=prefix,
                    token_nodes=token_nodes,
                    leaf_counter=leaf_counter,
                    nodes=nodes,
                    edges=edges,
                    input_spans=input_spans,
                )
                roots.append(root_id)

        return Projection(
            projection_id=f"{prefix}:structural",
            family="structural",
            nodes=tuple(nodes),
            edges=tuple(edges),
            roots=tuple(roots),
            metadata=metadata,
        )

    def _walk_tree(
        self,
        element: ET.Element,
        *,
        path: tuple[int, ...],
        prefix: str,
        token_nodes: Sequence[ProjectionNode],
        leaf_counter: list[int],
        nodes: list[ProjectionNode],
        edges: list[ProjectionEdge],
        input_spans: Sequence[SourceSpan],
    ) -> tuple[str, SourceSpan | None]:
        path_text = ".".join(str(item) for item in path)
        node_id = f"{prefix}:tree:{path_text}"
        children = _element_children(element)
        child_rows: list[tuple[str, SourceSpan | None]] = []
        if children:
            for child_index, child in enumerate(children):
                child_rows.append(
                    self._walk_tree(
                        child,
                        path=(*path, child_index),
                        prefix=prefix,
                        token_nodes=token_nodes,
                        leaf_counter=leaf_counter,
                        nodes=nodes,
                        edges=edges,
                        input_spans=input_spans,
                    )
                )
        else:
            token_index = leaf_counter[0]
            leaf_counter[0] += 1
            span = token_nodes[token_index].span if token_index < len(token_nodes) else None
            if token_index < len(token_nodes):
                edges.append(
                    ProjectionEdge(
                        source_id=node_id,
                        target_id=token_nodes[token_index].node_id,
                        relation="realizes-token",
                        attributes={"position": token_index},
                    )
                )
            child_rows = [("", span)]
        child_spans = [span for _, span in child_rows if span is not None]
        span = self._covering_span(child_spans, input_spans)
        nodes.append(
            ProjectionNode(
                node_id=node_id,
                category="tree-node",
                attributes={
                    "native_category": _local_name(element.tag),
                    "native_qualified_name": element.tag,
                    "native_attributes": dict(element.attrib),
                    "surface": element.text or "" if not children else "",
                },
                span=span,
                native_path="tree/" + "/".join(map(str, path)),
            )
        )
        if children:
            for position, (child_id, _) in enumerate(child_rows):
                edges.append(
                    ProjectionEdge(
                        source_id=node_id,
                        target_id=child_id,
                        relation="contains",
                        attributes={"position": position},
                    )
                )
        return node_id, span

    @staticmethod
    def _integer_attribute(element: ET.Element, local_name: str) -> int | None:
        for key, value in element.attrib.items():
            if _local_name(key) == local_name:
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    @classmethod
    def _source_span(
        cls, start: int, end: int, input_spans: Sequence[SourceSpan]
    ) -> SourceSpan:
        for span in input_spans:
            if start >= span.start and end <= span.end:
                return SourceSpan(
                    start=start,
                    end=end,
                    evidence_id=span.evidence_id,
                    evidence_start=start - span.start,
                    evidence_end=end - span.start,
                )
        return SourceSpan(start=start, end=end)

    @classmethod
    def _covering_span(
        cls,
        spans: Sequence[SourceSpan],
        input_spans: Sequence[SourceSpan],
    ) -> SourceSpan | None:
        if not spans:
            return None
        return cls._source_span(
            min(span.start for span in spans),
            max(span.end for span in spans),
            input_spans,
        )

    @staticmethod
    def _cross_links(
        semantic: Projection, structural: Projection
    ) -> tuple[ProjectionEdge, ...]:
        tokens = [
            node
            for node in structural.nodes
            if node.category == "parser-token" and node.span is not None
        ]
        links: list[ProjectionEdge] = []
        for semantic_node in semantic.nodes:
            if semantic_node.span is None:
                continue
            for token in tokens:
                assert token.span is not None
                overlap_start = max(semantic_node.span.start, token.span.start)
                overlap_end = min(semantic_node.span.end, token.span.end)
                # Zero-width punctuation spans are linked only on exact equality.
                overlaps = overlap_start < overlap_end or (
                    semantic_node.span.start == semantic_node.span.end
                    and token.span.start == token.span.end
                    and overlap_start == overlap_end
                )
                if overlaps:
                    links.append(
                        ProjectionEdge(
                            source_id=semantic_node.node_id,
                            target_id=token.node_id,
                            relation="span-overlap",
                            attributes={
                                "start": overlap_start,
                                "end": overlap_end,
                            },
                        )
                    )
        return tuple(links)
