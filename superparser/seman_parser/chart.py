"""Weighted chart parser with a packed parse forest.

Partial rule applications (dot items) advance through the chart; complete
constituents are packed by ``(start, end, category)`` so shared structure is
stored once. Nothing is thrown away: every item carries score and provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Any, Hashable, Mapping, Sequence

from .features import (
    Bindings,
    FeatureStructure,
    substitute_structure,
    unify,
)
from .grammar import Grammar, GrammarRule, RuleSymbol
from .segmentation import LexicalCandidate, LexicalLattice
from .syntax import EMPTY_SYNTAX, SyntacticLink, SyntacticPackage
from .symbols import intern


@dataclass(frozen=True, slots=True)
class Provenance:
    """Why an item exists: source spans, rules, lexical senses."""

    source: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        detail = dict(self.detail)
        children = detail.get("children")
        if isinstance(children, tuple) and all(isinstance(child, Provenance) for child in children):
            detail["children"] = [child.as_dict() for child in children]
        return {"source": self.source, "detail": detail}


@dataclass(frozen=True, slots=True)
class ChartItem:
    """One complete constituent hypothesis covering ``[start, end)``."""

    start: int
    end: int
    category: str
    features: FeatureStructure
    # Deprecated compatibility slot for manually constructed legacy items.
    # Parser-produced items always leave it at None; semantics are returned
    # by SemanticInterpreter after parsing.
    semantic: Any | None
    score: float
    provenance: Provenance
    children: tuple["ChartItem", ...] = ()
    rule_id: str | None = None
    bindings: Bindings = field(default_factory=dict)
    syntax: SyntacticPackage = EMPTY_SYNTAX
    lexical_candidate: LexicalCandidate | None = field(default=None, repr=False, compare=False)
    # Chart-local identifier assigned when the analysis is accepted.  Parent
    # derivations can consequently use a flat tuple of integers instead of a
    # recursively nested tree signature.
    _sig: Hashable | None = field(default=None, repr=False, compare=False)

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.start, self.end, intern(self.category))

    def signature(self) -> Hashable:
        """Cheap structural signature for duplicate detection.

        Computed once and reused; avoids deep tree comparison on every
        ``_offer`` call.
        """
        sig = self._sig
        if sig is not None:
            return sig
        child_sigs = tuple(child.signature() for child in self.children)
        anchor_sig = tuple(sorted(self.syntax.anchors.items()))
        sig = (self.rule_id, self.category, self.start, self.end, anchor_sig, child_sigs)
        object.__setattr__(self, "_sig", sig)
        return sig

    def as_dict(self) -> dict[str, Any]:
        return {
            "span": [self.start, self.end],
            "category": self.category,
            "features": self.features.as_dict(),
            "syntax": self.syntax.as_dict(),
            "score": self.score,
            "provenance": self.provenance.as_dict(),
            "rule_id": self.rule_id,
            "children": [child.as_dict() for child in self.children],
        }


@dataclass(frozen=True, slots=True)
class PartialItem:
    """A rule with a dot position: ``children`` matched against ``rule.rhs``."""

    rule_id: str
    dot: int
    start: int
    end: int
    children: tuple[ChartItem, ...]
    bindings: Bindings
    score: float
    _sig: tuple[Hashable, ...] | None = field(default=None, repr=False, compare=False)

    @property
    def next_category(self) -> str | None:
        rule = _RULE_CACHE[self.rule_id]
        if self.dot >= rule.arity:
            return None
        return rule.rhs[self.dot].category

    @property
    def complete(self) -> bool:
        rule = _RULE_CACHE[self.rule_id]
        return self.dot >= rule.arity

    def signature(self) -> tuple[Hashable, ...]:
        """Chart-local ids of the analyses consumed by this partial."""
        sig = self._sig
        if sig is None:
            sig = tuple(child.signature() for child in self.children)
            object.__setattr__(self, "_sig", sig)
        return sig


# Populated by Chart so PartialItem can resolve its rule without a backref.
_RULE_CACHE: dict[str, GrammarRule] = {}


@dataclass
class PackedNode:
    """Shared node for all analyses of one (span, category) region."""

    start: int
    end: int
    category: str
    best: ChartItem
    alternatives: list[ChartItem] = field(default_factory=list)
    seen_signatures: set[Hashable] = field(default_factory=set)
    rule_ids: set[str | None] = field(default_factory=set)

    def add(self, item: ChartItem, signature: Hashable) -> None:
        self.alternatives.append(item)
        self.seen_signatures.add(signature)
        self.rule_ids.add(item.rule_id)
        if item.score > self.best.score:
            self.best = item

    def as_dict(self) -> dict[str, Any]:
        return {
            "span": [self.start, self.end],
            "category": self.category,
            "best": self.best.as_dict(),
            "alternatives": [item.as_dict() for item in self.alternatives],
        }


@dataclass
class ParseResult:
    """Everything the parser learned about one input string."""

    text: str
    lattice: LexicalLattice
    packed: dict[tuple[int, int, int], PackedNode]
    roots: Sequence[ChartItem]
    completed: bool
    stats: Mapping[str, Any] = field(default_factory=dict)
    # All category-level alternatives remain available as compact references;
    # ``roots`` is only the k-best materialized view.
    shared_forest: Any | None = field(default=None, repr=False)

    def best(self) -> ChartItem | None:
        lazy_best = getattr(self.roots, "best", None)
        if callable(lazy_best):
            return lazy_best()
        if not self.roots:
            return None
        return max(self.roots, key=lambda item: item.score)

    def alternatives(self, *, limit: int | None = None) -> Sequence[ChartItem]:
        lazy_take = getattr(self.roots, "take", None)
        if callable(lazy_take) and limit is not None:
            return lazy_take(limit)
        ordered = sorted(self.roots, key=lambda item: item.score, reverse=True)
        return ordered if limit is None else ordered[:limit]

    def as_dict(self) -> dict[str, Any]:
        best = self.best()
        return {
            "text": self.text,
            "completed": self.completed,
            "lattice": self.lattice.as_dict(),
            "best": best.as_dict() if best else None,
            "alternatives": [item.as_dict() for item in self.alternatives()],
            "stats": dict(self.stats),
        }


class Chart:
    """Bottom-up weighted chart with packing and a beam."""

    def __init__(
        self,
        grammar: Grammar,
        *,
        beam: int = 80,
        max_items: int = 50_000,
        goal_category: str = "CLAUSE",
    ) -> None:
        self.grammar = grammar
        self.beam = beam
        self.max_items = max_items
        self.goal_category = goal_category
        self.packed: dict[tuple[int, int, int], PackedNode] = {}
        # Index: (start, category_id) -> nodes. A list: two constituents can
        # share a start and category but have different ends ("the box" vs
        # "the box that John opened"). Overwriting would lose one of them.
        self._packed_by_start: dict[tuple[int, int], list[PackedNode]] = {}
        # Partial rule applications: coordinates -> best variants.
        self._partials: dict[tuple, list[PartialItem]] = {}
        # Index: (wait_position, next_category_id) -> partials waiting
        # exactly there. Avoids scanning every partial on each item.
        self._partial_by_wait: dict[tuple[int, int], dict[int, PartialItem]] = {}
        self._agenda: list[tuple[float, int, ChartItem]] = []
        self._pushes = 0
        self._expanded = 0
        self._analysis_ids = 0
        self._goal_count = 0
        self._goal_limit: int | None = None
        self._text = ""
        for rule in grammar:
            _RULE_CACHE[rule.rule_id] = rule

    def _adjacent(self, left_end: int, right_start: int) -> bool:
        """True when only whitespace or quotation marks separate two spans."""
        if right_start < left_end:
            return False
        return not self._text[left_end:right_start].strip().strip('"\u201c\u201d\u2018\u2019').strip()

    def _is_root_span(self, start: int, end: int) -> bool:
        if start != 0:
            return False
        length = len(self._text)
        if end == length:
            return True
        # Accept a span that stops before trailing punctuation/quotes only.
        tail = self._text[end:].strip().strip(".!?;:," + '"\u201c\u201d\u2018\u2019')
        return end < length and not tail

    # -- item insertion --------------------------------------------------

    def _offer(self, item: ChartItem, *, signature: Hashable | None = None) -> bool:
        key = item.key
        dedupe_key = item.signature() if signature is None else signature
        node = self.packed.get(key)
        if node is None:
            node = PackedNode(start=item.start, end=item.end, category=item.category, best=item)
            self.packed[key] = node
            self._packed_by_start.setdefault((item.start, key[2]), []).append(node)
            self._analysis_ids += 1
            object.__setattr__(item, "_sig", self._analysis_ids)
            node.alternatives.append(item)
            node.seen_signatures.add(dedupe_key)
            node.rule_ids.add(item.rule_id)
            self._count_goal(item)
            self._push(item)
            return True
        if dedupe_key in node.seen_signatures:
            return False
        self._analysis_ids += 1
        object.__setattr__(item, "_sig", self._analysis_ids)
        node.add(item, dedupe_key)
        self._count_goal(item)
        # Expand every distinct analysis up to a per-node cap; extra
        # alternatives stay packed for provenance but do not spend agenda
        # budget. The cap is high enough to keep different constructions.
        if len(node.alternatives) <= self.beam or item.score >= node.best.score:
            self._push(item)
        return True

    def _count_goal(self, item: ChartItem) -> None:
        if item.category == self.goal_category and self._is_root_span(item.start, item.end):
            self._goal_count += 1

    def _push(self, item: ChartItem) -> None:
        self._pushes += 1
        # Reward covered input so positive rule scores cannot indefinitely
        # prioritize highly composed local ambiguity over broader analyses.
        priority = item.score + 0.01 * (item.end - item.start)
        heappush(self._agenda, (-priority, self._pushes, item))

    def _offer_partial(self, partial: PartialItem) -> bool:
        # Key on coordinates. Distinct bindings / children are kept as
        # variants of the same slot, capped so the chart cannot explode.
        key = (partial.rule_id, partial.dot, partial.start, partial.end)
        variants = self._partials.get(key)
        if variants is None:
            self._partials[key] = [partial]
            self._index_partial(partial)
            return True
        # Once the slot is full every further variant is rejected, duplicate
        # or not.  Do this before constructing and comparing signatures.
        if len(variants) >= 2:
            return False
        # Compare against the kept variants via their chart-local analysis
        # ids.  These signatures are flat and therefore cheap to hash.
        child_sig = partial.signature()
        for variant in variants:
            if variant.signature() == child_sig:
                # The same consumed analyses deterministically produce the
                # same bindings and score.
                return False
        variants.append(partial)
        self._index_partial(partial)
        return True

    def _partial_wait_key(self, partial: PartialItem) -> tuple[int, int] | None:
        rule = _RULE_CACHE[partial.rule_id]
        if partial.dot >= rule.arity:
            return None
        return (partial.end, rule.rhs[partial.dot].category_id)

    def _index_partial(self, partial: PartialItem) -> None:
        key = self._partial_wait_key(partial)
        if key is None:
            return
        # Identity avoids deep dataclass equality and duplicate list entries.
        self._partial_by_wait.setdefault(key, {})[id(partial)] = partial

    def _partials_waiting(self, position: int, category_id: int) -> Sequence[PartialItem]:
        """Partials that expect this category starting at this position.

        The item may start a few characters after the partial's end (the
        gap is whitespace), so we look at ``position`` and a small window
        *before* it.
        """
        out: list[PartialItem] = []
        for delta in range(0, 3):
            key = (position - delta, category_id)
            found = self._partial_by_wait.get(key)
            if found:
                # Snapshot because advancing a partial can update the index.
                out.extend(found.values())
        return out

    # -- main loop -------------------------------------------------------

    def parse_lattice(self, lattice: LexicalLattice) -> ParseResult:
        text = lattice.text
        self._text = text
        length = len(text)
        # Adaptive budget: long inputs get a tighter beam so a single
        # sentence cannot consume unbounded work. Caps are high enough
        # that trailing short constituents (pronouns, particles) still
        # get expanded before the budget runs out — coverage wins over
        # the old tighter caps (2026-10: "it" in long sentences never
        # attached at 20k items).
        if length > 160:
            self.beam = min(self.beam, 16)
            self.max_items = min(self.max_items, 28_000)
            self._goal_limit = self.beam
        elif length > 80:
            self.beam = min(self.beam, 24)
            self.max_items = min(self.max_items, 48_000)
            self._goal_limit = self.beam
        elif length > 40:
            self.beam = min(self.beam, 40)
            self.max_items = min(self.max_items, 40_000)
            self._goal_limit = self.beam

        for candidate in lattice.candidates:
            self._offer(self._item_from_candidate(candidate))

        while self._agenda and self._expanded < self.max_items:
            _, _, item = heappop(self._agenda)
            self._expanded += 1
            self._advance_with(item)
            if self._goal_limit is not None and self._goal_count >= self._goal_limit:
                break

        goal_id = intern(self.goal_category)

        root_items = [
            item
            for (start, end, cat_id), node in self.packed.items()
            if self._is_root_span(start, end) and cat_id == goal_id
            for item in node.alternatives
        ]
        return ParseResult(
            text=text,
            lattice=lattice,
            packed=self.packed,
            roots=tuple(root_items),
            completed=bool(root_items),
            stats={
                "semantic_graphs": 0,
                "semantic_operations": 0,
                "lexical_candidates": len(lattice.candidates),
                "expanded": self._expanded,
                "pushed": self._pushes,
                "packed_nodes": len(self.packed),
                "partials": len(self._partials),
                "goal_saturated": self._goal_limit is not None and self._goal_count >= self._goal_limit,
            },
        )

    def _item_from_candidate(self, candidate: LexicalCandidate) -> ChartItem:
        syntax = _lexical_syntax(candidate)
        return ChartItem(
            start=candidate.span_start,
            end=candidate.span_end,
            category=candidate.category,
            features=candidate.features,
            semantic=None,
            score=candidate.score,
            provenance=Provenance(
                source=candidate.source,
                detail={
                    "surface": candidate.surface,
                    "lemma": candidate.lemma,
                    "sense_id": candidate.sense_id,
                },
            ),
            children=(),
            syntax=syntax,
            lexical_candidate=candidate,
        )

    # -- rule advance ----------------------------------------------------

    def _advance_with(self, item: ChartItem) -> None:
        """Use a complete item to start rules and to extend partial rules."""
        self._start_rules_with(item)
        self._extend_partials_with(item)

    def _start_rules_with(self, item: ChartItem) -> None:
        for rule in self.grammar.candidates_for_first(item.category, item.features):
            # A full partial slot rejects every additional analysis.  Check
            # before unification, rebinding and handle export: on ambiguous
            # inputs this avoids most of the work in this method.
            if rule.arity > 1:
                variants = self._partials.get((rule.rule_id, 1, item.start, item.end))
                if variants is not None and len(variants) >= 2:
                    continue
            symbol = rule.rhs[0]
            result = unify(symbol.features, item.features)
            if result is None:
                continue
            merged, env = result
            child = _rebind(item, merged, env)
            exports = _export_handles(symbol, child)
            bindings: Bindings = dict(env)
            bindings.update(exports)
            partial = PartialItem(
                rule_id=rule.rule_id,
                dot=1,
                start=item.start,
                end=item.end,
                children=(child,),
                bindings=bindings,
                score=item.score,
            )
            if rule.arity == 1:
                self._complete(rule, partial)
            elif self._offer_partial(partial):
                self._advance_partial_from_chart(partial)

    def _extend_partials_with(self, item: ChartItem) -> None:
        cat_id = intern(item.category)
        for partial in self._partials_waiting(item.start, cat_id):
            rule_id = partial.rule_id
            rule = _RULE_CACHE[rule_id]
            if not self._adjacent(partial.end, item.start):
                continue
            if partial.dot >= rule.arity:
                continue
            symbol = rule.rhs[partial.dot]
            if symbol.category_id != cat_id:
                continue
            next_dot = partial.dot + 1
            if next_dot < rule.arity:
                variants = self._partials.get(
                    (rule_id, next_dot, partial.start, item.end)
                )
                if variants is not None and len(variants) >= 2:
                    continue
            result = unify(symbol.features, item.features, partial.bindings)
            if result is None:
                continue
            merged, env = result
            child = _rebind(item, merged, env)
            exports = _export_handles(symbol, child)
            new_bindings = dict(env)
            new_bindings.update(exports)
            advanced = PartialItem(
                rule_id=rule_id,
                dot=partial.dot + 1,
                start=partial.start,
                end=child.end,
                children=partial.children + (child,),
                bindings=new_bindings,
                score=partial.score + child.score,
            )
            if advanced.complete:
                self._complete(rule, advanced)
            elif self._offer_partial(advanced):
                self._advance_partial_from_chart(advanced)

    def _advance_partial_from_chart(self, partial: PartialItem) -> None:
        """A new partial must also see items already in the chart.

        Agenda order is score-driven, so a high-scoring longer constituent
        can land in the chart before the partial that wants it exists.
        Iterative worklist: no recursion, so long chains cannot blow the
        stack or re-enter the same expansion.
        """
        stack = [partial]
        while stack:
            current = stack.pop()
            rule = _RULE_CACHE[current.rule_id]
            if current.complete:
                continue
            symbol = rule.rhs[current.dot]
            cat_id = intern(symbol.category)
            for delta in range(0, 3):
                for node in self._packed_by_start.get((current.end + delta, cat_id), ()):
                    if not self._adjacent(current.end, node.start):
                        continue
                    for item in node.alternatives[-self.beam :]:
                        next_dot = current.dot + 1
                        if next_dot < rule.arity:
                            variants = self._partials.get(
                                (current.rule_id, next_dot, current.start, item.end)
                            )
                            if variants is not None and len(variants) >= 2:
                                continue
                        result = unify(symbol.features, item.features, current.bindings)
                        if result is None:
                            continue
                        merged, env = result
                        child = _rebind(item, merged, env)
                        exports = _export_handles(symbol, child)
                        new_bindings: Bindings = dict(env)
                        new_bindings.update(exports)
                        advanced = PartialItem(
                            rule_id=current.rule_id,
                            dot=current.dot + 1,
                            start=current.start,
                            end=child.end,
                            children=current.children + (child,),
                            bindings=new_bindings,
                            score=current.score + child.score,
                        )
                        if advanced.complete:
                            self._complete(rule, advanced)
                        elif self._offer_partial(advanced):
                            stack.append(advanced)

    def _complete(self, rule: GrammarRule, partial: PartialItem) -> None:
        children = partial.children
        if not children:
            return
        score = partial.score + rule.score
        if self._expanded >= self.max_items:
            return
        key = (partial.start, partial.end, intern(rule.lhs.category))
        node = self.packed.get(key)
        # A rule applied to the same accepted child analyses is the same
        # derivation.  Reject it before feature substitution, provenance and
        # semantic graph construction.  Child ids keep this key flat.
        derivation = (rule.rule_id, *(child.signature() for child in children))
        if node is not None and derivation in node.seen_signatures:
            return
        # Safe reject: a full slot whose alternatives already cover several
        # *different* rules, and this one is far below the best.
        if node is not None and len(node.alternatives) >= self.beam:
            if len(node.rule_ids) >= 4 and score < node.best.score - 2.0:
                return
        # Unifying against an empty structure cannot fail or add bindings.
        # Applying the existing environment directly is equivalent and
        # avoids two dictionary/feature-structure allocations.
        env = dict(partial.bindings)
        lhs_features = substitute_structure(rule.lhs.features, env)
        # Only pay for semantic composition when this item will actually be
        # expanded (pushed to the agenda). Packed-only items get a cheap
        # placeholder and lose no linguistic distinction at the tree level.
        will_expand = node is None or score >= node.best.score or len(node.alternatives) < self.beam
        if will_expand:
            syntax = _compose_syntax(rule, children)
        else:
            syntax = _compose_syntax(rule, children)
        item = ChartItem(
            start=partial.start,
            end=partial.end,
            category=rule.lhs.category,
            features=lhs_features,
            semantic=None,
            score=score,
            provenance=Provenance(
                source="rule",
                detail={
                    "rule_id": rule.rule_id,
                    "children": [child.provenance.as_dict() for child in children],
                },
            ),
            children=children,
            rule_id=rule.rule_id,
            bindings=env,
            syntax=syntax,
        )
        self._offer(item, signature=derivation)

def _rebind(item: ChartItem, features: FeatureStructure, env: Bindings) -> ChartItem:
    return ChartItem(
        start=item.start,
        end=item.end,
        category=item.category,
        features=features,
        semantic=item.semantic,
        score=item.score,
        provenance=item.provenance,
        children=item.children,
        rule_id=item.rule_id,
        bindings=env,
        syntax=item.syntax,
        lexical_candidate=item.lexical_candidate,
        _sig=item._sig,
    )


def _export_handles(symbol: RuleSymbol, item: ChartItem) -> dict[str, str]:
    exports: dict[str, str] = {}
    for child_name, rule_name in symbol.exports.items():
        resolved = item.syntax.anchors.get(child_name)
        if resolved:
            exports[rule_name] = resolved
    # Always expose stable defaults so semantic actions can use them.
    for name in ("referent", "event", "head"):
        if name in item.syntax.anchors:
            exports.setdefault(name, item.syntax.anchors[name])
    return exports


def _lexical_syntax(candidate: LexicalCandidate) -> SyntacticPackage:
    anchor = f"lex:{candidate.span_start}:{candidate.span_end}:{candidate.category}:{candidate.lemma}"
    anchors = {"head": anchor, "referent": anchor}
    if candidate.category.upper().startswith("V") or candidate.category in {"AUX", "AUX-BE", "COPULA", "MODAL"}:
        anchors["event"] = anchor
    return SyntacticPackage(anchors)


def _compose_syntax(rule: GrammarRule, children: tuple[ChartItem, ...]) -> SyntacticPackage:
    anchors: dict[str, str] = {}
    links: list[SyntacticLink] = []
    for index, (symbol, child) in enumerate(zip(rule.rhs, children)):
        for child_name, rule_name in symbol.exports.items():
            target = child.syntax.anchors.get(child_name)
            if target:
                anchors[rule_name] = target
                links.append(SyntacticLink(rule_name, target, index))
        for name in ("referent", "event", "head"):
            target = child.syntax.anchors.get(name)
            if target:
                anchors.setdefault(name, target)
    # A grammar-declared head outranks incidental closed-class defaults.
    if any("head" in symbol.exports.values() for symbol in rule.rhs) and "head" in anchors:
        anchors["referent"] = anchors["head"]
    return SyntacticPackage(anchors, tuple(links))


def _same_analysis(left: ChartItem, right: ChartItem) -> bool:
    """Structurally equivalent analyses share a signature (rule, handles,
    whole subtree). Signatures are cached per item."""
    return left.signature() == right.signature()


def _same_partial(left: PartialItem, right: PartialItem) -> bool:
    """Two partials at the same slot are duplicates when they consumed the
    same children and have the same bindings."""
    return (
        left.bindings == right.bindings
        and len(left.children) == len(right.children)
        and all(a.signature() == b.signature() for a, b in zip(left.children, right.children))
    )
