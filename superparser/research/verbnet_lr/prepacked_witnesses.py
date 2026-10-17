"""Conservative, opt-in reuse of C witnesses during vector-forest extraction.

Only *structurally unique, context-independent* constituents can be replayed.
All alternatives and lexical hypotheses remain in the canonical forest. The
normal materializer handles anything that fails the proof, including variables,
positive-evidence requirements, multiple derivations and budget truncation.
This module never invents productions or upgrades candidate evidence to gold.
"""
from __future__ import annotations

from collections import Counter

from seman_parser.features import Variable, Disjunction, FeatureStructure, unify
from seman_parser.symbols import intern
from seman_parser.vector_chart import (
    AnalysisUse, CompactAnalysis, LexicalDerivation, RuleDerivation,
    _feature_evidence, _rule_evidence,
)


def _contains_variable(value):
    if isinstance(value, Variable):
        return True
    if isinstance(value, FeatureStructure):
        return any(_contains_variable(v) for _, v in value.items())
    if isinstance(value, Disjunction):
        return any(_contains_variable(v) for v in value.options)
    return False


class PrepackedWitnessIndex:
    """Admit only witnesses with a proof of a unique native forest derivation.

    Uniqueness is checked in the *completed* category-level vector forest, not
    claimed from the C matcher's limited beam. A single lexical alternative and
    exactly one original rule/path at every descendant are necessary. Empty RHS
    feature requirements mean no hidden parent-to-child bindings are skipped.
    """

    def __init__(self, hits):
        self.hits = tuple(hits)
        self.eligible = {}
        self.stats = Counter(offered=len(self.hits))
        self._compiled = None
        self._forest = None

    def bind(self, compiled, forest, lattice):
        self._compiled = compiled
        self._forest = forest
        if forest.budget_exceeded:
            self.stats["skipped_incomplete_forest"] += 1
            return
        self._candidate_ids = {id(c) for c in lattice.candidates}
        for hit in self.hits:
            tree = hit.tree
            if tree is None or tree.lexical_candidate is not None:
                self.stats["skipped_non_constituent"] += 1
                continue
            row = self._certify(tree, set())
            if row is None:
                self.stats["rejected_nonunique_or_contextual"] += 1
                continue
            node_id = row
            existing = self.eligible.get(node_id)
            if existing is not None and existing is not tree:
                # Never let C choose between two local witnesses.
                self.eligible.pop(node_id, None)
                self.stats["rejected_multiple_hits"] += 1
                continue
            self.eligible[node_id] = tree
        self.stats["certified"] = len(self.eligible)

    def _unique_path(self, partial_id):
        path = []
        seen = set()
        while partial_id is not None:
            if partial_id in seen:
                return None
            seen.add(partial_id)
            partial = self._forest.partials[partial_id]
            if len(partial.derivations) != 1:
                return None
            edge = partial.derivations[0]
            path.append(edge.child_id)
            partial_id = edge.previous_id
        return tuple(reversed(path))

    def _certify(self, tree, ancestors):
        node = self._forest.by_key.get((tree.start, tree.end, intern(tree.category)))
        if node is None or node.node_id in ancestors or len(node.derivations) != 1:
            return None
        derivation = node.derivations[0]
        if tree.lexical_candidate is not None:
            candidate = tree.lexical_candidate
            if (
                id(candidate) not in self._candidate_ids
                or not isinstance(derivation, LexicalDerivation)
                or len(derivation.candidates) != 1
                or derivation.candidates[0] is not candidate
                or _contains_variable(candidate.features)
            ):
                return None
            return node.node_id
        if not isinstance(derivation, RuleDerivation):
            return None
        compiled_rule = self._compiled.rules[derivation.rule_index]
        rule = compiled_rule.rule
        if (
            rule.rule_id != tree.rule_id
            or len(rule.rhs) != len(tree.children)
            or _contains_variable(rule.lhs.features)
            or any(s.features.features or s.requires for s in rule.rhs)
            or tree.features.as_dict() != rule.lhs.features.as_dict()
        ):
            return None
        path = self._unique_path(derivation.partial_id)
        if path is None or len(path) != len(tree.children):
            return None
        for child_id, child in zip(path, tree.children):
            if self._certify(child, ancestors | {node.node_id}) != child_id:
                return None
        return node.node_id

    def take(self, node_id, state, materializer):
        tree = self.eligible.get(node_id)
        if tree is None:
            return None
        # An outer binding environment may constrain unexported descendants.
        # Until replay supports contextual re-unification, bypass ONLY closed
        # contexts: this never swallows an unresolved agreement dependency.
        if state.bindings or _contains_variable(state.constraint):
            self.stats["contextual_skips"] += 1
            return None
        # Parent context still has to unify with this particular constituent.
        result = unify(state.constraint, tree.features, state.bindings)
        if result is None:
            self.stats["context_rejected"] += 1
            return None
        merged, env = result
        analysis = self._replay(tree, materializer)
        if not set(state.required_features).issubset(analysis.evidence):
            self.stats["evidence_rejected"] += 1
            return None
        self.stats["reused"] += 1
        self.stats["estimated_unifications_avoided"] += self._internal_nodes(tree)
        return CompactAnalysis(
            analysis.analysis_id, node_id, merged, analysis.score,
            dict(env), analysis.evidence, rule_index=analysis.rule_index,
            children=tuple(AnalysisUse(use.analysis, use.features, dict(env))
                           for use in analysis.children),
        )

    @staticmethod
    def _internal_nodes(tree):
        return int(tree.rule_id is not None) + sum(
            PrepackedWitnessIndex._internal_nodes(child) for child in tree.children
        )

    def _replay(self, tree, materializer):
        node = self._forest.by_key[(tree.start, tree.end, intern(tree.category))]
        derivation = node.derivations[0]
        if tree.lexical_candidate is not None:
            candidate = tree.lexical_candidate
            return CompactAnalysis(
                next(materializer._analysis_ids), node.node_id,
                candidate.features, candidate.score, {},
                _feature_evidence(candidate.features), candidate=candidate,
            )
        assert isinstance(derivation, RuleDerivation)
        rule_index = derivation.rule_index
        rule = self._compiled.rules[rule_index].rule
        children = tuple(self._replay(child, materializer) for child in tree.children)
        return CompactAnalysis(
            next(materializer._analysis_ids), node.node_id,
            rule.lhs.features,
            sum(child.score for child in children) + rule.score - materializer.RULE_COST,
            {}, _rule_evidence(rule, children), rule_index=rule_index,
            children=tuple(AnalysisUse(child, child.features, {}) for child in children),
        )

    def summary(self):
        return dict(self.stats)
