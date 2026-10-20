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


if __name__ == "__main__":
    unittest.main()
