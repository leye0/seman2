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
from dataclasses import dataclass, field, replace
from itertools import product
from functools import lru_cache
from typing import Any

from seman_parser.chart import ChartItem, _compose_syntax
from seman_parser.features import FeatureStructure, Variable, substitute_structure, unify
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.symbols import intern
from seman_parser.vector_chart import _project_bindings
from .positional_template_index import PositionalTemplateIndex


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
        self._positional_index = PositionalTemplateIndex()
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
        while tokens and tokens[-1].text in (".", "!", "?"):
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
        self._positional_index.add(categories, key)
        return key

    def _restore_contextual_features(
        self,
        item: ChartItem,
        constraint: FeatureStructure,
        inherited: dict[str, object],
    ) -> tuple[ChartItem, dict[str, object]] | None:
        """Reconstruct the original *contextual* feature path, top down.

        A bottom-up PredictiveParser._reduce() validates that the selected
        rules/lexical readings unify. It does NOT, however, push RHS feature
        requirements down into children's exported ChartItems. VectorGrammar
        does: a PRONOUN with no lexical gender can inherit gender=?g from
        its parent's slot. Losing ?g would erase an unresolved agreement/
        coreference constraint even though the tree and lexical senses match.

        Use the SAME feature unifier and substitute only legitimate grammar
        bindings. Never copy a recorded training sentence's feature values:
        a new sentence must re-unify its own lexical alternatives.
        """
        if item.lexical_candidate is not None:
            matched = unify(constraint, item.lexical_candidate.features, inherited)
            if matched is None:
                return None
            merged, bindings = matched
            return replace(item, features=merged, bindings=dict(bindings), _sig=None), bindings

        rule = self.rules.get(item.rule_id)
        if rule is None or len(rule.rhs) != len(item.children):
            return None
        matched = unify(constraint, rule.lhs.features, inherited)
        if matched is None:
            return None
        lhs, env = matched
        children = []
        for symbol, child in zip(rule.rhs, item.children):
            # The vector materializer visits each RHS child under precisely
            # the feature constraint declared by that grammar slot.
            if symbol.category != child.category:
                return None
            # The vector chart projects parent bindings onto the variables
            # actually used by this RHS interface. Carrying the entire
            # environment down would alias unrelated local ?g/?p variables,
            # spuriously resolve open features and reject valid templates.
            projected, relevant = _project_bindings(symbol.features, env)
            inherited_before = dict(env)
            result = self._restore_contextual_features(
                child, symbol.features, projected)
            if result is None:
                return None
            updated, child_env = result
            env = dict(child_env)
            for name, value in inherited_before.items():
                if name not in relevant:
                    env[name] = value
            children.append(updated)
        restored_children = tuple(children)
        return replace(
            item,
            features=substitute_structure(lhs, env),
            bindings=dict(env),
            children=restored_children,
            syntax=_compose_syntax(rule, restored_children),
            _sig=None,
        ), env

    @staticmethod
    def _lexical_slots(lattice):
        tokens = tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".", "!", "?"):
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
        # Direct inverted-index intersection replaces the former
        # branching trie traversal. A category lookup is NOT a grammatical
        # proof; actual unification remains in the bounded build below.
        found = self._positional_index.lookup(
            tuple(tuple(by_category) for by_category in options),
            limit=max_templates_checked, offset=template_offset)
        ids = found.template_ids
        count = found.total
        next_offset = found.next_offset
        incomplete = next_offset is not None or count > max_states
        if not ids and count == 0:
            return SnapResult((), lattice, 0, 0, 0, False, "unseen_pattern")
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
            # A bottom-up viable variant may conflict with an inherited
            # contextual constraint, while a later lexical variant of
            # the SAME complete rule tree is valid. Do not discard the
            # entire stored template after testing only variants[0].
            # The explicit max_variants / reductions budgets remain intact.
            best_item = None
            for compact in variants:
                item = self._materializer._materialize(compact)
                contextual = self._restore_contextual_features(
                    item, FeatureStructure.empty(), {})
                if contextual is None:
                    continue
                restored, _bindings = contextual
                if best_item is None or restored.score > best_item.score:
                    best_item = restored
            if best_item is not None:
                matched.append(SnapMatch(
                    template_id, best_item,
                    template.verified_observations > 0,
                    template.grammar_witness_observations > 0))
        # An Earley witness proves a derivation EXISTS, NOT that it is
        # the preferred grammatical realization. Use the actual grammar
        # and lexical score to rank viable complete structures. External
        # independent gold may take priority; bounded witness existence
        # is only a tie-breaker. No held-out annotations enter ranking.
        matched.sort(key=lambda m: (
            int(m.independently_verified_template),
            m.item.score,
            int(m.grammar_witness_template),
            self.templates[m.template_id].grammar_witness_observations,
            self.templates[m.template_id].candidate_observations,
            -m.template_id,
        ), reverse=True)
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
                 fallback=None, max_templates_checked: int = 128,
                 construction_guard: bool = True,
                 sampler: Any | None = None):
        if max_templates_checked < 1:
            raise ValueError("max_templates_checked must be positive")
        self.resources = resources
        self.index = index
        self.fallback = fallback or SemanCompiledReader(resources)
        self.max_templates_checked = max_templates_checked
        self.construction_guard = construction_guard
        self.sampler = sampler

    def parse(self, text: str, *, learn_candidate: bool = False,
              lattice: Any | None = None):
        if lattice is None:
            from seman_parser.segmentation import build_lattice
            lattice = build_lattice(
                text, self.resources.lexicon, multiword_max=1)
        elif lattice.text != text:
            raise ValueError("Prepared lattice text does not match input")
        if self.sampler is not None:
            # Just enqueue. The expensive verifier is NEVER called by parse.
            self.sampler.enqueue(text, lattice)
        snapped = self.index.match(
            lattice, max_templates_checked=self.max_templates_checked)
        if snapped.complete and self.construction_guard:
            from research.verbnet_lr.construction_guard import ConstructionGuard
            guard = ConstructionGuard(modal_forms={
                candidate.surface.casefold()
                for candidate in lattice.candidates
                if candidate.category == "MODAL"})
            # The templates remain intact in the index. A local structural
            # candidate is usable only when it ALSO passes the same generic
            # construction guard available to the existing L-R experiments.
            snapped.matches = tuple(
                matched for matched in snapped.matches
                if guard.validate(matched.item).acceptable)
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
