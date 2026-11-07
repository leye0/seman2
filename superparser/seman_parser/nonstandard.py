"""Explicit, local evidence for marked linguistic usage in selected trees.

This module never repairs source text, changes unification, or grants a parse.
Only a grammar rule with an overt ``usage_deviation`` provenance declaration
can create a deviation record; both conflicting child features are checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

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
    parent_category: str = ""
    subject_category: str = ""
    predicate_category: str = ""
    parent_path: tuple[int, ...] = ()
    subject_path: tuple[int, ...] = ()
    predicate_path: tuple[int, ...] = ()
    subject_rule_id: str | None = None
    predicate_rule_id: str | None = None
    intent_provenance: str | None = None

    def as_dict(
        self, *, reference_span: Callable[[int, int], tuple[int, int] | None] | None = None,
    ) -> dict[str, Any]:
        """Export exact analysis coordinates; map reference offsets only when supplied.

        A null reference span is never guessed or described as a source offset:
        it can mean a synthetic delimiter or an otherwise unmappable region.
        """
        def map_span(span: tuple[int, int]) -> tuple[list[int] | None, str]:
            if reference_span is None:
                return None, "not_provided"
            mapped = reference_span(*span)
            if mapped is None:
                return None, "unavailable"
            if (len(mapped) != 2 or not all(isinstance(v, int) for v in mapped)
                    or mapped[0] < 0 or mapped[0] >= mapped[1]):
                raise ValueError("Invalid reference span mapping")
            return list(mapped), "exact"

        parent_ref, parent_mapping = map_span(self.parent_span)
        subject_ref, subject_mapping = map_span(self.subject_span)
        predicate_ref, predicate_mapping = map_span(self.predicate_span)
        return {
            "kind": self.kind,
            "status": "nonstandard_attested",
            "relation": self.relation,
            "rule_id": self.rule_id,
            "parent_span": list(self.parent_span),
            "parent_reference_span": parent_ref,
            "parent_reference_mapping": parent_mapping,
            "subject": {
                "surface": self.subject_surface,
                "analysis_span": list(self.subject_span),
                "reference_span": subject_ref,
                "reference_mapping": subject_mapping,
                "features": self.subject_features,
            },
            "predicate": {
                "surface": self.predicate_surface,
                "analysis_span": list(self.predicate_span),
                "reference_span": predicate_ref,
                "reference_mapping": predicate_mapping,
                "features": self.predicate_features,
            },
            "constraint": f"subject.{self.feature} == predicate.{self.feature}",
            "expected": self.expected,
            "observed": self.observed,
            "register": self.register,
            "intent": self.intent,
            "intent_provenance": self.intent_provenance,
            "evidence": {
                "type": "explicit_marked_grammar_rule",
                "rule_id": self.rule_id,
                "parent": {
                    "category": self.parent_category,
                    "path": list(self.parent_path),
                    "analysis_span": list(self.parent_span),
                },
                "subject": {
                    "category": self.subject_category,
                    "path": list(self.subject_path),
                    "rule_id": self.subject_rule_id,
                },
                "predicate": {
                    "category": self.predicate_category,
                    "path": list(self.predicate_path),
                    "rule_id": self.predicate_rule_id,
                },
            },
        }


def collect_usage_deviations(root: ChartItem | None, text: str) -> tuple[UsageDeviation, ...]:
    """Read only rule-licensed conflicts, anchored to selected child spans."""
    if root is None:
        return ()
    result: list[UsageDeviation] = []
    seen: set[tuple[Any, ...]] = set()

    def visit(node: ChartItem, path: tuple[int, ...]) -> None:
        template = node.provenance.detail.get("usage_deviation")
        if template is not None:
            if node.provenance.source != "rule" or node.rule_id is None:
                raise ValueError("A lexical node cannot license a structural deviation")
            subject_index = int(template["subject_child"])
            predicate_index = int(template["predicate_child"])
            if (subject_index == predicate_index or subject_index < 0 or predicate_index < 0
                    or max(subject_index, predicate_index) >= len(node.children)):
                raise ValueError("Deviation must identify two distinct rule children")
            subject = node.children[subject_index]
            predicate = node.children[predicate_index]
            feature = str(template["feature"])
            expected = str(template["expected"])
            observed = str(template["observed"])
            subj_features = subject.features.as_dict()
            pred_features = predicate.features.as_dict()
            if (not feature or expected == observed or
                    subj_features.get(feature) != expected or
                    pred_features.get(feature) != observed):
                raise ValueError("Usage deviation contradicts its actual child features")
            for child in (subject, predicate):
                if not (node.start <= child.start < child.end <= node.end):
                    raise ValueError("Deviation child lies outside its licensing rule span")
            intent = str(template.get("intent", "unknown"))
            intent_provenance = template.get("intent_provenance")
            if intent != "unknown" and not intent_provenance:
                raise ValueError("Non-unknown intent requires explicit annotation provenance")
            identity = (node.rule_id, node.start, node.end, subject.start, subject.end,
                        predicate.start, predicate.end, str(template["kind"]), feature)
            if identity not in seen:
                seen.add(identity)
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
                intent=intent,
                parent_category=node.category,
                subject_category=subject.category,
                predicate_category=predicate.category,
                parent_path=path,
                subject_path=path + (subject_index,),
                predicate_path=path + (predicate_index,),
                subject_rule_id=subject.rule_id,
                predicate_rule_id=predicate.rule_id,
                intent_provenance=str(intent_provenance) if intent_provenance else None,
                ))
        for index, child in enumerate(node.children):
            visit(child, path + (index,))

    visit(root, ())
    return tuple(result)
