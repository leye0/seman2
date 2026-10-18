"""Opt-in online sharing of exact consumed-prefix *recognition edges*.

All canonical rule-specific partial IDs and their insertion order survive.
No grammar rule, feature constraint, score, lexical reading or derivation is
discarded. The shared group is an edge store, not an accepted phrase.

Each live PackedPartial owns only a compact array of ordered references
into its group's interned (previous group, child node) edges. A lazy
read-only view reconstructs original PartialDerivation objects on demand.
The original rule-specific predecessor ID is recovered from group membership.

This is an experimental representation. Mutable indexes and Python group
objects remain present during recognition; actual RSS and speed are not
assumed to improve without measurement.
"""
from __future__ import annotations

from array import array
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from sys import getsizeof
from typing import Any, Callable


@dataclass(slots=True)
class _PrefixGroup:
    prev_groups: array = field(default_factory=lambda: array("i"))
    child_ids: array = field(default_factory=lambda: array("i"))
    edge_lookup: dict[tuple[int, int], int] = field(default_factory=dict)
    members: dict[int, int] = field(default_factory=dict)


class PrefixEdgeView(Sequence):
    """A rule-specific ordered list view; no stored PartialDerivation objects."""

    __slots__ = ("store", "group_id", "rule_index", "edge_ids")

    def __init__(self, store: "OnlinePrefixEdges", group_id: int,
                 rule_index: int) -> None:
        self.store = store
        self.group_id = group_id
        self.rule_index = rule_index
        self.edge_ids = array("I")

    def __len__(self) -> int:
        return len(self.edge_ids)

    def __getitem__(self, index: int | slice) -> Any:
        if isinstance(index, slice):
            return [self[j] for j in range(*index.indices(len(self)))]
        edge_index = self.edge_ids[index]
        group = self.store.groups[self.group_id]
        prev_group = group.prev_groups[edge_index]
        predecessor = (None if prev_group == -1 else
                       self.store.groups[prev_group].members[self.rule_index])
        return self.store.edge_factory(predecessor, group.child_ids[edge_index])

    def __iter__(self) -> Iterator[Any]:
        for i in range(len(self.edge_ids)):
            yield self[i]

    def append(self, previous_id: int | None, child_id: int) -> bool:
        """Append an original derivation once, with original ordering."""
        store = self.store
        previous_group = (-1 if previous_id is None
                          else store.group_of[previous_id])
        if previous_id is not None:
            actual = store.groups[previous_group].members.get(self.rule_index)
            if actual != previous_id:
                raise AssertionError(
                    "A previous partial must retain the exact same rule index")
        group = store.groups[self.group_id]
        edge = (previous_group, child_id)
        idx = group.edge_lookup.get(edge)
        if idx is None:
            idx = len(group.child_ids)
            group.edge_lookup[edge] = idx
            group.prev_groups.append(previous_group)
            group.child_ids.append(child_id)
            store.unique_edges += 1
        else:
            store.shared_edge_hits += 1
        # A canonical partial may be offered a duplicate derivation.
        # Most variants have one or two edges; avoid allocating a Python
        # set per partial unless measurements justify that overhead.
        if idx in self.edge_ids:
            return False
        self.edge_ids.append(idx)
        return True


class OnlinePrefixEdges:
    """Sentence-local prefix interning during forest recognition."""

    def __init__(self, prefix_ids: tuple[tuple[int, ...], ...],
                 edge_factory: Callable[[int | None, int], Any]) -> None:
        self.prefix_ids = prefix_ids
        self.edge_factory = edge_factory
        self.groups: list[_PrefixGroup] = []
        self.group_by_key: dict[tuple[int, int, int, int], int] = {}
        self.group_of: array = array("i")
        self.unique_edges = 0
        self.shared_edge_hits = 0

    def register(self, partial: Any) -> PrefixEdgeView:
        if partial.partial_id != len(self.group_of):
            raise AssertionError("Prefix store requires stable dense partial IDs")
        prefix = self.prefix_ids[partial.rule_index][partial.dot]
        key = (partial.start, partial.end, partial.dot, prefix)
        gid = self.group_by_key.get(key)
        if gid is None:
            gid = len(self.groups)
            self.group_by_key[key] = gid
            self.groups.append(_PrefixGroup())
        group = self.groups[gid]
        if partial.rule_index in group.members:
            raise AssertionError("Duplicate rule-specific prefix state")
        group.members[partial.rule_index] = partial.partial_id
        self.group_of.append(gid)
        return PrefixEdgeView(self, gid, partial.rule_index)

    def diagnostics(self) -> dict[str, int]:
        """Read-only diagnostics; does not claim real process peak memory."""
        return {
            "online_prefix_groups": len(self.groups),
            "online_prefix_unique_edges": self.unique_edges,
            "online_prefix_shared_edge_hits": self.shared_edge_hits,
            "online_prefix_member_count": len(self.group_of),
            "online_prefix_array_bytes": (
                getsizeof(self.group_of)
                + sum(getsizeof(g.prev_groups)+getsizeof(g.child_ids)
                      for g in self.groups)),
        }



class FlatOnlineEdgeView(Sequence):
    """Ordered per-rule derivations projected lazily from global arrays."""

    __slots__=("store","partial_id")

    def __init__(self,store:"FlatOnlinePrefixEdges",partial_id:int):
        self.store=store
        self.partial_id=partial_id

    def __len__(self)->int:
        return self.store.variant_count[self.partial_id]

    def _decode(self,occurrence:int)->Any:
        store=self.store
        edge=store.occurrence_edges[occurrence]
        prev_group=store.edge_prev_groups[edge]
        previous=(None if prev_group<0 else store.members[
            (prev_group,store.variant_rules[self.partial_id])])
        return store.edge_factory(previous,store.edge_children[edge])

    def __getitem__(self,index:int|slice)->Any:
        if isinstance(index,slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        total=len(self)
        if index<0:
            index+=total
        if index<0 or index>=total:
            raise IndexError(index)
        cursor=self.store.variant_first[self.partial_id]
        for _ in range(index):
            cursor=self.store.occurrence_next[cursor]
        return self._decode(cursor)

    def __iter__(self)->Iterator[Any]:
        store=self.store
        cursor=store.variant_first[self.partial_id]
        while cursor>=0:
            yield self._decode(cursor)
            cursor=store.occurrence_next[cursor]

    def append(self,previous_id:int|None,child_id:int)->bool:
        store=self.store
        pid=self.partial_id
        group=store.group_of[pid]
        previous_group=(-1 if previous_id is None
                        else store.group_of[previous_id])
        if previous_id is not None and store.members.get(
            (previous_group,store.variant_rules[pid]))!=previous_id:
            raise AssertionError("Rule-specific predecessor mismatch")
        signature=(group,previous_group,child_id)
        edge=store.edge_lookup.get(signature)
        if edge is None:
            edge=len(store.edge_children)
            store.edge_lookup[signature]=edge
            store.edge_prev_groups.append(previous_group)
            store.edge_children.append(child_id)
        else:
            store.shared_edge_hits+=1
        cursor=store.variant_first[pid]
        while cursor>=0:
            if store.occurrence_edges[cursor]==edge:
                return False
            cursor=store.occurrence_next[cursor]
        occurrence=len(store.occurrence_edges)
        store.occurrence_edges.append(edge)
        store.occurrence_next.append(-1)
        if store.variant_first[pid]<0:
            store.variant_first[pid]=occurrence
        else:
            store.occurrence_next[store.variant_last[pid]]=occurrence
        store.variant_last[pid]=occurrence
        store.variant_count[pid]+=1
        return True


class FlatOnlinePrefixEdges:
    """Incremental interned edge DAG using GLOBAL arrays, not group objects.

    Temporary hash indexes are still needed for deduplication. A live
    conversion is compared against a canonical forest, including every edge
    and all lazy k-best candidates, before considering production use.
    """
    __slots__=(
        "prefix_ids","edge_factory","group_by_key","members","group_of",
        "variant_rules","variant_first","variant_last","variant_count",
        "edge_lookup","edge_prev_groups","edge_children",
        "occurrence_edges","occurrence_next","shared_edge_hits")

    def __init__(self,prefix_ids:tuple[tuple[int,...],...],
                 edge_factory:Callable[[int|None,int],Any])->None:
        self.prefix_ids=prefix_ids
        self.edge_factory=edge_factory
        self.group_by_key:dict[tuple[int,int,int,int],int]={}
        self.members:dict[tuple[int,int],int]={}
        self.group_of=array("i")
        self.variant_rules=array("i")
        self.variant_first=array("i")
        self.variant_last=array("i")
        self.variant_count=array("I")
        self.edge_lookup:dict[tuple[int,int,int],int]={}
        self.edge_prev_groups=array("i")
        self.edge_children=array("i")
        self.occurrence_edges=array("I")
        self.occurrence_next=array("i")
        self.shared_edge_hits=0

    def register(self,partial:Any)->FlatOnlineEdgeView:
        pid=partial.partial_id
        if pid!=len(self.group_of):
            raise AssertionError("Expected densely indexed rule partials")
        prefix=self.prefix_ids[partial.rule_index][partial.dot]
        key=(partial.start,partial.end,partial.dot,prefix)
        group=self.group_by_key.get(key)
        if group is None:
            group=len(self.group_by_key)
            self.group_by_key[key]=group
        member=(group,partial.rule_index)
        if member in self.members:
            raise AssertionError("Rule variants must not be merged")
        self.members[member]=pid
        self.group_of.append(group)
        self.variant_rules.append(partial.rule_index)
        self.variant_first.append(-1)
        self.variant_last.append(-1)
        self.variant_count.append(0)
        return FlatOnlineEdgeView(self,pid)

    def diagnostics(self)->dict[str,int]:
        return {
            "online_prefix_groups":len(self.group_by_key),
            "online_prefix_unique_edges":len(self.edge_children),
            "online_prefix_shared_edge_hits":self.shared_edge_hits,
            "online_prefix_member_count":len(self.variant_rules),
            "online_prefix_array_bytes":sum(getsizeof(getattr(self,key))
                     for key in ("group_of","variant_rules","variant_first",
                                 "variant_last","variant_count","edge_prev_groups",
                                 "edge_children","occurrence_edges",
                                 "occurrence_next")),
        }
