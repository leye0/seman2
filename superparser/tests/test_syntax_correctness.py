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
    assert "np_comparative_than" in rules(comparative), comparative.as_dict()


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




def test_nonclausal_coordination_requires_an_attested_phrase_connector() -> None:
    """Causal 'for' is COORD for clauses, not a linker of NP/VP/ADJP."""
    from seman_parser.grammar import load_grammar
    grammar = load_grammar(DATA / "grammar.jsonl")
    phrase_coordinations = 0
    for rule in grammar:
        if rule.lhs.category == "CLAUSE":
            continue
        # A genuinely clausal dash parenthesis is also a clause-level
        # construction: it has two overt dashes, causal FOR, a licensed
        # pronominal subject and an agreeing finite predicate. It is not
        # phrase-level coordination of nominal or verbal fragments.
        if (
            rule.lhs.category == "PARENTHETICAL"
            and rule.lhs.features.as_dict().get("causal_incise") == "true"
        ):
            assert tuple(s.category for s in rule.rhs) == (
                "DASH", "COORD", "NP", "VP", "DASH",
            ), rule.rule_id
            assert rule.rhs[1].features.as_dict().get("causal_coordination") == "true"
            assert "causal_coordination" in rule.rhs[1].requires
            assert rule.rhs[2].features.as_dict().get("pronominal") == "true"
            assert "pronominal" in rule.rhs[2].requires
            assert rule.rhs[3].features.as_dict().get("vform") == "finite"
            assert "vform" in rule.rhs[3].requires
            continue
        for symbol in rule.rhs:
            if symbol.category != "COORD":
                continue
            phrase_coordinations += 1
            assert symbol.features.as_dict().get("nominal_coordination") == "true", (
                rule.rule_id, "causal for must not coordinate phrases"
            )
            assert "nominal_coordination" in symbol.requires, rule.rule_id
    assert phrase_coordinations >= 30


def test_phrase_coordination_keeps_causal_for_as_clausal_alternative() -> None:
    p = parser()
    tests = (
        "John waited for Mary.",
        "Mary spoke to John for she was concerned.",
        "The boy and the girl waited.",
        "The boy or the girl waited.",
    )
    for sentence in tests:
        report = p.parse(sentence)
        readings = [
            c for c in report.lattice.candidates
            if c.surface.casefold() == "for" and c.category == "COORD"
        ]
        if "for" in sentence:
            assert readings, ("for retains its clausal reading", sentence)
            assert all("nominal_coordination" not in c.features.as_dict()
                       for c in readings)
        assert report.result.completed, (sentence, report.result.stats)

    def tree_nodes(item):
        yield item
        for child in item.children:
            yield from tree_nodes(child)

    # This is a syntactic distinction, not a dictionary deletion:
    # a 'for' clause connector must not complete NP-COORD-NP, VP-COORD-VP,
    # PP-COORD-PP or ADJP-COORD-ADJP productions.
    sentence = "The captain carried the box for the pilot."
    report = p.parse(sentence)
    for root in report.result.alternatives(limit=8):
        for item in tree_nodes(root):
            if item.category in {"NP", "VP", "ADJP", "PP"}:
                assert not any(
                    child.category == "COORD"
                    and sentence[child.start:child.end].casefold() == "for"
                    for child in item.children
                ), (item.rule_id, sentence)



def test_causal_for_initial_clause_requires_overt_finite_predicate() -> None:
    """The clausal 'for' cannot consume a dislocated NP/PP as its subject."""
    p = parser()
    def walk(node):
        yield node
        for child in node.children:
            yield from walk(child)
    for text in ("For I longed to see my friends.", "For the weather was cold."):
        result = p.parse(text).result
        assert result.completed, (text, result.stats)
        assert any(
            "coord_clause_causal_finite" in {n.rule_id for n in walk(root)}
            for root in result.alternatives(limit=12)
        ), text
    for text in ("For my part, I waited.", "For the captain, he waited."):
        result = p.parse(text).result
        assert result.completed, (text, result.stats)
        assert all(
            "coord_clause_causal_finite" not in {n.rule_id for n in walk(root)}
            for root in result.alternatives(limit=12)
        ), text
    readings = [
        c for c in p.parse("For I waited.").lattice.candidates
        if c.surface.casefold() == "for"
    ]
    assert {"COORD", "PREP"} <= {c.category for c in readings}
    assert any(c.category == "COORD"
               and c.features.as_dict().get("causal_coordination") == "true"
               for c in readings)


def test_personal_pronoun_is_not_an_appositive_nominal_subject() -> None:
    """Resumptive 'he' is a clause subject, not a second appositive NP."""
    from seman_parser.grammar import load_grammar
    grammar = load_grammar(DATA / "grammar.jsonl")
    for name in ("np_pronoun", "np_indef_pron"):
        assert grammar.by_id(name).lhs.features.as_dict()["pronominal"] == "true"
    for name in ("np_appos_comma", "clause_appositive_subject"):
        rule = grammar.by_id(name)
        appos = next(s for s in rule.rhs if "appos" in s.exports.values())
        assert appos.features.as_dict()["pronominal"] == "false"
    p = parser()
    def walk(node):
        yield node
        for child in node.children:
            yield from walk(child)
    for text in ("John, the doctor, waited.", "The captain, he waited."):
        result = p.parse(text).result
        assert result.completed, (text, result.stats)
    for text in ("John, he waited.", "The captain, he waited."):
        for root in p.parse(text).result.alternatives(limit=12):
            for node in walk(root):
                if node.rule_id == "np_appos_comma":
                    assert node.children[2].rule_id not in (
                        "np_pronoun", "np_indef_pron"
                    ), text


def test_vp_coordination_rejects_explicit_mixed_inflection_but_retains_unknown() -> None:
    """VP constituent forms agree; underspecified lexical form stays possible."""
    from seman_parser.grammar import load_grammar
    from seman_parser.features import FeatureStructure, unify
    grammar = load_grammar(DATA / "grammar.jsonl")
    for rule_id in ("vp_coord", "vp_comma_coord", "vp_comma_list", "vp_list3"):
        rule = grammar.by_id(rule_id)
        vp_symbols = [symbol for symbol in rule.rhs if symbol.category == "VP"]
        variable = f"?coord_form_{rule_id}"
        assert len(vp_symbols) >= 2
        assert all(sym.features.as_dict().get("vform") == variable
                   for sym in vp_symbols), rule_id
        assert rule.lhs.features.as_dict().get("vform") == variable
        first = unify(vp_symbols[0].features,
                      FeatureStructure.build({"vform": "finite"}))
        assert first is not None, rule_id
        for other in vp_symbols[1:]:
            # Once a finite predicate has fixed the shared form variable,
            # an independently attested participial predicate is excluded.
            assert unify(other.features,
                         FeatureStructure.build({"vform": "ed"}),
                         first[1]) is None, rule_id
            assert unify(other.features,
                         FeatureStructure.build({"vform": "finite"}),
                         first[1]) is not None, rule_id
            # Missing morphological evidence is not conflated with "ed".
            assert unify(other.features, FeatureStructure.empty(),
                         first[1]) is not None, rule_id


def test_selected_vp_coordination_never_unifies_known_finite_with_ed() -> None:
    """Adversarial literary constructions stay within the shared public parse."""
    parser_instance = parser()
    text = "With this resolution I traversed the northern highlands and fixed on one of the remotest of the Orkneys as the scene of my labours."
    result = parser_instance.parse(text, max_items=50000).result
    for root in result.alternatives(limit=5):
        for node in nodes(root):
            if node.rule_id not in {
                "vp_coord", "vp_comma_coord", "vp_comma_list", "vp_list3",
            }:
                continue
            forms = {
                child.features.as_dict().get("vform") for child in node.children
                if child.category == "VP"
            }
            assert not ({"finite", "ed"} <= forms), (node.rule_id, forms)



def test_no_duplicate_grammar_constructions_with_identical_semantics() -> None:
    """Do not pay for the same compiled rule more than once.

    Distinct semantic interpretations of one surface pattern are allowed;
    exact duplicates are not. This checks constraints, required features,
    handle exports, lhs/rhs categories and *all* semantic operations.
    """
    import json
    from collections import defaultdict
    patterns = [
        json.loads(line)
        for line in (DATA / "grammar.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip()
    ]
    recipes = {
        row["id"]: row.get("semantic")
        for row in (
            json.loads(line)
            for line in (DATA / "semantic_rules.jsonl").read_text(
                encoding="utf-8").splitlines() if line.strip()
        )
    }
    by_pattern: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rule in patterns:
        syntax = json.dumps(
            {"lhs": rule["lhs"], "rhs": rule["rhs"]},
            sort_keys=True,
        )
        semantic = json.dumps(recipes.get(rule["id"]), sort_keys=True)
        by_pattern[(syntax, semantic)].append(rule["id"])
    duplicates = [items for items in by_pattern.values() if len(items) > 1]
    assert not duplicates, duplicates



def load_tests(loader, tests, pattern):
    """Register module-level test_* functions with the unittest CI runner.

    unittest's default module loader only discovers TestCase subclasses;
    without this hook the grammar/reference checks were silently skipped.
    """
    import unittest
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            tests.addTest(unittest.FunctionTestCase(function, description=name))
    assert tests.countTestCases() >= 36, "Grammatical checks are not registered"
    return tests


def test_causal_for_requires_independent_subject_constituent() -> None:
    """A causal coordinator cannot manufacture a subject from a comma list."""
    from seman_parser.grammar import load_grammar
    rule = load_grammar(DATA / "grammar.jsonl").by_id("coord_clause_causal_finite")
    subject = rule.rhs[1]
    assert subject.features.as_dict()["incidental_subject"] == "true"
    assert "incidental_subject" in subject.requires
    p = parser()
    for text in ("For I waited.", "For the weather was cold."):
        assert p.parse(text).result.completed, text
    for text in ("For my part, I waited.", "For the captain, he waited."):
        report = p.parse(text).result
        assert report.completed, (text, report.stats)
        def descendants(node):
            yield node
            for child in node.children:
                yield from descendants(child)
        assert all(
            "coord_clause_causal_finite" not in {
                sub.rule_id for sub in descendants(root)
            }
            for root in report.alternatives(limit=12)
        ), text


def test_lexical_title_priority_preserves_proper_name_hypothesis() -> None:
    """A strong lexical honorific beats capitalization-only name guessing."""
    p = parser()
    for sentence in ("Captain Nemo arrived.", "Doctor Watson waited.",
                     "Professor Moriarty spoke.", "Lady Catherine smiled."):
        report = p.parse(sentence)
        first = sentence.split()[0]
        reads = [c for c in report.lattice.candidates
                 if c.surface == first]
        categories = {c.category for c in reads}
        assert {"TITLE", "PROPER-NOUN", "N"} <= categories, sentence
        title = max(c.score for c in reads if c.category == "TITLE")
        guessed_name = max(c.score for c in reads
                           if c.category == "PROPER-NOUN"
                           and c.source == "proper-noun")
        assert title > guessed_name, (sentence,title,guessed_name)
        best = report.result.best()
        assert best is not None and "np_title_name" in rules(best), sentence


def test_delimited_discourse_adverbial_has_an_independent_matrix_clause() -> None:
    """'and, besides, X' is a construction; 'for, besides' is not."""
    from seman_parser.grammar import load_grammar
    grammar = load_grammar(DATA / "grammar.jsonl")
    rule = grammar.by_id("clause_discourse_coordinator_adv_incise")
    assert [part.category for part in rule.rhs] == [
        "COORD", "COMMA", "ADV", "COMMA", "CLAUSE",
    ]
    assert rule.rhs[0].features.as_dict()["nominal_coordination"] == "true"
    assert "nominal_coordination" in rule.rhs[0].requires
    assert rule.score == grammar.by_id("coord_clause").score

    p = parser()
    positive = p.parse("And, besides, John waited.").result
    assert positive.completed, positive.stats
    assert any(
        "clause_discourse_coordinator_adv_incise" in rules(root)
        for root in positive.alternatives(limit=12)
    )
    recovered = p.parse(
        "and, besides, it was such a pity that Lydia should be taken "
        "from a regiment where she was acquainted with everybody, and "
        "had so many favourites."
    ).result
    assert recovered.completed, recovered.stats
    assert recovered.best().rule_id == "clause_discourse_coordinator_adv_incise"
    assert recovered.best().children[-1].category == "CLAUSE"

    for text in (
        "For, besides, John waited.",
        "And besides John waited.",
        "And, besides John waited.",
    ):
        result = p.parse(text).result
        assert all(
            "clause_discourse_coordinator_adv_incise" not in rules(root)
            for root in result.alternatives(limit=12)
        ), text


def test_comma_adjective_lists_recurse_without_losing_head_agreement() -> None:
    p = parser()
    for text in (
        'The horrible, soft-spoken, eyeless creature gripped it.',
        'The horrible, soft-spoken, eyeless, scarred creature gripped it.',
    ):
        result = p.parse(text).result
        assert result.completed, text
        best = result.best()
        assert 'adjp_extend_comma_adjective_list' in rules(best), text
        subject = best.children[0]
        assert subject.category == 'NP'
        assert subject.features.as_dict()['number'] == 'singular'
    result = p.parse('These horrible, soft-spoken, eyeless creature gripped it.').result
    assert not result.completed


def test_licensed_adjective_infinitive_and_delimited_pp_preserve_structure() -> None:
    p = parser()
    for text, rule in (
        ('I should be happy to attain to eminence.', 'adjp_licensed_to_infinitive'),
        ('I should be happy, on his account, to attain to eminence.',
         'adjp_licensed_to_infinitive_parenthetical_pp'),
    ):
        report = p.parse(text)
        best = report.result.best()
        assert best is not None, text
        assert rule in rules(best), text
        assert 'vpnp_bare_prepositional_pp' in rules(best)
        assert report.result.text == text
        clause = next(n for n in nodes(best) if n.rule_id == rule)
        assert clause.children[-1].category == 'VP-NP'
        assert clause.children[0].features.as_dict()['to_infinitive'] == 'true'
    # Other legacy productions can overgenerate nominal readings of blue:
    # these negative checks specifically forbid the newly licensed construction.
    for text in ('The box should be blue to sleep.',
                 'I should be happy, on his account to attain eminence.',
                 'I should be happy to attained eminence.'):
        result = p.parse(text).result
        for root in result.alternatives(limit=20):
            for n in nodes(root):
                if n.rule_id in {'adjp_licensed_to_infinitive',
                                 'adjp_licensed_to_infinitive_parenthetical_pp'}:
                    assert 'blue' not in text[n.start:n.end]
                    assert 'attained' not in text[n.start:n.end]
                    assert ', on his account to' not in text[n.start:n.end]


def test_possessive_have_adverb_does_not_lose_its_infinitive() -> None:
    p = parser()
    text = 'I had barely time to get down again.'
    best = p.parse(text).result.best()
    assert best is not None
    rule = 'vp_possessive_have_adverb_np_infinitival_modifier'
    assert rule in rules(best)
    predicate = next(n for n in nodes(best) if n.rule_id == rule)
    assert [c.category for c in predicate.children] == ['HAVE','ADV','NP','TO','VP-NP']
    assert predicate.features.as_dict()['vform'] == 'finite'
    # A past-tense verb is not licensed as a bare infinitive by this rule.
    result = p.parse('I had barely time to went.').result
    assert all(rule not in rules(root) for root in result.alternatives(limit=20))


def test_comparative_incise_keeps_an_adjectival_matrix() -> None:
    p = parser()
    text = 'And, to confess the truth, we are scarcely less eager to meet her again.'
    best = p.parse(text).result.best()
    assert best is not None
    assert best.rule_id == 'clause_discourse_coordinator_infinitive_incise'
    assert best.children[-1].category == 'CLAUSE'
    assert 'adjp_modified_comparative' in rules(best)
    assert 'adjp_licensed_to_infinitive' in rules(best)
    eager = [n for n in nodes(best) if n.lexical_candidate is not None
             and text[n.start:n.end] == 'eager']
    assert eager and all(n.category == 'ADJ' for n in eager)
    for text in ('And, to confess the truth,',
                 'And to confess the truth we are eager.',
                 'For, to confess the truth, we are eager.'):
        result = p.parse(text).result
        assert all('clause_discourse_coordinator_infinitive_incise' not in rules(root)
                   for root in result.alternatives(limit=20)), text
