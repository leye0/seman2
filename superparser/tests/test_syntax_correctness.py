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


def test_sentence_initial_plural_is_not_promoted_to_a_name() -> None:
    best = parser().parse("Birds follow rivers.").result.best()
    assert best is not None
    subject = best.children[0]
    assert subject.rule_id == "np_bare"
    assert subject.children[0].category == "N"


def test_that_subject_relative_keeps_its_subject_gap() -> None:
    best = parser().parse("The dog that escaped returned.").result.best()
    assert best is not None
    assert "np_relative_subj" in rules(best)
    assert "wh_subj_clause" in rules(best)
    assert "np_relative_obj" not in rules(best)


def test_common_noun_genitive_is_not_a_compound_with_letter_s() -> None:
    best = parser().parse("The teacher's notebook was missing.").result.best()
    assert best is not None
    assert "np_genitive" in rules(best)
    leaves = [
        node.lexical_candidate.category
        for node in nodes(best) if node.lexical_candidate is not None
    ]
    assert "POSS" in leaves


def test_comma_delimited_causal_clause_is_licensed_generally() -> None:
    best = parser().parse(
        "Maya moved the equipment into the shed, because the rain started."
    ).result.best()
    assert best is not None
    assert best.rule_id == "clause_comma_sub"


def test_copular_locative_question_keeps_np_and_pp_separate() -> None:
    best = parser().parse("Are the keys inside the box?").result.best()
    assert best is not None
    assert best.rule_id == "clause_yn_cop_pp"
    assert [child.category for child in best.children] == ["COPULA", "NP", "PP", "QMARK"]


def test_existential_locative_keeps_pivot_and_pp_separate() -> None:
    best = parser().parse("There was a message inside the box.").result.best()
    assert best is not None
    assert best.rule_id == "clause_there_pp"
    assert [child.category for child in best.children] == ["EXPL", "COPULA", "NP", "PP"]


def test_less_frequent_wordnet_frames_remain_available() -> None:
    flooded = parser().parse("The river flooded.").result.best()
    visited = parser().parse("The scientist who visited spoke.").result.best()
    assert flooded is not None
    assert visited is not None
    assert "vp_intransitive" in rules(flooded)
    assert "np_relative_subj" in rules(visited)


def test_to_infinitive_cannot_be_reinterpreted_as_an_imperative_clause() -> None:
    best = parser().parse("Maya wanted to visit the museum.").result.best()
    assert best is not None
    assert "vp_to_inf" in rules(best)
    assert "vp_zero_clause" not in rules(best)
    assert "clause_imperative" not in rules(best)


def test_wordnet_valency_gaps_keep_productive_subject_control() -> None:
    for text in (
        "Lena decided to read the novel.",
        "Owen hoped to finish the project.",
        "Leo preferred to finish the project.",
    ):
        best = parser().parse(text).result.best()
        assert best is not None, text
        assert "vp_to_inf" in rules(best), text
        assert "clause_imperative" not in rules(best), text


def test_adverb_modifies_the_predicate_not_the_object_np() -> None:
    best = parser().parse("They remembered the event differently.").result.best()
    assert best is not None
    assert "vp_adv" in rules(best)
    assert "np_reflexive_adv" not in rules(best)
    assert "np_det_n_adv" not in rules(best)


def test_zero_complement_clause_keeps_clause_boundary() -> None:
    text = "He said the picture mattered because he could not read every word yet."
    result = parser().parse(text).result
    alternatives = result.alternatives(limit=8)
    expected = next(item for item in alternatives if item.rule_id == "clause_np_vp")
    assert "vp_zero_clause" in rules(expected)
    assert "np_quote" not in rules(expected)
    assert text[expected.children[0].start:expected.children[0].end] == "He"
    # Both attachment scopes for ``because`` are grammatical and tie under
    # the additive grammar score; neither may disappear from the k-best.
    assert any(item.rule_id == "clause_sub" for item in alternatives)


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
    # A WordNet prepositional frame is more informative than the generic
    # adjunct rule; both preserve the intended VP attachment.
    assert {"vp_pp", "vp_prepositional"} & set(rules(best))
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


def test_nominal_list_is_not_promoted_to_independent_clauses() -> None:
    text = (
        "They built a sample sign with a large picture, a short name, "
        "and a smaller paragraph explaining the route."
    )
    result = parser().parse(text).result
    best = result.best()
    assert best is not None
    assert best.rule_id == "clause_np_vp"
    assert not ({"clause_list3", "clause_list4"} & set(rules(best)))
    listed_np = next(node for node in nodes(best) if node.rule_id == "np_wh_list")
    members = [
        text[child.start:child.end]
        for child in listed_np.children
        if child.category == "NP"
    ]
    assert members == [
        "a sample sign with a large picture",
        "a short name",
        "a smaller paragraph explaining the route",
    ]


def test_comparative_construction_requires_a_comparative_preposition() -> None:
    ordinary = parser().parse("They built a sign with a picture.").result.best()
    comparative = parser().parse(
        "The container held less water than most children had guessed."
    ).result.best()
    assert ordinary is not None and comparative is not None
    assert not any(rule.startswith("np_comparative") for rule in rules(ordinary))
    assert "np_comparative_than" in rules(comparative)


def test_ed_verb_plus_pp_does_not_create_a_finite_passive() -> None:
    active = parser().parse("The children talked about raising money.").result.best()
    passive = parser().parse("The money was raised by the children.").result.best()
    assert active is not None and passive is not None
    assert active.rule_id == "clause_np_vp"
    assert "vp_part_pp" not in rules(active)
    assert "clause_passive" not in rules(active)
    assert passive.rule_id == "clause_passive"


def test_participial_np_cannot_absorb_an_active_subject_verb_object() -> None:
    # Bare object control is not yet represented for every lexical frame.
    # Until it is, an incomplete result is preferable to treating
    # ``She helped her`` as one passive participial noun phrase.
    result = parser().parse("She helped her remember without looking.").result
    best = result.best()
    if best is not None:
        assert "np_part_ed_obj" not in rules(best)


def test_prenominal_titles_are_lexically_licensed_not_arbitrary_nouns() -> None:
    """TITLE is a distinct function, not any WordNet noun preceding a name."""
    p = parser()
    for sentence in ("Captain Nemo arrived.", "Doctor Watson waited.",
                     "Professor Moriarty spoke.", "Lady Catherine smiled."):
        result = p.parse(sentence).result
        best = result.best()
        assert best is not None, (sentence, result.stats)
        assert "np_title_name" in rules(best), sentence
        titled = next(n for n in nodes(best) if n.rule_id == "np_title_name")
        assert titled.children[0].category == "TITLE", sentence
        assert titled.children[0].features.as_dict()["honorific"] == "true"

    for sentence in ("Lovely Dora smiled.", "River Mary smiled.",
                     "Carpet Dora spoke."):
        report = p.parse(sentence)
        # Noncompletion is acceptable; an illicit TITLE reading is not.
        assert all(
            "np_title_name" not in rules(root)
            for root in report.result.alternatives(limit=8)
        ), sentence


def test_title_licensing_keeps_wordnet_noun_alternatives() -> None:
    p = parser()
    for surface in ("captain", "doctor", "lovely", "think"):
        report = p.parse(surface.capitalize() + " arrived.")
        lexical = {
            c.category for c in report.lattice.candidates
            if c.surface.casefold() == surface
        }
        assert "N" in lexical, (surface, lexical)
    captain = p.parse("Captain Nemo arrived.")
    categories = {
        c.category for c in captain.lattice.candidates
        if c.surface.casefold() == "captain"
    }
    assert {"TITLE", "N"} <= categories, categories


def test_reporting_tag_with_real_participial_adjunct() -> None:
    text = "'It was a mistake,' I replied, quietly speaking to the witness."
    result = parser().parse(text).result
    best = result.best()
    assert best is not None, result.stats
    assert "dialogue_speech_tag_post_participial_adv_pp" in rules(best)


def test_comma_and_ing_required_for_reporting_participial_adjunct() -> None:
    p = parser()
    for sentence in (
        "'It was a mistake,' I replied quietly speaking to the witness.",
        "'It was a mistake,' I replied, quietly speak to the witness.",
    ):
        result = p.parse(sentence).result
        assert all(
            "dialogue_speech_tag_post_participial_adv_pp" not in rules(item)
            for item in result.alternatives(limit=6)
        ), sentence


def test_right_edge_transitive_participial_clause() -> None:
    result = parser().parse("Maya crossed the square, carrying a lantern.").result
    best = result.best()
    assert best is not None, result.stats
    assert "clause_final_transitive_participle" in rules(best)


def test_parenthetical_you_know_inside_postpredicate_vp() -> None:
    result = parser().parse("Mary waited, you know, near the entrance.").result
    best = result.best()
    assert best is not None, result.stats
    assert "parenthetical_interpersonal_you_know" in rules(best)
    assert "vp_postpredicate_parenthetical" in rules(best)


def test_parenthetical_verb_must_be_licensed_and_comma_delimited() -> None:
    p = parser()
    for sentence in (
        "Mary waited, you jump, near the entrance.",
        "Mary waited, you know near the entrance.",
        "Mary waited you know, near the entrance.",
    ):
        result = p.parse(sentence).result
        assert all(
            "parenthetical_interpersonal_you_know" not in rules(item)
            for item in result.alternatives(limit=6)
        ), sentence
