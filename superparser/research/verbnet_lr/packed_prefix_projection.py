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
from bisect import bisect_left
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


class FlatPrefixProjection:
    """Read-only *physical* packing using contiguous fixed-width integer arrays.

    A previous group and a rule index identify the exact predecessor partial.
    Each group maintains a SORTED, flat membership index to resolve it. Edge
    indices remain in their per-variant original order (important for tied
    k-best scores and reproducible derivation enumeration).

    This representation is not itself a live forest recognizer: its mutable
    insert/lookup indexes are discarded. Runtime integration will need an
    efficient transient build index, budget discipline and online updates.
    """
    __slots__=(
        "group_of","variant_rule","variant_offsets","variant_edges",
        "group_edge_offsets","prev_groups","children",
        "member_offsets","member_rules","member_ids")

    def __init__(self,source:PrefixProjection):
        self.group_of=array("i",source.group_of)
        self.variant_rule=array("i",source.variant_rule)
        self.variant_offsets=array("I",[0])
        self.variant_edges=array("I")
        for edges in source.variant_edges:
            self.variant_edges.extend(edges)
            self.variant_offsets.append(len(self.variant_edges))
        self.group_edge_offsets=array("I",[0])
        self.prev_groups=array("i")
        self.children=array("i")
        self.member_offsets=array("I",[0])
        self.member_rules=array("i")
        self.member_ids=array("i")
        for group in source.groups:
            self.prev_groups.extend(group.previous_groups)
            self.children.extend(group.children)
            self.group_edge_offsets.append(len(self.children))
            # Rule IDs are unique per (shared group,variant). Preserve sorted
            # membership for binary-search resolution without hash maps.
            members=sorted(
                ((source.variant_rule[pid],pid) for pid in group.members))
            for rule,pid in members:
                self.member_rules.append(rule)
                self.member_ids.append(pid)
            self.member_offsets.append(len(self.member_rules))

    def reconstruct(self,partial_id:int)->list[tuple[int|None,int]]:
        gid=self.group_of[partial_id]
        rule=self.variant_rule[partial_id]
        start=self.variant_offsets[partial_id]
        stop=self.variant_offsets[partial_id+1]
        base=self.group_edge_offsets[gid]
        result=[]
        for offset in self.variant_edges[start:stop]:
            eid=base+offset
            prev_group=self.prev_groups[eid]
            if prev_group < 0:
                prev=None
            else:
                left=self.member_offsets[prev_group]
                right=self.member_offsets[prev_group+1]
                idx=bisect_left(self.member_rules,rule,left,right)
                if idx==right or self.member_rules[idx]!=rule:
                    raise KeyError(
                        f"No predecessor variant for group={prev_group}, "
                        f"rule={rule}")
                prev=self.member_ids[idx]
            result.append((prev,self.children[eid]))
        return result

    def metrics(self,forest:Any)->dict[str,int|float]:
        original=sum(len(p.derivations) for p in forest.partials)
        interned=len(self.children)
        fields=self.__slots__
        # Include ALL owned storage in the read-only representation,
        # including rule-group membership and ordered variant edges.
        bytes_allocated=sum(sys.getsizeof(getattr(self,key)) for key in fields)
        original_edge_bytes=sum(
            sys.getsizeof(p.derivations)
            +sum(sys.getsizeof(edge) for edge in p.derivations)
            for p in forest.partials)
        return {
            "partial_variants":len(self.variant_rule),
            "prefix_groups":len(self.member_offsets)-1,
            "original_edges":original,
            "unique_edges":interned,
            "flat_arrays_bytes":bytes_allocated,
            "original_list_and_edge_bytes":original_edge_bytes,
            "flat_over_original_edge_bytes":round(
                bytes_allocated/original_edge_bytes,5)
                if original_edge_bytes else 0.0,
            "unique_edge_ratio":round(interned/original,5)
                if original else 0.0,
        }

    def verify(self,forest:Any)->int:
        checked=0
        for partial in forest.partials:
            expected=[(d.previous_id,d.child_id) for d in partial.derivations]
            if self.reconstruct(partial.partial_id)!=expected:
                raise AssertionError(
                    f"Flat prefix packing changed ordered edges for "
                    f"partial {partial.partial_id}")
            checked+=len(expected)
        return checked


def pack_flat(forest:Any,*,validate:bool=True)->FlatPrefixProjection:
    """Offline conversion, for evidence only; leaves canonical forest intact."""
    view=build_projection(forest,validate=validate)
    flat=FlatPrefixProjection(view)
    if validate:
        flat.verify(forest)
    return flat


def pack_flat_direct(forest:Any,*,validate:bool=True)->FlatPrefixProjection:
    """Construct the same read-only packed layout DIRECTLY from the forest.

    Unlike pack_flat(), this never instantiates a PrefixGroup or one small
    array per original rule variant. It uses temporary indexes while packing,
    then keeps only fixed-width contiguous arrays in the returned object.
    This is still an offline conversion and does not alter recognition.
    """
    partials=forest.partials
    rule_prefixes={}
    group_ids={}
    group_of=array("i")
    variant_rule=array("i")
    # Pass 1: assign a shared consumed-prefix group to every old state.
    for part in partials:
        if part.partial_id!=len(group_of):
            raise ValueError("Expected densely indexed partial IDs")
        rk=(part.rule_index,part.dot)
        prefix=rule_prefixes.get(rk)
        if prefix is None:
            rule=forest.compiled.rules[part.rule_index].rule
            prefix=json.dumps(
                [s.as_dict() for s in rule.rhs[:part.dot]],sort_keys=True,
                separators=(",",":"),ensure_ascii=False)
            rule_prefixes[rk]=prefix
        key=(part.start,part.end,part.dot,prefix)
        gid=group_ids.get(key)
        if gid is None:
            gid=len(group_ids)
            group_ids[key]=gid
        group_of.append(gid)
        variant_rule.append(part.rule_index)
    n_groups=len(group_ids)
    del group_ids,rule_prefixes

    # Pass 2: intern edge evidence globally while retaining its original
    # per-variant ordering. Intermediate edge IDs are global, not yet local
    # to groups; contiguous packing happens in pass 3.
    edge_ids={}
    edge_triples=[]
    old_edge_refs=array("I")
    variant_offsets=array("I",[0])
    for part in partials:
        gid=group_of[part.partial_id]
        for derivation in part.derivations:
            prev=(-1 if derivation.previous_id is None
                  else group_of[derivation.previous_id])
            key=(gid,prev,derivation.child_id)
            eid=edge_ids.get(key)
            if eid is None:
                eid=len(edge_triples)
                edge_ids[key]=eid
                edge_triples.append(key)
            old_edge_refs.append(eid)
        variant_offsets.append(len(old_edge_refs))
    del edge_ids

    # Pass 3: physically lay out edges by group; remap original variant
    # references to local edge offsets. No small Python per-group objects.
    counts=array("I",[0])*n_groups
    for gid,_,_ in edge_triples:
        counts[gid]+=1
    starts=array("I",[0])
    for n in counts:
        starts.append(starts[-1]+n)
    cursor=array("I",[0])*n_groups
    remap=array("I",[0])*len(edge_triples)
    prev_groups=array("i",[0])*len(edge_triples)
    children=array("i",[0])*len(edge_triples)
    for eid,(gid,prev,child) in enumerate(edge_triples):
        local=cursor[gid]
        cursor[gid]+=1
        position=starts[gid]+local
        remap[eid]=local
        prev_groups[position]=prev
        children[position]=child
    variant_edges=array("I",(remap[eid] for eid in old_edge_refs))
    del edge_triples,old_edge_refs,remap,counts,cursor

    # Pass 4: flat sorted membership records permit rule-specific parent
    # projection by binary search (previous_group, same_rule_index).
    members=sorted((group_of[p.partial_id],p.rule_index,p.partial_id)
                   for p in partials)
    member_offsets=array("I",[0])
    member_rules=array("i")
    member_ids=array("i")
    at=0
    for gid in range(n_groups):
        while at<len(members) and members[at][0]==gid:
            _,rule,pid=members[at]
            member_rules.append(rule)
            member_ids.append(pid)
            at+=1
        member_offsets.append(at)
    if at!=len(members):
        raise AssertionError("Unassigned shared-prefix variants")

    # Construct without an object-based PrefixProjection intermediary.
    flat=FlatPrefixProjection.__new__(FlatPrefixProjection)
    flat.group_of=group_of
    flat.variant_rule=variant_rule
    flat.variant_offsets=variant_offsets
    flat.variant_edges=variant_edges
    flat.group_edge_offsets=starts
    flat.prev_groups=prev_groups
    flat.children=children
    flat.member_offsets=member_offsets
    flat.member_rules=member_rules
    flat.member_ids=member_ids
    if validate:
        flat.verify(forest)
    return flat
