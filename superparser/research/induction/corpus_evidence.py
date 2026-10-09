"""Extraction helpers restricted to the cached 849-observation real corpus."""

from __future__ import annotations

import json
from pathlib import Path

from .latent_referents import SubstitutionObservation
from .latent_relations import RelationObservation
from .observation_graph import ObservationGraph
from .partial_state import PartialState, ReportedProposition
from .transitions import EventOccurrence, TransitionEpisode


POSITIVE_REFERENCE_KINDS = frozenset(
    {"ASSERTED_IDENTITY", "BOUND_VARIABLE", "TYPE_ANAPHORA"}
)
NEGATIVE_REFERENCE_KINDS = frozenset({"DIFFERENT_REF", "NO_LINK"})


def load_real_corpus(cache_dir: str | Path, *, required: int = 849) -> list[ObservationGraph]:
    cache_dir = Path(cache_dir)
    paths = [
        path for path in cache_dir.glob("the_map_of_everything_nlp_novel-lines-500-*.jsonl")
        if "cases-10" not in path.name
    ]
    if not paths:
        raise FileNotFoundError("compact 849-observation cache is missing")
    graphs = []
    with max(paths, key=lambda path: path.stat().st_mtime).open(encoding="utf-8") as handle:
        next(handle)
        graphs = [ObservationGraph.from_dict(json.loads(raw)["graph"]) for raw in handle]
    if len(graphs) != required:
        raise ValueError(f"expected {required} observations, found {len(graphs)}")
    return graphs


def referent_substitution_observations(
    graphs: list[ObservationGraph], *, offset: int = 0
) -> list[SubstitutionObservation]:
    """Extract opaque grammatical substitution evidence from real graphs."""
    rows = []
    for graph_index, graph in enumerate(graphs, offset):
        nodes = {node.node_id: node for node in graph.nodes}
        for edge in graph.edges:
            if edge.role != "CHILD":
                continue
            child, parent = nodes[edge.target], nodes[edge.source]
            if child.kind != "CONSTITUENT" or child.properties.get("category") not in {
                "N", "PROPER-NOUN", "PRONOUN"
            }:
                continue
            lemma = child.properties.get("lemma")
            if lemma:
                rows.append(
                    SubstitutionObservation(
                        str(lemma).lower(),
                        f"{parent.properties.get('category')}:{parent.properties.get('rule_id')}",
                        f"{edge.position}:{child.properties.get('category')}",
                        f"{graph_index}:{child.node_id}",
                    )
                )
    return rows


def reference_relation_observations(
    graphs: list[ObservationGraph], *, offset: int = 0
) -> list[RelationObservation]:
    rows = []
    accepted = POSITIVE_REFERENCE_KINDS | NEGATIVE_REFERENCE_KINDS
    for graph_index, graph in enumerate(graphs, offset):
        nodes = {node.node_id: node for node in graph.nodes}
        for edge in graph.edges:
            kind = edge.properties.get("kind")
            if edge.role != "REFERENCE" or kind not in accepted:
                continue
            source, target = nodes[edge.source], nodes[edge.target]
            domain = (
                f"{source.kind}:{source.properties.get('kind', 'anchor')}->"
                f"{target.kind}:{target.properties.get('kind', 'anchor')}"
            )
            rows.append(
                RelationObservation(
                    str(graph_index),
                    domain,
                    edge.source,
                    edge.target,
                    str(edge.properties["rule_id"]),
                    kind in POSITIVE_REFERENCE_KINDS,
                )
            )
    return rows


def reference_partial_states(graphs: list[ObservationGraph], *, offset: int = 0) -> list[PartialState]:
    states = []
    for graph_index, graph in enumerate(graphs, offset):
        nodes = {node.node_id: node for node in graph.nodes}
        propositions = []
        for edge in graph.edges:
            kind = edge.properties.get("kind")
            if edge.role != "REFERENCE" or kind not in (
                POSITIVE_REFERENCE_KINDS | NEGATIVE_REFERENCE_KINDS
            ):
                continue
            if edge.source not in nodes or edge.target not in nodes:
                continue
            propositions.append(
                ReportedProposition(
                    str(edge.properties["rule_id"]),
                    (edge.source, edge.target),
                    kind in POSITIVE_REFERENCE_KINDS,
                )
            )
        states.append(
            PartialState.build(
                f"observation-{graph_index}",
                "narrative-source",
                graph_index,
                propositions,
            )
        )
    return states


def reference_transition_episodes(graphs: list[ObservationGraph]) -> list[TransitionEpisode]:
    states = reference_partial_states(graphs)
    episodes = []
    for graph_index in range(1, len(graphs)):
        graph = graphs[graph_index]
        current_mentions = [
            node for node in graph.nodes
            if node.kind == "MENTION" and node.properties.get("sentence") == graph_index
        ]
        events = [node for node in current_mentions if node.properties.get("kind") == "event"]
        arguments = tuple(
            node.node_id
            for node in sorted(
                current_mentions,
                key=lambda node: (node.properties.get("span", [0])[0], node.node_id),
            )
        )
        root = next((node for node in graph.nodes if node.node_id in graph.root_ids), None)
        features = root.properties.get("features", {}) if root else {}
        polarity = str(features.get("negation", "false")).lower() not in {"true", "yes", "1"}
        mode = "question" if features.get("stype") in {"question", "interrogative"} else "asserted"
        context = str(root.properties.get("rule_id") if root else "no-root")
        for event_index, event_node in enumerate(events):
            event_id = f"{graph_index}:{event_index}"
            event = EventOccurrence(
                event_id,
                str(event_node.properties.get("head_lemma") or event_node.properties.get("surface")),
                arguments,
                "narrative-source",
                graph_index,
                polarity,
                mode,
            )
            episodes.append(
                TransitionEpisode(
                    event_id,
                    context,
                    states[graph_index - 1],
                    event,
                    states[graph_index],
                )
            )
    return episodes
