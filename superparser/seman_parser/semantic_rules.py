"""Semantic recipes keyed by syntax rule id.

This module is intentionally not imported by the parser or grammar loader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class SemanticAction:
    kind: str
    args: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **dict(self.args)}


def parse_action(raw: Mapping[str, Any]) -> SemanticAction:
    payload = dict(raw)
    if "kind" in payload:
        kind = str(payload.pop("kind"))
    elif "op" in payload:
        kind = str(payload.pop("op"))
    elif len(payload) == 1:
        kind, body = next(iter(payload.items()))
        payload = dict(body) if isinstance(body, Mapping) else {"value": body}
    else:
        kind = "copy"
    if kind == "compose" and "links" in payload:
        payload["links"] = [
            expanded for link in payload["links"] for expanded in _expand_link(link)
        ]
    return SemanticAction(kind, payload)


def _expand_link(link: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Distribute a declared relation across one ordered endpoint list.

    This is data shorthand for identical individual links, not inference
    about argument sharing. In particular, it cannot introduce a Cartesian
    product or introduce endpoints the recipe did not name.
    """
    plural = [name for name in ("sources", "targets") if name in link]
    if not plural:
        return (link,)
    if len(plural) != 1:
        raise ValueError("A semantic link can distribute only one endpoint")
    name, = plural
    singular = name[:-1]
    other = "target" if singular == "source" else "source"
    endpoints = link[name]
    if (singular in link or other not in link
            or not isinstance(endpoints, (tuple, list)) or not endpoints):
        raise ValueError(f"A semantic link with {name} needs a nonempty list and one {other}")
    rest = {key: value for key, value in link.items() if key != name}
    return tuple({**rest, singular: endpoint} for endpoint in endpoints)


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
