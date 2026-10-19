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
    _VectorForest, intern,
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


class TrieRecognitionBase(_VectorForest):
    """Only the common-prefix agenda shared by the active lazy trie.

    Rule-specific partial states are NOT created here. The subclass
    implements _group with compact virtual partial IDs and derivation views.
    """

    def __init__(self, compiled, lattice, *, max_items: int):
        super().__init__(compiled, lattice, max_items=max_items)
        self.trie_states = []
        self.trie_by_key: dict[tuple[int, int, int], int] = {}
        self.trie_transitions = 0
        self.trie_edges = 0
        self.trie_duplicate_edges = 0

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
