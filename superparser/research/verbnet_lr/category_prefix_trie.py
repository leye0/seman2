"""Category-prefix trie recognizer over an existing canonical forest.

EXPERIMENTAL / NOT a drop-in parser. This replays the category/span evidence
already discovered by canonical VectorGrammar, using ONE trie progression for
multiple grammar rule variants. The canonical forest remains the oracle for
which constituent nodes exist; no standalone grammatical result is claimed.

Unlike storing the same per-rule edges compactly, this actually performs a
single prefix/category transition per trie state and then projects back to
each original rule/dot when needed. Feature constraints, rule score and
semantic actions are NEVER merged: they remain in compiled.rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class _TrieNode:
    transitions: dict[int,int] = field(default_factory=dict)
    variants: list[tuple[int,int]] = field(default_factory=list)


@dataclass(slots=True)
class _TrieState:
    trie_node: int
    start: int
    end: int
    # (previous trie-state ID or None, child canonical forest-node ID)
    edges: set[tuple[int | None,int]] = field(default_factory=set)


class CategoryPrefixTrie:
    """One category path for all matching RHS rule variants."""

    def __init__(self,compiled:Any)->None:
        self.nodes=[_TrieNode()]
        self.member_node:dict[tuple[int,int],int]={}
        for rule in compiled.rules:
            current=0
            for dot,category in enumerate(rule.rhs_ids,1):
                child=self.nodes[current].transitions.get(category)
                if child is None:
                    child=len(self.nodes)
                    self.nodes[current].transitions[category]=child
                    self.nodes.append(_TrieNode())
                current=child
                self.nodes[current].variants.append((rule.index,dot))
                self.member_node[(rule.index,dot)]=current

    def replay(self,forest:Any,*,check_canonical:bool=True)->dict[str,Any]:
        """Recognize shared prefixes from *already-discovered* category nodes.

        This function never edits forest.partials, nodes or semantic rules.
        On nonsaturated forests it can verify that shared trie states and
        group edges project to the exact same rule-specific partial states.
        """
        text=forest.text
        preserve=forest.compiled.preserve_quote_delimiters
        separators=(' \\t\\r\\n' if preserve
                    else ' \\t\\r\\n"\\u201c\\u201d\\u2018\\u2019')
        next_start=[0]*(len(text)+1)
        next_start[len(text)]=len(text)
        for pos in range(len(text)-1,-1,-1):
            next_start[pos]=(next_start[pos+1]
                             if text[pos] in separators else pos)
        state_ids:dict[tuple[int,int,int],int]={}
        states:list[_TrieState]=[]
        proposed_edges=0

        def push(tid:int,start:int,end:int,previous:int|None,child:int)->None:
            nonlocal proposed_edges
            proposed_edges+=1
            key=(tid,start,end)
            sid=state_ids.get(key)
            if sid is None:
                sid=len(states)
                state_ids[key]=sid
                states.append(_TrieState(tid,start,end))
            states[sid].edges.add((previous,child))

        # Initial terminals/phrases are already grouped into canonical
        # category nodes. No need to seed each rule separately.
        root=self.nodes[0].transitions
        for node in forest.nodes:
            tid=root.get(node.category_id)
            if tid is not None:
                push(tid,node.start,node.end,None,node.node_id)

        cursor=0
        transition_lookups=0
        while cursor<len(states):
            state=states[cursor]
            cursor+=1
            pos=next_start[state.end]
            for category,tid in self.nodes[state.trie_node].transitions.items():
                transition_lookups+=1
                for node in forest.by_start_category.get((pos,category),()):
                    push(tid,state.start,node.end,cursor-1,node.node_id)

        # Project only the ORIGINAL variants; there is no lexical reading
        # filtering or fabricated grammar acceptance. A grouped prefix may
        # contain many distinct rules, each still owning its semantics.
        projected:dict[tuple[int,int,int,int],int]={}
        for group in states:
            for rule_index,dot in self.nodes[group.trie_node].variants:
                key=(rule_index,dot,group.start,group.end)
                if key in projected:
                    raise AssertionError("Overlapping projected partials")
                projected[key]=state_ids[(group.trie_node,group.start,group.end)]

        canonical_keys={
            (p.rule_index,p.dot,p.start,p.end):p.partial_id
            for p in forest.partials
        }
        verified=0
        failures=[]
        if check_canonical and not forest.budget_exceeded:
            absent=set(canonical_keys)-set(projected)
            extra=set(projected)-set(canonical_keys)
            if absent or extra:
                failures.append({
                    "missing_canonical":len(absent),
                    "extra_projected":len(extra),
                    "sample_missing":list(absent)[:3],
                    "sample_extra":list(extra)[:3],
                })
            # Check logical edge sets using group-level previous state IDs.
            for key,pid in canonical_keys.items():
                sid=projected.get(key)
                if sid is None:
                    continue
                actual=states[sid].edges
                expected={
                    (None if derivation.previous_id is None else
                     projected.get((
                         forest.partials[derivation.previous_id].rule_index,
                         forest.partials[derivation.previous_id].dot,
                         forest.partials[derivation.previous_id].start,
                         forest.partials[derivation.previous_id].end,
                     )),derivation.child_id)
                    for derivation in forest.partials[pid].derivations
                }
                if expected != actual:
                    failures.append({"partial":list(key),
                                     "expected":len(expected),
                                     "observed":len(actual)})
                    if len(failures)>=12:
                        break
                else:
                    verified+=len(expected)

        result={
            "canonical_partial_states":len(forest.partials),
            "shared_prefix_states":len(states),
            "projected_rule_states":len(projected),
            "canonical_partial_edges":sum(len(p.derivations)
                                          for p in forest.partials),
            "unique_shared_prefix_edges":sum(len(s.edges) for s in states),
            "prefix_transitions_checked":transition_lookups,
            "shared_proposals":proposed_edges,
            "trie_nodes":len(self.nodes),
            "verified_edges":verified,
            "saturated":forest.budget_exceeded,
            "comparison_skipped_due_to_budget":bool(forest.budget_exceeded),
            "projection_failures":failures,
        }
        if check_canonical and not forest.budget_exceeded and failures:
            raise AssertionError(
                f"Trie replay cannot yet reproduce canonical prefixes: {failures[:2]}")
        return result
