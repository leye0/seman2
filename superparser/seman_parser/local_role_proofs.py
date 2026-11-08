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
GROUNDABLE_ROLE_FEATURES = ("number", "person", "vform", "tense")


def _grounded_child_atoms(child: Any) -> dict[str, str]:
    """Inspect actual materialized child features, excluding open values.

    Strings here are the existing FeatureStructure serialization of atoms;
    `?variables`, lists of alternatives, nested structures and TOP cannot
    justify comparisons. No speculative lexical agreement is introduced.
    """
    features = getattr(child, "features", None)
    data = features.as_dict() if features is not None else {}
    if not isinstance(data, dict):
        return {}
    return {key: value for key in GROUNDABLE_ROLE_FEATURES
            if isinstance((value := data.get(key)), str)
            and value and not value.startswith("?")}


def _selected_lexical_head_atoms(child: Any, role: dict[str, Any]) -> dict[str, Any]:
    """Read a head's original features from the *selected* lexical leaf.

    Matching the original lattice by span/category alone would mix alternate
    readings. Here we only inspect the actual selected child's descendants;
    no lexical candidate is re-ranked, guessed, or assigned a new feature.
    """
    target = (tuple(role["head_analysis_span"]),
              role["head_lexical_category"], role["head_lemma"])
    stack = [child]
    visited: set[int] = set()
    matched: list[Any] = []
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        candidate = getattr(node, "lexical_candidate", None)
        if candidate is not None and (
                (candidate.span_start, candidate.span_end),
                candidate.category, candidate.lemma) == target:
            matched.append(candidate)
        stack.extend(getattr(node, "children", ()) or ())
    if len(matched) != 1:
        return {
            "proof_basis": "selected_materialized_child_lexical_leaf_exact_match",
            "status": "not_uniquely_observed",
            "head_analysis_span": list(role["head_analysis_span"]),
            "head_lexical_category": role["head_lexical_category"],
            "head_lemma": role["head_lemma"],
            "matching_selected_leaf_count": len(matched),
            "candidate_feature_atoms": {},
            "candidate_source": None,
            "whole_sentence_grammaticality_proven": False,
        }
    candidate = matched[0]
    # The candidate is a lexical *hypothesis*, not a ground-truth reading.
    return {
        "proof_basis": "selected_materialized_child_lexical_leaf_exact_match",
        "status": "unique_selected_lexical_leaf",
        "head_analysis_span": list(role["head_analysis_span"]),
        "head_lexical_category": role["head_lexical_category"],
        "head_lemma": role["head_lemma"],
        "matching_selected_leaf_count": 1,
        "candidate_feature_atoms": _grounded_child_atoms(candidate),
        "candidate_source": candidate.source,
        "whole_sentence_grammaticality_proven": False,
    }


def _declared_rhs_feature_equalities(rule: Any, children: tuple[Any, ...],
                                     subject_index: int,
                                     predicate_index: int) -> dict[str, Any]:
    """Audit only *direct* RHS equality in the exact selected grammar rule.

    Two occurrences of the same unification variable make the two RHS slots
    equal for that feature. Other restrictions (ancestors, semantic context,
    lexical alternatives, indirect bindings) are deliberately not inferred.
    Missing RHS features do not mean the language lacks an agreement rule.
    """
    rhs = tuple(rule.rhs)
    if len(rhs) != len(children) or any(
            symbol.category != child.category
            for symbol, child in zip(rhs, children)):
        raise ValueError("Materialized local children disagree with compiled rule RHS")
    side_features = {
        "subject": rhs[subject_index].features.as_dict(),
        "predicate": rhs[predicate_index].features.as_dict(),
    }
    equalities = []
    for feature in ("number", "person"):
        left = side_features["subject"].get(feature)
        right = side_features["predicate"].get(feature)
        if isinstance(left, str) and left.startswith("?") and len(left) > 1 \
                and left == right:
            equalities.append({
                "feature": feature,
                "shared_rhs_variable": left,
                "basis": "same_unification_variable_on_both_rhs_children",
            })
    return {
        "proof_basis": "exact_compiled_rule_rhs_for_accepted_local_composition",
        "subject_rhs_feature_terms": {
            feature: side_features["subject"].get(feature)
            for feature in ("number", "person")},
        "predicate_rhs_feature_terms": {
            feature: side_features["predicate"].get(feature)
            for feature in ("number", "person")},
        "explicit_shared_rhs_variable_equalities": equalities,
        "other_indirect_constraints_excluded_from_this_audit": True,
        "whole_sentence_agreement_proven": False,
    }


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


def resolved_local_subject_predicate_pairs(item: Any, *,
                                           compiled_rule: Any = None) -> list[dict[str, Any]]:
    """Prove *local* links only when both syntax anchors really resolved.

    ``item`` is the materialized ChartItem corresponding to the same
    positively validated rule analysis retained by the bounded sampler.
    No candidate string matching or grammar-rule-name inference is used.
    """
    if not item.rule_id or not item.children or not item.start < item.end:
        return []
    children = tuple(item.children)
    if compiled_rule is not None and compiled_rule.rule_id != item.rule_id:
        raise ValueError("Selected local rule and compiled rule identity disagree")
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
            subject_atoms = _grounded_child_atoms(children[subject["child_index"]])
            predicate_atoms = _grounded_child_atoms(children[predicate["child_index"]])
            lexical_heads = {
                "subject": _selected_lexical_head_atoms(
                    children[subject["child_index"]], subject),
                "predicate": _selected_lexical_head_atoms(
                    children[predicate["child_index"]], predicate),
            }
            lexical_child_comparisons = [{
                "role": name,
                "feature": feature,
                "lexical_candidate_atom": lexical_heads[name]["candidate_feature_atoms"][feature],
                "materialized_child_atom": child_atoms[feature],
                "same_atom": (
                    lexical_heads[name]["candidate_feature_atoms"][feature]
                    == child_atoms[feature]),
            } for name, child_atoms in (("subject", subject_atoms),
                                        ("predicate", predicate_atoms))
                for feature in ("number", "person")
                if feature in lexical_heads[name]["candidate_feature_atoms"]
                and feature in child_atoms]
            subject_lexical_atoms = lexical_heads["subject"]["candidate_feature_atoms"]
            predicate_lexical_atoms = lexical_heads["predicate"]["candidate_feature_atoms"]
            cross_lexical_comparisons = [{
                "feature": feature,
                "subject_lexical_candidate_atom": subject_lexical_atoms[feature],
                "predicate_lexical_candidate_atom": predicate_lexical_atoms[feature],
                "same_atom": (subject_lexical_atoms[feature]
                              == predicate_lexical_atoms[feature]),
            } for feature in ("number", "person")
                if feature in subject_lexical_atoms and feature in predicate_lexical_atoms]
            rule_constraints = (
                _declared_rhs_feature_equalities(
                    compiled_rule, children,
                    subject["child_index"], predicate["child_index"])
                if compiled_rule is not None else None)
            comparisons = [{
                "feature": key,
                "subject_atom": subject_atoms[key],
                "predicate_atom": predicate_atoms[key],
                "same_atom": subject_atoms[key] == predicate_atoms[key],
            } for key in ("number", "person")
                if key in subject_atoms and key in predicate_atoms]
            result.append({
                "proof_basis": "accepted_local_rule_with_resolved_syntax_links",
                "category": item.category,
                "rule_id": item.rule_id,
                "analysis_span": [item.start, item.end],
                "subject": {"role": "subject", **subject},
                "predicate": {"role": role, **predicate},
                "materialized_child_feature_atoms": {
                    "subject": subject_atoms,
                    "predicate": predicate_atoms,
                },
                "cross_child_grounded_atom_comparisons": comparisons,
                "selected_lexical_head_feature_observations": lexical_heads,
                "lexical_candidate_vs_child_atom_comparisons": lexical_child_comparisons,
                "cross_lexical_candidate_atom_comparisons": cross_lexical_comparisons,
                "lexical_candidate_conflict_proven": False,
                "local_rule_rhs_feature_constraints": rule_constraints,
                "grammatical_agreement_requirement_proven": False,
                "same_accepted_local_composition": True,
                "global_tree_proven": False,
                "whole_sentence_relation_proven": False,
                "grammatical_conflict_proven": False,
            })
            if len(result) >= 4:
                return result
    return result
