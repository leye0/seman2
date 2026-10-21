"""Integration tests: parse real English strings with the seed data."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser
from seman_parser.chart import Chart
from seman_parser.engine import ParserResources
from seman_parser.grammar import load_grammar
from seman_parser.lexicon import load_lexicon
from seman_parser.segmentation import build_lattice

DATA = Path(__file__).resolve().parents[1] / "data"


def make_parser() -> Parser:
    return Parser.from_dir(DATA)


class SegmentationTests(unittest.TestCase):
    def test_serial_nominal_subject_and_negative_perfect_compose(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        simple = p.parse("My old dog arrived.").result
        self.assertTrue(simple.completed, simple.stats)
        # The established N->ADJ N + possessive NP tree is equally valid.
        # Test the new full ADJP construction in the serial-subject tree below.

        perfect = p.parse("She had not yet found the box.").result
        self.assertTrue(perfect.completed, perfect.stats)
        self.assertIn("vp_perfect_negated_adverbial_transitive",
                      set(rules(perfect.best())))

        sentence = (
            "Her house and her barn, her books and her letters, "
            "and all their old toys, had not yet lost their value."
        )
        result = p.parse(sentence).result
        self.assertTrue(result.completed, result.stats)
        root = result.best()
        self.assertEqual(root.rule_id,
                         "clause_serial_nominal_subject_comma_predicate")
        observed = set(rules(root))
        self.assertIn("np_serial_third_person_nominal_coordination", observed)
        self.assertIn("np_universal_third_person_nominal", observed)
        self.assertIn("vp_perfect_negated_adverbial_transitive", observed)

        # A simple uncoordinated subject does not license the punctuation
        # merely by satisfying common-noun features.
        plain = p.parse("The dog, barks.").result
        for root in plain.alternatives(limit=8):
            self.assertNotIn(
                "clause_serial_nominal_subject_comma_predicate",
                set(rules(root)),
            )

    def test_shared_subject_coordination_across_conjunct_adjunct(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        cases = (
            ("John waited, and in frustration, opened the box.",
             "vp_finite_comma_coord_fronted_pp"),
            ("Mary waited, and suddenly, opened the door.",
             "vp_finite_comma_coord_fronted_adv"),
        )
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertIn(expected, set(rules(parsed.best())))

    def test_interpolated_modal_reporting_requires_reporting_verb(self) -> None:
        p = make_parser()

        def rules(node):
            yield node.rule_id
            for child in node.children:
                yield from rules(child)

        for sentence in (
            "John, I may observe, opened the box.",
            "Mary, I might add, arrived.",
            "Peter, I may remark, waited patiently.",
        ):
            with self.subTest(sentence=sentence):
                result = p.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn(
                    "parenthetical_reporting_modal_bare",
                    set(rules(result.best())),
                )
        for sentence in (
            "John, I may eat, opened the box.",
            "Mary, I might swim, arrived.",
        ):
            with self.subTest(unlicensed=sentence):
                result = p.parse(sentence).result
                for root in result.alternatives(limit=8):
                    self.assertNotIn(
                        "parenthetical_reporting_modal_bare",
                        set(rules(root)),
                    )

    def test_literary_question_and_habitual_trees_are_licensed(self) -> None:
        parser = make_parser()

        def derivations(node):
            yield node.rule_id
            for child in node.children:
                yield from derivations(child)

        cases = (
            ("What brings you here, man?", "clause_wh_subject_question_vocative"),
            ("Dick, was it?", "clause_copular_left_dislocation_question"),
            ("And when you used to tell the stories?", "vp_past_habitual_used_to"),
            ("I've half a mind to dine first.", "vp_possessive_have_np_infinitival_modifier"),
        )
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertIsNotNone(root)
                self.assertIn(expected, set(derivations(root)))

    def test_british_directional_towards_keeps_preposition_and_wordnet(self) -> None:
        p = make_parser()
        lattice = p.parse("She moved towards the door.").lattice
        readings = [c for c in lattice.candidates
                    if c.surface.casefold() == "towards"]
        self.assertIn("PREP", {c.category for c in readings})
        self.assertTrue(any(c.lemma == "toward" for c in readings
                            if c.category == "PREP"))
        self.assertIn("PREP", {c.category for c in p.parse(
            "She moved toward the door.").lattice.candidates
            if c.surface.casefold() == "toward"})

    def test_quoted_exclamation_with_iterated_adverbial_has_true_structure(self) -> None:
        parser = make_parser()
        text = '"Darby M\'Graw!" again and again and again.'
        parsed = parser.parse(text).result
        self.assertTrue(parsed.completed, parsed.stats)
        best = parsed.best()
        self.assertEqual(best.rule_id,
                         "clause_direct_speech_iterative_reporting_ellipsis")
        self.assertEqual([node.category for node in best.children],
                         ["DIRECT-SPEECH", "ADVP"])
        self.assertEqual(best.children[1].rule_id,
                         "advp_iterative_recursive_coordination")

    def test_negative_copular_distance_keeps_numeral_and_reference_pp(self) -> None:
        parser = make_parser()
        parsed = parser.parse(
            "I was not a hundred yards from her when the wind came again in a clap."
        ).result
        self.assertTrue(parsed.completed, parsed.stats)
        best = parsed.best()
        self.assertEqual(best.rule_id, "clause_when_post")
        assert best is not None
        self.assertIn(
            "vp_copular_negated_measure_pp",
            {n.rule_id for n in self._descendants_for_test(best)}
        )

    @staticmethod
    def _descendants_for_test(item):
        yield item
        for child in item.children:
            yield from SegmentationTests._descendants_for_test(child)

    def test_predicative_inversion_free_relatives_keep_genuine_subjects(self) -> None:
        p = make_parser()
        examples = (
            ("Such is my journal of what relates to this strange occurrence "
             "up to the present day.",
             {"clause_predicative_adjp_copular_inversion",
              "np_nominal_free_relative_subject"}),
            ("and still different from either was what Mr. Bennet sent to Mr. Collins, "
             "in reply to his last.",
             {"clause_predicative_adjp_copular_inversion",
              "np_nominal_free_relative_object_pp",
              "np_free_relative_supplementary_pp"}),
        )
        for sentence, expected in examples:
            with self.subTest(sentence=sentence):
                parsed = p.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                root = parsed.best()
                self.assertIsNotNone(root)
                descendants = [root]
                for item in descendants:
                    descendants.extend(item.children)
                realized = {node.rule_id for node in descendants}
                self.assertTrue(expected <= realized, (expected, realized))

    def test_distributive_either_and_neither_keep_nominal_alternatives(self) -> None:
        p = make_parser()
        for word in ("either", "neither"):
            with self.subTest(word=word):
                lexical = {c.category for c in p.parse(word).lattice.candidates
                           if c.surface.casefold() == word}
                self.assertIn("DET", lexical)
                self.assertIn("PRONOUN", lexical)

    def test_comparative_elliptical_than_pp_keeps_both_comparison_scopes(self) -> None:
        p = make_parser()
        text = ("When we accosted him, his manner was something more confused, "
                "and something less genteel, than of yore.")
        result = p.parse(text).result
        self.assertTrue(result.completed, result.stats)
        root = result.best()
        self.assertEqual(root.rule_id, "clause_when_comma")
        visited = [root]
        for item in visited:
            visited.extend(item.children)
        rules = {item.rule_id for item in visited}
        self.assertIn("np_coordinated_comparative_predicatives", rules)
        self.assertIn("np_comparative_elliptical_than_pp", rules)
        assert sum(item.rule_id == "np_indefinite_pronoun_comparative_adj"
                   for item in visited) == 2

    def test_more_less_comparative_degree_preserves_wordnet_adverbs(self) -> None:
        p = make_parser()
        for word in ("more", "less"):
            with self.subTest(word=word):
                candidates = [
                    c for c in p.parse(word).lattice.candidates
                    if c.surface.casefold() == word
                ]
                self.assertTrue(any(c.category == "DEGREE" and
                                    c.features.as_dict().get("comparative") == "true"
                                    for c in candidates))
                self.assertIn("ADV", {c.category for c in candidates})

    def test_internal_apostrophe_surnames_are_full_span_names(self) -> None:
        parser = make_parser()
        for surface in ("O'Brien", "D'Artagnan", "M'Graw", "O’Connor"):
            with self.subTest(surface=surface):
                lattice = parser.parse(surface).lattice
                names = [c for c in lattice.candidates
                         if c.span_start == 0 and c.span_end == len(surface)
                         and c.category == "PROPER-NOUN"]
                self.assertTrue(names, surface)
                self.assertTrue(
                    any(c.source == "proper-noun-apostrophe" for c in names),
                    [c.as_dict() for c in names],
                )
        for contraction in ("I've", "John's", "We'd"):
            with self.subTest(contraction=contraction):
                lattice = parser.parse(contraction).lattice
                self.assertFalse(any(
                    c.category == "PROPER-NOUN"
                    and c.span_start == 0 and c.span_end == len(contraction)
                    and c.source == "proper-noun-apostrophe"
                    for c in lattice.candidates
                ))

    def test_send_true_double_object_is_not_donate_double_object(self) -> None:
        parser = make_parser()

        def rule_ids(node):
            yield node.rule_id
            for child in node.children:
                yield from rule_ids(child)

        for sentence in ("Peter sent Susan a message.",
                         "Mary sent John a letter.",
                         "They sent her the manuscript."):
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertIn("vp_ditransitive", set(rule_ids(result.best())))

        # Donate selects a prepositional recipient instead. In particular
        # an ambiguous unrelated noun-compound analysis is NOT evidence
        # for donation's ditransitive lexical frame.
        for sentence in ("They donated John a book.",
                         "She donated Mary a painting."):
            with self.subTest(sentence=sentence):
                result = parser.parse(sentence).result
                if result.best() is not None:
                    self.assertNotIn("vp_ditransitive",
                                     set(rule_ids(result.best())))
        grammatical = parser.parse("They donated a book to John.").result
        self.assertTrue(grammatical.completed, grammatical.stats)

    def test_habitual_used_and_fractional_half_keep_open_class_readings(self) -> None:
        parser = make_parser()
        for word, specialty, lexical in (
            ("used", "HABITUAL", "V"),
            ("half", "DET", "N"),
        ):
            with self.subTest(word=word):
                candidates = [
                    c for c in parser.parse(word).lattice.candidates
                    if c.surface.casefold() == word
                ]
                categories = {c.category for c in candidates}
                self.assertIn(specialty, categories)
                self.assertIn(lexical, categories)

    def test_lattice_has_candidates(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John opened the box.", lexicon)
        self.assertGreater(len(lattice.candidates), 4)
        surfaces = {c.surface for c in lattice.candidates}
        self.assertIn("John", surfaces)
        self.assertIn("opened", surfaces)
        self.assertIn("the", surfaces)
        self.assertIn("box", surfaces)

    def test_multiword_overlap_preserved(self) -> None:
        lexicon = load_lexicon(DATA / "lexicon.jsonl")
        lattice = build_lattice("John found a box.", lexicon)
        # At least the proper-noun and lexicon hypotheses must coexist.
        john = [c for c in lattice.candidates if c.surface == "John"]
        self.assertGreaterEqual(len(john), 1)

    def test_independent_wh_subject_question_needs_question_boundary(self) -> None:
        """A relative fragment must not be rescued by a lexical homograph."""
        parser = make_parser()
        fragment = "which I accordingly did"
        result = parser.parse(fragment).result
        self.assertFalse(result.completed, result.stats)
        self.assertIsNone(result.best())

        # Ordinary questions retain their nominal wh constructions, while
        # the proper noun/letter-N interpretation of I remains lexical.
        for question in ("Who arrived?", "Which guests arrived?"):
            with self.subTest(question=question):
                parsed = parser.parse(question).result
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertEqual(parsed.best().rule_id, "clause_wh_subj")
        lattice = parser.parse(fragment).lattice
        self.assertIn("N", {c.category for c in lattice.candidates
                            if c.surface == "I"})
        self.assertIn("PRONOUN", {c.category for c in lattice.candidates
                                  if c.surface == "I"})

    def test_local_irregular_inflection_does_not_hide_wordnet_verb(self) -> None:
        """A local auxiliary and an irregular lexical verb are both real."""
        parser = make_parser()
        for surface in ("did", "does"):
            with self.subTest(surface=surface):
                lattice = parser.parse(f"John {surface} the work.").lattice
                readings = [candidate for candidate in lattice.candidates
                            if candidate.surface.lower() == surface]
                self.assertTrue(any(c.category == "AUX" for c in readings))
                self.assertTrue(any(
                    c.category == "V" and c.lemma == "do"
                    and c.features.as_dict().get("vform") == "finite"
                    and any(i.sense_id and i.sense_id.startswith("wn-")
                            for i in c.interpretations)
                    for c in readings
                ), [c.as_dict() for c in readings])

        lexical = parser.parse("John did the work.").result
        self.assertTrue(lexical.completed, lexical.stats)
        best = lexical.best()
        self.assertIsNotNone(best)
        def rules(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in rules(child)
            }
        self.assertIn("vp_transitive", rules(best))

        auxiliary = parser.parse("John did not open the box.").result
        self.assertTrue(auxiliary.completed, auxiliary.stats)
        self.assertIn("clause_neg_vp", rules(auxiliary.best()))


class MorphologyAndNominalAgreementRegressionTests(unittest.TestCase):
    """Tests across lexical, morphology, composition and sentence levels."""

    def test_did_has_finite_but_not_past_participle_reading(self) -> None:
        p = make_parser()
        did = [c for c in p.parse("John did the work.").lattice.candidates
               if c.surface == "did" and c.category == "V"]
        self.assertIn("finite", {c.features.as_dict().get("vform") for c in did})
        self.assertNotIn("ed", {c.features.as_dict().get("vform") for c in did})
        done = [c for c in p.parse("The work was done.").lattice.candidates
                if c.surface == "done" and c.category == "V"]
        self.assertIn("ed", {c.features.as_dict().get("vform") for c in done})
        self.assertNotIn("finite", {c.features.as_dict().get("vform") for c in done})

    def test_unlicensed_past_participle_cannot_make_pronoun_nominal(self) -> None:
        p = make_parser()
        for text in ("They did opened the door.",
                     "She did not opened the door."):
            with self.subTest(text=text):
                result = p.parse(text).result
                self.assertFalse(result.completed, result.stats)
        self.assertTrue(p.parse("They did open the door.").result.completed)
        self.assertTrue(p.parse("She did not open the door.").result.completed)

    def test_common_noun_subject_is_third_person(self) -> None:
        p = make_parser()
        wrong = p.parse("The boy are happy.").result
        self.assertFalse(wrong.completed, wrong.stats)
        self.assertFalse(p.parse("The books is heavy.").result.completed)
        self.assertTrue(p.parse("The boy is happy.").result.completed)
        self.assertTrue(p.parse("You are happy.").result.completed)
        self.assertTrue(p.parse("They are happy.").result.completed)
        self.assertTrue(p.parse("John must be happy.").result.completed)

class ChartParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = make_parser()

    def test_transitive_clause(self) -> None:
        report = self.parser.parse("John opened the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.category, "CLAUSE")
        self.assertEqual(best.start, 0)

    def test_semantic_roles_on_transitive(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("AGENT", relations)
        # Object role name comes from the WordNet verb frame mapping
        # (THEME or AFFECTED depending on the frame).
        self.assertTrue(relations & {"AFFECTED", "THEME"}, relations)

    def test_ditransitive_clause(self) -> None:
        report = self.parser.parse("John gave Mary the box.")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        assert best is not None
        semantic = report.interpret(best)
        relations = {edge.relation for edge in semantic.graph.relations}
        self.assertIn("RECIPIENT", relations)
        self.assertIn("THEME", relations)

    def test_copula_adjective(self) -> None:
        report = self.parser.parse("Mary is happy.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_intransitive(self) -> None:
        report = self.parser.parse("John left.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_pied_piped_relative_pp_is_a_headed_np(self) -> None:
        """A preposition plus an oblique wh-word modifies a real NP head."""
        examples = (
            ("The shore on which Mary stood was quiet.",
             "np_relative_pp_restrictive"),
            ("The sea, on which the moon shone, was calm.",
             "np_relative_pp_comma_pair"),
            ("The question to which Mary replied was difficult.",
             "np_relative_pp_restrictive"),
            ("The students, of whose work Mary spoke, waited.",
             "np_relative_pp_comma_pair"),
        )
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence, rule in examples:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence).result
                self.assertTrue(parsed.completed, parsed.stats)
                best = parsed.best()
                self.assertIsNotNone(best)
                self.assertIn(rule, descendants(best))

    def test_pied_piping_cannot_be_invented_from_any_wh_or_prep(self) -> None:
        """Reject missing relative pronouns and unlicensed possessive gaps."""
        def descendants(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in descendants(child)
            }
        for sentence in (
            "The shore on Mary stood was quiet.",
            "The shore on what Mary stood was quiet.",
            "The students, of whose Mary spoke, waited.",
            "The shore on which Mary.",
        ):
            with self.subTest(sentence=sentence):
                best = self.parser.parse(sentence).result.best()
                if best is not None:
                    self.assertFalse(
                        any(rule is not None and rule.startswith("np_relative_pp")
                            for rule in descendants(best)),
                        sentence,
                    )
        control = self.parser.parse("Mary stood on the shore.").result.best()
        self.assertIsNotNone(control)
        self.assertFalse(
            any(rule is not None and rule.startswith("np_relative_pp")
                for rule in descendants(control))
        )

    def test_predicative_adjectives_license_finite_content_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        cases = (
            ("Mary is sure John will return.", "adjp_clausal_bare"),
            ("Mary is sure that John will return.", "adjp_clausal_that"),
            ("Mary is afraid John will leave.", "adjp_clausal_bare"),
            ("Mary is glad that John will return.", "adjp_clausal_that"),
            ("Are you quite sure that you can go?", "adjp_degree_clausal"),
        )
        for text, required in cases:
            with self.subTest(text=text):
                parsed = self.parser.parse(text).result
                self.assertTrue(parsed.completed, parsed.stats)
                trees = [tree for tree in parsed.alternatives(limit=64)]
                self.assertTrue(
                    any(required in rule_ids(tree) for tree in trees),
                    (text, parsed.stats, [tree.rule_id for tree in trees]),
                )

    def test_clausal_adjective_valency_excludes_generic_adjectives(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary is tall John will return.",
            "Mary is blue that John returned.",
            "Are you quite tall that John returned?",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=8):
                    self.assertNotIn("adjp_clausal_bare", rule_ids(tree))
                    self.assertNotIn("adjp_clausal_that", rule_ids(tree))
        # Existing ordinary adjectival predication remains available.
        basic = self.parser.parse("Mary is sure.").result
        self.assertTrue(basic.completed, basic.stats)

    def test_discourse_parentheticals_inside_finite_clauses(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        sentences = (
            ("Mary, however, opened the box.", "clause_subject_parenthetical_vp"),
            ("Mary, indeed, left.", "clause_subject_parenthetical_vp"),
            ("John tried, therefore, to open the box.",
             "vp_subject_control_parenthetical_inf"),
        )
        for text, expected in sentences:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    any(expected in rule_ids(tree)
                        for tree in result.alternatives(limit=24)),
                    (text, result.stats),
                )

    def test_discourse_parenthetical_cannot_swallow_plain_adverbs(self) -> None:
        def rule_ids(node):
            return {node.rule_id} | {
                name for child in node.children for name in rule_ids(child)
            }
        for text in (
            "Mary, quickly, opened the box.",
            "Mary however opened the box.",
            "Mary, however opened the box.",
            "John kicked, therefore, to open the box.",
        ):
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                for tree in result.alternatives(limit=16):
                    rule_set = rule_ids(tree)
                    self.assertNotIn("clause_subject_parenthetical_vp", rule_set)
                    self.assertNotIn("vp_subject_control_parenthetical_inf", rule_set)

    def test_subject_supplementary_adjective_between_commas(self) -> None:
        """An ADJP adjunct must not erase the subject's finite agreement."""
        def ids(node):
            return {node.rule_id} | {key for child in node.children for key in ids(child)}
        positives = (
            "The Turk, amazed and delighted, endeavoured to kindle the zeal of his deliverer by promises of reward and wealth.",
            "The scientist, exhausted and hungry, returned home.",
            "Mary, tired, opened the box.",
        )
        for sentence in positives:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                self.assertTrue(result.completed, result.stats)
                self.assertTrue(
                    any("clause_subject_parenthetical_adjp_referential" in ids(tree)
                        for tree in result.alternatives(limit=24)),
                    (sentence, result.stats),
                )

    def test_subject_supplementary_adjective_requires_adjp_and_two_commas(self) -> None:
        def ids(node):
            return {node.rule_id} | {key for child in node.children for key in ids(child)}
        for sentence in (
            "The scientist, and hungry, returned home.",
            "The scientist, opened the box, returned home.",
            "The scientist, hungry returned home.",
            "The scientist hungry, returned home.",
            "The scientist, Mary, returned home.",
        ):
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence).result
                for tree in result.alternatives(limit=16):
                    self.assertFalse("clause_subject_parenthetical_adjp_referential" in ids(tree))

    def test_parenthetical_adjective_cannot_invent_bare_subjects(self) -> None:
        """Reject bare count nouns and spurious noun readings in incidentals."""
        def walk(item):
            yield item
            for child in item.children:
                yield from walk(child)

        negative_corpus = (
            "I could only sit down before my fire, biting the key of my carpet-bag, and think of the captivating, girlish, bright-eyed lovely Dora.",
            '"You were thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder."',
        )
        for text in negative_corpus:
            with self.subTest(text=text):
                parsed = self.parser.parse(text, max_items=50000,
                                           kbest_work_limit=500000).result
                for tree in parsed.alternatives(limit=2):
                    for node in walk(tree):
                        if node.rule_id == "clause_subject_parenthetical_adjp_referential":
                            self.assertNotIn(
                                text[node.children[0].start:node.children[0].end],
                                {"shore", "think of the captivating"},
                            )

    def test_recovered_turk_clause_anchors_its_correct_subject(self) -> None:
        sentence = '"The Turk, amazed and delighted, endeavoured to kindle the zeal of his deliverer by promises of reward and wealth."'
        best = self.parser.parse(sentence).result.best()
        self.assertIsNotNone(best)
        spoken = best.children[0]
        self.assertEqual(spoken.category, "DIRECT-SPEECH")
        clause = next(child for child in spoken.children if child.category == "CLAUSE")
        self.assertEqual(clause.rule_id, "clause_subject_parenthetical_adjp_referential")
        subject, _, adjunct, _, predicate = clause.children
        self.assertEqual(sentence[subject.start:subject.end], "The Turk")
        self.assertEqual(sentence[adjunct.start:adjunct.end], "amazed and delighted")
        self.assertTrue(sentence[predicate.start:predicate.end].startswith("endeavoured to"))

    def test_second_person_agreement_retains_both_be_number_readings(self) -> None:
        """Are/were must license 2sg you, without making 3sg he agree."""
        from seman_parser.segmentation import build_lattice
        lexicon = self.parser.resources.lexicon
        for surface in ("are", "were"):
            with self.subTest(surface=surface):
                lattice = build_lattice(surface, lexicon)
                readings = [
                    c.features.as_dict()
                    for c in lattice.candidates
                    if c.category == "AUX-BE"
                ]
                self.assertTrue(any(
                    f.get("number") == "singular" and f.get("person") == "2"
                    for f in readings
                ), readings)
                self.assertTrue(any(
                    f.get("number") == "plural" for f in readings
                ), readings)
        self.assertTrue(self.parser.parse("You are happy.").result.completed)
        self.assertTrue(self.parser.parse("You were captured.").result.completed)

    def test_shared_auxiliary_rejects_third_person_singular_were(self) -> None:
        def rules(node):
            return {node.rule_id} | {
                rule for child in node.children for rule in rules(child)
            }
        parsed = self.parser.parse("He were captured, and released.").result
        for tree in parsed.alternatives(limit=20):
            self.assertNotIn("vp_passive_shared_aux_sequence", rules(tree))

    def test_shared_finite_auxiliary_in_passive_participle_series(self) -> None:
        """The coordinated verbs share one finite passive auxiliary."""
        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)
        cases = (
            "The doors were opened, and closed.",
            "The prisoners were questioned, and released.",
            "The parcel was wrapped, and delivered.",
            "You were thrown, by some surprising accident, on this shore, renowned for its hospitality, seized immediately, and charged with murder.",
        )
        for sentence in cases:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence, max_items=50000,
                                           kbest_work_limit=500000).result
                self.assertTrue(parsed.completed, parsed.stats)
                alternatives = parsed.alternatives(limit=12)
                self.assertTrue(any(
                    any(n.rule_id == "vp_passive_shared_aux_sequence" for n in walk(tree))
                    for tree in alternatives
                ), (sentence, parsed.stats))

    def test_complex_shared_aux_passive_is_best_and_preserves_np_attachment(self) -> None:
        """Check the internal *tree*, not merely a completed root."""
        sentence = (
            "You were thrown, by some surprising accident, on this shore, "
            "renowned for its hospitality, seized immediately, "
            "and charged with murder."
        )
        parsed = self.parser.parse(
            sentence, max_items=50000, kbest_work_limit=500000,
        ).result
        best = parsed.best()
        self.assertIsNotNone(best)
        self.assertEqual(best.rule_id, "clause_passive", parsed.stats)

        def nodes(item):
            yield item
            for child in item.children:
                yield from nodes(child)
        rules = {item.rule_id for item in nodes(best)}
        self.assertIn("vp_passive_shared_aux_sequence", rules)
        self.assertIn("np_postposed_supplementary_adjp", rules)
        adjunct = next(
            n for n in nodes(best)
            if n.rule_id == "np_postposed_supplementary_adjp"
        )
        self.assertEqual(
            sentence[adjunct.children[2].start:adjunct.children[2].end],
            "renowned for its hospitality",
        )
        self.assertNotIn("pp_np_coord", rules)
        self.assertNotIn("clause_subject_parenthetical_adjp_referential", rules)
        self.assertEqual(sentence[best.children[0].start:best.children[0].end],
                         "You")

    def test_np_coordination_disallows_causal_for(self) -> None:
        """Conjunction 'for' joins clauses, not bare nominal objects."""
        parser = self.parser
        parsed = parser.parse("John and Mary opened the box.").result
        self.assertTrue(parsed.completed)
        # The nominal 'and' reading remains legal, without making
        # 'for' a coordinator inside PP objects.
        from seman_parser.engine import Parser
        pp_parser = Parser(parser.resources, goal_category="PP",
                           cache_size=0)
        pp = pp_parser.parse("on this shore, renowned for its hospitality").result
        self.assertTrue(pp.completed, pp.stats)

        def all_nodes(item):
            yield item
            for child in item.children:
                yield from all_nodes(child)

        best = pp.best()
        self.assertEqual(best.rule_id, "pp_prep_np")
        self.assertIn(
            "np_postposed_supplementary_adjp",
            {n.rule_id for n in all_nodes(best)},
        )
        self.assertNotIn(
            "pp_np_coord",
            {n.rule_id for n in all_nodes(best)},
        )

    def test_passive_participle_coordination_requires_real_passives(self) -> None:
        """Do not accept active infinitives or present verbs as passive participles."""
        def rules(node):
            return {node.rule_id} | {r for child in node.children for r in rules(child)}
        negatives = (
            "The doors were open, and close.",
            "The children were happy, and laughed.",
            "The doors opened, and closed.",
            "The doors were opening, and closing.",
        )
        for sentence in negatives:
            with self.subTest(sentence=sentence):
                parsed = self.parser.parse(sentence).result
                for tree in parsed.alternatives(limit=16):
                    self.assertNotIn("vp_passive_shared_aux_sequence", rules(tree))

    def test_unattested_hyphen_compounds_do_not_invent_verb_lemmas(self) -> None:
        """Preserve POS ambiguity when attested, not via a different word's suffix."""
        from seman_parser.segmentation import build_lattice

        for text, expected in (
            ("bright-eyed", "ADJ"),
            ("carpet-bag", "N"),
        ):
            with self.subTest(compound=text):
                lattice = build_lattice(text, self.parser.resources.lexicon)
                candidates = lattice.covering(0, len(text))
                self.assertTrue(
                    any(c.category == expected for c in candidates),
                    [c.as_dict() for c in candidates],
                )
                unlicensed_verbs = [
                    c for c in candidates
                    if c.category == "V" and c.source == "hyphen-compound"
                ]
                self.assertEqual(unlicensed_verbs, [])

        # Prefixal compounds retain lexically justified verb categories,
        # constrained by the morphology of the attested verbal head.
        prefixed = build_lattice("over-rated", self.parser.resources.lexicon)
        verb_forms = {
            c.features.as_dict().get("vform")
            for c in prefixed.covering(0, len("over-rated"))
            if c.category == "V"
        }
        self.assertIn("ed", verb_forms)
        self.assertTrue(verb_forms.isdisjoint({"base", "ing"}), verb_forms)

        compounds = build_lattice(
            "my carpet-bag and bright-eyed Dora",
            self.parser.resources.lexicon,
        )
        carpet = compounds.covering(3, 13)
        self.assertFalse(any(
            c.category == "N" and c.features.as_dict().get("number") == "plural"
            and c.source == "hyphen-compound" for c in carpet
        ))
        # The legitimate WordNet N and V interpretations of *think*
        # continue to coexist; the restriction applies only to UNATTESTED
        # hyphenated compounds, not individual words.
        think = build_lattice("think", self.parser.resources.lexicon)
        categories = {c.category for c in think.candidates}
        self.assertIn("N", categories)
        self.assertIn("V", categories)

    def test_alternatives_are_preserved(self) -> None:
        report = self.parser.parse("John opened the box.")
        # Even with one preferred reading, the API exposes alternatives.
        alts = report.result.alternatives()
        self.assertGreaterEqual(len(alts), 1)
        self.assertIs(report.result.best(), max(alts, key=lambda i: i.score))

    def test_failed_parse_is_honest(self) -> None:
        # Function words alone cannot form a clause.
        report = self.parser.parse("the the the the.")
        self.assertFalse(report.result.completed)

    def test_provenance_present(self) -> None:
        report = self.parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        payload = best.provenance.as_dict()
        self.assertEqual(payload["source"], "rule")
        self.assertIn("rule_id", payload["detail"])


class ParserCacheTests(unittest.TestCase):
    def test_repeated_parse_reuses_complete_result(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        first = parser.parse("John opened the box.")
        after_first = parser.cache_stats()
        second = parser.parse("John opened the box.")
        after_second = parser.cache_stats()

        self.assertIs(second.result, first.result)
        self.assertEqual(after_first["parse"]["misses"], 1)
        self.assertEqual(after_first["parse"]["size"], 1)
        self.assertEqual(after_second["parse"]["hits"], 1)

    def test_hierarchical_result_is_cached_too(self) -> None:
        parser = Parser.from_dir(DATA, cache_size=4)
        text = (
            "Mom worked during the day, Dad worked from home, "
            "and Eli learned to read."
        )
        first = parser.parse(text)
        self.assertEqual(first.result.stats.get("engine"), "vector-hierarchical-lazy-kbest")
        second = parser.parse(text)

        self.assertIs(second.result, first.result)
        self.assertEqual(parser.cache_stats()["parse"]["hits"], 1)


class ConstitutionTests(unittest.TestCase):
    """The engine must not encode domain nouns as dispatch."""

    def test_no_domain_identifiers_in_package(self) -> None:
        import ast

        root = Path(__file__).resolve().parents[1] / "seman_parser"
        forbidden = {"requesthandler", "transferevent", "understand_request", "passivesentence"}
        violations: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.lower() in forbidden:
                        violations.append(f"{path.name}:{node.lineno}:{node.name}")
                if isinstance(node, ast.If):
                    # No dispatch on literal semantic type / verb names.
                    for child in ast.walk(node.test):
                        if isinstance(child, ast.Compare):
                            for comparator in child.comparators:
                                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                                    if comparator.value.upper() in {"REQUEST", "TRANSFER", "GIVE", "OPEN"}:
                                        violations.append(
                                            f"{path.name}:{node.lineno}:dispatch on {comparator.value!r}"
                                        )
        self.assertEqual(violations, [])



class ProductiveSupplementTests(unittest.TestCase):
    """Full public Parser.parse parses and counterexamples."""

    @staticmethod
    def rule_ids(root):
        if root is None:
            return set()
        return ({root.rule_id} if root.rule_id else set()) | {
            rule for child in root.children
            for rule in ProductiveSupplementTests.rule_ids(child)
        }

    def test_reporting_tag_with_real_participial_adjunct(self):
        result = make_parser().parse(
            "'It was a mistake,' I replied, quietly speaking to the witness."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("dialogue_speech_tag_post_participial_adv_pp",
                      self.rule_ids(result.best()))

    def test_comma_and_ing_required_for_reporting_participial_adjunct(self):
        p = make_parser()
        for sentence in (
            "'It was a mistake,' I replied quietly speaking to the witness.",
            "'It was a mistake,' I replied, quietly speak to the witness.",
        ):
            result = p.parse(sentence).result
            for item in result.alternatives(limit=6):
                self.assertNotIn(
                    "dialogue_speech_tag_post_participial_adv_pp",
                    self.rule_ids(item), sentence,
                )

    def test_right_edge_transitive_participial_clause(self):
        result = make_parser().parse(
            "Maya crossed the square, carrying a lantern."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("clause_final_transitive_participle", self.rule_ids(result.best()))

    def test_parenthetical_you_know_inside_postpredicate_vp(self):
        result = make_parser().parse(
            "Mary waited, you know, near the entrance."
        ).result
        self.assertIsNotNone(result.best(), result.stats)
        self.assertIn("parenthetical_interpersonal_you_know", self.rule_ids(result.best()))
        self.assertIn("vp_postpredicate_parenthetical", self.rule_ids(result.best()))

    def test_parenthetical_verb_must_be_licensed_and_comma_delimited(self):
        p = make_parser()
        for sentence in (
            "Mary waited, you jump, near the entrance.",
            "Mary waited, you know near the entrance.",
            "Mary waited you know, near the entrance.",
        ):
            result = p.parse(sentence).result
            for item in result.alternatives(limit=6):
                self.assertNotIn(
                    "parenthetical_interpersonal_you_know",
                    self.rule_ids(item), sentence,
                )



class PerfectPassiveMorphologyTests(unittest.TestCase):
    """Perfect-passive auxiliary chains must not reanalyze HAVE as a noun."""

    def test_productive_perfect_passive_with_and_without_negation(self):
        p = make_parser()
        for text in (
            "The door has been opened.",
            "The door has never been opened.",
            "The door had already been opened.",
        ):
            best = p.parse(text).result.best()
            self.assertIsNotNone(best, text)
            root = best
            self.assertEqual(root.rule_id, "clause_passive", text)
            self.assertEqual(root.children[0].category, "NP", text)
            self.assertEqual(text[root.children[0].start:root.children[0].end],
                             "The door", text)
            def tree_rules(node):
                return {node.rule_id} | {r for c in node.children for r in tree_rules(c)}
            self.assertTrue({"vp_perfect_passive", "vp_perfect_passive_adv",
                             "vp_perfect_passive_neg"} & tree_rules(root), text)

    def test_perfect_passive_participle_be_is_not_finite(self):
        p = make_parser()
        result = p.parse("The box has never been opened.")
        be_candidates = [c for c in result.lattice.candidates
                         if c.surface.casefold() == "been" and c.category == "AUX-BE"]
        self.assertIn("ed", {c.features.as_dict().get("vform") for c in be_candidates})
        self.assertIn("finite", {c.features.as_dict().get("vform") for c in be_candidates})



class GreetingVocativeTests(unittest.TestCase):
    """A greeting plus addressee is a dialogue act, not an arbitrary NP."""

    def test_productive_greeting_plus_modified_proper_vocative(self):
        p = make_parser()
        for sentence in ("Adieu, my dear Margaret.", "Hello, our dear Alice.",
                         "Farewell, dear Eleanor."):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            rules = set()
            def collect(node):
                if node.rule_id is not None:
                    rules.add(node.rule_id)
                for child in node.children:
                    collect(child)
            collect(best)
            self.assertIn("clause_farewell_vocative", rules, sentence)
            # A noun-appellation reading ("my dear Margaret") is also
            # lexically possible; do not force the adjective alternative.
            self.assertTrue({"np_poss_adj_proper", "np_poss_n_name", "np_adj_proper"} & rules,
                            sentence)

    def test_salutation_is_required_and_wordnet_noun_alternative_survives(self):
        p = make_parser()
        for sentence in ("River, my dear Margaret.", "Table, dear Eleanor."):
            report = p.parse(sentence)
            for root in report.result.alternatives(limit=8):
                def includes(node):
                    return node.rule_id == "clause_farewell_vocative" or any(
                        includes(child) for child in node.children)
                self.assertFalse(includes(root), sentence)
        lattice = p.parse("Farewell, dear Eleanor.").lattice
        candidates = [c for c in lattice.candidates if c.surface.lower() == "farewell"]
        self.assertIn("INTERJECTION", {c.category for c in candidates})
        self.assertIn("N", {c.category for c in candidates})


class PersonalPronounParadigmTests(unittest.TestCase):
    """Possessive determiner is not a free pronoun, even with WordNet present."""

    def test_we_us_and_our_keep_distinct_grammatical_functions(self):
        p = make_parser()
        samples = {
            "we": {"PRONOUN"},
            "us": {"PRONOUN"},
            "our": {"POSS"},
        }
        for word, expected in samples.items():
            report = p.parse(f"Mary said {word} could help.")
            found = {c.category for c in report.lattice.candidates
                     if c.surface.lower() == word}
            self.assertTrue(expected <= found, (word, found))
            if word == "our":
                self.assertNotIn("PRONOUN", found)

    def test_our_is_available_inside_ordinary_possessive_np(self):
        result = make_parser().parse("Our friends arrived.").result
        best = result.best()
        self.assertIsNotNone(best, result.stats)
        self.assertEqual(best.children[0].category, "NP")
        subject_text = "Our friends arrived."[best.children[0].start:best.children[0].end]
        self.assertEqual(subject_text, "Our friends")


class InterposedAdverbPassiveAndBareControlTests(unittest.TestCase):
    """Productive auxiliary scope and explicit verbal valency."""

    @staticmethod
    def rule_ids(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            rule for child in item.children
            for rule in InterposedAdverbPassiveAndBareControlTests.rule_ids(child)
        }

    def test_interposed_adverb_is_licensed_by_finite_be_and_past_participle(self):
        p = make_parser()
        for text in (
            "The visitor was kindly received.",
            "The children were quickly rescued.",
            "The guest was likewise accommodated with a room.",
        ):
            report = p.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, (text, report.result.stats))
            self.assertIn("vp_passive_interposed_manner_adverb",
                          self.rule_ids(best), text)
            self.assertEqual(best.rule_id, "clause_passive", text)

    def test_non_participle_cannot_fill_passive_slot(self):
        p = make_parser()
        for text in ("The guest was kindly receive.", "The guest was kindly receiving."):
            for item in p.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vp_passive_interposed_manner_adverb",
                                 self.rule_ids(item), text)

    def test_base_subject_control_under_do_support(self):
        p = make_parser()
        for text in (
            "John did not try to leave.",
            "Mary did not attempt to conceal the truth from her friends.",
        ):
            report = p.parse(text)
            best = report.result.best()
            self.assertIsNotNone(best, (text, report.result.stats))
            self.assertIn("vpnp_base_subject_control_to_inf",
                          self.rule_ids(best), text)
            self.assertIn(best.rule_id, {"clause_neg", "clause_neg_vp"}, text)

    def test_base_control_requires_lexical_subject_control(self):
        p = make_parser()
        for text in (
            "John did not admire to leave.",
            "John did not smile to leave.",
        ):
            for item in p.parse(text).result.alternatives(limit=8):
                self.assertNotIn("vpnp_base_subject_control_to_inf",
                                 self.rule_ids(item), text)


class NamedEntityNominalConstructionTests(unittest.TestCase):
    """Lexically supported proper-name nominalization and attributive names."""

    @staticmethod
    def rules(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            r for child in item.children
            for r in NamedEntityNominalConstructionTests.rules(child)
        }

    def test_definite_proper_name_with_article(self):
        p = make_parser()
        for sentence in (
            "The Orfling arrived.",
            "The Titanic sank.",
            "The Turk smiled.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            forms = [self.rules(item) for item in report.result.alternatives(limit=8)]
            self.assertTrue(any("np_definite_named_entity" in form for form in forms),
                            (sentence, forms))

    def test_proper_names_can_modify_real_common_noun_heads(self):
        p = make_parser()
        for sentence in (
            "The Longbourn family arrived.",
            "The London train departed.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("np_determiner_name_noun_compound", self.rules(best), sentence)


    def test_abbreviated_honorific_forms_subject_not_dislocated_topic(self):
        p = make_parser()
        for sentence in (
            "Mr. Gardiner did not attempt to conceal these particulars from the Longbourn family.",
            "Mr. Gardiner smiled.",
            "Mrs. Bennet waited.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("np_honorific_abbreviation",
                          NamedEntityNominalConstructionTests.rules(best), sentence)
            self.assertNotEqual(best.rule_id, "clause_front_np", sentence)

    def test_abbreviated_honorific_requires_real_title(self):
        p = make_parser()
        result = p.parse("Tree. Alice smiled.")
        for item in result.result.alternatives(limit=8):
            self.assertNotIn("np_honorific_abbreviation",
                             NamedEntityNominalConstructionTests.rules(item))

    def test_indefinite_article_does_not_license_bare_name(self):
        p = make_parser()
        for sentence in ("A Orfling arrived.", "A Titanic sank."):
            report = p.parse(sentence)
            for item in report.result.alternatives(limit=8):
                self.assertNotIn("np_definite_named_entity", self.rules(item), sentence)



class LicensedObjectTopicalizationTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            rule for child in node.children
            for rule in LicensedObjectTopicalizationTests.rules(child)
        }

    def test_topicalized_object_of_transitive_predicate(self):
        p = make_parser()
        for sentence in (
            "The latter you must develop in her.",
            "The book you must put on the shelf.",
            "The work they can finish.",
        ):
            report = p.parse(sentence)
            best = report.result.best()
            self.assertIsNotNone(best, (sentence, report.result.stats))
            self.assertIn("clause_object_topicalization_modal",
                          self.rules(best), sentence)
            self.assertIn("licensed_transitive",
                          dict(best.children[-1].features.as_dict()), sentence)

    def test_modal_topicalization_preserves_gapped_object_and_subordinate_if(self):
        text = "The latter you must develop in her, if you can."
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertIn("clause_object_topicalization_modal",
                      self.rules(best))

    def test_transitive_verb_is_required_for_object_fronting(self):
        p = make_parser()
        for sentence in ("The rock you must arrive.", "The mountain you can perish."):
            report = p.parse(sentence)
            for root in report.result.alternatives(limit=8):
                self.assertNotIn("clause_object_topicalization_modal",
                                 self.rules(root), sentence)


class SubordinateComplementAgainstDefiniteProperModifierTests(unittest.TestCase):
    def test_complementizer_that_is_not_swallowed_by_name_nominal(self):
        text = "Mary believes that John left."
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        self.assertNotIn("np_determiner_name_noun_compound",
                         NamedEntityNominalConstructionTests.rules(best))
        self.assertIn("John", text[best.start:best.end])

    def test_true_definite_name_noun_still_composes(self):
        text = "The Longbourn family arrived."
        best = make_parser().parse(text).result.best()
        self.assertIsNotNone(best)
        self.assertIn("np_determiner_name_noun_compound",
                      NamedEntityNominalConstructionTests.rules(best))



class AdverbialWhModalAndBarePPTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            name for child in node.children
            for name in AdverbialWhModalAndBarePPTests.rules(child)
        }

    def test_adverbial_wh_question_and_prepositional_bare_predicate(self):
        p=make_parser()
        for sentence in (
            "Why should I sleep in the garden?",
            "Where can they dwell in the valley?",
            "But why should I dwell upon the incidents that followed this last overwhelming event?",
        ):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,(sentence,report.result.stats))
            self.assertIn("clause_wh_adverbial_modal",self.rules(best),sentence)
            self.assertTrue({"vpnp_bare_intransitive_pp", "vpnp_bare_prepositional_pp"} & self.rules(best), (sentence, self.rules(best)))


    def test_upon_is_real_preposition_with_preserved_lexical_hypotheses(self):
        p=make_parser()
        report=p.parse("John slept upon the ground.")
        cats={c.category for c in report.lattice.candidates if c.surface.casefold()=="upon"}
        self.assertIn("PREP",cats)
        best=report.result.best()
        self.assertIsNotNone(best,report.result.stats)
        rules=self.rules(best)
        self.assertIn("pp_prep_np",rules)

    def test_prepositional_base_predicate_requires_real_valency(self):
        p=make_parser()
        for sentence in ("Why should I depend upon the answer?", "Why should I dwell upon the issue?"):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,report.result.stats)
            self.assertTrue({"vpnp_bare_prepositional_pp", "vpnp_bare_intransitive_pp"} & self.rules(best), (sentence,self.rules(best)))

    def test_an_object_wh_is_not_mistaken_for_adverbial_wh(self):
        p=make_parser()
        for sentence in ("What should I sleep in the garden?", "Which can John sleep in the garden?"):
            report=p.parse(sentence)
            for tree in report.result.alternatives(limit=6):
                self.assertNotIn("clause_wh_adverbial_modal",self.rules(tree),sentence)

    def test_bare_intransitive_pp_does_not_consume_transitive_object(self):
        p=make_parser()
        for sentence in ("Why should I conceal the book?", "Where can we eat the soup?"):
            report=p.parse(sentence)
            for tree in report.result.alternatives(limit=6):
                # These verbs may have other lexical senses, but a real object
                # cannot be swallowed by the intransitive+PP construction.
                for node in tree.children:
                    if node.rule_id=="vpnp_bare_intransitive_pp":
                        self.assertNotIn("the book",sentence[node.start:node.end])


class ClauseSupplementaryCommaPPTests(unittest.TestCase):
    @staticmethod
    def rules(node):
        if node is None:
            return set()
        return ({node.rule_id} if node.rule_id else set()) | {
            r for ch in node.children
            for r in ClauseSupplementaryCommaPPTests.rules(ch)
        }

    def test_compositional_sentence_final_supplementary_pp(self):
        p=make_parser()
        for sentence in (
            "Mary waited, with a look of anxiety.",
            "The road was quiet, with trees along the path.",
            "It was a bitter cold winter, with long, hard frosts and heavy gales.",
        ):
            report=p.parse(sentence)
            best=report.result.best()
            self.assertIsNotNone(best,(sentence,report.result.stats))
            self.assertIn("clause_final_comma_pp_adjunct",self.rules(best),sentence)
            if "long, hard" in sentence:
                self.assertIn("adjp_comma_separated_adjectives",self.rules(best),sentence)

    def test_comma_and_prepositional_phrase_are_both_necessary(self):
        p=make_parser()
        for sentence in ("Mary waited with a look of anxiety.", "Mary waited, the house.", "Mary waited, by the doorway."):
            report=p.parse(sentence)
            for item in report.result.alternatives(limit=8):
                self.assertNotIn("clause_final_comma_pp_adjunct",self.rules(item),sentence)


class EmDashPunctuationProvenanceTests(unittest.TestCase):
    def test_double_hyphen_and_typographic_emdash_have_dash_hypotheses(self):
        parser = make_parser()
        for sentence, marker in (
            ("Anderson's ball--for it was Job--had broken the window.", "--"),
            ("Anderson's ball—for it was Job—had broken the window.", "—"),
        ):
            lattice = parser.parse(sentence).lattice
            spans = {(c.span_start, c.span_end, c.surface, c.category,
                      c.features.as_dict().get("dash_kind"))
                     for c in lattice.candidates if c.surface == marker}
            for position in (sentence.index(marker),
                             sentence.index(marker, sentence.index(marker) + len(marker))):
                self.assertIn((position, position + len(marker), marker,
                               "DASH", "em"), spans)
                self.assertIn((position, position + len(marker), marker,
                               "COMMA", None), spans)

    def test_apostrophe_in_anderson_possessive_is_not_dash(self):
        sentence = "Anderson's ball--for it was Job--had broken the window."
        report = make_parser().parse(sentence)
        dash_spans = [c for c in report.lattice.candidates if c.category == "DASH"]
        self.assertEqual(len(dash_spans), 2)
        self.assertNotIn("'s", [c.surface for c in dash_spans])


class EllipticalOffWithDispatchTests(unittest.TestCase):
    @staticmethod
    def rules(item):
        if item is None:
            return set()
        return ({item.rule_id} if item.rule_id else set()) | {
            rule for child in item.children
            for rule in EllipticalOffWithDispatchTests.rules(child)
        }

    def test_real_dialogue_dispatch_coordinates_with_transitive_imperative(self):
        text = '"Off with you to the cook and get some work."'
        report = make_parser().parse(text)
        best = report.result.best()
        self.assertIsNotNone(best, report.result.stats)
        rules = self.rules(best)
        self.assertIn("clause_elliptical_off_with_np_pp", rules)
        self.assertIn("clause_imperative", rules)
        self.assertIn("vp_bare_trans", rules)
        self.assertIn("clause_coordinate_dispatch_imperative", rules)

        def collect(node):
            result = [(node.rule_id, text[node.start:node.end])]
            for child in node.children:
                result.extend(collect(child))
            return result

        spans = collect(best)
        self.assertIn(("clause_imperative", "get some work"), spans)
        self.assertIn(("vp_bare_trans", "get some work"), spans)
        self.assertIn(("clause_elliptical_off_with_np_pp", "Off with you to the cook"), spans)

    def test_elliptical_dispatch_is_productive_without_the_coordination(self):
        p = make_parser()
        for text in ("Off with you to the cook!", "Off with them to the harbour!",
                     "Off with you!"):
            best = p.parse(text).result.best()
            self.assertIsNotNone(best, text)
            rules = self.rules(best)
            self.assertTrue({"clause_elliptical_off_with_np",
                             "clause_elliptical_off_with_np_pp"} & rules, text)

    def test_off_and_with_are_not_arbitrary_imperative_markers(self):
        p = make_parser()
        for text in ("Across with you to the cook!", "Off beyond you to the cook!"):
            result = p.parse(text)
            for best in result.result.alternatives(limit=8):
                self.assertNotIn("clause_elliptical_off_with_np_pp", self.rules(best), text)
                self.assertNotIn("clause_elliptical_off_with_np", self.rules(best), text)


class LiteraryExceptionDictionaryTests(unittest.TestCase):
    """Attested orthographic variants are first-class lexicon hypotheses."""

    def test_source_attested_hyphenated_words_have_independent_readings(self):
        p = make_parser()
        pairs = (
            ("blood-stained", "ADJ"),
            ("bright-eyed", "ADJ"),
            ("shoulder-blade", "N"),
            ("pick-axe", "N"),
            ("spy-glass", "N"),
            ("charnel-houses", "N"),
            ("well-known", "ADJ"),
            ("stage-cutch", "N"),
            ("carpet-bag", "N"),
        )
        for surface, category in pairs:
            with self.subTest(surface=surface):
                report = p.parse(surface)
                full = report.lattice.covering(0, len(surface))
                matched = [c for c in full
                           if c.category == category
                           and any(i.provenance.get("source") ==
                                   "attested-literary-supplement"
                                   for i in c.interpretations)]
                self.assertTrue(matched, [x.as_dict() for x in full])
                self.assertEqual(matched[0].source, "lexicon-multiword")

    def test_dialectal_words_preserve_attested_spelling_and_normalized_lemma(self):
        lexicon = make_parser().resources.lexicon
        expected = {
            "unfort'nate": ("unfortunate", "ADJ"),
            "howsomever": ("however", "ADV"),
            "sperrits": ("spirit", "N"),
            "sperrit": ("spirit", "N"),
            "babby": ("baby", "N"),
            "cap'n": ("captain", "N"),
            "porkypine": ("porcupine", "N"),
        }
        for surface, (lemma, category) in expected.items():
            with self.subTest(surface=surface):
                matches = lexicon.lookup_morphology(surface)
                self.assertTrue(any(
                    meaning == lemma and sense.category == category
                    and sense.provenance.get("source") ==
                    "attested-literary-supplement"
                    for _, sense, meaning in matches), (surface, matches))

    def test_plural_and_singular_forms_do_not_inherit_each_other(self):
        lexicon = make_parser().resources.lexicon
        for surface, number in (("cross-trees", "plural"),
                                ("school-fellows", "plural"),
                                ("spy-glass", "singular"),
                                ("shoulder-blade", "singular"),
                                ("sperrits", "plural")):
            with self.subTest(surface=surface):
                matches = [(sense.category, sense.features.as_dict().get("number"))
                           for _, sense, _ in lexicon.lookup_morphology(surface)
                           if sense.provenance.get("source") ==
                              "attested-literary-supplement"]
                self.assertIn(("N", number), matches)
                self.assertNotIn(("N", "singular" if number == "plural"
                                  else "plural"), matches)

    def test_distinct_double_dash_does_not_become_hyphenated_word(self):
        p = make_parser()
        text = "Anderson's ball--for it was Job--had broken his shoulder-blade."
        lattice = p.parse(text).lattice
        for c in lattice.candidates:
            if c.source == "lexicon-multiword" and c.surface.count("-") > 0:
                self.assertNotIn("--", c.surface)
        dashes = [c for c in lattice.candidates
                  if c.category == "DASH" and c.surface == "--"]
        self.assertEqual(len(dashes), 2)
        self.assertTrue(any(c.category == "N"
                            and c.surface == "shoulder-blade"
                            for c in lattice.candidates))

    def test_wordnet_and_compound_fallback_remain_available(self):
        p = make_parser()
        for word in ("think", "uninvented-frost", "blood-stained"):
            lattice = p.parse(word).lattice
            self.assertTrue(lattice.candidates, word)
        lattice = p.parse("blood-stained knife").lattice
        self.assertTrue(any(c.source == "lexicon-multiword"
                            and c.surface == "blood-stained"
                            and c.category == "ADJ"
                            for c in lattice.candidates))


class ProductiveHyphenMorphologyWithoutDictionaryTests(unittest.TestCase):
    """Standard hyphenated compounds require no per-word curated entry."""

    @classmethod
    def setUpClass(cls) -> None:
        # Explicitly omit literary_lexicon.jsonl to prove generalization.
        from seman_parser.engine import discover_wordnet
        cls.lexicon = load_lexicon(
            DATA / "function_words.jsonl",
            wordnet_dict=discover_wordnet(DATA),
            supplemental_paths=(DATA / "syntax_lexicon.jsonl",),
            max_senses=8,
        )

    def test_participial_adjectives_productive_without_literary_words(self):
        for word in ("sun-painted", "river-washed", "well-described",
                     "moon-carried"):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                derived = [c for c in full
                           if c.category == "ADJ" and
                           c.source == "hyphen-participial-adjective"]
                self.assertTrue(derived, [c.as_dict() for c in full])
                self.assertTrue(all(
                    any(i.provenance.get("head_lemma") for i in c.interpretations)
                    for c in derived))
                self.assertFalse(any(c.category == "V" and
                                     c.source == "hyphen-participial-adjective"
                                     for c in full))

    def test_headed_nominal_compounds_agree_without_literary_words(self):
        for word, number in (("orchard-bag", "singular"),
                             ("orchard-bags", "plural"),
                             ("hill-trees", "plural")):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                self.assertTrue(any(
                    c.category == "N" and
                    c.features.as_dict().get("number") == number and
                    c.source == "hyphen-compound"
                    for c in full), [c.as_dict() for c in full])

    def test_do_not_fabricate_verbs_or_adjectives_for_unlicensed_heads(self):
        for word in ("carpet-bag", "stone-walk", "silver-cook"):
            with self.subTest(word=word):
                lattice = build_lattice(word, self.lexicon)
                full = lattice.covering(0, len(word))
                self.assertFalse(any(
                    c.source == "hyphen-participial-adjective"
                    for c in full), [c.as_dict() for c in full])
                self.assertFalse(any(
                    c.category == "V" and c.source == "hyphen-compound"
                    for c in full), [c.as_dict() for c in full])

    def test_em_dash_is_never_inside_a_productive_compound(self):
        text = "The sky--for it was night--was sun-painted."
        lattice = build_lattice(text, self.lexicon)
        self.assertTrue(any(
            c.category == "ADJ" and c.surface == "sun-painted"
            for c in lattice.candidates))
        self.assertFalse(any(
            "--" in c.surface and "hyphen" in c.source
            for c in lattice.candidates))

if __name__ == "__main__":
    unittest.main()

