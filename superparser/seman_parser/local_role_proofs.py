"""Conservative role links from actual *accepted* local syntactic packages.

Unlike grammar-declared ``exports``, a SyntacticLink exists only if its
child's anchor resolved during _compose_syntax. A verified local subject /
predicate pair proves that one selected *local rule composition* linked
the two heads; it says nothing about full-sentence completion, author
intent, alternatives or grammatical faults.
"""
from __future__ import annotations

from typing import Any


# A resolved referent is not automatically a nominal head: the current
# open-world syntax package can inherit the first lexical anchor of a
# construction (including an OPEN-QUOTE or COPULA). Keep this *evidence*
# threshold conservative; it is not a lexical filter on recognition.
NOMINAL_SUBJECT_HEADS = frozenset({
    "N", "PRONOUN", "PROPER-NOUN", "WH-PRONOUN",
})
PREDICATE_EVENT_HEADS = frozenset({
    "V", "COPULA", "AUX", "AUX-BE",
})


def _resolved_link(link: Any, children: tuple[Any, ...]) -> dict[str, Any] | None:
    if (type(link.child_index) is not int or link.child_index < 0
            or link.child_index >= len(children)
            or not isinstance(link.target, str)):
        return None
    # Only actual lexical occurrence anchors, not inferred words or names.
    fields = link.target.split(":", 4)
    if len(fields) != 5 or fields[0] != "lex" or not fields[3] or not fields[4]:
        return None
    try:
        start, end = int(fields[1]), int(fields[2])
    except ValueError:
        return None
    child = children[link.child_index]
    if not child.start <= start < end <= child.end:
        return None
    return {
        "child_index": link.child_index,
        "child_category": child.category,
        "child_analysis_span": [child.start, child.end],
        "head_analysis_span": [start, end],
        "head_lexical_category": fields[3],
        "head_lemma": fields[4],
    }


def resolved_local_subject_predicate_pairs(item: Any) -> list[dict[str, Any]]:
    """Prove *local* links only when both syntax anchors really resolved.

    ``item`` is the materialized ChartItem corresponding to the same
    positively validated rule analysis retained by the bounded sampler.
    No candidate string matching or grammar-rule-name inference is used.
    """
    if not item.rule_id or not item.children or not item.start < item.end:
        return []
    children = tuple(item.children)
    subjects: list[dict[str, Any]] = []
    predicates: list[tuple[str, dict[str, Any]]] = []
    for link in item.syntax.links:
        if link.relation not in {"subject", "event", "predicate"}:
            continue
        resolved = _resolved_link(link, children)
        if resolved is None:
            continue
        if link.relation == "subject":
            if resolved["head_lexical_category"] in NOMINAL_SUBJECT_HEADS:
                subjects.append(resolved)
        else:
            if resolved["head_lexical_category"] in PREDICATE_EVENT_HEADS:
                predicates.append((link.relation, resolved))
    # A named predicate outranks an auxiliary/event when both were exported
    # by this rule. Do not assert which reading is linguistically intended.
    predicates.sort(key=lambda pair: (pair[0] != "predicate", pair[1]["child_index"]))
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for subject in subjects:
        for role, predicate in predicates:
            if subject["child_index"] == predicate["child_index"]:
                continue
            left, right = subject["child_analysis_span"], predicate["child_analysis_span"]
            if not (left[1] <= right[0] or right[1] <= left[0]):
                continue
            # Two names for the same resolved head are one local relation,
            # not two independent proofs. Prefer explicit `predicate`.
            key = (subject["child_index"], predicate["child_index"],
                   tuple(subject["head_analysis_span"]),
                   tuple(predicate["head_analysis_span"]))
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "proof_basis": "accepted_local_rule_with_resolved_syntax_links",
                "category": item.category,
                "rule_id": item.rule_id,
                "analysis_span": [item.start, item.end],
                "subject": {"role": "subject", **subject},
                "predicate": {"role": role, **predicate},
                "same_accepted_local_composition": True,
                "global_tree_proven": False,
                "whole_sentence_relation_proven": False,
                "grammatical_conflict_proven": False,
            })
            if len(result) >= 4:
                return result
    return result
