"""Research-only, reversible physical interning of packed grammar prefixes.

This module does NOT replace the recognizer or change any parse output. It
constructs a candidate factored *edge representation* from a completed
_VectorForest, and proves that every original rule-specific derivation edge
can be reproduced, in its ORIGINAL order. Actual runtime adoption requires
a separate online implementation and independent speed/memory measurements.

Sharing consumes exact RHS prefix symbols (category, features, required
evidence, exports). Rule identity, future RHS, LHS, scores, syntax and
semantics remain rule-specific. A group is never a grammatical derivation.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass, field
import json
import sys
from typing import Any


@dataclass(slots=True)
class PrefixGroup:
    """One shared recognition-prefix envelope; no rule-specific claims."""
    start: int
    end: int
    dot: int
    signature: str
    # Parallel C-integer arrays: -1 encodes an absent previous prefix.
    previous_groups: array = field(default_factory=lambda: array("i"))
    children: array = field(default_factory=lambda: array("i"))
    members: list[int] = field(default_factory=list)
    _edge_to_index: dict[tuple[int,int],int] = field(default_factory=dict,repr=False)

    def intern(self, previous_group: int, child: int) -> int:
        edge=(previous_group,child)
        old=self._edge_to_index.get(edge)
        if old is not None:
            return old
        idx=len(self.children)
        self.previous_groups.append(previous_group)
        self.children.append(child)
        self._edge_to_index[edge]=idx
        return idx

    def finish(self) -> None:
        # The lookup is only needed during construction; in a real runtime,
        # it would need to survive while new edges can still be appended.
        self._edge_to_index.clear()
        self._edge_to_index={}


class PrefixProjection:
    """Exact derivation order recovered from shared prefix edges + variants.

    One variant per original PackedPartial; the projection deliberately does
    NOT combine scores, feature bindings or grammar-rule semantic actions.
    """
    def __init__(self, groups: list[PrefixGroup], group_of: array,
                 variant_edges: list[array], variant_rule: array,
                 by_group_rule: dict[tuple[int,int],int]) -> None:
        self.groups=groups
        self.group_of=group_of
        self.variant_edges=variant_edges
        self.variant_rule=variant_rule
        self.by_group_rule=by_group_rule

    def reconstruct(self, partial_id: int) -> list[tuple[int | None,int]]:
        group=self.groups[self.group_of[partial_id]]
        rule_id=self.variant_rule[partial_id]
        output=[]
        for edge_idx in self.variant_edges[partial_id]:
            previous_group=group.previous_groups[edge_idx]
            previous=(None if previous_group < 0 else
                      self.by_group_rule[(previous_group,rule_id)])
            output.append((previous,group.children[edge_idx]))
        return output

    def metrics(self,forest:Any) -> dict[str,int|float]:
        original_edges=sum(len(p.derivations) for p in forest.partials)
        shared_edges=sum(len(g.children) for g in self.groups)
        # Include index vectors and group mappings, not just unique edges.
        # These are shallow in-process sizes for the EDGE REPRESENTATIONS,
        # not end-to-end resident memory / allocations of a future parser.
        old_edge_bytes=sum(
            sys.getsizeof(p.derivations)+sum(sys.getsizeof(d) for d in p.derivations)
            for p in forest.partials)
        compact_bytes=(
            sys.getsizeof(self.groups)+sys.getsizeof(self.group_of)
            +sys.getsizeof(self.variant_edges)+sys.getsizeof(self.variant_rule)
            +sys.getsizeof(self.by_group_rule)
            +sum(sys.getsizeof(x) for x in self.variant_edges)
            +sum(sys.getsizeof(g)+sys.getsizeof(g.members)
                +sys.getsizeof(g.previous_groups)+sys.getsizeof(g.children)
                for g in self.groups)
        )
        return {
            "partials":len(forest.partials),
            "shared_groups":len(self.groups),
            "variant_links":sum(len(g.members) for g in self.groups),
            "original_edges":original_edges,
            "interned_edges":shared_edges,
            "reused_edge_occurrences":original_edges-shared_edges,
            "edge_reuse_rate":round(1-shared_edges/original_edges,5)
                              if original_edges else 0.0,
            "original_edge_objects_estimated_bytes":old_edge_bytes,
            "projected_edge_objects_estimated_bytes":compact_bytes,
            "edge_representation_byte_ratio":round(compact_bytes/old_edge_bytes,5)
                              if old_edge_bytes else 0.0,
        }


def build_projection(forest:Any,*,validate:bool=True) -> PrefixProjection:
    """Build a compact, independently decodable representation of the DAG.

    Group identifiers refer only to *syntactic prefix evidence*. Previous
    derivation links are projected using (previous_group, same_rule_index).
    This reconstruction rule is checked for every edge, including on
    forests which terminated at a budget boundary.
    """
    parts=forest.partials
    rule_prefixes={}
    groups=[]
    group_index={}
    group_of=array("i")
    variant_rule=array("i")
    by_group_rule={}
    for partial in parts:
        if partial.partial_id!=len(group_of):
            raise ValueError("Expected densely indexed canonical partial IDs")
        pair=(partial.rule_index,partial.dot)
        prefix=rule_prefixes.get(pair)
        if prefix is None:
            rule=forest.compiled.rules[partial.rule_index].rule
            prefix=json.dumps(
                [symbol.as_dict() for symbol in rule.rhs[:partial.dot]],
                sort_keys=True,separators=(",",":"),ensure_ascii=False)
            rule_prefixes[pair]=prefix
        key=(partial.start,partial.end,partial.dot,prefix)
        gid=group_index.get(key)
        if gid is None:
            gid=len(groups)
            group_index[key]=gid
            groups.append(PrefixGroup(partial.start,partial.end,
                                      partial.dot,prefix))
        groups[gid].members.append(partial.partial_id)
        group_of.append(gid)
        variant_rule.append(partial.rule_index)
        ref=(gid,partial.rule_index)
        if ref in by_group_rule:
            raise ValueError("A rule variant has two states for one prefix span")
        by_group_rule[ref]=partial.partial_id

    variant_edges=[]
    for partial in parts:
        group=groups[group_of[partial.partial_id]]
        indexes=array("I")
        for derivation in partial.derivations:
            prev=(-1 if derivation.previous_id is None
                  else group_of[derivation.previous_id])
            indexes.append(group.intern(prev,derivation.child_id))
        variant_edges.append(indexes)
    for group in groups:
        group.finish()
    view=PrefixProjection(groups,group_of,variant_edges,
                          variant_rule,by_group_rule)
    if validate:
        for partial in parts:
            original=[(d.previous_id,d.child_id) for d in partial.derivations]
            actual=view.reconstruct(partial.partial_id)
            if actual!=original:
                raise AssertionError(
                    "Prefix projection changed ordered derivation "
                    f"for partial_id={partial.partial_id}")
    return view
