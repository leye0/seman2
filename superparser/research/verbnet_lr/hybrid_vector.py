"""Opt-in C-guided vector parse forest; never replaces classic syntax.

This first hybrid slice learns support for the *original* typed productions
from complete trees, including recursively licensed extensions already
present in the grammar. It changes only the order of the compiled
first-category rule agenda. It NEVER deletes lexical readings, productions
or forest alternatives, and never changes grammar scores.

The ordinary VectorGrammar remains the authoritative reference. In a
bounded, incomplete chart, the hybrid retries with the original rule
order rather than trusting a possibly truncated guided derivation.
Sentence syntax remains a normal Parser ParseReport / ParseResult with
full ChartItem children, grammar features and SyntacticPackage links.

No independently labelled gold is inferred from an observed parse.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from research.verbnet_lr.hierarchical_pattern_memory import HierarchicalPatternMemory
from seman_parser.chart import ChartItem, ParseResult
from seman_parser.engine import Parser, ParserResources, ParseReport
from seman_parser.vector_chart import VectorGrammar


class GuidedVectorGrammar(VectorGrammar):
    """Same productions and unifier; ordered alternatives, never filtering."""

    def __init__(self, grammar, *, support, min_support: int = 2):
        super().__init__(grammar)
        if min_support < 1:
            raise ValueError("min_support must be >=1")
        self.rule_support = dict(support)
        self.min_support = min_support
        self.active_support = {
            key: value for key, value in support.items() if value >= min_support
        }
        self.prioritized_edges = 0
        self.touched_categories = 0
        for category, indices in tuple(self.first.items()):
            ordered = tuple(sorted(indices, key=lambda i: (
                -self.active_support.get(self.rules[i].rule.rule_id, 0), i)))
            self.prioritized_edges += sum(
                int(before != after)
                for before, after in zip(indices, ordered)
            )
            self.touched_categories += int(ordered != indices)
            self.first[category] = ordered


class HybridVectorParser(Parser):
    """Research prototype combining learned C rule support + complete chart.

    .observe() is EXPLICIT. Only a complete, already materialized
    grammar-derived CLAUSE is usable. A rule counter is NOT proof that a
    learned structure is semantically or syntactically gold.

    This pass integrates a learned hierarchical grammar-rule agenda, not
    arbitrary learned regex quantifiers or preverified subtree injection.
    """

    def __init__(self, resources: ParserResources, *,
                 min_rule_sentences: int = 2,
                 **kwargs: Any):
        super().__init__(resources, **kwargs)
        self.patterns = HierarchicalPatternMemory(
            resources, min_rule_sentences=min_rule_sentences)
        self._original_vector = self._vector_grammar
        self._original_assembly = self._assembly_vector_grammar
        self._seen_sources: set[str] = set()
        self._source_evidence = Counter()
        self._guidance_revision = 0
        self._guide_stats: dict[str, int] = {
            "rules_with_support": 0,
            "prioritized_edges": 0,
            "touched_categories": 0,
        }

    def observe(self, report: ParseReport | ParseResult | ChartItem, *,
                source_id: str, evidence: str = "candidate") -> dict[str, int | bool]:
        """Learn from a completed tree. Provenance prevents duplicated votes.

        'candidate' counts locally grammar-unified evidence only. 'verified'
        must be supplied by an external gold verifier, never inferred here.
        """
        if evidence not in {"candidate", "verified"}:
            raise ValueError("Evidence must be candidate or verified")
        if not source_id:
            raise ValueError("source_id must be nonempty")
        if source_id in self._seen_sources:
            return {"learned": False, "distinct_rules": 0, "reused": False}
        if isinstance(report, ParseReport):
            result = report.result
            item = result.best() if result.completed else None
        elif isinstance(report, ParseResult):
            item = report.best() if report.completed else None
        else:
            item = report
        if item is None or item.category != self.goal_category:
            return {"learned": False, "distinct_rules": 0, "reused": False}
        # A complete tree must be connected to genuine lexical occurrences.
        stack = [item]
        lexical_count = 0
        while stack:
            child = stack.pop()
            if child.lexical_candidate is not None:
                lexical_count += 1
            elif not child.rule_id:
                return {"learned": False, "distinct_rules": 0, "reused": False}
            stack.extend(child.children)
        if not lexical_count:
            return {"learned": False, "distinct_rules": 0, "reused": False}

        info = self.patterns.observe(
            [item], failed=False,
            sentence_id=self.patterns.training_sentences + 1)
        self._seen_sources.add(source_id)
        self._source_evidence[evidence] += 1
        return {
            "learned": True,
            "distinct_rules": info["distinct_rules"],
            "reused": bool(info["reused_subtree_shapes"]),
        }

    def compile_guidance(self) -> dict[str, int]:
        """Publish observed grammar-rule support, keeping all original rules."""
        evidence = {
            key: count for key, count in self.patterns.rule_sentence_count.items()
            if count >= self.patterns.min_rule_sentences
        }
        self._vector_grammar = GuidedVectorGrammar(
            self._original_vector.grammar,
            support=evidence,
            min_support=self.patterns.min_rule_sentences)
        self._assembly_vector_grammar = GuidedVectorGrammar(
            self._original_assembly.grammar,
            support=evidence,
            min_support=self.patterns.min_rule_sentences)
        guided = self._vector_grammar
        self._guide_stats = {
            "rules_with_support": len(guided.active_support),
            "prioritized_edges": guided.prioritized_edges,
            "touched_categories": guided.touched_categories,
        }
        self._guidance_revision += 1
        # Learned priorities change the run. An old parse-result object
        # must never impersonate a parse under the new configuration.
        self._parse_cache.clear()
        return dict(self._guide_stats)

    def _parse_vector_text(self, text: str) -> ParseResult:
        result = super()._parse_vector_text(text)
        stats = result.stats
        if not isinstance(stats, dict):
            return result
        stats["hybrid_guidance"] = {
            **self._guide_stats, "revision": self._guidance_revision,
            "learned_sources": len(self._seen_sources)}
        if result.stats.get("budget_exceeded") and self._guidance_revision:
            # A reordered *truncated* agenda is not equivalent to the
            # original grammar chart. Explicitly retry with original
            # agenda, preserving original semantics and budgets.
            guided = self._vector_grammar
            try:
                self._vector_grammar = self._original_vector
                fallback = super()._parse_vector_text(text)
            finally:
                self._vector_grammar = guided
            if isinstance(fallback.stats, dict):
                fallback.stats["hybrid_guidance"] = {
                    **self._guide_stats, "revision": self._guidance_revision,
                    "learned_sources": len(self._seen_sources),
                    "fallback_after_guided_budget": True,
                    "guided_completed": result.completed,
                }
            return fallback
        return result

    def guidance_summary(self):
        return {
            **self._guide_stats,
            "revision": self._guidance_revision,
            "observed_sources": len(self._seen_sources),
            "provenance_counts": dict(self._source_evidence),
            "observed_structures": self.patterns.summary(),
        }
