"""Semantic recipes keyed by syntax rule id.

This module is intentionally not imported by the parser or grammar loader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SemanticAction:
    kind: str
    args: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **dict(self.args)}


def parse_action(raw: Mapping[str, Any]) -> SemanticAction:
    payload = dict(raw)
    if "kind" in payload:
        return SemanticAction(str(payload.pop("kind")), payload)
    if "op" in payload:
        return SemanticAction(str(payload.pop("op")), payload)
    if len(payload) == 1:
        kind, body = next(iter(payload.items()))
        return SemanticAction(
            str(kind), dict(body) if isinstance(body, Mapping) else {"value": body},
        )
    return SemanticAction("copy", payload)


def load_semantic_rules(path: str | Path) -> dict[str, tuple[SemanticAction, ...]]:
    """Load only the semantic sidecar embedded in legacy grammar JSONL."""
    result: dict[str, tuple[SemanticAction, ...]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            raw = json.loads(line)
            actions = tuple(parse_action(row) for row in raw.get("semantic", ()))
            if actions:
                result[str(raw["id"])] = actions
    return result
