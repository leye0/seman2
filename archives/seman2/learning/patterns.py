"""Anti-unification, compression scoring and recursive abstraction."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..evidence.store import canonical_json
from .structures import digest, shape


def anti_unify(values: Sequence[Any]) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """Return the most specific common structure plus per-instance bindings."""
    if not values:
        raise ValueError("anti-unification needs at least one value")
    bindings: list[dict[str, Any]] = [dict() for _ in values]
    counter = [0]

    def walk(items: Sequence[Any]) -> Any:
        first = items[0]
        if all(item == first for item in items[1:]):
            return first
        if all(isinstance(item, Mapping) for item in items):
            common = set(items[0])
            for item in items[1:]:
                common.intersection_update(item)
            return {key: walk([item[key] for item in items]) for key in sorted(common)}
        if all(isinstance(item, (list, tuple)) for item in items):
            lengths = {len(item) for item in items}
            if len(lengths) == 1:
                return [walk([item[index] for item in items]) for index in range(len(first))]
        variable = f"$v{counter[0]}"
        counter[0] += 1
        for index, item in enumerate(items):
            bindings[index][variable] = item
        return {"variable": variable, "shape": shape(items)}

    return walk(values), tuple(bindings)


def description_length(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def compression_score(instances: Sequence[Any], pattern: Any, bindings: Sequence[Any]) -> dict[str, float]:
    independent = float(sum(description_length(item) for item in instances))
    compressed = float(description_length(pattern) + sum(description_length(item) for item in bindings))
    gain = independent - compressed
    ratio = gain / independent if independent else 0.0
    support = float(len(instances))
    stability = 1.0 / (1.0 + sum(len(item) for item in bindings) / max(1, len(bindings)))
    return {
        "independent_bytes": independent,
        "compressed_bytes": compressed,
        "gain_bytes": gain,
        "compression_ratio": ratio,
        "support": support,
        "stability": stability,
        "rank": ratio * math.log2(1.0 + support) * stability,
    }


def induce_pattern(instances: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    generalized, bindings = anti_unify(instances)
    scores = compression_score(instances, generalized, bindings)
    payload = {
        "generalized": generalized,
        "instance_count": len(instances),
        "shape": shape(generalized),
        "scores": scores,
    }
    return {
        "pattern_id": digest("pattern", payload),
        "fingerprint": digest("fp", shape(generalized), length=64).removeprefix("fp_"),
        "payload": payload,
        "bindings": bindings,
        "scores": scores,
    }


def instantiate(pattern: Any, bindings: Mapping[str, Any]) -> Any:
    if isinstance(pattern, Mapping):
        if set(pattern) >= {"variable"}:
            variable = pattern["variable"]
            return bindings.get(variable, pattern)
        return {key: instantiate(value, bindings) for key, value in pattern.items()}
    if isinstance(pattern, list):
        return [instantiate(value, bindings) for value in pattern]
    return pattern


def match_pattern(pattern: Any, instance: Any) -> dict[str, Any] | None:
    bindings: dict[str, Any] = {}

    def walk(left: Any, right: Any) -> bool:
        if isinstance(left, Mapping) and "variable" in left:
            variable = left["variable"]
            if variable in bindings:
                return bindings[variable] == right
            bindings[variable] = right
            return True
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            return all(key in right and walk(value, right[key]) for key, value in left.items())
        if isinstance(left, list) and isinstance(right, (list, tuple)):
            return len(left) == len(right) and all(walk(a, b) for a, b in zip(left, right))
        return left == right

    return bindings if walk(pattern, instance) else None
