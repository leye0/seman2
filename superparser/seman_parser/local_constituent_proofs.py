"""Bounded positive witnesses from *successfully materialized* local rules.

The caller must invoke ``record`` only AFTER a composition has passed the
materializer's contextual unification and positive-evidence checks. A packed
forest node or a rejected derivation is never a constituent proof. The pool
is an observational sample, not an exhaustive set or a global syntax tree.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class BoundedLocalConstituentProofs:
    """Keep a few source-span-aware witnesses without changing search."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("local constituent sample limit must be positive")
        self.limit = limit
        self.observed = 0
        self.samples: list[dict[str, Any]] = []
        self._keys: set[tuple[Any, ...]] = set()

    @staticmethod
    def _rank(item: Mapping[str, Any]) -> tuple[int, int]:
        start, end = item["analysis_span"]
        return (end - start, len(item["children"]))

    @staticmethod
    def _key(item: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            item["category"], tuple(item["analysis_span"]), item["rule_id"],
            tuple((c["category"], tuple(c["analysis_span"]), c["rule_id"])
                  for c in item["children"]),
            repr(item["required_context_features"]),
        )

    def record(self, *, category: str, analysis_span: Sequence[int], rule_id: str,
               children: Sequence[Mapping[str, Any]],
               verified_features: Mapping[str, Any],
               required_context_features: Mapping[str, Any],
               required_positive_features: Sequence[str],
               witnessed_positive_features: Sequence[str]) -> None:
        """Record an actual accepted rule composition, never a candidate hint."""
        start, end = analysis_span
        if not (isinstance(start, int) and isinstance(end, int) and
                0 <= start < end and rule_id and children):
            raise ValueError("A local rule proof needs a rule and nonempty span/children")
        if not set(required_positive_features).issubset(witnessed_positive_features):
            raise ValueError("A constituent cannot be proven with missing positive features")
        self.observed += 1
        item = {
            "proof_basis": "materialized_rule_after_context_unification",
            "category": category,
            "analysis_span": [start, end],
            "rule_id": rule_id,
            "children": [{"child_index": i, "category": child["category"],
                          "analysis_span": list(child["analysis_span"]),
                          "rule_id": child.get("rule_id")}
                         for i, child in enumerate(children)],
            "verified_features": dict(verified_features),
            "required_context_features": dict(required_context_features),
            "required_positive_features": sorted(set(required_positive_features)),
            "witnessed_positive_features": sorted(set(witnessed_positive_features)),
            "global_tree_selected": False,
            "whole_sentence_grammaticality_proven": False,
        }
        key = self._key(item)
        if key in self._keys:
            return
        # Avoid a full sample of alternative analyses of the same small span.
        # Both breadth and long-span examples remain explicitly sampled.
        same_span = [i for i, old in enumerate(self.samples)
                     if old["category"] == category and
                     old["analysis_span"] == item["analysis_span"]]
        replace_index = None
        if len(same_span) >= 2:
            weakest = min(same_span, key=lambda i: (self._rank(self.samples[i]), i))
            if self._rank(item) <= self._rank(self.samples[weakest]):
                return
            replace_index = weakest
        elif len(self.samples) >= self.limit:
            weakest = min(range(len(self.samples)),
                          key=lambda i: (self._rank(self.samples[i]), i))
            if self._rank(item) <= self._rank(self.samples[weakest]):
                return
            replace_index = weakest
        if replace_index is not None:
            self._keys.remove(self._key(self.samples[replace_index]))
            self.samples[replace_index] = item
        else:
            self.samples.append(item)
        self._keys.add(key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "seman2-local-constituent-proof-sample-v1",
            "observed_materialized_rule_analyses": self.observed,
            "sampled_local_constituents": len(self.samples),
            "sample_limit": self.limit,
            "truncated": self.observed > len(self.samples),
            "sampling_policy": "longer_spans_with_at_most_two_variants_per_category_span",
            "witnesses": sorted(self.samples, key=lambda s: (
                -(s["analysis_span"][1] - s["analysis_span"][0]),
                s["analysis_span"][0], s["category"], s["rule_id"])),
            "exhaustive": False,
            "global_tree_proven": False,
            "sentence_grammatical_fault_established": False,
        }
