"""Research-only lazy projection of ONLINE shared category-prefix states.

This is the critical departure from per-rule postprocessing: recognition
creates ONLY shared prefix/span groups. A lightweight integer describes each
original rule/dot variant, but PackedPartial objects and derivation lists are
generated ON DEMAND by k-best. Every variant and all original features,
scores, role recipes and lexical provenance survive in the grammar.

NOT the default parser and NOT enabled by the adaptive router until proved.
"""
from __future__ import annotations

from array import array
from collections.abc import Iterator,Sequence
from dataclasses import dataclass,field
from typing import Any

from .shared_trie_forest import SharedTrieForest
from .vector_chart import PackedPartial,PartialDerivation,RuleDerivation


@dataclass(slots=True)
class LazyGroup:
    trie_id:int
    start:int
    end:int
    first_partial:int
    edges:list[tuple[int|None,int]]=field(default_factory=list)
    seen:set[tuple[int|None,int]]=field(default_factory=set)


class LazyRuleDerivations(Sequence):
    """Original partial derivations projected from group edges on demand."""

    __slots__=("table","group_id","rule_index","_edge_cache")

    def __init__(self,table:"VirtualPartials",group_id:int,rule_index:int):
        self.table=table
        self.group_id=group_id
        self.rule_index=rule_index
        # Allocate nothing until the k-best materializer really accesses
        # this rule's edges; repeated rank probes reuse the same objects.
        self._edge_cache=None

    def __len__(self)->int:
        return len(self.table.forest.trie_states[self.group_id].edges)

    def __getitem__(self,index):
        edges=self.table.forest.trie_states[self.group_id].edges
        if isinstance(index,slice):
            return [self[i] for i in range(*index.indices(len(edges)))]
        if self._edge_cache is None:
            self._edge_cache=[None]*len(edges)
        else:
            cached=self._edge_cache[index]
            if cached is not None:
                return cached
        prev,child=edges[index]
        if prev is None:
            pid=None
        else:
            previous=self.table.forest.trie_states[prev]
            offset=self.table.forest.compiled.trie_variant_offsets[
                previous.trie_id].get(self.rule_index)
            if offset is None:
                raise AssertionError("Trie rule variant predecessor missing")
            pid=previous.first_partial+offset
        decoded=PartialDerivation(pid,child)
        self._edge_cache[index]=decoded
        return decoded

    def __iter__(self)->Iterator[PartialDerivation]:
        for index in range(len(self)):
            yield self[index]


class VirtualPartials(Sequence):
    """Dense original partial IDs, but no eager PackedPartial allocations."""

    __slots__=("forest","gid_for_pid","cached")

    def __init__(self,forest:"LazySharedTrieForest") -> None:
        self.forest=forest
        self.gid_for_pid=array("I")
        self.cached:dict[int,PackedPartial]={}

    def __len__(self)->int:
        return len(self.gid_for_pid)

    def register(self,gid:int,count:int)->int:
        base=len(self.gid_for_pid)
        self.gid_for_pid.extend([gid]*count)
        return base

    def __getitem__(self,pid):
        if isinstance(pid,slice):
            return [self[i] for i in range(*pid.indices(len(self)))]
        if pid<0:
            pid+=len(self)
        if pid<0 or pid>=len(self):
            raise IndexError(pid)
        found=self.cached.get(pid)
        if found is not None:
            return found
        group=self.forest.trie_states[self.gid_for_pid[pid]]
        rule_index,dot=self.forest.compiled.trie_nodes[
            group.trie_id].variants[pid-group.first_partial]
        partial=PackedPartial(pid,rule_index,dot,group.start,group.end)
        partial.derivations=LazyRuleDerivations(
            self,self.gid_for_pid[pid],rule_index)
        partial.seen=None
        self.cached[pid]=partial
        return partial


class LazySharedTrieForest(SharedTrieForest):
    """Recognize grammar prefixes ONCE; project original rule only for k-best."""

    def __init__(self,compiled,lattice,*,max_items:int):
        super().__init__(compiled,lattice,max_items=max_items)
        self.partials=VirtualPartials(self)
        self.trie_states:list[LazyGroup]=[]
        self.trie_members.clear()
        self.virtual_complete_rules=0
        self.virtual_groups_allocated=0

    def _group(self,trie_id:int,start:int,end:int,
               previous_id:int|None,child_id:int)->None:
        if self.budget_exceeded:
            return
        key=(trie_id,start,end)
        gid=self.trie_by_key.get(key)
        fresh=gid is None
        rule_variants=self.compiled.trie_nodes[trie_id].variants
        if fresh:
            # Equivalent logical rule-partial cap, NOT a discounted group
            # count. A saturated forest is still uncertified until a
            # canonical-order fairness proof exists.
            if len(self.nodes)+len(self.partials)+len(rule_variants)>self.max_items:
                self.budget_exceeded=True
                return
            gid=len(self.trie_states)
            self.trie_by_key[key]=gid
            first=self.partials.register(gid,len(rule_variants))
            group=LazyGroup(trie_id,start,end,first)
            self.trie_states.append(group)
            self.operations+=len(rule_variants)
            self.virtual_groups_allocated+=1
        else:
            group=self.trie_states[gid]
        edge=(previous_id,child_id)
        if edge in group.seen:
            self.trie_duplicate_edges+=1
            return
        group.seen.add(edge)
        group.edges.append(edge)
        self.trie_edges+=1
        self.trie_transitions+=1
        self.partial_proposals+=len(rule_variants)
        self.partial_derivation_count+=len(rule_variants)
        if not fresh:
            return
        # Completed original rules create the SAME kinds of constituent
        # nodes and RuleDerivation(rule index, original partial ID). The
        # actual partial and its previous-edge path remain virtual.
        for offset,(rule_index,dot) in enumerate(rule_variants):
            rule=self.compiled.rules[rule_index]
            if dot==len(rule.rhs_ids):
                self.virtual_complete_rules+=1
                self._add_node_derivation(
                    start,end,rule.lhs_id,rule.rule.lhs.category,
                    rule.lhs_mask,
                    RuleDerivation(rule_index,group.first_partial+offset),
                    ("rule",rule_index,group.first_partial+offset))
        pos=self._next_start(end)
        for category,child_trie in self.compiled.trie_nodes[
                trie_id].transitions.items():
            self.waiting.setdefault((pos,category),[]).append(gid)
            for node in tuple(self.by_start_category.get((pos,category),())):
                self._group(child_trie,start,node.end,gid,node.node_id)
                if self.budget_exceeded:
                    return
