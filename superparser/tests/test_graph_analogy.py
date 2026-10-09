"""POC-05 tests for lossless partial structural analogy."""

from __future__ import annotations

from research.induction import (
    AnalogyPolicy,
    align_partial,
    parse_to_observation,
    propose_partial_analogies,
    root_snapshot,
)
from seman_parser.chart import ChartItem, PackedNode, ParseResult, Provenance
from seman_parser.features import FeatureStructure
from seman_parser.segmentation import LexicalLattice, tokenize
from seman_parser.semantics import SemanticGraph, SemanticPackage


def item(category, start, end, *, surface=None, rule=None, features=None, children=()):
    detail = {}
    if surface is not None:
        detail = {"surface": surface, "lemma": surface.lower()}
    return ChartItem(
        start=start,
        end=end,
        category=category,
        features=FeatureStructure.build(features or {}),
        semantic=SemanticPackage(SemanticGraph()),
        score=1.0,
        provenance=Provenance("rule" if rule else "fixture", detail),
        children=tuple(children),
        rule_id=rule,
    )


def clause(subject, verb, object_, *, adjunct=None, negation="false"):
    words = [subject, verb, object_] + ([] if adjunct is None else [adjunct])
    text = " ".join(words)
    starts = []
    cursor = 0
    for word in words:
        starts.append(cursor)
        cursor += len(word) + 1
    subject_node = item("NP", starts[0], starts[0] + len(subject), surface=subject)
    verb_node = item("V", starts[1], starts[1] + len(verb), surface=verb)
    object_node = item("NP", starts[2], starts[2] + len(object_), surface=object_)
    vp_children = [verb_node, object_node]
    if adjunct is not None:
        vp_children.append(item("ADVP", starts[3], len(text), surface=adjunct))
    vp = item("VP", starts[1], len(text), rule="vp_transitive", children=vp_children)
    root = item(
        "CLAUSE",
        0,
        len(text),
        rule="clause_np_vp",
        features={"negation": negation},
        children=(subject_node, vp),
    )
    all_items = [root, subject_node, vp, *vp_children]
    packed = {
        (node.start, node.end, index): PackedNode(
            node.start, node.end, node.category, node, [node]
        )
        for index, node in enumerate(all_items)
    }
    result = ParseResult(
        text,
        LexicalLattice(text, tokenize(text), ()),
        packed,
        (root,),
        True,
    )
    return parse_to_observation(result, parser_version="fixture")


def test_added_adjunct_is_an_explicit_lossless_residual():
    left = clause("john", "opened", "box")
    right = clause("mary", "opened", "door", adjunct="quickly")
    analogy = align_partial(left, left.root_ids[0], right, right.root_ids[0])
    assert analogy is not None
    assert analogy.left_residual_nodes == 0
    assert analogy.right_residual_nodes == 1
    assert analogy.instantiate("left") == root_snapshot(left, left.root_ids[0])
    assert analogy.instantiate("right") == root_snapshot(right, right.root_ids[0])


def test_protected_negation_cannot_be_erased_by_partial_matching():
    positive = clause("john", "opened", "box")
    negative = clause("john", "opened", "box", negation="true")
    assert align_partial(
        positive, positive.root_ids[0], negative, negative.root_ids[0]
    ) is None


def test_argument_order_is_preserved_instead_of_matching_equal_words():
    left = clause("dog", "follows", "man")
    right = clause("man", "follows", "dog")
    analogy = align_partial(left, left.root_ids[0], right, right.root_ids[0])
    assert analogy is not None
    paired_values = {
        (str(analogy.bindings_for("left")[name]), str(analogy.bindings_for("right")[name]))
        for name in analogy.bindings_for("left")
    }
    assert ("dog", "man") in paired_values
    assert ("man", "dog") in paired_values
    assert analogy.instantiate("left") == root_snapshot(left, left.root_ids[0])
    assert analogy.instantiate("right") == root_snapshot(right, right.root_ids[0])


def test_shallow_lexical_overlap_is_not_a_structural_analogy():
    left = clause("dog", "follows", "man")
    right = clause("dog", "sees", "tree")
    strict = AnalogyPolicy(min_shared_edges=4, min_coverage=0.9)
    assert align_partial(left, left.root_ids[0], right, right.root_ids[0], policy=strict)
    leaf_candidates = propose_partial_analogies(
        left,
        right,
        policy=AnalogyPolicy(min_shared_edges=1),
    )
    assert all(candidate.matched_edges >= 1 for candidate in leaf_candidates)


def test_candidate_boundaries_are_ranked_deterministically():
    left = clause("john", "opened", "box")
    right = clause("mary", "opened", "door", adjunct="slowly")
    first = propose_partial_analogies(left, right, limit=10)
    second = propose_partial_analogies(left, right, limit=10)
    assert [row.analogy_id for row in first] == [row.analogy_id for row in second]
    assert first
    assert first[0].left_root_id == left.root_ids[0]
    assert first[0].right_root_id == right.root_ids[0]
    assert first[0].instantiate("left") == root_snapshot(left, left.root_ids[0])
    assert first[0].instantiate("right") == root_snapshot(right, right.root_ids[0])
