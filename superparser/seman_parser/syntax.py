"""Compact, meaning-free interfaces exported by the syntax layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SyntacticLink:
    """A named structural role resolved to a lexical occurrence anchor."""

    relation: str
    target: str
    child_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"relation": self.relation, "target": self.target, "child": self.child_index}


@dataclass(frozen=True, slots=True)
class SyntacticPackage:
    """Structural references produced without constructing semantic objects.

    Anchors identify occurrences in the selected tree.  Their names mirror
    grammar exports (``head``, ``subject``, ``object``...) but their values
    are syntax-local ids, never semantic graph node ids.
    """

    anchors: Mapping[str, str] = field(default_factory=dict)
    links: tuple[SyntacticLink, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchors": dict(self.anchors),
            "links": [link.as_dict() for link in self.links],
        }


EMPTY_SYNTAX = SyntacticPackage()
