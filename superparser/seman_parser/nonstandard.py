"""Explicit, local evidence for marked linguistic usage in selected trees.

This module never repairs source text, changes unification, or grants a parse.
Only a grammar rule with an overt ``usage_deviation`` provenance declaration
can create a deviation record; both conflicting child features are checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .chart import ChartItem


@dataclass(frozen=True, slots=True)
class UsageDeviation:
    kind: str
    relation: str
    rule_id: str
    parent_span: tuple[int, int]
    subject_span: tuple[int, int]
    predicate_span: tuple[int, int]
    subject_surface: str
    predicate_surface: str
    feature: str
    expected: str
    observed: str
    subject_features: dict[str, Any]
    predicate_features: dict[str, Any]
    register: str
    intent: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": "nonstandard_attested",
            "relation": self.relation,
            "rule_id": self.rule_id,
            "parent_span": list(self.parent_span),
            "subject": {
                "surface": self.subject_surface,
                "analysis_span": list(self.subject_span),
                "features": self.subject_features,
            },
            "predicate": {
                "surface": self.predicate_surface,
                "analysis_span": list(self.predicate_span),
                "features": self.predicate_features,
            },
            "constraint": f"subject.{self.feature} == predicate.{self.feature}",
            "expected": self.expected,
            "observed": self.observed,
            "register": self.register,
            "intent": self.intent,
        }


def collect_usage_deviations(root: ChartItem | None, text: str) -> tuple[UsageDeviation, ...]:
    """Read only rule-licensed conflicts, anchored to selected child spans."""
    if root is None:
        return ()
    result: list[UsageDeviation] = []

    def visit(node: ChartItem) -> None:
        template = node.provenance.detail.get("usage_deviation")
        if template is not None:
            if node.provenance.source != "rule" or node.rule_id is None:
                raise ValueError("A lexical node cannot license a structural deviation")
            subject = node.children[int(template["subject_child"])]
            predicate = node.children[int(template["predicate_child"])]
            feature = str(template["feature"])
            expected = str(template["expected"])
            observed = str(template["observed"])
            subj_features = subject.features.as_dict()
            pred_features = predicate.features.as_dict()
            if subj_features.get(feature) != expected or pred_features.get(feature) != observed:
                raise ValueError("Usage deviation contradicts its actual child features")
            result.append(UsageDeviation(
                kind=str(template["kind"]),
                relation=str(template["relation"]),
                rule_id=node.rule_id,
                parent_span=(node.start, node.end),
                subject_span=(subject.start, subject.end),
                predicate_span=(predicate.start, predicate.end),
                subject_surface=text[subject.start:subject.end],
                predicate_surface=text[predicate.start:predicate.end],
                feature=feature,
                expected=expected,
                observed=observed,
                subject_features=subj_features,
                predicate_features=pred_features,
                register=str(template.get("register", "unknown")),
                intent=str(template.get("intent", "unknown")),
            ))
        for child in node.children:
            visit(child)

    visit(root)
    return tuple(result)
