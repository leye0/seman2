"""POC-04: recursive, lossless composition of structural components."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .anti_unification import ComponentTemplate, PatternEdge, PatternNode
from .library import (
    _template_from_dict,
    _template_variables,
    _uint_bits,
    canonicalize_template,
    template_description_bits,
    value_description_bits,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CompositionError(ValueError):
    """A component composition is malformed or cannot be matched."""


class CompositionCycleError(CompositionError):
    """A component dependency graph contains a non-terminating cycle."""


@dataclass(frozen=True, slots=True)
class ComponentCall:
    port_variable: str
    component_id: str
    variable_map: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "port_variable": self.port_variable,
            "component_id": self.component_id,
            "variable_map": [
                {"inner": inner, "outer": outer}
                for inner, outer in self.variable_map
            ],
        }


@dataclass(frozen=True, slots=True)
class CompositeComponent:
    component_id: str
    shell: ComponentTemplate
    shell_variable_map: tuple[tuple[str, str], ...]
    calls: tuple[ComponentCall, ...]

    @property
    def dependencies(self) -> tuple[str, ...]:
        return tuple(call.component_id for call in self.calls)

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "shell": self.shell.as_dict(),
            "shell_variable_map": [
                {"inner": inner, "outer": outer}
                for inner, outer in self.shell_variable_map
            ],
            "calls": [call.as_dict() for call in self.calls],
        }


ComponentDefinition = ComponentTemplate | CompositeComponent


class ComponentComposer:
    def __init__(self) -> None:
        self.components: dict[str, ComponentDefinition] = {}

    def register_atomic(self, template: ComponentTemplate) -> ComponentTemplate:
        canonical, _ = canonicalize_template(template)
        self.components.setdefault(canonical.component_id, canonical)
        return canonical

    def as_dict(self) -> dict[str, Any]:
        definitions = []
        for component_id, component in sorted(self.components.items()):
            if isinstance(component, ComponentTemplate):
                definitions.append({"kind": "atomic", "template": component.as_dict()})
            else:
                definitions.append({"kind": "composite", **component.as_dict()})
        return {
            "schema_version": "component-composer/0.1",
            "definitions": definitions,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComponentComposer":
        if payload.get("schema_version") != "component-composer/0.1":
            raise CompositionError("unsupported component composer schema")
        composer = cls()
        pending = []
        for row in payload.get("definitions", ()):
            if row.get("kind") == "atomic":
                template = composer.register_atomic(_template_from_dict(row["template"]))
                if template.component_id != row["template"]["component_id"]:
                    raise CompositionError("non-canonical atomic component id")
            elif row.get("kind") == "composite":
                pending.append(row)
            else:
                raise CompositionError("unknown component definition kind")
        while pending:
            progressed = False
            for row in tuple(pending):
                dependencies = {call["component_id"] for call in row["calls"]}
                if not dependencies.issubset(composer.components):
                    continue
                shell = _template_from_dict(row["shell"])
                calls = tuple(
                    ComponentCall(
                        str(call["port_variable"]),
                        str(call["component_id"]),
                        tuple(
                            (str(mapping["inner"]), str(mapping["outer"]))
                            for mapping in call["variable_map"]
                        ),
                    )
                    for call in row["calls"]
                )
                shell_map = {
                    str(mapping["inner"]): str(mapping["outer"])
                    for mapping in row["shell_variable_map"]
                }
                component = composer.compose(
                    shell,
                    calls,
                    shell_variable_map=shell_map,
                )
                if component.component_id != row["component_id"]:
                    raise CompositionError("non-canonical composite component id")
                pending.remove(row)
                progressed = True
            if not progressed:
                validate_dependency_graph(
                    {
                        str(row["component_id"]): tuple(
                            str(call["component_id"]) for call in row["calls"]
                        )
                        for row in pending
                    }
                )
                raise CompositionError("unresolved component dependencies")
        return composer

    def compose(
        self,
        shell: ComponentTemplate,
        calls: Sequence[ComponentCall],
        *,
        shell_variable_map: Mapping[str, str] | None = None,
    ) -> CompositeComponent:
        canonical_shell, renamed = canonicalize_template(shell)
        normalized_calls = [
            ComponentCall(
                renamed.get(call.port_variable, call.port_variable),
                call.component_id,
                tuple(call.variable_map),
            )
            for call in calls
        ]
        port_names = {call.port_variable for call in normalized_calls}
        shell_variables = set(_template_variables(canonical_shell))
        if not port_names.issubset(shell_variables):
            raise CompositionError("a call targets an unknown shell port")
        if len(port_names) != len(normalized_calls):
            raise CompositionError("a shell port can have only one component call")
        for call in normalized_calls:
            if call.component_id not in self.components:
                raise CompositionError(f"unknown dependency: {call.component_id}")
            expected = set(self.exposed_variables(call.component_id))
            supplied = {inner for inner, _ in call.variable_map}
            if supplied != expected:
                raise CompositionError("call mapping does not cover dependency variables")

        raw_shell_map = dict(shell_variable_map or {})
        canonical_shell_map = {
            renamed.get(inner, inner): outer for inner, outer in raw_shell_map.items()
        }
        non_ports = shell_variables - port_names
        unknown = set(canonical_shell_map) - non_ports
        if unknown:
            raise CompositionError("shell mapping contains a port or unknown variable")
        for variable in non_ports:
            canonical_shell_map.setdefault(variable, variable)
        if set(canonical_shell_map) != non_ports:
            raise CompositionError("shell mapping does not cover shell variables")

        ordered_calls = sorted(
            normalized_calls,
            key=lambda call: (call.port_variable, call.component_id, call.variable_map),
        )
        outer_renames: dict[str, str] = {}

        def outer(name: str) -> str:
            return outer_renames.setdefault(name, f"X{len(outer_renames)}")

        normalized_shell_map = tuple(
            (inner, outer(canonical_shell_map[inner]))
            for inner in sorted(canonical_shell_map)
        )
        final_calls = tuple(
            ComponentCall(
                call.port_variable,
                call.component_id,
                tuple((inner, outer(target)) for inner, target in sorted(call.variable_map)),
            )
            for call in ordered_calls
        )
        body = {
            "shell": canonical_shell.as_dict(),
            "shell_variable_map": list(normalized_shell_map),
            "calls": [call.as_dict() for call in final_calls],
        }
        component_id = "composite_" + sha256(_json(body).encode("utf-8")).hexdigest()[:24]
        component = CompositeComponent(
            component_id,
            canonical_shell,
            normalized_shell_map,
            final_calls,
        )
        self.components[component_id] = component
        try:
            self.validate_acyclic()
        except CompositionCycleError:
            del self.components[component_id]
            raise
        return component

    def exposed_variables(self, component_id: str) -> tuple[str, ...]:
        component = self.components[component_id]
        if isinstance(component, ComponentTemplate):
            return _template_variables(component)
        values = {outer for _, outer in component.shell_variable_map}
        for call in component.calls:
            values.update(outer for _, outer in call.variable_map)
        return tuple(sorted(values, key=lambda name: int(name[1:]) if name[1:].isdigit() else name))

    def instantiate(
        self,
        component_id: str,
        bindings: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected = set(self.exposed_variables(component_id))
        if set(bindings) != expected:
            raise CompositionError("bindings do not exactly cover exposed variables")
        return self._instantiate(component_id, bindings, ())

    def _instantiate(
        self,
        component_id: str,
        bindings: Mapping[str, Any],
        active: tuple[str, ...],
    ) -> dict[str, Any]:
        if component_id in active:
            raise CompositionCycleError("cyclic component expansion")
        component = self.components[component_id]
        if isinstance(component, ComponentTemplate):
            return component.instantiate(bindings)
        shell_bindings = {
            inner: bindings[outer] for inner, outer in component.shell_variable_map
        }
        for call in component.calls:
            child_bindings = {
                inner: bindings[outer] for inner, outer in call.variable_map
            }
            shell_bindings[call.port_variable] = self._instantiate(
                call.component_id,
                child_bindings,
                (*active, component_id),
            )
        return component.shell.instantiate(shell_bindings)

    def match(self, component_id: str, snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
        return self._match(component_id, snapshot, ())

    def _match(
        self,
        component_id: str,
        snapshot: Mapping[str, Any],
        active: tuple[str, ...],
    ) -> dict[str, Any] | None:
        if component_id in active:
            raise CompositionCycleError("cyclic component matching")
        component = self.components[component_id]
        if isinstance(component, ComponentTemplate):
            env: dict[str, Any] = {}
            return env if _match_value(_template_pattern(component), snapshot, env) else None
        shell_env: dict[str, Any] = {}
        if not _match_value(_template_pattern(component.shell), snapshot, shell_env):
            return None
        outer_env: dict[str, Any] = {}
        for inner, outer in component.shell_variable_map:
            if not _merge(outer_env, outer, shell_env[inner]):
                return None
        for call in component.calls:
            child_snapshot = shell_env[call.port_variable]
            if not isinstance(child_snapshot, Mapping):
                return None
            child_env = self._match(
                call.component_id,
                child_snapshot,
                (*active, component_id),
            )
            if child_env is None:
                return None
            for inner, outer in call.variable_map:
                if not _merge(outer_env, outer, child_env[inner]):
                    return None
        return outer_env

    def symbolic_pattern(self, component_id: str) -> dict[str, Any]:
        return self.instantiate(
            component_id,
            {name: {"$var": name} for name in self.exposed_variables(component_id)},
        )

    def discover_composition(
        self,
        flat_template: ComponentTemplate,
        dependency_ids: Sequence[str],
    ) -> CompositeComponent | None:
        """Factor the largest matching non-root subtree into one call."""
        canonical_flat, _ = canonicalize_template(flat_template)
        nodes = {node.node_id: node for node in canonical_flat.nodes}
        outgoing = _edge_index(canonical_flat.edges)
        incoming: dict[str, int] = {}
        for edge in canonical_flat.edges:
            incoming[edge.target] = incoming.get(edge.target, 0) + 1

        choices: list[tuple[int, str, str, dict[str, str], set[str]]] = []
        for node_id in nodes:
            if node_id == canonical_flat.root_id or incoming.get(node_id, 0) != 1:
                continue
            subtree_ids = _descendants(node_id, outgoing)
            if any(
                edge.source not in subtree_ids and edge.target in subtree_ids and edge.target != node_id
                for edge in canonical_flat.edges
            ):
                continue
            flat_pattern = _template_pattern(canonical_flat, node_id)
            for dependency_id in dependency_ids:
                dependency_pattern = self.symbolic_pattern(dependency_id)
                variable_map: dict[str, str] = {}
                if _match_pattern_variables(dependency_pattern, flat_pattern, variable_map):
                    choices.append(
                        (_pattern_node_count(dependency_pattern), node_id, dependency_id, variable_map, subtree_ids)
                    )
        if not choices:
            return None
        _, target_id, dependency_id, dependency_map, removed = max(
            choices, key=lambda row: (row[0], row[1], row[2])
        )
        existing_variables = set(_template_variables(canonical_flat))
        port = "PORT0"
        while port in existing_variables:
            port = f"PORT{len(existing_variables)}"
        kept_nodes = []
        for node in canonical_flat.nodes:
            if node.node_id == target_id:
                category = node.properties.get("category")
                kept_nodes.append(
                    PatternNode(
                        node.node_id,
                        "SUBGRAPH_PORT",
                        _json({"port": {"$var": port}, "accepts_category": category}),
                    )
                )
            elif node.node_id not in removed:
                kept_nodes.append(node)
        kept_edges = tuple(
            edge for edge in canonical_flat.edges
            if edge.source not in removed and edge.target not in (removed - {target_id})
        )
        shell = ComponentTemplate(
            "shell",
            canonical_flat.root_id,
            tuple(kept_nodes),
            kept_edges,
        )
        shell_map = {
            name: name
            for name in _template_variables(shell)
            if name != port
        }
        call = ComponentCall(
            port,
            dependency_id,
            tuple(sorted(dependency_map.items())),
        )
        return self.compose(shell, (call,), shell_variable_map=shell_map)

    def validate_acyclic(self) -> None:
        dependencies = {
            component_id: component.dependencies
            if isinstance(component, CompositeComponent)
            else ()
            for component_id, component in self.components.items()
        }
        validate_dependency_graph(dependencies)


def validate_dependency_graph(dependencies: Mapping[str, Sequence[str]]) -> None:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in active:
            raise CompositionCycleError(f"cyclic dependency at {component_id}")
        if component_id in visited:
            return
        active.add(component_id)
        for dependency in dependencies.get(component_id, ()):
            if dependency not in dependencies:
                raise CompositionError(f"unknown dependency: {dependency}")
            visit(dependency)
        active.remove(component_id)
        visited.add(component_id)

    for component_id in dependencies:
        visit(component_id)


def hierarchical_model_bits(
    composer: ComponentComposer,
    root_component_ids: Sequence[str],
) -> int:
    closure: set[str] = set()

    def collect(component_id: str) -> None:
        if component_id in closure:
            return
        closure.add(component_id)
        component = composer.components[component_id]
        if isinstance(component, CompositeComponent):
            for dependency in component.dependencies:
                collect(dependency)

    for component_id in root_component_ids:
        collect(component_id)
    ordered = sorted(closure)
    indexes = {component_id: index for index, component_id in enumerate(ordered)}
    total = _uint_bits(len(ordered))
    for component_id in ordered:
        component = composer.components[component_id]
        if isinstance(component, ComponentTemplate):
            total += 1 + template_description_bits(component)
            continue
        shell_vars = _template_variables(component.shell)
        shell_indexes = {name: index for index, name in enumerate(shell_vars)}
        outer_vars = composer.exposed_variables(component_id)
        outer_indexes = {name: index for index, name in enumerate(outer_vars)}
        total += 1 + template_description_bits(component.shell) + _uint_bits(len(component.calls))
        total += sum(
            _uint_bits(shell_indexes[inner]) + _uint_bits(outer_indexes[outer])
            for inner, outer in component.shell_variable_map
        )
        for call in component.calls:
            inner_vars = composer.exposed_variables(call.component_id)
            inner_indexes = {name: index for index, name in enumerate(inner_vars)}
            total += _uint_bits(shell_indexes[call.port_variable])
            total += _uint_bits(indexes[call.component_id])
            total += _uint_bits(len(call.variable_map))
            total += sum(
                _uint_bits(inner_indexes[inner]) + _uint_bits(outer_indexes[outer])
                for inner, outer in call.variable_map
            )
    return total


def composed_instance_bits(
    composer: ComponentComposer,
    component_id: str,
    bindings: Mapping[str, Any],
    *,
    selector_bits: int = 1,
) -> int:
    variables = composer.exposed_variables(component_id)
    if set(bindings) != set(variables):
        raise CompositionError("bindings do not exactly cover exposed variables")
    return selector_bits + sum(value_description_bits(bindings[name]) for name in variables)


def composition_depth(composer: ComponentComposer, component_id: str) -> int:
    def visit(current: str, active: tuple[str, ...]) -> int:
        if current in active:
            raise CompositionCycleError("cyclic component depth")
        component = composer.components[current]
        if isinstance(component, ComponentTemplate):
            return 1
        return 1 + max(
            visit(dependency, (*active, current))
            for dependency in component.dependencies
        )

    return visit(component_id, ())


def composition_is_promotable(
    *,
    support: int,
    gain_bits: int,
    depth: int,
    min_support: int = 4,
    min_gain_bits: int = 1,
    max_depth: int = 8,
) -> bool:
    """Pre-registered guard against one-off or unbounded compositions."""
    return (
        support >= min_support
        and gain_bits >= min_gain_bits
        and 2 <= depth <= max_depth
    )


def _template_pattern(template: ComponentTemplate, root_id: str | None = None) -> dict[str, Any]:
    nodes = {node.node_id: node for node in template.nodes}
    outgoing = _edge_index(template.edges)

    def expand(node_id: str) -> dict[str, Any]:
        node = nodes[node_id]
        if node.kind == "SUBGRAPH_PORT":
            marker = node.properties.get("port")
            if not isinstance(marker, Mapping) or set(marker) != {"$var"}:
                raise CompositionError("invalid subgraph port")
            return dict(marker)
        value = node.properties
        value["children"] = [expand(edge.target) for edge in outgoing.get(node_id, ())]
        return value

    return expand(root_id or template.root_id)


def _edge_index(edges: Sequence[PatternEdge]) -> dict[str, tuple[PatternEdge, ...]]:
    grouped: dict[str, list[PatternEdge]] = {}
    for edge in edges:
        grouped.setdefault(edge.source, []).append(edge)
    return {
        source: tuple(sorted(rows, key=lambda edge: (edge.position, edge.role, edge.target)))
        for source, rows in grouped.items()
    }


def _descendants(root_id: str, outgoing: Mapping[str, Sequence[PatternEdge]]) -> set[str]:
    found: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in found:
            return
        found.add(node_id)
        for edge in outgoing.get(node_id, ()):
            visit(edge.target)

    visit(root_id)
    return found


def _match_value(pattern: Any, actual: Any, env: dict[str, Any]) -> bool:
    if isinstance(pattern, Mapping) and set(pattern) == {"$var"}:
        return _merge(env, str(pattern["$var"]), actual)
    if isinstance(pattern, Mapping) and isinstance(actual, Mapping):
        return set(pattern) == set(actual) and all(
            _match_value(pattern[key], actual[key], env) for key in pattern
        )
    if isinstance(pattern, list) and isinstance(actual, list):
        return len(pattern) == len(actual) and all(
            _match_value(left, right, env) for left, right in zip(pattern, actual)
        )
    return pattern == actual


def _merge(env: dict[str, Any], name: str, value: Any) -> bool:
    if name in env:
        return env[name] == value
    env[name] = value
    return True


def _match_pattern_variables(
    dependency: Any,
    flat: Any,
    mapping: dict[str, str],
) -> bool:
    if isinstance(dependency, Mapping) and set(dependency) == {"$var"}:
        if not isinstance(flat, Mapping) or set(flat) != {"$var"}:
            return False
        return _merge(mapping, str(dependency["$var"]), str(flat["$var"]))
    if isinstance(dependency, Mapping) and isinstance(flat, Mapping):
        return set(dependency) == set(flat) and all(
            _match_pattern_variables(dependency[key], flat[key], mapping)
            for key in dependency
        )
    if isinstance(dependency, list) and isinstance(flat, list):
        return len(dependency) == len(flat) and all(
            _match_pattern_variables(left, right, mapping)
            for left, right in zip(dependency, flat)
        )
    return dependency == flat


def _pattern_node_count(value: Any) -> int:
    if not isinstance(value, Mapping):
        return 0
    children = value.get("children", ())
    return 1 + sum(_pattern_node_count(child) for child in children)
