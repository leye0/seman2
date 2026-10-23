"""Known quality gaps exposed when a formerly capped forest becomes complete.

These are NOT extra corpus-specific grammar rules. They are adversarial tree
acceptance tests, all through Parser.parse, documenting what must be fixed
before the left-corner feasibility optimization becomes the default.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def descendants(node):
    yield node
    for child in node.children:
        yield from descendants(child)


class ExperimentalTreeQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            DATA, cache_size=0, lexical_left_corner_pruning=True,
        )

    @unittest.expectedFailure
    def test_verb_particle_not_reinterpreted_as_second_imperative(self):
        text = (
            "As soon as the sun had climbed above our girdle of trees, "
            "it fell with all its force upon the clearing and drank up "
            "the vapours at a draught."
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            item.rule_id == "clause_imperative"
            and text[item.start:item.end].startswith("up the vapours")
            for item in descendants(best)
        ), "In an indicative narrative, 'drank up' is one verb-particle unit")

    @unittest.expectedFailure
    def test_object_topicalization_does_not_absorb_subject_pronoun(self):
        text = (
            "“The turn of your countenance I shall never forget, as you said "
            "that I could not have addressed you in any possible way that "
            "would induce you to accept me.”"
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            item.category == "NP"
            and text[item.start:item.end].endswith(" I")
            and text[item.start:item.end].startswith("The turn")
            for item in descendants(best)
        ), "The subject 'I' must not be part of the fronted object NP")

    def test_for_my_part_is_prepositional_adjunct_not_coordination(self):
        text = (
            "For my part, as I was not much use at carrying, I was kept "
            "busy all day in the cave packing the minted money into bread-bags."
        )
        best = self.parser.parse(text, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertNotEqual(best.rule_id, "coord_clause",
                            "'For my part' is a PP, not a clausal coordinator")

    def test_copular_gerund_requires_positive_ing_evidence(self):
        from seman_parser.grammar import load_grammar
        grammar = load_grammar(DATA / "grammar.jsonl")
        matching = [rule for rule in grammar.rules
                    if rule.rule_id == "np_gerund_cop_adjp"]
        self.assertEqual(len(matching), 1)
        copula = matching[0].rhs[0]
        self.assertEqual(copula.category, "COPULA")
        self.assertEqual(copula.features.as_dict().get("vform"), "ing")
        self.assertIn("vform", copula.requires)

    def test_clause_coordination_rejects_causal_for_as_plain_coordinator(self):
        rules = [r for r in self.parser.resources.grammar
                 if r.rule_id == "clause_correlative"]
        self.assertEqual(len(rules), 1)
        coordinator = rules[0].rhs[1]
        self.assertEqual(
            coordinator.features.as_dict().get("nominal_coordination"), "true",
        )
        self.assertIn("nominal_coordination", coordinator.requires)
        gapping = [r for r in self.parser.resources.grammar
                   if r.rule_id == "clause_gapping_np"]
        self.assertEqual(len(gapping), 1)
        self.assertIn("nominal_coordination", gapping[0].rhs[1].requires)

    def test_causal_dash_incise_and_finite_predicate_cohere(self):
        text = (
            "Anderson's ball--for it was Job that shot him first--"
            "had broken his shoulder-blade and touched the lung, not badly."
        )
        report = self.parser.parse(text, max_items=50000)
        best = report.result.best()
        if best is None:
            probes = (
                ("Anderson's ball", "NP"),
                ("for it was Job that shot him first", "CLAUSE"),
                ("--for it was Job that shot him first--", "PARENTHETICAL"),
                ("had broken his shoulder-blade", "VP"),
                ("had broken his shoulder-blade and touched the lung", "VP"),
                ("Anderson's ball had broken his shoulder-blade and touched the lung", "CLAUSE"),
                ("Anderson's ball--for it was Job that shot him first--had broken his shoulder-blade and touched the lung", "CLAUSE"),
            )
            details = []
            for probe, goal in probes:
                p = Parser(self.parser.resources, goal_category=goal,
                           lexical_left_corner_pruning=True, cache_size=0)
                result = p.parse(probe, max_items=50000).result
                selected = result.best()
                details.append((
                    probe, goal, bool(selected),
                    result.stats.get("structural_root_nodes"),
                    result.stats.get("budget_exceeded"),
                    [(node.rule_id, node.category, probe[node.start:node.end])
                     for node in descendants(selected)][:22] if selected else [],
                ))
            self.fail(("No 486 full analysis", report.result.stats, details))
        self.assertTrue(
            any(node.rule_id == "parenthetical_dash_causal_clause"
                for node in descendants(best)),
            "The dashes must enclose an overt finite causal clause",
        )

    def test_obligation_with_intervening_adverb_coordinates_finite_clauses(self):
        text = "I have only to tell her so, and she is sure to come."
        report = self.parser.parse(text, max_items=50000)
        best = report.result.best()
        if best is None:
            probes = (
                ("have only to tell her so", "VP"),
                ("tell her so", "VP-NP"),
                ("I have only to tell her so", "CLAUSE"),
                ("she is sure to come", "CLAUSE"),
                ("and she is sure to come", "CLAUSE"),
                ("I have only to tell her so, and she is sure to come.", "CLAUSE"),
                ("I have only to tell her so, and she is sure to come.’", "CLAUSE"),
            )
            details = []
            for probe, goal in probes:
                p = Parser(self.parser.resources, goal_category=goal,
                           lexical_left_corner_pruning=True, cache_size=0)
                result = p.parse(probe, max_items=50000).result
                selected = result.best()
                details.append((
                    probe, goal, bool(selected),
                    result.stats.get("structural_root_nodes"),
                    result.stats.get("budget_exceeded"),
                    [(node.rule_id, node.category)
                     for node in descendants(selected)][:18] if selected else [],
                ))
            self.fail(("Obligation/coordination missing", report.result.stats, details))
        self.assertTrue(any(
            node.rule_id == "clause_np_vp" and text[node.start:node.end].startswith("I have")
            for node in descendants(best)),
            "The matrix obligation is a finite clause, not a nominal fragment",
        )

    def test_reduced_concessive_adjective_incise(self):
        text = "her features, though not plain, were insignificant."
        report = self.parser.parse(text, max_items=50000)
        best = report.result.best()
        if best is None:
            details = []
            for probe, goal in (
                ("her features", "NP"),
                ("though not plain", "ADJP"),
                ("were insignificant", "VP"),
                (text, "CLAUSE"),
            ):
                p = Parser(self.parser.resources, goal_category=goal,
                           lexical_left_corner_pruning=True, cache_size=0)
                result = p.parse(probe, max_items=50000).result
                selected = result.best()
                details.append((probe, goal, bool(selected),
                                result.stats.get("structural_root_nodes"),
                                [(node.rule_id, node.category)
                                 for node in descendants(selected)][:12]
                                if selected else []))
            self.fail(("Concessive incise missing", report.result.stats, details))
        self.assertTrue(any(
            node.rule_id == "adjp_concessive_negated_adjective"
            for node in descendants(best)
        ), "The concessive should retain its overt conjunction and negation")
        self.assertTrue(any(
            node.rule_id == "clause_subject_parenthetical_adjp_referential"
            for node in descendants(best)
        ), "The paired commas attach the concessive adjective to the subject")

    def test_free_relative_wh_object_forms_nominal_subject(self):
        sentence = "Whatever he said, was said well."
        best = self.parser.parse(sentence, max_items=50000).result.best()
        if best is None:
            details = []
            for probe, goal in (
                ("Whatever he said", "NP"),
                ("was said well", "VP"),
                (sentence, "CLAUSE"),
            ):
                p = Parser(self.parser.resources, goal_category=goal,
                           lexical_left_corner_pruning=True, cache_size=0)
                result = p.parse(probe, max_items=50000).result
                selected = result.best()
                details.append((probe, goal, bool(selected),
                                result.stats.get("structural_root_nodes"),
                                [(node.rule_id, node.category)
                                 for node in descendants(selected)][:14]
                                if selected else []))
            self.fail(("Free relative unavailable", details))
        self.assertTrue(any(
            n.rule_id == "np_free_relative_object_pause_subject"
            for n in descendants(best)
        ), "The WH word names the missing object inside the nominal relative")
        self.assertTrue(any(
            n.rule_id == "clause_free_relative_subject_pause"
            for n in descendants(best)
        ), "The comma marks a pause after an overt nominal free relative")
        self.assertTrue(any(
            n.rule_id == "vp_adv"
            for n in descendants(best)
        ), "The passive predicate takes its final manner adverb through VP attachment")

        self.assertTrue(any(
            n.rule_id == "vp_passive" for n in descendants(best)
        ), "The predicate must use an overt passive, not a copular adjective")
        np = Parser(self.parser.resources, goal_category="NP",
                    lexical_left_corner_pruning=True, cache_size=0)
        other = np.parse("Whoever arrived", max_items=50000).result.best()
        self.assertIsNotNone(other, "The WH family is not one corpus-specific phrase")

    def test_genitive_subject_agrees_with_possessed_head(self):
        for sentence, number in (
            ("Mary's eyes were ready.", "plural"),
            ("Mary's eye was ready.", "singular"),
        ):
            with self.subTest(sentence=sentence):
                best = self.parser.parse(sentence, max_items=50000).result.best()
                self.assertIsNotNone(best, "A genitive subject must compose with a finite VP")
                self.assertTrue(any(
                    node.rule_id in {"np_genitive", "np_poss_s"}
                    and node.features.as_dict().get("number") == number
                    for node in descendants(best)
                ), "The possessed head determines the subject number")

    def test_copular_predicate_not_detached_into_dislocated_np(self):
        text = (
            "but while Peggotty’s eyes were full of compassion for him, "
            "she said his generous impulse would do him good, "
            "and it was better not to check it."
        )
        report = self.parser.parse(text, max_items=50000)
        best = report.result.best()
        if best is None:
            probes = (
                ("Peggotty’s eyes", "NP"),
                ("Peggotty's eyes", "NP"),
                ("Peggotty’s eyes were ready", "CLAUSE"),
                ("Peggotty's eyes were ready", "CLAUSE"),
                ("Mary's eyes were ready", "CLAUSE"),
                ("Peggotty’s eyes were full of compassion for him", "CLAUSE"),
                ("were full of compassion for him", "VP"),
                ("while Peggotty’s eyes were full of compassion for him, she said his generous impulse would do him good", "CLAUSE"),
                ("she said his generous impulse would do him good", "CLAUSE"),
                ("and it was better not to check it", "CLAUSE"),
            )
            details = []
            for probe, goal in probes:
                subparser = Parser(
                    self.parser.resources, goal_category=goal,
                    lexical_left_corner_pruning=True, cache_size=0,
                )
                subresult = subparser.parse(probe, max_items=50000).result
                selected = subresult.best()
                details.append((probe, goal, bool(selected),
                                subresult.stats.get("structural_root_nodes"),
                                subresult.stats.get("budget_exceeded"),
                                [(node.rule_id, node.category)
                                 for node in descendants(selected)][:24]
                                if selected else []))
            control = Parser(
                self.parser.resources, goal_category="CLAUSE",
                lexical_left_corner_pruning=False, cache_size=0,
            ).parse("Peggotty’s eyes were full of compassion for him",
                    max_items=50000).result
            details.append(("without left-corner pruning", bool(control.best()),
                            control.stats.get("structural_root_nodes"),
                            control.stats.get("budget_exceeded")))
            self.fail(("No selected full tree", report.result.stats, details))
        self.assertFalse(any(
            item.rule_id == "clause_cop_ellipsis"
            and text[item.start:item.end].endswith("eyes were")
            for item in descendants(best)
        ), "The predicative ADJP 'full ...' belongs to the copular clause")
        self.assertTrue(any(
            item.rule_id == "vp_cop_adjp"
            and text[item.start:item.end].startswith("were full")
            for item in descendants(best)
        ), (
            "The explicit copula and its ADJP must form one selected predicate",
            [(node.rule_id, node.category, text[node.start:node.end])
             for node in descendants(best)
             if any(word in text[node.start:node.end]
                    for word in ("Peggotty", "were", "full", "compassion"))],
        ))


    def test_bare_modal_coordination_with_participial_incise_and_named_object(self):
        """A shared-subject modal combines two bare predicates around an -ing incise."""
        text = (
            "I could only sit down before my fire, biting the key of my "
            "carpet-bag, and think of the captivating, girlish, "
            "bright-eyed lovely Dora."
        )
        report = self.parser.parse(text, max_items=50000)
        best = report.result.best()
        self.assertIsNotNone(best, (
            "The entire sentence must have a feature-valid analysis",
            report.result.stats,
        ))
        rules = {node.rule_id for node in descendants(best)}
        for expected in (
            "adjp_extend_comma_adjective_list",
            "np_definite_adjlist_final_adjective_proper_name",
            "vpnp_bare_coord_participial_incise",
            "vp_modal_bare",
        ):
            with self.subTest(construction=expected):
                self.assertIn(expected, rules, (
                    "The best analysis should retain the overt syntactic "
                    "construction, rather than a spurious alternative",
                    report.result.stats, rules,
                ))

    @unittest.expectedFailure
    def test_tough_movement_requires_an_eligible_adjective(self):
        """A merely ADJ reading does not license every tough infinitive."""
        sentence = "The wall is green to believe."
        best = self.parser.parse(sentence, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            node.rule_id == "vp_tough" for node in descendants(best)
        ), "Green is not a lexically licensed tough-movement predicate")

    @unittest.expectedFailure
    def test_subject_control_infinitive_not_mislabeled_as_tough_movement(self):
        """'Ready to leave' is subject control, not object-gap tough syntax."""
        sentence = "Mary is ready to leave."
        best = self.parser.parse(sentence, max_items=50000).result.best()
        self.assertIsNotNone(best)
        self.assertFalse(any(
            node.rule_id == "vp_tough" for node in descendants(best)
        ), "The subject of 'leave' is Mary, not a gap object of 'leave'")


if __name__ == "__main__":
    unittest.main()
