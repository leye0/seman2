"""POC-03: lossless component library and representation-neutral MDL costs.

The code length is defined over logical values and graph/template fields.  It
does not count Python objects, JSON whitespace or content-address identifiers.
Every promoted component pays its model cost; every use pays a selector and
all variable values required for exact reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence

from .anti_unification import (
    AntiUnificationError,
    ComponentTemplate,
    PatternEdge,
    PatternNode,
    anti_unify,
)
from .observation_graph import GraphEdge, ObservationGraph


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _uint_bits(value: int) -> int:
    """Elias-gamma length for a non-negative integer."""
    if value < 0:
        raise ValueError("expected a non-negative integer")
    width = (value + 1).bit_length()
    return 2 * width - 1


def _string_bits(value: str) -> int:
    size = len(value.encode("utf-8"))
    return _uint_bits(size) + 8 * size


def value_description_bits(value: Any) -> int:
    """Logical prefix-code length shared by every POC-03 baseline."""
    tag = 3
    if value is None:
        return tag
    if isinstance(value, bool):
        return tag + 1
    if isinstance(value, int):
        return tag + 1 + _uint_bits(abs(value))
    if isinstance(value, float):
        return tag + 64
    if isinstance(value, str):
        return tag + _string_bits(value)
    if isinstance(value, Mapping):
        return tag + _uint_bits(len(value)) + sum(
            _string_bits(str(key)) + value_description_bits(child)
            for key, child in sorted(value.items(), key=lambda row: str(row[0]))
        )
    if isinstance(value, (list, tuple)):
        return tag + _uint_bits(len(value)) + sum(
            value_description_bits(child) for child in value
        )
    raise TypeError(f"unsupported logical value: {type(value).__name__}")


def root_snapshot(graph: ObservationGraph, root_id: str) -> dict[str, Any]:
    nodes = {node.node_id: node for node in graph.nodes}
    if root_id not in nodes:
        raise KeyError(root_id)
    children = _child_index(graph.edges)
    active: set[str] = set()

    def expand(node_id: str) -> dict[str, Any]:
        if node_id in active:
            raise ValueError("cyclic constituent graph cannot be encoded as a tree snapshot")
        active.add(node_id)
        row = nodes[node_id].properties
        row["children"] = [expand(edge.target) for edge in children.get(node_id, ())]
        active.remove(node_id)
        return row

    return expand(root_id)


@dataclass(frozen=True, slots=True)
class ObservationExample:
    observation_id: str
    graph: ObservationGraph
    root_id: str

    @property
    def snapshot(self) -> dict[str, Any]:
        return root_snapshot(self.graph, self.root_id)


@dataclass(frozen=True, slots=True)
class ComponentOccurrence:
    observation_id: str
    root_id: str
    bindings_json: str
    raw_bits: int
    instance_bits: int

    @property
    def bindings(self) -> dict[str, Any]:
        value = json.loads(self.bindings_json)
        assert isinstance(value, dict)
        return value

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "root_id": self.root_id,
            "bindings": self.bindings,
            "raw_bits": self.raw_bits,
            "instance_bits": self.instance_bits,
        }


@dataclass(frozen=True, slots=True)
class LibraryComponent:
    template: ComponentTemplate
    occurrences: tuple[ComponentOccurrence, ...]
    model_bits: int
    training_raw_bits: int
    training_encoded_bits: int
    gain_bits: int
    status: str = "promoted"

    @property
    def support(self) -> int:
        return len(self.occurrences)

    def as_dict(self) -> dict[str, Any]:
        return {
            "template": self.template.as_dict(),
            "occurrences": [row.as_dict() for row in self.occurrences],
            "model_bits": self.model_bits,
            "training_raw_bits": self.training_raw_bits,
            "training_encoded_bits": self.training_encoded_bits,
            "gain_bits": self.gain_bits,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class EncodedObservation:
    observation_id: str
    mode: str
    payload_json: str
    encoded_bits: int
    component_id: str | None = None

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        assert isinstance(value, dict)
        return value


@dataclass(frozen=True, slots=True)
class MDLReport:
    observation_count: int
    b0_raw_bits: int
    b1_exact_dictionary_bits: int
    b2_single_component_bits: int
    b3_library_bits: int
    library_model_bits: int
    library_data_bits: int
    component_count: int
    encoded_occurrences: int
    raw_exceptions: int
    reconstruction_rate: float

    @property
    def gain_vs_raw_bits(self) -> int:
        return self.b0_raw_bits - self.b3_library_bits

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_count": self.observation_count,
            "b0_raw_bits": self.b0_raw_bits,
            "b1_exact_dictionary_bits": self.b1_exact_dictionary_bits,
            "b2_single_component_bits": self.b2_single_component_bits,
            "b3_library_bits": self.b3_library_bits,
            "library_model_bits": self.library_model_bits,
            "library_data_bits": self.library_data_bits,
            "component_count": self.component_count,
            "encoded_occurrences": self.encoded_occurrences,
            "raw_exceptions": self.raw_exceptions,
            "reconstruction_rate": self.reconstruction_rate,
            "gain_vs_raw_bits": self.gain_vs_raw_bits,
            "compression_ratio": self.b3_library_bits / self.b0_raw_bits
            if self.b0_raw_bits
            else 1.0,
        }


def canonicalize_template(
    template: ComponentTemplate,
) -> tuple[ComponentTemplate, dict[str, str]]:
    """Canonicalize node ids and variables by rooted first occurrence."""
    nodes = {node.node_id: node for node in template.nodes}
    outgoing: dict[str, list[PatternEdge]] = {}
    for edge in template.edges:
        outgoing.setdefault(edge.source, []).append(edge)
    for rows in outgoing.values():
        rows.sort(key=lambda edge: (edge.position, edge.role, edge.target))

    ordered: list[str] = []
    node_names: dict[str, str] = {}

    def visit(node_id: str) -> None:
        if node_id in node_names:
            return
        node_names[node_id] = f"N{len(node_names)}"
        ordered.append(node_id)
        for edge in outgoing.get(node_id, ()):
            visit(edge.target)

    visit(template.root_id)
    for node_id in sorted(nodes):
        visit(node_id)

    variable_names: dict[str, str] = {}

    def normalize(value: Any) -> Any:
        if isinstance(value, Mapping) and set(value) == {"$var"}:
            old = str(value["$var"])
            new = variable_names.setdefault(old, f"V{len(variable_names)}")
            return {"$var": new}
        if isinstance(value, Mapping):
            return {
                str(key): normalize(child)
                for key, child in sorted(value.items(), key=lambda row: str(row[0]))
            }
        if isinstance(value, list):
            return [normalize(child) for child in value]
        return value

    canonical_nodes = tuple(
        PatternNode(
            node_names[old_id],
            nodes[old_id].kind,
            _json(normalize(nodes[old_id].properties)),
        )
        for old_id in ordered
    )
    canonical_edges = tuple(
        sorted(
            (
                PatternEdge(
                    node_names[edge.source],
                    node_names[edge.target],
                    edge.role,
                    edge.position,
                )
                for edge in template.edges
            ),
            key=lambda edge: (edge.source, edge.position, edge.role, edge.target),
        )
    )
    body = {
        "root_id": node_names[template.root_id],
        "nodes": [node.as_dict() for node in canonical_nodes],
        "edges": [edge.as_dict() for edge in canonical_edges],
    }
    component_id = "component_" + sha256(_json(body).encode("utf-8")).hexdigest()[:24]
    return (
        ComponentTemplate(
            component_id,
            node_names[template.root_id],
            canonical_nodes,
            canonical_edges,
        ),
        variable_names,
    )


def template_description_bits(template: ComponentTemplate) -> int:
    variables = _template_variables(template)
    variable_indexes = {name: index for index, name in enumerate(variables)}

    def pattern_bits(value: Any) -> int:
        if isinstance(value, Mapping) and set(value) == {"$var"}:
            return 3 + _uint_bits(variable_indexes[str(value["$var"])])
        if isinstance(value, Mapping):
            return 3 + _uint_bits(len(value)) + sum(
                _string_bits(str(key)) + pattern_bits(child)
                for key, child in sorted(value.items(), key=lambda row: str(row[0]))
            )
        if isinstance(value, list):
            return 3 + _uint_bits(len(value)) + sum(pattern_bits(child) for child in value)
        return value_description_bits(value)

    node_indexes = {node.node_id: index for index, node in enumerate(template.nodes)}
    return (
        _uint_bits(len(template.nodes))
        + _uint_bits(len(template.edges))
        + _uint_bits(node_indexes[template.root_id])
        + sum(_string_bits(node.kind) + pattern_bits(node.properties) for node in template.nodes)
        + sum(
            _uint_bits(node_indexes[edge.source])
            + _uint_bits(node_indexes[edge.target])
            + _string_bits(edge.role)
            + _uint_bits(edge.position)
            for edge in template.edges
        )
    )


def instance_description_bits(
    template: ComponentTemplate,
    bindings: Mapping[str, Any],
    *,
    selector_bits: int = 1,
) -> int:
    variables = _template_variables(template)
    if set(bindings) != set(variables):
        raise ValueError("bindings do not exactly cover the template variables")
    return selector_bits + sum(value_description_bits(bindings[name]) for name in variables)


class ComponentLibrary:
    def __init__(
        self,
        *,
        min_support: int = 4,
        min_gain_bits: int = 1,
        seed_window: int = 8,
        max_variable_ratio: float = 0.65,
    ) -> None:
        if min_support < 2:
            raise ValueError("min_support must be at least 2")
        self.min_support = min_support
        self.min_gain_bits = min_gain_bits
        self.seed_window = max(2, seed_window)
        if not 0.0 <= max_variable_ratio <= 1.0:
            raise ValueError("max_variable_ratio must be between 0 and 1")
        self.max_variable_ratio = max_variable_ratio
        self.components: dict[str, LibraryComponent] = {}
        self.frozen = False

    @property
    def active_components(self) -> tuple[LibraryComponent, ...]:
        return tuple(
            component
            for _, component in sorted(self.components.items())
            if component.status == "promoted"
        )

    def fit(self, examples: Sequence[ObservationExample]) -> MDLReport:
        if self.frozen:
            raise RuntimeError("a frozen library cannot be fitted")
        observation_ids = [example.observation_id for example in examples]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation ids must be unique")
        buckets: dict[str, list[ObservationExample]] = {}
        for example in examples:
            buckets.setdefault(_learning_shape(example), []).append(example)

        for bucket in buckets.values():
            remaining = list(bucket)
            while len(remaining) >= self.min_support:
                candidates: dict[str, ComponentTemplate] = {}
                sample = remaining[: self.seed_window]
                for left_index, left in enumerate(sample):
                    for right in sample[left_index + 1 :]:
                        try:
                            proposal = anti_unify(
                                left.graph,
                                left.root_id,
                                right.graph,
                                right.root_id,
                            )
                        except AntiUnificationError:
                            continue
                        if (
                            proposal.evaluation.trivial
                            or proposal.evaluation.variable_ratio > self.max_variable_ratio
                        ):
                            continue
                        template, _ = canonicalize_template(proposal.template)
                        candidates[template.component_id] = template

                if not candidates:
                    # Every pair in the deterministic seed is structurally
                    # invalid or above the promotion complexity ceiling.
                    break

                best: tuple[int, LibraryComponent, set[str]] | None = None
                for template in candidates.values():
                    component = self._evaluate_candidate(template, remaining)
                    matched = {row.observation_id for row in component.occurrences}
                    if component.support < self.min_support:
                        continue
                    key = (component.gain_bits, component.support, -component.model_bits)
                    if best is None or key > (best[0], best[1].support, -best[1].model_bits):
                        best = (component.gain_bits, component, matched)
                if best is None or best[0] < self.min_gain_bits:
                    remaining.pop(0)
                    continue
                component = best[1]
                existing = self.components.get(component.template.component_id)
                if existing is None or component.gain_bits > existing.gain_bits:
                    self.components[component.template.component_id] = component
                remaining = [
                    example for example in remaining
                    if example.observation_id not in best[2]
                ]
        return self.evaluate(examples)

    def freeze(self) -> None:
        self.frozen = True

    def retire(self, component_id: str) -> None:
        component = self.components[component_id]
        self.components[component_id] = replace(component, status="retired")

    def retire_unprofitable(
        self,
        examples: Sequence[ObservationExample],
    ) -> tuple[str, ...]:
        retired: list[str] = []
        for component in self.active_components:
            measured = self._evaluate_candidate(component.template, examples)
            if measured.support < self.min_support or measured.gain_bits < self.min_gain_bits:
                self.retire(component.template.component_id)
                retired.append(component.template.component_id)
        return tuple(retired)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "component-library/0.1",
            "min_support": self.min_support,
            "min_gain_bits": self.min_gain_bits,
            "seed_window": self.seed_window,
            "max_variable_ratio": self.max_variable_ratio,
            "frozen": self.frozen,
            "components": [
                component.as_dict()
                for _, component in sorted(self.components.items())
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComponentLibrary":
        if payload.get("schema_version") != "component-library/0.1":
            raise ValueError("unsupported component library schema")
        library = cls(
            min_support=int(payload["min_support"]),
            min_gain_bits=int(payload["min_gain_bits"]),
            seed_window=int(payload["seed_window"]),
            max_variable_ratio=float(payload["max_variable_ratio"]),
        )
        for raw_component in payload.get("components", ()):
            template = _template_from_dict(raw_component["template"])
            occurrences = tuple(
                ComponentOccurrence(
                    str(row["observation_id"]),
                    str(row["root_id"]),
                    _json(row["bindings"]),
                    int(row["raw_bits"]),
                    int(row["instance_bits"]),
                )
                for row in raw_component["occurrences"]
            )
            component = LibraryComponent(
                template,
                occurrences,
                int(raw_component["model_bits"]),
                int(raw_component["training_raw_bits"]),
                int(raw_component["training_encoded_bits"]),
                int(raw_component["gain_bits"]),
                str(raw_component["status"]),
            )
            library.components[template.component_id] = component
        library.frozen = bool(payload.get("frozen", False))
        return library

    def encode(self, example: ObservationExample) -> EncodedObservation:
        raw = example.snapshot
        raw_bits = 1 + value_description_bits(raw)
        best = EncodedObservation(
            example.observation_id,
            "raw",
            _json(raw),
            raw_bits,
        )
        selector_bits = _selector_bits(len(self.active_components))
        for component in self.active_components:
            bindings = component.template.match(example.graph, example.root_id)
            if bindings is None:
                continue
            bits = instance_description_bits(
                component.template,
                bindings,
                selector_bits=selector_bits,
            )
            if bits < best.encoded_bits:
                best = EncodedObservation(
                    example.observation_id,
                    "component",
                    _json(bindings),
                    bits,
                    component.template.component_id,
                )
        return best

    def decode(self, encoded: EncodedObservation) -> dict[str, Any]:
        if encoded.mode == "raw":
            return encoded.payload
        if encoded.mode != "component" or encoded.component_id is None:
            raise ValueError("invalid encoded observation")
        component = self.components.get(encoded.component_id)
        if component is None or component.status != "promoted":
            raise KeyError(encoded.component_id)
        return component.template.instantiate(encoded.payload)

    def evaluate(self, examples: Sequence[ObservationExample]) -> MDLReport:
        snapshots = [example.snapshot for example in examples]
        b0 = _uint_bits(len(snapshots)) + sum(value_description_bits(row) for row in snapshots)
        b1 = _exact_dictionary_bits(snapshots)
        active = self.active_components
        model_bits = _uint_bits(len(active)) + sum(
            template_description_bits(component.template) for component in active
        )
        encoded = [self.encode(example) for example in examples]
        data_bits = _uint_bits(len(encoded)) + sum(row.encoded_bits for row in encoded)
        b3 = model_bits + data_bits
        b2 = b0
        for component in active:
            single_model = _uint_bits(1) + template_description_bits(component.template)
            single_data = _uint_bits(len(examples))
            for example, snapshot in zip(examples, snapshots):
                bindings = component.template.match(example.graph, example.root_id)
                if bindings is None:
                    single_data += 1 + value_description_bits(snapshot)
                else:
                    single_data += instance_description_bits(
                        component.template, bindings, selector_bits=1
                    )
            b2 = min(b2, single_model + single_data)
        reconstructed = sum(
            self.decode(row) == snapshot for row, snapshot in zip(encoded, snapshots)
        )
        return MDLReport(
            observation_count=len(examples),
            b0_raw_bits=b0,
            b1_exact_dictionary_bits=b1,
            b2_single_component_bits=b2,
            b3_library_bits=b3,
            library_model_bits=model_bits,
            library_data_bits=data_bits,
            component_count=len(active),
            encoded_occurrences=sum(row.mode == "component" for row in encoded),
            raw_exceptions=sum(row.mode == "raw" for row in encoded),
            reconstruction_rate=reconstructed / len(examples) if examples else 1.0,
        )

    def evaluate_heldout(self, examples: Sequence[ObservationExample]) -> dict[str, Any]:
        encoded = [self.encode(example) for example in examples]
        raw_bits = _uint_bits(len(examples)) + sum(
            value_description_bits(example.snapshot) for example in examples
        )
        encoded_bits = _uint_bits(len(encoded)) + sum(row.encoded_bits for row in encoded)
        reconstructed = sum(
            self.decode(row) == example.snapshot
            for row, example in zip(encoded, examples)
        )
        return {
            "observation_count": len(examples),
            "raw_bits": raw_bits,
            "encoded_bits": encoded_bits,
            "gain_bits": raw_bits - encoded_bits,
            "compression_ratio": encoded_bits / raw_bits if raw_bits else 1.0,
            "component_uses": sum(row.mode == "component" for row in encoded),
            "raw_exceptions": sum(row.mode == "raw" for row in encoded),
            "reconstruction_rate": reconstructed / len(examples) if examples else 1.0,
        }

    def _evaluate_candidate(
        self,
        template: ComponentTemplate,
        examples: Sequence[ObservationExample],
    ) -> LibraryComponent:
        model_bits = template_description_bits(template)
        occurrences: list[ComponentOccurrence] = []
        for example in examples:
            bindings = template.match(example.graph, example.root_id)
            if bindings is None:
                continue
            raw_bits = value_description_bits(example.snapshot)
            instance_bits = instance_description_bits(template, bindings, selector_bits=1)
            occurrences.append(
                ComponentOccurrence(
                    example.observation_id,
                    example.root_id,
                    _json(bindings),
                    raw_bits,
                    instance_bits,
                )
            )
        raw_total = sum(row.raw_bits for row in occurrences)
        encoded_total = model_bits + sum(row.instance_bits for row in occurrences)
        return LibraryComponent(
            template,
            tuple(occurrences),
            model_bits,
            raw_total,
            encoded_total,
            raw_total - encoded_total,
        )


def _child_index(edges: Sequence[GraphEdge]) -> dict[str, tuple[GraphEdge, ...]]:
    grouped: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        if edge.role == "CHILD":
            grouped.setdefault(edge.source, []).append(edge)
    return {
        source: tuple(
            sorted(
                rows,
                key=lambda edge: edge.position if edge.position is not None else -1,
            )
        )
        for source, rows in grouped.items()
    }


def _template_from_dict(payload: Mapping[str, Any]) -> ComponentTemplate:
    nodes = tuple(
        PatternNode(
            str(row["id"]),
            str(row["kind"]),
            _json(row["properties"]),
        )
        for row in payload["nodes"]
    )
    edges = tuple(
        PatternEdge(
            str(row["source"]),
            str(row["target"]),
            str(row["role"]),
            int(row["position"]),
        )
        for row in payload["edges"]
    )
    template = ComponentTemplate(
        str(payload["component_id"]),
        str(payload["root_id"]),
        nodes,
        edges,
    )
    canonical, _ = canonicalize_template(template)
    if canonical.component_id != template.component_id:
        raise ValueError("component id does not match canonical template")
    return template


def _template_variables(template: ComponentTemplate) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Mapping) and set(value) == {"$var"}:
            name = str(value["$var"])
            if name not in seen:
                seen.add(name)
                found.append(name)
            return
        if isinstance(value, Mapping):
            for key in sorted(value):
                visit(value[key])
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for node in template.nodes:
        visit(node.properties)
    return tuple(found)


def _selector_bits(component_count: int) -> int:
    return max(1, math.ceil(math.log2(component_count + 1)))


def _exact_dictionary_bits(snapshots: Sequence[Mapping[str, Any]]) -> int:
    unique = {_json(snapshot): snapshot for snapshot in snapshots}
    if not snapshots:
        return _uint_bits(0)
    selector = max(1, math.ceil(math.log2(len(unique))))
    return (
        _uint_bits(len(unique))
        + sum(value_description_bits(value) for value in unique.values())
        + _uint_bits(len(snapshots))
        + selector * len(snapshots)
    )


def _learning_shape(example: ObservationExample) -> str:
    nodes = {node.node_id: node for node in example.graph.nodes}
    children = _child_index(example.graph.edges)
    protected = {"case", "inversion", "modal", "mood", "negation", "stype", "voice", "wh"}
    memo: dict[str, int] = {}

    def shape_value(value: Any, path: tuple[str, ...]) -> Any:
        if path and path[-1] == "span":
            return "$SPAN"
        if path and path[-1] in {"category", "rule_id", "origin"}:
            return value
        if "features" in path and path and path[-1] in protected:
            return value
        if isinstance(value, Mapping):
            return {
                str(key): shape_value(child, (*path, str(key)))
                for key, child in sorted(value.items())
            }
        if isinstance(value, list):
            return [shape_value(child, (*path, str(index))) for index, child in enumerate(value)]
        return f"${type(value).__name__}"

    def visit(node_id: str) -> Any:
        if node_id in memo:
            return {"$ref": memo[node_id]}
        node = nodes[node_id]
        memo[node_id] = len(memo)
        return {
            "kind": node.kind,
            "properties": shape_value(node.properties, ()),
            "children": [
                {"role": edge.role, "position": edge.position, "node": visit(edge.target)}
                for edge in children.get(node_id, ())
            ],
        }

    return _json(visit(example.root_id))
