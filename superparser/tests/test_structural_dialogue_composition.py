"""Evidence-gated dialogue composition through the one public Parser.parse.

A quoted speech sequence can be counted complete only if each source clause
has its own accepted finite subject-predicate tree AND the source-delimiter
assembly grammar produces a full-span root. A provisional source annotation
by itself never provides a successful grammatical analysis.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from seman_parser.dialogue_clause_plans import PARENTHETICAL_MODAL
from seman_parser.engine import Parser
from seman_parser.structural_preanalysis import analyze_paragraph

DATA = Path(__file__).resolve().parents[1] / "data"


class QuotedStructuralCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def _parse_case(self, source: str):
        rows, _ = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(len(rows), 1, source)
        return parse_corpus_case(
            self.parser, rows[0], max_items=50_000,
            kbest_work_limit=500_000,
        )

    def test_two_full_quoted_clauses_are_really_parsed_and_assembled(self):
        source = '"John walks. Mary walks."'
        prepared, lattice, result = self._parse_case(source)
        self.assertEqual(prepared.analysis_text, source)
        self.assertEqual(result.text, source)
        self.assertEqual(lattice.text, source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_two_finite_clauses")
        self.assertEqual(prepared.source_component("qc0_0"), "John walks.")
        self.assertEqual(prepared.source_component("qc0_1"), "Mary walks.")
        self.assertEqual(result.stats["structural_segment_count"], 2)
        self.assertEqual(result.stats["structural_segment_rule_ids"],
                         ["clause_np_vp", "clause_np_vp"])
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["John walks", "Mary walks"],
        )
        self.assertEqual(
            [source[a:b] for a, b in result.stats["source_punctuation_spans"]],
            [".", "."],
        )
        root = result.best()
        self.assertEqual(root.category, "CLAUSE")
        self.assertEqual(root.start, 0)
        self.assertEqual(root.end, len(source))
        self.assertEqual(len(root.children), 6)
        self.assertEqual(
            [child.category for child in root.children],
            ["OPEN-QUOTE", "CLAUSE", "SPEECH-STOP",
             "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        for child in (root.children[1], root.children[3]):
            self.assertEqual(child.rule_id, "segment_interface")
            self.assertEqual(child.children[0].rule_id, "clause_np_vp")

    def test_three_full_quoted_clauses_use_three_proven_interfaces(self):
        source = '"John walks. Mary walks. Jane walks."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_three_finite_clauses")
        self.assertEqual(result.stats["structural_segment_count"], 3)
        self.assertEqual(len(result.best().children), 8)
        self.assertEqual(prepared.source_component("qc0_2"), "Jane walks.")

    def test_composed_dialogue_preserves_reported_content_and_speech_links(self):
        source = '"John walks," said Mary, "Jane walks."'
        rows, _ = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(len(rows), 1)
        report = self.parser.parse(
            source,
            structural_constituents=rows[0]["structural_constituents"],
            max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertTrue(report.result.completed, report.result.stats)
        self.assertEqual(report.result.best().rule_id,
                         "dialogue_structural_intercalated_two_finite_clauses")
        relations = [r.as_dict()["relation"]
                     for r in report.interpret().graph.relations]
        self.assertIn("AGENT", relations)
        self.assertIn("REPORTED_CONTENT", relations)
        self.assertIn("CONTINUED_SPEECH", relations)

    def test_no_composition_when_one_part_is_not_a_finite_clause(self):
        source = '"John walks. Very quickly."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(prepared.structural_constituents)
        self.assertFalse(result.stats.get("structural_composition", False),
                         "A sentence fragment may not be promoted to a finite clause")
        self.assertEqual(result.text, source)

    def test_split_dialogue_composes_real_clauses_and_reporting_tag(self):
        source = '"John walks," said Mary, "Jane walks."'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_intercalated_two_finite_clauses")
        self.assertEqual(result.text, source)
        self.assertEqual(result.stats["structural_composition_kind"],
                         "intercalated_reporting_clause")
        self.assertEqual(result.stats["structural_clause_count"], 2)
        self.assertEqual(prepared.source_component("r0"), "said Mary")
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["John walks", "said Mary", "Jane walks"],
        )
        self.assertEqual(len(result.best().children), 10)
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE", "CLAUSE", "COMMA", "CLOSE-QUOTE",
             "SPEECH-TAG", "COMMA", "OPEN-QUOTE",
             "CLAUSE", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        self.assertEqual(
            [node.rule_id for node in result.best().children
             if node.category in ("CLAUSE", "SPEECH-TAG")],
            ["segment_interface"] * 3,
        )
        self.assertTrue(result.stats["structural_segment_rule_ids"][2]
                        .startswith("dialogue_speech_tag_"))

    def test_split_subject_and_predicate_cannot_fake_two_finite_clauses(self):
        source = '"John," said Mary, "walks."'
        _, _, result = self._parse_case(source)
        self.assertFalse(result.stats.get("structural_composition", False))
        self.assertEqual(result.text, source)

    def test_unattributed_adjacent_quotes_are_two_independent_utterances(self):
        source = '"John walks." "Mary walks."'
        units = analyze_paragraph(source)
        self.assertEqual([u.text for u in units],
                         ['"John walks."', '"Mary walks."'])
        self.assertTrue(all(u.eligible_for_parse for u in units))
        self.assertTrue(all(
            not any(p.function == "split_direct_speech_turn"
                    for p in u.constituents)
            for u in units
        ))

    def test_attested_minor_dialogue_answer_is_composed_without_a_verb(self):
        source = '‘Perfectly, sir.’'
        prepared, _, result = self._parse_case(source)
        self.assertTrue(result.completed, result.stats)
        self.assertTrue(result.stats.get("structural_composition"), result.stats)
        self.assertEqual(result.best().rule_id,
                         "dialogue_structural_minor_adv_vocative")
        self.assertEqual(result.best().features.as_dict()["minor_utterance"],
                         "true")
        self.assertEqual(result.stats["structural_clause_count"], 0)
        self.assertEqual(result.stats["structural_composition_kind"],
                         "adverbial_answer_with_vocative")
        self.assertEqual(
            [source[a:b] for a, b in result.stats["structural_segment_spans"]],
            ["Perfectly", "sir"],
        )
        self.assertEqual(
            [node.category for node in result.best().children],
            ["OPEN-QUOTE", "ADV", "COMMA", "NP", "SPEECH-STOP", "CLOSE-QUOTE"],
        )
        self.assertEqual(prepared.source_text, source)
        self.assertEqual(result.text, source)
        self.assertTrue(all(
            n.category not in ("V", "VP", "COPULA")
            for n in result.best().children
        ), "Verbless minor utterance must not fabricate a predicate")

    def test_minor_dialogue_must_be_classified_and_parse_both_components(self):
        for source in ('‘Perfectly, very.’', '‘Slowly, perhaps.’'):
            with self.subTest(source=source):
                prepared, _, result = self._parse_case(source)
                self.assertFalse(result.stats.get("structural_composition", False))
                self.assertEqual(prepared.source_text, source)

    def test_direct_parse_without_source_graph_retains_original_route(self):
        source = '"John walks. Mary walks."'
        raw = self.parser.parse(
            source, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertFalse(raw.result.stats.get("structural_composition", False))
        self.assertEqual(raw.result.text, source)

    def test_broken_quote_is_never_synthetically_closed_to_force_success(self):
        source = '"John walks. Mary walks.'
        unit, = analyze_paragraph(source)
        self.assertFalse(unit.eligible_for_parse)
        rows, counts = extract(
            Book(999, "Grammar", "Test", "train"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(rows, [])
        self.assertEqual(counts["requires_source_context"], 1)


class SourceParentheticalModalTests(unittest.TestCase):
    CONTROL = (
        "We could stay in the room (she knew with a smile) "
        "and watch the door when we met them at dawn."
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(
            Path(__file__).resolve().parents[1] / "data", cache_size=0,
        )

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000,
                                 kbest_work_limit=500_000)

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=100)
        self.assertEqual([row["source_text"] for row in rows], [text])
        return self.parse(rows[0])[2]

    def spans(self, nodes, text):
        return [(n.category, text[n.start:n.end]) for n in nodes]

    def test_case_493_preserves_shared_modal_and_nested_attachment(self):
        case = select_cases(500)[0][493]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "f02fcc4a918d02fc")
        prepared, lattice, result = self.parse(case)
        self.assertEqual(prepared.analysis_text, text)
        self.assertEqual(lattice.text, text)
        self.assertTrue(result.completed, result.stats)
        best = result.best()
        self.assertEqual(best.rule_id, PARENTHETICAL_MODAL)
        self.assertEqual((best.start, best.end), (0, len(text)))
        self.assertEqual(self.spans(best.children, text), [
            ("NP", "I"), ("MODAL", "should"), ("VP-NP", "lie down in my own place"),
            ("PARENTHETICAL", "(I thought with a silent chuckle)"), ("COORD", "and"),
            ("VP-NP", "enjoy their faces when they found me in the morning"),
            ("SPEECH-STOP", "."),
        ])
        _, _, first, aside, _, second, _ = best.children
        self.assertEqual(first.children[0].rule_id, "vpnp_bare_prepositional_pp")
        self.assertEqual(self.spans(aside.children, text), [
            ("OPEN-PAREN", "("), ("NP", "I"), ("V", "thought"),
            ("PP", "with a silent chuckle"), ("CLOSE-PAREN", ")"),
        ])
        self.assertEqual(prepared.source_component(f"p{aside.start}"),
                         "(I thought with a silent chuckle)")
        action, temporal = second.children
        self.assertEqual(action.children[0].rule_id, "vp_bare_trans")
        self.assertEqual(self.spans(temporal.children, text), [
            ("CONJ", "when"), ("CLAUSE", "they found me"), ("PP", "in the morning"),
        ])
        self.assertEqual(temporal.children[1].children[0].children[1].rule_id,
                         "vp_transitive")
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))

    def test_independent_parenthetical_with_optional_temporal_pp(self):
        for text in (self.CONTROL, self.CONTROL.replace(" at dawn", "")):
            with self.subTest(text=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, PARENTHETICAL_MODAL)
                self.assertEqual(result.best().children[3].category, "PARENTHETICAL")
                self.assertEqual(result.best().children[5].rule_id,
                                 "structural_source_bare_predicate_with_when")

    def test_does_not_admit_nonclausal_incise_or_finite_second_predicate(self):
        for old, new in (("she knew", "she laughed"), ("and watch", "and watches"),
                         ("(she knew with a smile)", "with a smile")):
            with self.subTest(new=new):
                result = self.control(self.CONTROL.replace(old, new))
                self.assertNotEqual(result.stats.get("structural_composition_kind"),
                                    PARENTHETICAL_MODAL)

    def test_preanalysis_records_parentheses_not_quoted_or_unmatched_marks(self):
        source = 'He stayed (she knew) and waited. He said "I stayed (she knew)."'
        first, quoted = analyze_paragraph(source)
        candidates = [c for c in first.constituents if c.function == "parenthetical_candidate"]
        self.assertEqual([(first.text[c.start:c.end], c.governor) for c in candidates],
                         [("(she knew)", "s0")])
        self.assertFalse(any(c.function == "parenthetical_candidate" for c in quoted.constituents))
        for sentence in analyze_paragraph("He stayed (she knew and waited."):
            self.assertFalse(any(c.function == "parenthetical_candidate"
                                 for c in sentence.constituents))

class SubjectResumptionTests(unittest.TestCase):
    CASES = {
        101: ("My face, neck, and hands", "structural_causal_subject_supplement",
              "from unaccustomed exposure to the air and sun", "were burnt to a berry-brown"),
        220: ("his manners", "structural_reduced_concessive_subject_supplement",
              "though well-bred", "were not inviting"),
        239: ("Elizabeth", "structural_controlled_transitive_participle",
              "immediately recognizing the livery",
              "guessed what it meant, and imparted no small degree of her surprise to her relations "
              "by acquainting them with the honour which she expected"),
        291: ("A meeting", "structural_finite_object_gap_manner",
              "which he anticipated with such joy", "so strangely turned to bitterness"),
        463: ("He himself", "structural_epistemic_subject_supplement",
              "I thought", "looked somewhat paler and more stern than I was used to"),
        485: ("someone", "structural_temporal_controlled_participle",
              "at the same time snatching another",
              "gave me a cut across the knuckles which I hardly felt"),
        486: ("These biscuits", "structural_inverted_should_subject_supplement",
              "should anything befall me",
              "would keep me, at least, from starving till far on in the next day"),
    }
    CONTROLS = (
        "Her arms, legs, and shoulders, from prolonged exposure to the heat and wind, "
        "were burnt to a deep red.",
        "She was at the same time kind, patient, and generous, and her friends, "
        "though shy, were not distant.",
        "Martha immediately recognizing the visitor, guessed what it meant, and imparted "
        "some degree of her anxiety to her sister by acquainting her with the news which she expected.",
        "A journey, which she awaited with great joy, unexpectedly turned to disaster.",
        "She herself, I supposed, looked somewhat taller and more serious than I was used to.",
        "I took a book from the shelf, and someone, at the same time taking another, "
        "gave me a mark across the page which I hardly noticed.",
        "These blankets, should anything befall him, would keep him, at least, "
        "from freezing till far on in the next day.",
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000,
                                 kbest_work_limit=500_000)

    @staticmethod
    def walk(node):
        yield node
        for child in node.children:
            yield from SubjectResumptionTests.walk(child)

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=120)
        self.assertEqual([row["source_text"] for row in rows], [text])
        return self.parse(rows[0])[2]

    def test_all_seven_source_cases_have_the_correct_resumed_subject(self):
        cases, _ = select_cases(500)
        for i, (subject, rule, aside, predicate) in self.CASES.items():
            with self.subTest(index=i):
                prepared, lattice, result = self.parse(cases[i])
                text = cases[i]["source_text"]
                self.assertEqual(prepared.analysis_text, text)
                self.assertEqual(lattice.text, text)
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                root = result.best()
                self.assertEqual((root.start, root.end), (0, len(text)))
                self.assertEqual(root.features.as_dict()["resumed_subject"], "true")
                resumed, = [n for n in root.children if n.category == "RESUMED-CLAUSE"]
                surface = lambda n: text[n.start:n.end]
                subject_tree, vp = resumed.children[0], resumed.children[-1]
                if i == 291:
                    # This relative modifies the subject, not the event.
                    self.assertEqual(surface(subject_tree.children[0]), subject)
                    supplement, = [n for n in subject_tree.children if n.rule_id == rule]
                else:
                    self.assertEqual(surface(subject_tree), subject)
                    supplement, = [n for n in resumed.children if n.rule_id == rule]
                self.assertEqual(surface(supplement), aside)
                self.assertEqual(surface(vp), predicate)
                for key in ("number", "person"):
                    self.assertEqual(subject_tree.features.as_dict()[key],
                                     vp.features.as_dict()[key])
                by_rule = {n.rule_id: n for n in self.walk(root) if n.rule_id}
                if i == 101:
                    env = by_rule["structural_binary_environment_coordination"]
                    self.assertEqual(surface(env), "the air and sun")
                    self.assertEqual(vp.features.as_dict()["voice"], "passive")
                    self.assertEqual(subject_tree.children[-1].features.as_dict()["number"],
                                     "plural")
                elif i == 220:
                    self.assertEqual(surface(by_rule["structural_three_adjectival_predicatives"]),
                                     "haughty, reserved, and fastidious")
                    self.assertEqual(vp.features.as_dict()["negation"], "true")
                elif i == 239:
                    coord = by_rule["structural_shared_subject_finite_predicate_coordination"]
                    self.assertEqual(surface(coord.children[0]), "guessed what it meant")
                    self.assertEqual(coord.children[-1].children[-1].category, "MEANS-SUPPLEMENT")
                    self.assertEqual(surface(by_rule["structural_referent_with_object_relative"]),
                                     "the honour which she expected")
                elif i == 463:
                    standard = by_rule["structural_accustomed_stranded_standard"]
                    self.assertEqual(surface(standard), "than I was used to")
                    self.assertEqual(standard.children[-1].category, "PREP")
                    self.assertEqual(standard.features.as_dict()["comparative_gap"], "pp_object")
                elif i == 485:
                    theme = by_rule["structural_locative_object_with_relative"]
                    self.assertEqual([surface(n) for n in theme.children],
                                     ["a cut", "across the knuckles", "which I hardly felt"])
                    self.assertEqual(supplement.children[-1].category, "INDEF-PRONOUN")
                    rel = theme.children[-1]
                    self.assertEqual(rel.children[-1].lexical_candidate.lemma, "feel")
                elif i == 486:
                    self.assertEqual([surface(n) for n in supplement.children],
                                     ["should", "anything", "befall", "me"])
                    self.assertEqual([surface(n) for n in vp.children[-2:]],
                                     ["from starving", "till far on in the next day"])

    def test_independent_controls_share_one_subject_resumption_grammar(self):
        rules = set()
        for text in self.CONTROLS:
            with self.subTest(text=text):
                r = self.control(text)
                self.assertTrue(r.completed, r.stats)
                tree = r.best()
                self.assertEqual(tree.features.as_dict().get("resumed_subject"), "true")
                resumed, = [n for n in tree.children if n.category == "RESUMED-CLAUSE"]
                rules.add(resumed.rule_id)
        self.assertEqual(rules, {
            "structural_subject_resumption", "structural_subject_resumption_relative",
            "structural_subject_resumption_participial",
        })

    def test_negative_controls_reject_agreement_and_attachment_false_positives(self):
        for control, old, new in (
            (0, "were burnt", "was burnt"),
            (1, "were not", "was not"),
            (2, "recognizing", "recognize"),
            (3, "which she", "which her"),
            (3, "turned to disaster", "turn to disaster"),
            (3, "joy, unexpectedly", "joy unexpectedly"),
            (4, "She herself", "He herself"),
            (5, "taking", "takes"),
            (6, "should anything", "might anything"),
            (6, "befall him", "befalls him"),
        ):
            with self.subTest(control=control, replacement=new):
                text = self.CONTROLS[control]
                self.assertIn(old, text)
                result = self.control(text.replace(old, new))
                best = result.best()
                self.assertTrue(best is None or
                                best.features.as_dict().get("resumed_subject") != "true")

class SharedSubjectCoordinationTests(unittest.TestCase):
    ROOT = "structural_shared_subject_source_sentence"
    CONTROLS = (
        "We notified them that she sent the note, and was getting on quite well.",
        "Miss Smith had worked hard, and though awake, was very weary, "
        "and not strong enough to carry the box.",
        "The children laughed for pleasure when they watched the parade from the bridge, "
        "and greeted with delight the returning sailors.",
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000,
                                 kbest_work_limit=500_000)

    def control(self, source):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), source,
                          length_min=1, length_max=120)
        self.assertEqual([r["source_text"] for r in rows], [source])
        return self.parse(rows[0])[2]

    @staticmethod
    def parts(node, text):
        return [(c.category, text[c.start:c.end]) for c in node.children]

    def case_tree(self, index, case, expected_sha):
        source = case["source_text"]
        self.assertEqual(sha256(source.encode()).hexdigest()[:16], expected_sha, index)
        prepared, lattice, result = self.parse(case)
        self.assertEqual(prepared.analysis_text, source)
        self.assertEqual(lattice.text, source)
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        tree = result.best()
        self.assertEqual(tree.rule_id, self.ROOT)
        self.assertEqual((tree.start, tree.end), (0, len(source)))
        self.assertEqual(tree.children[-1].category, "SPEECH-STOP")
        return source, tree.children[0]

    def assert_agreement(self, subject, pair, number):
        for n in (subject, pair, pair.children[0], pair.children[-1]):
            self.assertEqual(n.features.as_dict()["number"], number)
            self.assertEqual(n.features.as_dict()["person"], "3")

    def test_original_three_preserve_the_selected_subject_and_attachment(self):
        cases, _ = select_cases(500)
        text, report = self.case_tree(69, cases[69], "48fb528a88ac0b67")
        self.assertEqual(self.parts(report, text)[:-1], [
            ("NP", "I"), ("V", "informed"), ("NP", "her"), ("COMP-THAT", "that"),
        ])
        embedded = report.children[-1]
        subject, pair = embedded.children
        self.assertEqual(self.parts(embedded, text)[0], ("NP", "he"))
        self.assert_agreement(subject, pair, "singular")
        self.assertEqual(self.parts(pair, text), [
            ("VP", "sent his compliments"), ("COMMA", ","), ("COORD", "and"),
            ("VP", "was getting on very well indeed"),
        ])
        self.assertEqual(self.parts(pair.children[-1], text), [
            ("AUX-BE", "was"), ("V", "getting"), ("PARTICLE", "on"),
            ("ADVP", "very well indeed"),
        ])

        text, clause = self.case_tree(189, cases[189], "41e23438a4717cff")
        subject, pair = clause.children
        self.assertEqual(self.parts(clause, text)[0], ("NP", "Miss Bennet"))
        self.assert_agreement(subject, pair, "singular")
        self.assertEqual(self.parts(pair, text), [
            ("VP", "had slept ill"), ("COMMA", ","), ("COORD", "and"),
            ("CONCESSIVE", "though up"), ("COMMA", ","),
            ("VP", "was very feverish, and not well enough to leave her room"),
        ])
        self.assertEqual(self.parts(pair.children[-1], text), [
            ("COPULA", "was"), ("ADJP", "very feverish"), ("COMMA", ","),
            ("COORD", "and"), ("ADJP", "not well enough to leave her room"),
        ])
        self.assertEqual(self.parts(pair.children[-1].children[-1], text), [
            ("NEG", "not"), ("ADJ", "well"), ("DEGREE", "enough"),
            ("TO", "to"), ("V", "leave"), ("NP", "her room"),
        ])

        text, clause = self.case_tree(372, cases[372], "c99a901b6a78b64e")
        subject, pair = clause.children
        self.assertEqual(self.parts(clause, text)[0], ("NP", "The Greeks"))
        self.assert_agreement(subject, pair, "plural")
        first, _, _, second = pair.children
        self.assertEqual(self.parts(first, text), [
            ("V", "wept"), ("PP", "for joy"),
            ("TEMPORAL-CLAUSE", "when they beheld the Mediterranean from the hills of Asia"),
        ])
        self.assertEqual(self.parts(first.children[-1], text), [
            ("CONJ", "when"), ("NP", "they"), ("V", "beheld"),
            ("NP", "the Mediterranean"), ("PP", "from the hills of Asia"),
        ])
        self.assertEqual(self.parts(second, text), [
            ("V", "hailed"), ("PP", "with rapture"), ("NP", "the boundary of their toils"),
        ])

    def test_construction_lexemes_are_confined_to_their_attested_surfaces(self):
        for form in ("went", "got", "gone", "gets", "informing"):
            with self.subTest(form=form):
                self.assertFalse(any(
                    c.features.as_dict().get("progress_particle_on") == "true"
                    or c.features.as_dict().get("selects_report_addressee") == "true"
                    for c in self.parser._lattice_for_text(form).candidates
                ))
        self.assertTrue(any(c.category == "V" and
                            c.features.as_dict().get("vform") == "finite"
                            for c in self.parser._lattice_for_text("went").candidates))

    def test_different_vocabulary_and_same_coordination(self):
        for source in self.CONTROLS:
            with self.subTest(source=source):
                result = self.control(source)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, self.ROOT)

    def test_invalid_agreement_and_different_scopes_do_not_use_this_assembly(self):
        for i, before, after in (
            (0, "was getting", "were getting"),
            (0, "and was", "and she was"),
            (0, "notified them", "watched them"),
            (1, "was very", "were very"),
            (1, "though awake,", "though awake"),
            (2, "and greeted", "and greets"),
            (2, "and greeted", "and they greeted"),
        ):
            with self.subTest(i=i, replacement=after):
                result = self.control(self.CONTROLS[i].replace(before, after))
                tree = result.best()
                self.assertTrue(tree is None or tree.rule_id != self.ROOT)


if __name__ == "__main__":
    unittest.main()
