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
