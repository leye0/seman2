"""Recurrence index and growth-based induction.

Selection is empirical: only motifs that already recur become candidates,
only candidates grow, and only by attaching pieces actually observed next
to them. Compression, non-redundancy and predictive fit decide what is
solidified — not raw frequency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Iterable, Mapping, Sequence

from ..evidence.store import canonical_json
from .structures import digest, exact_fingerprint, shape


class RecurrenceIndex:
    """hash -> (count, first_seen, last_seen, supports). O(1) update, O(1) lookup."""

    __slots__ = ("_counts", "_supports", "_first_seen", "_last_seen")

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._supports: dict[str, list[str]] = {}
        self._first_seen: dict[str, float] = {}
        self._last_seen: dict[str, float] = {}

    def add(self, key: str, support_id: str, *, now: float | None = None) -> None:
        stamp = time.monotonic() if now is None else now
        self._counts[key] = self._counts.get(key, 0) + 1
        rows = self._supports.get(key)
        if rows is None:
            self._supports[key] = [support_id]
            self._first_seen[key] = stamp
        elif support_id not in rows:
            rows.append(support_id)
        self._last_seen[key] = stamp

    def count(self, key: str) -> int:
        return self._counts.get(key, 0)

    def first_seen(self, key: str) -> float | None:
        return self._first_seen.get(key)

    def last_seen(self, key: str) -> float | None:
        return self._last_seen.get(key)

    def age(self, key: str, *, now: float | None = None) -> float | None:
        stamp = self._first_seen.get(key)
        if stamp is None:
            return None
        return (time.monotonic() if now is None else now) - stamp

    def staleness(self, key: str, *, now: float | None = None) -> float | None:
        stamp = self._last_seen.get(key)
        if stamp is None:
            return None
        return (time.monotonic() if now is None else now) - stamp

    def supports(self, key: str) -> tuple[str, ...]:
        rows = self._supports.get(key)
        return tuple(rows) if rows else ()

    def keys(self) -> tuple[str, ...]:
        return tuple(self._counts)

    def frequent(self, minimum: int) -> tuple[tuple[str, int], ...]:
        rows = [(key, n) for key, n in self._counts.items() if n >= minimum]
        rows.sort(key=lambda item: (-item[1], item[0]))
        return tuple(rows)

    def entries(self) -> tuple[tuple[str, int, float, float], ...]:
        """Every entry with its count, first_seen and last_seen timestamps."""
        return tuple(
            (key, self._counts[key], self._first_seen[key], self._last_seen[key])
            for key in self._counts
        )

    def forget_older_than(self, cutoff: float) -> int:
        """Drop entries not seen since ``cutoff`` (a monotonic timestamp)."""
        stale = [key for key, stamp in self._last_seen.items() if stamp < cutoff]
        for key in stale:
            del self._counts[key]
            del self._supports[key]
            del self._first_seen[key]
            del self._last_seen[key]
        return len(stale)

    def __len__(self) -> int:
        return len(self._counts)


@dataclass(frozen=True, slots=True)
class GrowthCandidate:
    """A recurring motif under consideration for solidification."""

    key: str
    tree: Mapping[str, Any]
    support: int
    supports: tuple[str, ...]
    extensions_tried: frozenset[str] = frozenset()
    parent_key: str | None = None
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "tree": dict(self.tree),
            "support": self.support,
            "supports": list(self.supports),
            "parent_key": self.parent_key,
            "score": self.score,
        }


def _tree_nodes(tree: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(tree, Mapping):
        nodes.append(dict(tree))
        for key in ("children", "nodes"):
            for child in tree.get(key, ()) or ():
                nodes.extend(_tree_nodes(child))
    elif isinstance(tree, (list, tuple)):
        for child in tree:
            nodes.extend(_tree_nodes(child))
    return nodes


def _frontier_slots(tree: Any) -> tuple[str, ...]:
    slots: list[str] = []
    for node in _tree_nodes(tree):
        if "frontier" in node and not node.get("children"):
            slots.append(str(node.get("fingerprint") or node.get("category") or "?"))
        if node.get("frontier") is True:
            slots.append(str(node.get("category") or "?"))
    return tuple(slots)


def _shape_key(value: Any) -> str:
    """Stable fingerprint of topology-with-values-erased; cheap to compare."""
    return canonical_json(shape(value))


def compression_ratio(instances: Sequence[Mapping[str, Any]], pattern: Mapping[str, Any]) -> float:
    """MDL-style gain: how much the motif compresses its instances."""
    if not instances:
        return 0.0
    pattern_key = _shape_key(pattern)
    pattern_len = float(len(pattern_key))
    independent = 0.0
    compressed = pattern_len
    for item in instances:
        key = _shape_key(item)
        independent += float(len(key))
        compressed += float(len(key))
    if independent <= 0:
        return 0.0
    gain = independent - compressed + pattern_len
    return max(0.0, gain / (independent + pattern_len))


def novelty_score(
    candidate: Mapping[str, Any],
    solidified_keys: Sequence[str],
) -> float:
    """Non-redundancy: a motif that adds nothing beyond solidified ones scores 0."""
    if not solidified_keys:
        return 1.0
    candidate_key = _shape_key(candidate)
    candidate_tokens = set(candidate_key)
    best = 0.0
    for existing_key in solidified_keys:
        existing_tokens = set(existing_key)
        union = candidate_tokens | existing_tokens
        if not union:
            similarity = 1.0
        else:
            similarity = len(candidate_tokens & existing_tokens) / len(union)
        if similarity > best:
            best = similarity
    return max(0.0, 1.0 - best)


def predictiveness(candidate: Mapping[str, Any], observation_keys: Sequence[str]) -> float:
    """How often the motif's shape occurs across held-out observations."""
    if not observation_keys:
        return 0.0
    target = _shape_key(candidate)
    hits = sum(1 for key in observation_keys if key == target)
    return hits / len(observation_keys)


def alignment_stability(alignment_counts: Mapping[str, int]) -> float:
    """Stable alignments beat one-off ones; empty means unaligned."""
    if not alignment_counts:
        return 0.0
    total = sum(alignment_counts.values())
    if total <= 0:
        return 0.0
    return max(alignment_counts.values()) / total


def rank_candidate(
    *,
    compression: float,
    novelty: float,
    prediction: float,
    alignment: float,
    support: int,
) -> float:
    """Decide what to solidify. Frequency is only a mild factor."""
    return (
        0.35 * max(0.0, compression)
        + 0.30 * max(0.0, novelty)
        + 0.20 * max(0.0, prediction)
        + 0.10 * max(0.0, alignment)
        + 0.05 * (support / (support + 10.0))
    )


@dataclass
class GrowthInducer:
    """Recurrence to select, local growth to explore, scoring to solidify."""

    minimum_support: int = 2
    max_candidates: int = 256
    max_extensions_per_candidate: int = 8
    exploration_rate: float = 0.05

    def __init__(self, **kwargs: Any) -> None:
        for name, value in kwargs.items():
            setattr(self, name, value)
        self._shape_cache: dict[str, str] = {}

    def _cached_shape_key(self, fingerprint: str, value: Any) -> str:
        key = self._shape_cache.get(fingerprint)
        if key is None:
            key = _shape_key(value)
            self._shape_cache[fingerprint] = key
        return key

    def select(
        self,
        index: RecurrenceIndex,
        payloads: Mapping[str, Mapping[str, Any]],
    ) -> list[GrowthCandidate]:
        """Keep only motifs that already recur enough to be worth examining."""
        chosen: list[GrowthCandidate] = []
        for key, count in index.frequent(self.minimum_support):
            if len(chosen) >= self.max_candidates:
                break
            payload = payloads.get(key)
            if payload is None:
                continue
            chosen.append(
                GrowthCandidate(
                    key=key,
                    tree=payload,
                    support=count,
                    supports=index.supports(key),
                )
            )
        return chosen

    def grow(
        self,
        candidate: GrowthCandidate,
        neighbors: Mapping[str, Sequence[str]],
        index: RecurrenceIndex,
        payloads: Mapping[str, Mapping[str, Any]],
        rng: Any = None,
    ) -> list[GrowthCandidate]:
        """Local growth: attach only pieces actually observed next to this motif."""
        extensions: list[GrowthCandidate] = []
        slots = _frontier_slots(candidate.tree)
        connected = list(neighbors.get(candidate.key, ()))
        if rng is not None and len(connected) > self.max_extensions_per_candidate:
            # A little exploration, never the main engine.
            connected = rng.sample(connected, self.max_extensions_per_candidate)
        else:
            connected = connected[: self.max_extensions_per_candidate]
        for neighbor_key in connected:
            if neighbor_key in candidate.extensions_tried:
                continue
            neighbor = payloads.get(neighbor_key)
            if neighbor is None:
                continue
            combined = _combine(candidate.tree, neighbor, slots)
            if combined is None:
                continue
            combined_key = exact_fingerprint(combined)
            if index.count(combined_key) < self.minimum_support:
                # Never grew here in the data: do not keep the branch.
                continue
            extensions.append(
                GrowthCandidate(
                    key=combined_key,
                    tree=combined,
                    support=index.count(combined_key),
                    supports=index.supports(combined_key),
                    extensions_tried=frozenset(
                        (*candidate.extensions_tried, neighbor_key)
                    ),
                    parent_key=candidate.key,
                )
            )
        return extensions

    def solidify(
        self,
        candidates: Sequence[GrowthCandidate],
        *,
        payloads: Mapping[str, Mapping[str, Any]],
        observations: Sequence[str],
        alignment_counts: Mapping[str, int],
        already_solidified: Sequence[str] = (),
    ) -> tuple[GrowthCandidate, ...]:
        """Score and keep only motifs that compress, add and predict."""
        scored: list[GrowthCandidate] = []
        solidified_keys: list[str] = list(already_solidified)
        observation_set = set(observations)
        observation_total = max(1, len(observations))
        for candidate in candidates:
            candidate_key = self._cached_shape_key(candidate.key, candidate.tree)
            instance_keys = [
                self._cached_shape_key(key, payloads[key])
                for key in candidate.supports
                if key in payloads
            ] or [candidate_key]
            compression = max(
                0.0,
                (len(set(instance_keys)) / max(1, len(instance_keys)))
                * (1.0 - len(candidate_key) / (len(candidate_key) + 1000.0)),
            )
            novelty = novelty_score(candidate.tree, solidified_keys)
            prediction = (
                1.0 if candidate_key in observation_set else 0.0
            ) + (candidate.support / observation_total)
            alignment = alignment_stability(alignment_counts)
            score = rank_candidate(
                compression=compression,
                novelty=novelty,
                prediction=min(1.0, prediction),
                alignment=alignment,
                support=candidate.support,
            )
            scored.append(
                GrowthCandidate(
                    key=candidate.key,
                    tree=candidate.tree,
                    support=candidate.support,
                    supports=candidate.supports,
                    extensions_tried=candidate.extensions_tried,
                    parent_key=candidate.parent_key,
                    score=score,
                )
            )
        scored.sort(key=lambda row: (-row.score, row.key))
        kept = [
            row
            for row in scored
            if row.score > 0.15 and row.support >= self.minimum_support
        ]
        for row in kept:
            solidified_keys.append(self._cached_shape_key(row.key, row.tree))
        return tuple(kept)


def _combine(
    tree: Mapping[str, Any],
    neighbor: Mapping[str, Any],
    slots: Sequence[str],
) -> dict[str, Any] | None:
    """Attach a neighbor into a frontier slot of the tree.

    Only a structural graft: no semantic label is invented. Returns None
    when the two shapes cannot be joined without inventing structure.
    """
    if not slots:
        return None
    merged = {
        "family": "grown-structure",
        "root": dict(tree),
        "extension": dict(neighbor),
        "slots": list(slots),
        "joined": True,
    }
    return merged
