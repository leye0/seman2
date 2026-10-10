"""Experimental lexical signature / construction-index fast path for Seman2.

This module deliberately DOES NOT replace the chart parser. It provides:
  * an optional bounded cache of lexical morphology results;
  * a compact bit-vector representation of ALL lexical categories per span;
  * an NFA-style trie matcher for known surface construction signatures;
  * candidate construction induction from validated parse trees;
  * an opt-in FastParser compatible with the existing Parser API.

Recognizing a signature is NEVER proof of a valid grammatical/semantic parse.
The existing feature unifier and chart remain authoritative.
"""

from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .engine import Parser, ParserResources
from .segmentation import LexicalLattice, build_lattice


class CachedLexiconView:
    """Bounded transparent wrapper for expensive repeated surface lookups.

    The underlying lexicon is not modified. Explicitly invalidate the cache
    after editing lexicon entries or changing a WordNet-backed resource.
    """

    def __init__(self, lexicon: Any, capacity: int = 16_384) -> None:
        self.lexicon = lexicon
        self.capacity = max(0, capacity)
        self._cache: OrderedDict[str, tuple] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def lookup_morphology(self, surface: str) -> tuple:
        key = surface.lower()
        if key in self._cache:
            self.hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self.misses += 1
        value = tuple(self.lexicon.lookup_morphology(surface))
        if self.capacity:
            self._cache[key] = value
            self._cache.move_to_end(key)
            if len(self._cache) > self.capacity:
                self._cache.popitem(last=False)
        return value

    def invalidate(self) -> None:
        self._cache.clear()

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "entries": len(self._cache)}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.lexicon, name)


@dataclass(frozen=True, slots=True)
class SignatureEdge:
    """All POS alternatives over one character span; no cross-product."""

    start: int
    end: int
    mask: int
    categories: tuple[str, ...]
    candidate_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TokenSignature:
    index: int
    surface: str
    start: int
    end: int
    mask: int
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConstructionMatch:
    label: str
    start: int
    end: int
    categories: tuple[str, ...]
    source: str
    evidence: int


@dataclass(frozen=True, slots=True)
class ConstructionTemplate:
    label: str
    categories: tuple[str, ...]
    source: str = "observed"
    evidence: int = 0


class LexicalSignatureLattice:
    """Projection of Seman2's lattice into POS bitmasks.

    Supports token-aligned words, multiword edges and contraction subspans.
    Edge identities are preserved, and the original lattice remains intact.
    """

    def __init__(self, lattice: LexicalLattice, vocabulary: "CategoryBits") -> None:
        self.original = lattice
        self.vocabulary = vocabulary
        groups: dict[tuple[int, int], list[tuple[int, Any]]] = defaultdict(list)
        for i, candidate in enumerate(lattice.candidates):
            groups[(candidate.span_start, candidate.span_end)].append((i, candidate))
        edges: list[SignatureEdge] = []
        for (start, end), alternatives in sorted(groups.items()):
            categories = tuple(sorted({c.category for _, c in alternatives}))
            edges.append(SignatureEdge(
                start, end, vocabulary.mask(categories), categories,
                tuple(i for i, _ in alternatives),
            ))
        self.edges = tuple(edges)
        self._categories_by_span = { (e.start, e.end): e.categories for e in edges }
        by_start: dict[int, list[SignatureEdge]] = defaultdict(list)
        for edge in edges:
            by_start[edge.start].append(edge)
        self.by_start = dict(by_start)
        self.starts = frozenset(by_start)
        self.token_signatures = tuple(self._token_signature(t) for t in lattice.tokens)
        self._successors: dict[int, int | None] = {}

    def _token_signature(self, token: Any) -> TokenSignature:
        categories = self._categories_by_span.get((token.start, token.end), ())
        return TokenSignature(
            token.index, token.text, token.start, token.end,
            self.vocabulary.mask(categories), categories,
        )

    def successor(self, end: int) -> int | None:
        """Only traverse separators allowed by chart._adjacent().

        A token may end where the next begins (clitics). Ignore whitespace
        and quotation separators, but never skip actual unknown material.
        """
        if end in self._successors:
            return self._successors[end]
        text = self.original.text
        pos = end
        separators = ' \t\r\n"\u201c\u201d\u2018\u2019'
        while pos < len(text) and text[pos] in separators:
            pos += 1
        successor = pos if pos in self.starts else None
        self._successors[end] = successor
        return successor


class CategoryBits:
    """Local, extensible category -> integer-bit map."""

    def __init__(self, initial: Iterable[str] = ()) -> None:
        self._bits: dict[str, int] = {}
        for name in initial:
            self.bit(name)

    def bit(self, category: str) -> int:
        value = self._bits.get(category)
        if value is None:
            value = 1 << len(self._bits)
            self._bits[category] = value
        return value

    def mask(self, categories: Iterable[str]) -> int:
        result = 0
        for category in categories:
            result |= self.bit(category)
        return result

    def categories(self, mask: int) -> tuple[str, ...]:
        return tuple(name for name, bit in self._bits.items() if bit & mask)

    def __len__(self) -> int:
        return len(self._bits)


@dataclass(slots=True)
class _TrieNode:
    outgoing: dict[int, int] = field(default_factory=dict)
    terminals: list[ConstructionTemplate] = field(default_factory=list)


class ConstructionIndex:
    """Compiled trie of known POS sequences, matched without POS enumeration.

    Patterns are hints for fast recognition and induction; matching a pattern
    does not bypass agreement, feature unification or semantic composition.
    """

    def __init__(self, vocabulary: CategoryBits | None = None) -> None:
        self.vocabulary = vocabulary if vocabulary is not None else CategoryBits()
        self._templates: dict[tuple[str, tuple[str, ...]], ConstructionTemplate] = {}
        self._nodes: list[_TrieNode] = [_TrieNode()]
        self._dirty = False

    def add(self, template: ConstructionTemplate) -> None:
        if not template.categories or any(not c for c in template.categories):
            raise ValueError("a construction needs one or more POS categories")
        key = (template.label, template.categories)
        previous = self._templates.get(key)
        if previous == template:
            return
        self._templates[key] = template
        self._dirty = True

    def templates(self) -> tuple[ConstructionTemplate, ...]:
        return tuple(self._templates.values())

    def seed_from_grammar(self, grammar: Any) -> int:
        """Index every *direct RHS pattern* of the declared grammar.

        A category such as N may be both lexical and a grammar LHS. It must
        NOT be discarded as a terminal merely because N has productions.
        Nested productions are recognized by EarleyStructureRecognizer;
        this flat trie only matches RHS sequences present in lexical edges.
        """
        added = 0
        for rule in grammar:
            categories = tuple(sym.category for sym in rule.rhs)
            if not categories:
                continue
            key = (rule.lhs.category, categories)
            if key not in self._templates:
                self.add(ConstructionTemplate(
                    label=rule.lhs.category, categories=categories,
                    source=f"grammar:{rule.rule_id}", evidence=0,
                ))
                added += 1
        return added

    def _compile(self) -> None:
        if not self._dirty:
            return
        self._nodes = [_TrieNode()]
        for template in self._templates.values():
            index = 0
            for category in template.categories:
                bit = self.vocabulary.bit(category)
                nxt = self._nodes[index].outgoing.get(bit)
                if nxt is None:
                    nxt = len(self._nodes)
                    self._nodes[index].outgoing[bit] = nxt
                    self._nodes.append(_TrieNode())
                index = nxt
            self._nodes[index].terminals.append(template)
        self._dirty = False

    def scan(self, lattice: LexicalLattice | LexicalSignatureLattice, *, max_matches: int = 25_000) -> tuple[ConstructionMatch, ...]:
        """Traverse all compatible categories in a lattice by bit operations.

        Each distinct NFA state is (trie_node_id, original_span_start).
        There is no exponential cartesian product of token interpretations.
        """
        self._compile()
        signature = lattice if isinstance(lattice, LexicalSignatureLattice) else LexicalSignatureLattice(lattice, self.vocabulary)
        if signature.vocabulary is not self.vocabulary:
            raise ValueError("signature lattice uses a different CategoryBits table")
        pending: dict[int, set[tuple[int, int]]] = defaultdict(set)
        found: dict[tuple[str, int, int, tuple[str, ...]], ConstructionMatch] = {}
        for start in sorted(signature.starts):
            states = pending.pop(start, set())
            states.add((0, start))
            for edge in signature.by_start[start]:
                for node_id, origin in states:
                    for category_bit, target_id in self._nodes[node_id].outgoing.items():
                        if not (edge.mask & category_bit):
                            continue
                        target = self._nodes[target_id]
                        for template in target.terminals:
                            key = (template.label, origin, edge.end, template.categories)
                            found[key] = ConstructionMatch(
                                template.label, origin, edge.end,
                                template.categories, template.source, template.evidence,
                            )
                            if len(found) >= max_matches:
                                return tuple(found.values())
                        next_position = signature.successor(edge.end)
                        if target.outgoing and next_position is not None:
                            pending[next_position].add((target_id, origin))
        return tuple(found.values())


class ConstructionLearner:
    """Incremental evidence accumulator, NOT an automatic grammar mutator.

    Only existing parse results can give validated examples. New shapes from
    unparsed sentences are quarantined as hypotheses. Promotion to the fast
    matcher is not promotion into the authoritative grammar.
    """

    def __init__(self, index: ConstructionIndex, *, threshold: int = 3,
                 max_hypotheses: int = 4_096, max_pattern_length: int = 12) -> None:
        self.index = index
        self.threshold = max(2, threshold)
        self.max_hypotheses = max(1, max_hypotheses)
        self.max_pattern_length = max(1, max_pattern_length)
        self.evidence: Counter[tuple[str, tuple[str, ...]]] = Counter()
        self.unknown_shapes: OrderedDict[tuple[tuple[str, ...], ...], int] = OrderedDict()

    @staticmethod
    def _leaves(node: Any) -> tuple[Any, ...]:
        if not node.children:
            return (node,)
        return tuple(leaf for child in node.children for leaf in ConstructionLearner._leaves(child))

    def observe_parsed(self, report: Any, *, top_k: int = 1) -> int:
        """Collect category strings backed by actual parsed constituents.

        Deduplicate patterns per sentence so repeated trees do not inflate
        evidence; leaves retain distinct POS readings for ambiguity.
        """
        results = report.result if hasattr(report, "result") else report
        if not results.completed:
            return 0
        roots = results.alternatives(limit=top_k)
        seen: set[tuple[str, tuple[str, ...]]] = set()

        def visit(node: Any) -> None:
            if node.children:
                leaves = self._leaves(node)
                cats = tuple(leaf.category for leaf in leaves)
                if 1 <= len(cats) <= self.max_pattern_length:
                    seen.add((node.category, cats))
            for child in node.children:
                visit(child)

        for root in roots:
            visit(root)
        promoted = 0
        for key in seen:
            self.evidence[key] += 1
            if self.evidence[key] == self.threshold:
                self.index.add(ConstructionTemplate(
                    label=key[0], categories=key[1],
                    source="induced-from-parsed", evidence=self.evidence[key],
                ))
                promoted += 1
        if len(self.evidence) > self.max_hypotheses:
            for key, _ in self.evidence.most_common()[self.max_hypotheses:]:
                del self.evidence[key]
        return promoted

    def observe_unparsed(self, signature: LexicalSignatureLattice) -> None:
        """Store *one* compact POS-set sequence, not all POS combinations."""
        shape = tuple(slot.categories for slot in signature.token_signatures)
        if not shape:
            return
        self.unknown_shapes[shape] = self.unknown_shapes.get(shape, 0) + 1
        self.unknown_shapes.move_to_end(shape)
        while len(self.unknown_shapes) > self.max_hypotheses:
            self.unknown_shapes.popitem(last=False)

    def stats(self) -> dict[str, int]:
        return {
            "candidate_constructions": len(self.evidence),
            "unparsed_shapes": len(self.unknown_shapes),
            "known_matcher_templates": len(self.index.templates()),
        }


@dataclass(frozen=True, slots=True)
class StructuralRecognition:
    """Feature-blind necessary-condition recognition, NOT a full parse."""

    possible: bool
    state_count: int
    completion_count: int
    root_ends: tuple[int, ...]
    exceeded_budget: bool = False


class EarleyStructureRecognizer:
    """Shared predictive recognizer over all grammar productions.

    Positions are character offsets on the original lexical lattice.
    The same (rule, dot, origin, position) state is computed once regardless
    of how many alternative derivations reach it. This recognizer ignores
    feature unification, semantic bindings and scores; it is a *superset*
    recognizer useful for diagnostics and cheap structural prechecks.
    """

    def __init__(self, grammar: Any) -> None:
        self.rules = tuple(grammar)
        self._rhs = [tuple(s.category for s in r.rhs) for r in self.rules]
        self._lhs = [r.lhs.category for r in self.rules]
        self._by_lhs: dict[str, list[int]] = defaultdict(list)
        for i, cat in enumerate(self._lhs):
            self._by_lhs[cat].append(i)

    def recognize(self, lattice: LexicalSignatureLattice, *, goal: str = "CLAUSE",
                  max_states: int = 200_000) -> StructuralRecognition:
        if not lattice.edges:
            return StructuralRecognition(False, 0, 0, ())
        # Store completed lexical spans and grammar constituents in the same
        # index. end offsets point to the next potential token position.
        completed: dict[tuple[int, str], set[int]] = defaultdict(set)
        chart: dict[int, set[tuple[int, int, int]]] = defaultdict(set)
        waiters: dict[tuple[int, str], set[tuple[int, int, int]]] = defaultdict(set)
        agenda: list[tuple[int, tuple[int, int, int]]] = []
        exceeded = False
        state_count = 0

        def add_state(pos: int, state: tuple[int, int, int]) -> None:
            nonlocal exceeded, state_count
            if state in chart[pos] or exceeded:
                return
            chart[pos].add(state)
            state_count += 1
            agenda.append((pos, state))
            if state_count > max_states:
                exceeded = True

        def add_complete(start: int, category: str, end: int) -> None:
            target = completed[(start, category)]
            if end in target:
                return
            target.add(end)
            for rule_id, dot, origin in tuple(waiters.get((start, category), ())):
                add_state(end, (rule_id, dot + 1, origin))

        for edge in lattice.edges:
            end = lattice.successor(edge.end)
            if end is None:
                end = edge.end
            for category in edge.categories:
                add_complete(edge.start, category, end)

        root_start = min(lattice.starts)
        for rule_id in self._by_lhs.get(goal, ()):
            add_state(root_start, (rule_id, 0, root_start))

        # Agenda order is irrelevant: both freshly created waiters and already
        # known completions are joined symmetrically (fundamental rule).
        cursor = 0
        while cursor < len(agenda) and not exceeded:
            pos, (rule_id, dot, origin) = agenda[cursor]
            cursor += 1
            rhs = self._rhs[rule_id]
            if dot == len(rhs):
                add_complete(origin, self._lhs[rule_id], pos)
                continue
            category = rhs[dot]
            waiting = (rule_id, dot, origin)
            waiters[(pos, category)].add(waiting)
            for end in tuple(completed.get((pos, category), ())):
                add_state(end, (rule_id, dot + 1, origin))
            for child_rule_id in self._by_lhs.get(category, ()):
                add_state(pos, (child_rule_id, 0, pos))

        # A chart goal may legally end before terminal punctuation, per
        # Chart._is_root_span. Do not treat partial recognition as certainty.
        raw_text = lattice.original.text
        valid_ends = []
        for end in sorted(completed.get((root_start, goal), ())):
            tail = raw_text[end:].strip().strip('.!?;:,"\u201c\u201d\u2018\u2019')
            if not tail:
                valid_ends.append(end)
        return StructuralRecognition(
            possible=bool(valid_ends) and not exceeded,
            state_count=state_count,
            completion_count=sum(map(len, completed.values())),
            root_ends=tuple(valid_ends),
            exceeded_budget=exceeded,
        )


class FastParser(Parser):
    """Opt-in drop-in Parser, with lexical cache + construction scanner.

    The authoritative parse result is unchanged in kind and still produced by
    the existing Chart. Automatic learning is OFF by default, to avoid adding
    runtime cost or implicit learning during performance comparisons.
    """

    def __init__(self, resources: ParserResources, *,
                 surface_cache_size: int = 16_384,
                 induction_threshold: int = 3,
                 auto_learn: bool = False, **kwargs: Any) -> None:
        self.lexical_cache = CachedLexiconView(resources.lexicon, surface_cache_size)
        wrapped = ParserResources(
            grammar=resources.grammar,
            lexicon=self.lexical_cache,
            types=resources.types,
            metadata=resources.metadata,
        )
        super().__init__(wrapped, **kwargs)
        self.category_bits = CategoryBits()
        self.constructions = ConstructionIndex(self.category_bits)
        self.seeded_patterns = self.constructions.seed_from_grammar(resources.grammar)
        self.learner = ConstructionLearner(self.constructions, threshold=induction_threshold)
        self.recognizer = EarleyStructureRecognizer(resources.grammar)
        self.auto_learn = auto_learn

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().strip('"\u201c\u201d\u2018\u2019').strip()

    def signature_lattice(self, text: str) -> LexicalSignatureLattice:
        text = self._normalize(text)
        lattice = self._lattice_cache.get(text)
        if lattice is None:
            lattice = build_lattice(text, self.resources.lexicon)
            self._lattice_cache.put(text, lattice)
        return LexicalSignatureLattice(lattice, self.category_bits)

    def scan_constructions(self, text: str) -> tuple[ConstructionMatch, ...]:
        return self.constructions.scan(self.signature_lattice(text))

    def recognize_structure(self, text: str, goal: str | None = None) -> StructuralRecognition:
        """Coarse Earley-style syntax recognition; no semantic proof."""
        return self.recognizer.recognize(self.signature_lattice(text), goal=goal or self.goal_category)

    def parse(self, text: str) -> Any:
        report = super().parse(text)
        if self.auto_learn:
            self.observe(report)
        return report

    def observe(self, report: Any) -> int:
        if report.result.completed:
            return self.learner.observe_parsed(report)
        self.learner.observe_unparsed(self.signature_lattice(report.result.text))
        return 0

    def parse_with_scan(self, text: str) -> tuple[Any, tuple[ConstructionMatch, ...]]:
        """Diagnostic: independently time scanner and the authoritative chart."""
        matches = self.scan_constructions(text)
        return self.parse(text), matches

    def invalidate_knowledge_caches(self) -> None:
        """Call after external lexical/grammar mutations; reinstantiate for grammar edits."""
        self.lexical_cache.invalidate()
        self._lattice_cache.clear()
        self._parse_cache.clear()


__all__ = [
    "CachedLexiconView", "CategoryBits", "TokenSignature", "SignatureEdge",
    "LexicalSignatureLattice", "ConstructionMatch", "ConstructionTemplate",
    "ConstructionIndex", "ConstructionLearner", "FastParser",
    "StructuralRecognition", "EarleyStructureRecognizer",
]
