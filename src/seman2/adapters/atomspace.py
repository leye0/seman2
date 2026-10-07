"""AtomSpace projection for Seman2's generic learned-structure ledger."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..evidence.store import canonical_json
from ..learning.store import LearningStore


class AtomSpaceAdapter:
    """Synchronize immutable ledger objects into a live local AtomSpace."""

    def __init__(self, *, strict: bool = False) -> None:
        self.atomspace: Any | None = None
        self.types: Any | None = None
        self._error: str | None = None
        try:
            from opencog.atomspace import AtomSpace, types  # type: ignore

            self.atomspace = AtomSpace()
            self.types = types
            try:
                from opencog.utilities import initialize_opencog  # type: ignore

                initialize_opencog(self.atomspace)
            except (ImportError, AttributeError):
                pass
        except (ImportError, OSError, RuntimeError) as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            if strict:
                raise RuntimeError(f"local AtomSpace unavailable: {exc}") from exc

    @property
    def available(self) -> bool:
        return self.atomspace is not None and self.types is not None

    @property
    def status(self) -> dict[str, Any]:
        return {"available": self.available, "error": self._error, "mode": "local-in-process"}

    def _node(self, kind: str, name: str) -> Any:
        assert self.atomspace is not None and self.types is not None
        node_type = getattr(self.types, kind)
        return self.atomspace.add_node(node_type, name)

    def _link(self, kind: str, outgoing: Iterable[Any]) -> Any:
        assert self.atomspace is not None and self.types is not None
        link_type = getattr(self.types, kind)
        return self.atomspace.add_link(link_type, list(outgoing))

    def put(self, kind: str, object_id: str, payload: Mapping[str, Any]) -> None:
        if not self.available:
            raise RuntimeError(self._error or "local AtomSpace unavailable")
        object_node = self._node("ConceptNode", f"seman2:{kind}:{object_id}")
        kind_node = self._node("ConceptNode", f"seman2:object-kind:{kind}")
        payload_node = self._node("ConceptNode", "seman2:json:" + canonical_json(payload))
        family = self._node("PredicateNode", "seman2:object-kind")
        content = self._node("PredicateNode", "seman2:payload")
        self._link("EvaluationLink", [family, self._link("ListLink", [object_node, kind_node])])
        self._link("EvaluationLink", [content, self._link("ListLink", [object_node, payload_node])])
        if kind == "relation":
            source = payload.get("source")
            target = payload.get("target")
            relation = payload.get("relation")
            if all(isinstance(value, str) for value in (source, target, relation)):
                predicate = self._node("PredicateNode", f"seman2:relation:{relation}")
                source_node = self._node("ConceptNode", f"seman2:structure:{source}")
                target_node = self._node("ConceptNode", f"seman2:structure:{target}")
                self._link(
                    "EvaluationLink",
                    [predicate, self._link("ListLink", [source_node, target_node])],
                )

    def synchronize(self, store: LearningStore, *, limit: int = 1000) -> dict[str, Any]:
        if not self.available:
            return {"synchronized": 0, "pending": len(store.pending_sync(limit=limit)), **self.status}
        synchronized = 0
        for row in store.pending_sync(limit=limit):
            try:
                self.put(row["kind"], row["id"], row["payload"])
                store.mark_synchronized(row["sequence"])
                synchronized += 1
            except Exception as exc:
                store.mark_sync_error(row["sequence"], f"{type(exc).__name__}: {exc}")
                raise
        return {"synchronized": synchronized, "pending": len(store.pending_sync(limit=limit)), **self.status}
