"""Generic multi-factor ranking without learned-category branches."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from ..evidence.store import canonical_json


def _flatten(value: Any, prefix: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}/{key}"
            result.add(path)
            result.update(_flatten(item, path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{prefix}/*"))
    else:
        result.add(f"{prefix}={canonical_json(value)}")
    return result


def structural_similarity(left: Any, right: Any) -> float:
    left_features = _flatten(left)
    right_features = _flatten(right)
    if not left_features and not right_features:
        return 1.0
    union = left_features | right_features
    return len(left_features & right_features) / len(union) if union else 0.0


def rank_components(
    *,
    compatibility: float,
    support: int,
    compression: float = 0.0,
    context_fit: float = 0.0,
    provenance_weight: float = 1.0,
) -> dict[str, float]:
    values = {
        "compatibility": max(0.0, compatibility),
        "support": math.log2(1.0 + max(0, support)),
        "compression": compression,
        "context_fit": context_fit,
        "provenance_weight": max(0.0, provenance_weight),
    }
    values["total"] = (
        0.40 * values["compatibility"]
        + 0.20 * values["support"]
        + 0.15 * values["compression"]
        + 0.15 * values["context_fit"]
        + 0.10 * values["provenance_weight"]
    )
    return values


def rank_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -float(row.get("score", {}).get("total", 0.0)),
                str(row.get("id", "")),
            ),
        )
    )
