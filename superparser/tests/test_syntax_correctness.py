"""Adversarial checks for best-tree grammatical plausibility."""

from __future__ import annotations

from pathlib import Path

from seman_parser import Parser
from seman_parser.vector_chart import RuleDerivation


DATA = Path(__file__).resolve().parents[1] / "data"


def parser() -> Parser:
    return Parser.from_dir(DATA, cache_size=0)


def nodes(root):
    yield root
    for child in root.children:
        yield from nodes(child)


def rules(root) -> list[str]:
    return [node.rule_id for node in nodes(root) if node.rule_id is not None]


def test_active_and_passive_minimal_pair() -> None:
    active = parser().parse("John opened the door.").result.best()
    passive = parser().parse("The door was opened by John.").result.best()
    assert active is not None and passive is not None
    assert active.rule_id == "clause_np_vp"
    assert "clause_passive" not in rules(active)
    assert passive.rule_id == "clause_passive"
    assert "vp_passive_by_flat" in rules(passive)


def test_ditransitive_requires_lexical_valency() -> None:
    gave = parser().parse("Mary gave John a book.").result.best()
    remembered = parser().parse("Mary remembered the book.").result.best()
    assert gave is not None and remembered is not None
    assert "vp_ditransitive" in rules(gave)
    assert "vp_ditransitive" not in rules(remembered)
    assert "vp_transitive" in rules(remembered)


def test_compound_subject_is_not_reanalyzed_as_a_relative() -> None:
    text = "A classroom project could encourage kindness."
    best = parser().parse(text).result.best()
    assert best is not None
    assert best.rule_id == "clause_np_vp"
    assert text[best.children[0].start:best.children[0].end] == "A classroom project"
    assert "np_relative_obj" not in rules(best)
    assert "wh_bare" not in rules(best)


def test_adverb_modifies_the_predicate_not_the_object_np() -> None:
    best = parser().parse("They remembered the event differently.").result.best()
    assert best is not None
    assert "vp_adv" in rules(best)
    assert "np_reflexive_adv" not in rules(best)
    assert "np_det_n_adv" not in rules(best)


def test_zero_complement_clause_keeps_clause_boundary() -> None:
    text = "He said the picture mattered because he could not read every word yet."
    best = parser().parse(text).result.best()
    assert best is not None
    assert best.rule_id == "clause_np_vp"
    assert "vp_zero_clause" in rules(best)
    assert "np_quote" not in rules(best)
    assert text[best.children[0].start:best.children[0].end] == "He"


def test_pp_attachment_alternatives_remain_in_shared_forest() -> None:
    result = parser().parse("The child watched the man with a telescope.").result
    assert result.completed
    forest = result.shared_forest
    assert forest is not None
    rule_ids = {
        forest.compiled.rules[derivation.rule_index].rule.rule_id
        for node in forest.nodes
        for derivation in node.derivations
        if isinstance(derivation, RuleDerivation)
    }
    assert "vp_pp" in rule_ids
    assert rule_ids & {"np_pp", "np_pp_mod", "np_rel_pp"}


def test_passive_adverb_is_not_misread_as_ditransitive_recipient() -> None:
    best = parser().parse("The machine was inspected yesterday.").result.best()
    assert best is not None
    assert best.rule_id == "clause_passive"
    assert "vp_adv" in rules(best)
    assert "clause_passive_ditrans" not in rules(best)


def test_prepositional_adjunct_beats_spurious_participial_subject() -> None:
    text = "The children waited near the entrance."
    best = parser().parse(text).result.best()
    assert best is not None
    assert text[best.children[0].start:best.children[0].end] == "The children"
    assert "vp_pp" in rules(best)
    assert "pp_prep_np" in rules(best)
    assert "np_part_ed" not in rules(best)


def test_comma_vp_coordination_requires_actual_comma() -> None:
    coordinated = parser().parse("John sang, danced.").result.best()
    uncoordinated = parser().parse("John sang near the entrance.").result.best()
    assert coordinated is not None and uncoordinated is not None
    assert "vp_comma_coord" in rules(coordinated)
    assert "vp_comma_coord" not in rules(uncoordinated)


def test_legitimate_passive_ditransitive_remains_available() -> None:
    best = parser().parse("John was given a book.").result.best()
    assert best is not None
    assert best.rule_id == "clause_passive_ditrans"


def test_temporal_preposition_and_spelled_numbers_keep_their_categories() -> None:
    text = "Maya counted the minutes until seven forty and decided twelve minutes was plenty."
    result = parser().parse(text).result
    best = result.best()
    assert best is not None
    leaves = [node.lexical_candidate for node in nodes(best) if node.lexical_candidate]
    selected = {(leaf.surface.casefold(), leaf.category) for leaf in leaves}
    assert ("until", "PREP") in selected
    assert ("twelve", "NUM") in selected
    assert "np_n_clause" not in rules(best)
    assert "vp_coord_finite" in rules(best)


def test_bare_noun_cannot_absorb_an_ordinary_finite_clause() -> None:
    best = parser().parse("Twelve minutes was plenty.").result.best()
    assert best is not None
    assert "np_n_clause" not in rules(best)
    assert best.children[0].category == "NP"
    assert "Twelve minutes" == "Twelve minutes was plenty."[
        best.children[0].start:best.children[0].end
    ]


def test_embedded_wh_object_keeps_filler_subject_and_predicate_separate() -> None:
    text = "Laura asked which route David chose."
    best = parser().parse(text).result.best()
    assert best is not None
    assert "vp_wh_embed" in rules(best)
    assert "wh_clause_obj_embedded" in rules(best)
    wh_clause = next(
        node for node in nodes(best) if node.rule_id == "wh_clause_obj_embedded"
    )
    assert [text[child.start:child.end] for child in wh_clause.children] == [
        "which route", "David", "chose",
    ]


def test_direct_wh_subject_question_remains_available() -> None:
    best = parser().parse("Who arrived?").result.best()
    assert best is not None
    assert best.rule_id == "clause_wh_subj"
