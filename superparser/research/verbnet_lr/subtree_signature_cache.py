"""Research-only cache of *observed* grammatical SUBTREE signatures.

This is a conservative adaptation of Seman2's historical full-tree
snapping research to long, ambiguous sentences.

An observation is a completed, feature-unified ChartItem subtree from the
canonical Layer 1 materializer (NOT human-labelled gold). The cache indexes
its whole immutable rule-ID tree shape and its actual lexical leaf category
sequence, WITHOUT memorising words, names, lexical senses, or raw text.
Queries test all possible lexical category readings without cross-product
enumeration, using a bounded category trie.

A hit is ONLY A HINT. It may never produce a ForestNode, ChartItem,
ParseResult, completion, grammatical acceptance, or semantic claim. No
candidate is removed from the original lexical lattice. In particular, a
matched category signature does not guarantee compatible morphology,
variable scope, valence, rule context or attachment. The normal recognizer
and feature-unifying k-best materializer remain authoritative.

This design intentionally separates measured lookup utility from the
future engineering of sound reuse. Unknown/missing evidence remains UNKNOWN.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Hashable


@dataclass(frozen=True, slots=True)
class ObservedSubtree:
    categories: tuple[str, ...]
    root_category: str
    root_rule: str
    # Complete tree of grammar rule IDs + categories; lexical leaves have
    # category only. There is no word, lemma, surface or relative offset.
    shape: Hashable


@dataclass(frozen=True, slots=True)
class SignatureHint:
    start_token: int
    end_token: int
    start_char: int
    end_char: int
    template_id: int
    root_category: str
    root_rule: str


@dataclass(frozen=True, slots=True)
class SignatureScan:
    matches: tuple[SignatureHint, ...]
    transitions: int
    saturated: bool
    lexical_tokens: int


@dataclass(slots=True)
class _Trie:
    edges: dict[str, int] = field(default_factory=dict)
    template_ids: list[int] = field(default_factory=list)


def _tree_description(item: Any):
    """Return grammar tree signature and lexical leaves in surface order."""
    if item.lexical_candidate is not None and not item.children:
        candidate = item.lexical_candidate
        if item.rule_id:
            return None
        return (("lex", candidate.category), (
            (candidate.span_start, candidate.span_end, candidate.category),
        ))
    if not item.rule_id or not item.children:
        return None
    children = []
    leaves = []
    for child in item.children:
        data = _tree_description(child)
        if data is None:
            return None
        shape, child_leaves = data
        children.append(shape)
        leaves.extend(child_leaves)
    return (("rule", item.rule_id, item.category, tuple(children)),
            tuple(leaves))


def _observed(item: Any, lattice: Any, *, min_tokens: int, max_tokens: int):
    """Only contiguous, one-token-per-leaf, full-span observations qualify.

    A multiword candidate, gap, overlap, extra punctuation, or interface
    leaf is NOT silently reinterpreted as a token-aligned template.
    """
    if item.rule_id is None:
        return None
    data = _tree_description(item)
    if data is None:
        return None
    shape, leaves = data
    if not min_tokens <= len(leaves) <= max_tokens:
        return None
    by_span = {(t.start, t.end): i for i, t in enumerate(lattice.tokens)}
    positions = []
    for start, end, category in leaves:
        index = by_span.get((start, end))
        if index is None:
            return None
        positions.append(index)
    if positions != list(range(positions[0], positions[0] + len(leaves))):
        return None
    if item.start != leaves[0][0] or item.end != leaves[-1][1]:
        return None
    return ObservedSubtree(
        tuple(category for _, _, category in leaves),
        item.category, item.rule_id, shape,
    )


def observations(item: Any, lattice: Any, *, min_tokens: int = 2,
                 max_tokens: int = 8) -> tuple[ObservedSubtree, ...]:
    """Collect every compatible subtree, not only the sentence root."""
    seen = set()
    values = []
    stack = [item]
    while stack:
        node = stack.pop()
        obs = _observed(node, lattice, min_tokens=min_tokens,
                        max_tokens=max_tokens)
        if obs is not None and obs not in seen:
            seen.add(obs)
            values.append(obs)
        stack.extend(reversed(node.children))
    return tuple(values)


class SubtreeSignatureCache:
    """Bounded, append-only category trie of *observed* syntax structures.

    Train only on separately selected sentences. The cache is stable during
    queries. A scan does not learn from, and cannot mutate, held-out text.
    """

    def __init__(self, *, min_tokens: int = 2, max_tokens: int = 8,
                 max_templates: int = 50_000) -> None:
        if min_tokens < 2 or max_tokens < min_tokens or max_templates < 1:
            raise ValueError("Invalid signature cache limits")
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.max_templates = max_templates
        self.templates: list[ObservedSubtree] = []
        self._ids: dict[ObservedSubtree, int] = {}
        self.trie: list[_Trie] = [_Trie()]
        self.training_observations = 0
        self.rejected_capacity = 0
        self._frozen = False

    def observe(self, tree: Any, lattice: Any) -> int:
        if self._frozen:
            raise RuntimeError("A frozen signature cache cannot learn")
        added = 0
        for template in observations(tree, lattice,
                                     min_tokens=self.min_tokens,
                                     max_tokens=self.max_tokens):
            self.training_observations += 1
            if template in self._ids:
                continue
            if len(self.templates) >= self.max_templates:
                self.rejected_capacity += 1
                continue
            template_id = len(self.templates)
            self.templates.append(template)
            self._ids[template] = template_id
            pos = 0
            for category in template.categories:
                next_pos = self.trie[pos].edges.get(category)
                if next_pos is None:
                    next_pos = len(self.trie)
                    self.trie[pos].edges[category] = next_pos
                    self.trie.append(_Trie())
                pos = next_pos
            self.trie[pos].template_ids.append(template_id)
            added += 1
        return added

    def freeze(self) -> None:
        self._frozen = True

    def scan(self, lattice: Any, *, max_transitions: int = 25_000,
             max_matches: int = 2_000) -> SignatureScan:
        if max_transitions < 1 or max_matches < 1:
            raise ValueError("Signature budgets must be positive")
        tokens = lattice.tokens
        if len(tokens) < self.min_tokens or not self.templates:
            return SignatureScan((), 0, False, len(tokens))
        by_span: dict[tuple[int,int], set[str]] = {}
        for candidate in lattice.candidates:
            by_span.setdefault((candidate.span_start,candidate.span_end),set()
                               ).add(candidate.category)
        lexical = tuple(by_span.get((token.start,token.end),set())
                        for token in tokens)
        matches = []
        transitions = 0
        saturated = False
        # At most n * max_tokens * number of distinct prefix states. No
        # product over the alternative POS lists is ever materialised.
        for start in range(len(tokens)):
            frontier = {0}
            for end in range(start,min(len(tokens),start+self.max_tokens)):
                new = set()
                for parent in frontier:
                    for category in lexical[end]:
                        transitions += 1
                        if transitions > max_transitions:
                            return SignatureScan(
                                tuple(matches),transitions,True,len(tokens))
                        child = self.trie[parent].edges.get(category)
                        if child is not None:
                            new.add(child)
                if not new:
                    break
                if end-start+1 >= self.min_tokens:
                    for tid in sorted(
                        tid for state in new
                        for tid in self.trie[state].template_ids
                    ):
                        template = self.templates[tid]
                        matches.append(SignatureHint(
                            start,end+1,tokens[start].start,tokens[end].end,
                            tid,template.root_category,template.root_rule,
                        ))
                        if len(matches)>=max_matches:
                            saturated=True
                            break
                    if saturated:
                        return SignatureScan(
                            tuple(matches),transitions,True,len(tokens))
                frontier=new
        return SignatureScan(tuple(matches),transitions,saturated,len(tokens))

    def summary(self) -> dict[str,int]:
        return {
            "templates":len(self.templates),
            "prefix_nodes":len(self.trie),
            "training_observations":self.training_observations,
            "rejected_capacity":self.rejected_capacity,
        }


def witnessed_matches(scan: SignatureScan, cache: SubtreeSignatureCache,
                      tree: Any, lattice: Any) -> int:
    """Independent witness count from a completed test parse only.

    Equal lexical categories are not enough: require the FULL grammar-rule
    tree shape in the tested best tree. This is a lower-bound diagnostic,
    not proof that other matches are grammatical/invalid.
    """
    if tree is None:
        return 0
    by_location: dict[tuple[int,int,ObservedSubtree],bool] = {}
    token_index={(t.start,t.end):i for i,t in enumerate(lattice.tokens)}
    stack=[tree]
    while stack:
        node=stack.pop()
        observed=_observed(node,lattice,min_tokens=cache.min_tokens,
                           max_tokens=cache.max_tokens)
        if observed is not None:
            start=token_index.get((node.start,node.children[0].start)) if False else None
            # Root [start,end) corresponds exactly to an uninterrupted
            # token interval by the _observed() contract.
            beginning=next((i for i,t in enumerate(lattice.tokens)
                            if t.start==node.start),None)
            last=next((i+1 for i,t in enumerate(lattice.tokens)
                       if t.end==node.end),None)
            if beginning is not None and last is not None:
                by_location[(beginning,last,observed)]=True
        stack.extend(node.children)
    return sum((hint.start_token,hint.end_token,
                cache.templates[hint.template_id]) in by_location
               for hint in scan.matches)
