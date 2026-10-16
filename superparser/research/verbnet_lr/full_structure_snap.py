"""Research-only whole-sentence grammatical structure snapping.

A structure is an entire tree of grammar rule IDs and lexical category slots,
not a bag of POS tags or a cached sentence. The input lexical lattice is never
collapsed: every one-token candidate remains available for grammar unification.

This index only recognizes observed templates. It is NOT an exhaustive parser,
a syntactic proof, or a replacement for a no-hit fallback. Unverified L-R
trees remain explicitly tagged as candidates. No words/lemmas are indexed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from functools import lru_cache
from typing import Any

from seman_parser.features import Variable
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.symbols import intern


@dataclass(frozen=True, slots=True)
class Structure:
    """One full grammatical derivation, with lexical categories at leaves."""
    category: str
    rule_id: str | None = None
    children: tuple["Structure", ...] = ()


@dataclass(slots=True)
class Template:
    shape: Structure
    categories: tuple[str, ...]
    candidate_observations: int = 0
    verified_observations: int = 0
    grammar_witness_observations: int = 0


@dataclass(slots=True)
class _Trie:
    edges: dict[str, "_Trie"] = field(default_factory=dict)
    template_ids: list[int] = field(default_factory=list)
    lexical_signature: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class SnapMatch:
    template_id: int
    item: Any
    independently_verified_template: bool
    grammar_witness_template: bool = False


@dataclass(slots=True)
class SnapResult:
    matches: tuple[SnapMatch, ...]
    lattice: Any
    candidate_templates: int
    checked_templates: int
    reductions: int
    incomplete: bool
    reason: str
    next_template_offset: int | None = None

    @property
    def complete(self) -> bool:
        return bool(self.matches)

    @property
    def item(self):
        return self.matches[0].item if self.matches else None


@lru_cache(maxsize=131072)
def _slots(shape: Structure) -> int:
    return 1 if shape.rule_id is None else sum(_slots(ch) for ch in shape.children)


def _leaf_categories(shape: Structure) -> tuple[str, ...]:
    if shape.rule_id is None:
        return (shape.category,)
    return tuple(cat for child in shape.children for cat in _leaf_categories(child))


class FullStructureSnapIndex:
    """Exact, whole-tree templates indexed by all candidate lexical categories.

    Observed templates are not assumed to be independently verified. A shared
    prefix trie indexes FULL flattened category sequences; its terminal IDs
    retain every different complete derivation with that same sequence.
    """
    def __init__(self, resources: Any, *, goal: str = "CLAUSE",
                 max_templates: int = 20_000_000):
        if max_templates < 1:
            raise ValueError("max_templates must be positive")
        self.resources = resources
        self.goal = goal
        self.max_templates = max_templates
        self.rules = {r.rule_id: r for r in resources.grammar.rules}
        self.templates: list[Template] = []
        self._by_shape: dict[Structure, int] = {}
        self._root = _Trie()
        # Only materialization and the real grammar unifier are reused.
        # There is no call to the production search parser.
        self._materializer = PredictiveParser(resources)

    def _shape(self, node: Any) -> Structure:
        if node.lexical_candidate is not None:
            if node.rule_id is not None or node.children:
                raise ValueError("Lexical node also has a grammar derivation")
            return Structure(node.category)
        if not node.rule_id or not node.children:
            raise ValueError("Cannot index an unproven or empty node")
        rule = self.rules.get(node.rule_id)
        if (rule is None or rule.lhs.category != node.category
                or len(rule.rhs) != len(node.children)
                or any(sym.category != child.category
                       for sym, child in zip(rule.rhs, node.children))):
            raise ValueError("Tree does not match a licensed grammar rule")
        return Structure(node.category, node.rule_id,
                         tuple(self._shape(ch) for ch in node.children))

    def observe(self, item: Any, *, lattice: Any,
                evidence: str = "candidate") -> int:
        """Index a whole tree; only an EXTERNAL verifier may label 'verified'.

        Never infer independent correctness from the fact that L-R completed.
        Unsupported multiword lexical spans are rejected, not silently split.
        """
        if evidence not in {"candidate", "verified", "grammar_witness"}:
            raise ValueError("Evidence must be candidate, grammar_witness, or externally verified")
        if item.category != self.goal:
            raise ValueError("Template must be a completed goal-category tree")
        shape = self._shape(item)
        leaves = []
        def walk(n):
            if n.lexical_candidate is not None:
                leaves.append((n.start, n.end, n.category))
            else:
                for child in n.children:
                    walk(child)
        walk(item)
        tokens = tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".", "!"):
            tokens = tokens[:-1]
        if (len(leaves) != len(tokens) or
                any((start, end) != (t.start, t.end)
                    for (start, end, _), t in zip(leaves, tokens))):
            raise ValueError("Only fully aligned, one-token structures can snap")
        previous = self._by_shape.get(shape)
        if previous is not None:
            template = self.templates[previous]
            if evidence == "verified":
                template.verified_observations += 1
            elif evidence == "grammar_witness":
                template.grammar_witness_observations += 1
            else:
                template.candidate_observations += 1
            return previous
        if len(self.templates) >= self.max_templates:
            raise OverflowError("Template capacity reached")
        categories = tuple(cat for _, _, cat in leaves)
        state = self._root
        for cat in categories:
            state = state.edges.setdefault(cat, _Trie())
        # Intern the category sequence per full lexical path. Millions of
        # different attachments may share precisely the same leaf sequence.
        if state.lexical_signature is None:
            state.lexical_signature = categories
        else:
            categories = state.lexical_signature
        key = len(self.templates)
        self._by_shape[shape] = key
        self.templates.append(Template(
            shape, categories, int(evidence == "candidate"),
            int(evidence == "verified"),
            int(evidence == "grammar_witness")))
        state.template_ids.append(key)
        return key

    @staticmethod
    def _lexical_slots(lattice):
        tokens = tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".", "!"):
            tokens = tokens[:-1]
        spans = {(t.start, t.end): i for i, t in enumerate(tokens)}
        entries = [defaultdict(list) for _ in tokens]
        for cand in lattice.candidates:
            pos = spans.get((cand.span_start, cand.span_end))
            if pos is not None:
                entries[pos][cand.category].append(cand)
        for by_cat in entries:
            for options in by_cat.values():
                options.sort(key=lambda c: c.score, reverse=True)
        return entries

    def match(self, lattice: Any, *, max_templates_checked: int = 128,
              max_states: int = 4096, max_variants: int = 8,
              max_reductions: int = 512,
              template_offset: int = 0) -> SnapResult:
        """Return ALL matching whole-tree templates within explicit budgets.

        Any budget cutoff sets incomplete=True; a truncated search must never
        be interpreted as proof that other plausible structures do not exist.
        """
        if min(max_templates_checked, max_states, max_variants, max_reductions) < 1:
            raise ValueError("All budgets must be positive")
        if template_offset < 0:
            raise ValueError("template_offset must be nonnegative")
        options = self._lexical_slots(lattice)
        active = [self._root]
        incomplete = False
        for lexical in options:
            available = lexical.keys()
            upcoming = []
            for state in active:
                for category in available:
                    child = state.edges.get(category)
                    if child is not None:
                        upcoming.append(child)
            if len(upcoming) > max_states:
                incomplete = True
                upcoming = upcoming[:max_states]
            active = upcoming
            if not active:
                return SnapResult((), lattice, 0, 0, 0, incomplete,
                                  "trie_budget" if incomplete else "unseen_pattern")
        # A category trie has no merging transitions: each reachable state
        # represents one distinct lexical prefix. Template IDs are stored
        # at exactly one terminal. Hence no O(bucket_size) deduplication or
        # full traversal of a potentially multimillion-ID bucket is needed.
        count = sum(len(state.template_ids) for state in active)
        ids = []
        skip = template_offset
        for state in active:
            length = len(state.template_ids)
            if skip >= length:
                skip -= length
                continue
            remaining = max_templates_checked - len(ids)
            if remaining <= 0:
                break
            ids.extend(state.template_ids[skip:skip + remaining])
            skip = 0
        next_offset = (template_offset + len(ids)
                       if template_offset + len(ids) < count else None)
        if next_offset is not None:
            incomplete = True
        reductions = 0
        matched = []

        def build(shape: Structure, at: int):
            nonlocal incomplete, reductions
            if shape.rule_id is None:
                candidates = options[at].get(shape.category, ())
                if len(candidates) > max_variants:
                    incomplete = True
                out = []
                for candidate in candidates[:max_variants]:
                    evidence = frozenset(
                        key for key, value in candidate.features.items()
                        if not isinstance(value, Variable))
                    out.append(CompactNode(
                        candidate.category, intern(candidate.category),
                        candidate.span_start, candidate.span_end,
                        candidate.features, evidence, candidate.score,
                        candidate=candidate))
                return out
            rule = self.rules[shape.rule_id]
            children = []
            cursor = at
            for child in shape.children:
                variants = build(child, cursor)
                if not variants:
                    return []
                children.append(variants)
                cursor += _slots(child)
            result = []
            for choice in product(*children):
                if reductions >= max_reductions:
                    incomplete = True
                    break
                reductions += 1
                item = PredictiveParser._reduce(rule, choice)
                if item is not None:
                    result.append(item)
                    if len(result) >= max_variants:
                        # We have a valid witness, but did not certify all
                        # lexical variants of this same template.
                        incomplete = True
                        break
            return result

        for template_id in ids:
            if reductions >= max_reductions:
                incomplete = True
                break
            template = self.templates[template_id]
            variants = build(template.shape, 0)
            if variants:
                item = self._materializer._materialize(variants[0])
                matched.append(SnapMatch(
                    template_id, item,
                    template.verified_observations > 0,
                    template.grammar_witness_observations > 0))
        if incomplete:
            reason = "budget_exhausted_or_lexical_variants_unexplored"
        elif matched:
            reason = "matched"
        elif count and not ids and template_offset > 0:
            reason = "template_offset_past_end"
        elif count:
            reason = "templates_failed_feature_unification"
        else:
            reason = "unseen_pattern"
        return SnapResult(tuple(matched), lattice, count, len(ids),
                          reductions, incomplete, reason, next_offset)

    def summary(self):
        return {
            "templates": len(self.templates),
            "verified_templates": sum(t.verified_observations > 0
                                      for t in self.templates),
            "grammar_witness_templates": sum(t.grammar_witness_observations > 0
                                              for t in self.templates),
            "candidate_templates": sum(t.verified_observations == 0 and
                                       t.grammar_witness_observations == 0
                                       for t in self.templates),
        }


class SnappingResearchReader:
    """Opt-in fast-path front end; default L-R remains unchanged.

    A miss is handed to the existing L-R fallback. One revalidated match
    is sufficient for the fast path even if other known alternatives remain
    unmaterialized; the result explicitly advertises incompleteness and the
    next offset for deferred layer-2 enumeration.
    """
    def __init__(self, resources, *, index: FullStructureSnapIndex,
                 fallback=None, max_templates_checked: int = 128):
        if max_templates_checked < 1:
            raise ValueError("max_templates_checked must be positive")
        self.resources = resources
        self.index = index
        self.fallback = fallback or SemanCompiledReader(resources)
        self.max_templates_checked = max_templates_checked

    def parse(self, text: str, *, learn_candidate: bool = False):
        from seman_parser.segmentation import build_lattice
        lattice = build_lattice(text, self.resources.lexicon, multiword_max=1)
        snapped = self.index.match(
            lattice, max_templates_checked=self.max_templates_checked)
        if snapped.complete:
            # A complete grammar-licensed derivation is an operational
            # answer. Incomplete means OTHER plausible trees remain deferred,
            # not that this matched tree is invalid. Layer 2 can page them.
            return snapped, "snap"
        if (isinstance(self.fallback, SemanCompiledReader)
                and self.fallback.token_only_lattice
                and not self.fallback.fast_multiword):
            # These two readers use the identical one-token lexicon lattice.
            # Avoid rebuilding it after a cache miss; no grammar is bypassed.
            fallback = self.fallback.parse(text, lattice=lattice)
        else:
            fallback = self.fallback.parse(text)
        if learn_candidate and fallback.complete:
            try:
                self.index.observe(fallback.item, lattice=lattice,
                                   evidence="candidate")
            except ValueError:
                pass
        return fallback, "left_to_right"
