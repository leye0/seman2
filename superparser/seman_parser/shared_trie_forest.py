"""Experimental ONLINE category-prefix recognizer.

Unlike oracle replay, discovers constituents directly from the lexical
lattice. Grammar-rule variants share ONE prefix/span progression through
an RHS-category trie. The original rule-specific PackedPartial derivations
remain for the unchanged k-best materializer and semantic layer.

Only the preparse router may opt into this engine. Canonical remains default.
Budget behavior on saturated forests remains experimental.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .vector_chart import (
    _VectorForest, PackedPartial, PartialDerivation, RuleDerivation, intern,
)


@dataclass(slots=True)
class TrieSpec:
    transitions: dict[int,int] = field(default_factory=dict)
    variants: list[tuple[int,int]] = field(default_factory=list)


def compile_category_trie(rules:tuple[Any,...]) -> tuple[TrieSpec,...]:
    nodes=[TrieSpec()]
    for rule in rules:
        current=0
        for dot,category in enumerate(rule.rhs_ids,1):
            nxt=nodes[current].transitions.get(category)
            if nxt is None:
                nxt=len(nodes)
                nodes[current].transitions[category]=nxt
                nodes.append(TrieSpec())
            current=nxt
            nodes[current].variants.append((rule.index,dot))
    return tuple(nodes)


@dataclass(slots=True)
class SharedState:
    trie_id:int
    start:int
    end:int
    seen_edges:set[tuple[int|None,int]] = field(default_factory=set)


class SharedTrieForest(_VectorForest):
    """Recognize shared category prefixes; project all original derivations."""

    def __init__(self,compiled,lattice,*,max_items:int):
        super().__init__(compiled,lattice,max_items=max_items)
        self.trie_states:list[SharedState]=[]
        self.trie_by_key:dict[tuple[int,int,int],int]={}
        self.trie_members:dict[tuple[int,int],int]={}
        # The base waiting table now holds shared trie IDs, not partial IDs.
        self.trie_transitions=0
        self.trie_edges=0
        self.trie_duplicate_edges=0

    def _project(self,rule_index:int,dot:int,start:int,end:int,
                 prev_pid:int|None,child_id:int)->int|None:
        """Exact original rule and derivation, without per-rule waiting."""
        self.partial_proposals+=1
        key=(rule_index,dot,start,end)
        partial=self.partial_by_key.get(key)
        is_new=partial is None
        if partial is None:
            if len(self.nodes)+len(self.partials)>=self.max_items:
                self.budget_exceeded=True
                return None
            partial=PackedPartial(len(self.partials),rule_index,dot,start,end)
            self.partials.append(partial)
            self.partial_by_key[key]=partial
            self.operations+=1
        signature=(prev_pid,child_id)
        if signature not in partial.seen:
            partial.seen.add(signature)
            partial.derivations.append(PartialDerivation(prev_pid,child_id))
            self.partial_derivation_count+=1
        else:
            self.duplicate_partial_proposals+=1
        if is_new:
            rule=self.compiled.rules[rule_index]
            if dot==len(rule.rhs_ids):
                self._add_node_derivation(
                    start,end,rule.lhs_id,rule.rule.lhs.category,rule.lhs_mask,
                    RuleDerivation(rule_index,partial.partial_id),
                    ("rule",rule_index,partial.partial_id))
        return partial.partial_id

    def _group(self,trie_id:int,start:int,end:int,
               previous_id:int|None,child_id:int)->None:
        if self.budget_exceeded:
            return
        key=(trie_id,start,end)
        gid=self.trie_by_key.get(key)
        new=gid is None
        if new:
            gid=len(self.trie_states)
            self.trie_by_key[key]=gid
            self.trie_states.append(SharedState(trie_id,start,end))
        group=self.trie_states[gid]
        edge=(previous_id,child_id)
        if edge in group.seen_edges:
            self.trie_duplicate_edges+=1
            return
        group.seen_edges.add(edge)
        self.trie_edges+=1
        self.trie_transitions+=1
        for rule_index,dot in self.compiled.trie_nodes[trie_id].variants:
            prev_rule_partial=(None if previous_id is None else
                self.trie_members.get((previous_id,rule_index)))
            if previous_id is not None and prev_rule_partial is None:
                raise AssertionError("Lost predecessor for rule variant")
            pid=self._project(rule_index,dot,start,end,
                              prev_rule_partial,child_id)
            if pid is None:
                return
            ref=(gid,rule_index)
            existing=self.trie_members.get(ref)
            if existing is None:
                self.trie_members[ref]=pid
            elif existing!=pid:
                raise AssertionError("Rule variant changed partial identity")
            if self.budget_exceeded:
                return
        if not new:
            return
        pos=self._next_start(end)
        for category,child_trie in self.compiled.trie_nodes[trie_id].transitions.items():
            self.waiting.setdefault((pos,category),[]).append(gid)
            for node in tuple(self.by_start_category.get((pos,category),())):
                self._group(child_trie,start,node.end,gid,node.node_id)
                if self.budget_exceeded:
                    return

    def recognize(self,goal_category:str):
        self._seed_lexicon()
        root=self.compiled.trie_nodes[0].transitions
        cursor=0
        while cursor<len(self.agenda) and not self.budget_exceeded:
            node=self.nodes[self.agenda[cursor]]
            cursor+=1
            self.operations+=1
            initial=root.get(node.category_id)
            if initial is not None:
                self._group(initial,node.start,node.end,None,node.node_id)
            if self.budget_exceeded:
                break
            waiting=self.waiting.get((node.start,node.category_id),())
            self.duplicate_transitions_avoided+=len(waiting)-node.waiting_cutoff
            for gid in tuple(waiting[:node.waiting_cutoff]):
                old=self.trie_states[gid]
                following=self.compiled.trie_nodes[old.trie_id].transitions[
                    node.category_id]
                self._group(following,old.start,node.end,gid,node.node_id)
                if self.budget_exceeded:
                    break
        goal_id=intern(goal_category)
        return tuple(node for node in self.nodes
                     if node.category_id==goal_id
                     and self._root_span(node.start,node.end))
