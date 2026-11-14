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

from research.verbnet_lr.corpus_pipeline import parse_corpus_case, prepare_corpus_input
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.diagnose_novel_parses import select_cases
from seman_parser.dialogue_clause_plans import PARENTHETICAL_MODAL
from seman_parser.adjective_infinitive_scope import ROOT as ADJECTIVE_INFINITIVE_ROOT
from seman_parser.embedded_relative_scope import ROOT as EMBEDDED_RELATIVE_ROOT
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

    def test_semicolon_resumes_matrix_subject_without_crossing_comparison(self):
        cases, _ = select_cases(500)
        text, frame = self.case_tree(113, cases[113], "e4a5ae9674b49144")
        self.assertEqual(frame.rule_id, "structural_framed_shared_subject_coordination")
        self.assertEqual(self.parts(frame, text)[0], ("ADV", "Here"))
        subject, pair = frame.children[-1].children
        self.assertEqual(text[subject.start:subject.end], "she")
        self.assertEqual(pair.rule_id, "structural_semicolon_shared_predicates_with_supplement")
        self.assert_agreement(subject, pair, "singular")
        self.assertEqual(self.parts(pair, text)[:3], [
            ("V", "ceased"), ("SEMICOLON", ";"), ("COORD", "and"),
        ])
        supplement, comma, appearance = pair.children[-1].children
        self.assertEqual(comma.category, "COMMA")
        self.assertEqual(self.parts(supplement, text), [
            ("TRANSITIVE-PARTICIPIAL", "snapping her reticule again"),
            ("COMMA", ","), ("COORD", "and"),
            ("TRANSITIVE-PARTICIPIAL", "shutting her mouth"),
        ])
        first_part = supplement.children[0].children[0]
        self.assertEqual(self.parts(first_part, text), [
            ("TRANSITIVE-PARTICIPIAL", "snapping her reticule"), ("ADV", "again"),
        ])
        self.assertEqual(self.parts(appearance, text)[0], ("V", "looked"))
        comparison = appearance.children[-1]
        self.assertEqual(self.parts(comparison, text)[:3], [
            ("CONJ", "as"), ("CONJ", "if"), ("NP", "she"),
        ])
        self.assertGreater(comparison.children[2].start, subject.end)
        contrast = comparison.children[-1]
        self.assertEqual(self.parts(contrast, text), [
            ("VP", "might be broken"), ("COMMA", ","), ("COORD", "but"),
            ("VP", "could never be bent"),
        ])
        first_passive, second_passive = contrast.children[0], contrast.children[-1]
        for passive, verb in ((first_passive, "break"), (second_passive, "bend")):
            self.assertEqual(passive.features.as_dict()["voice"], "passive")
            self.assertEqual(passive.children[-1].lexical_candidate.lemma, verb)
            self.assertEqual(passive.children[-1].features.as_dict()["vform"], "ed")
            self.assertEqual(passive.children[-2].features.as_dict()["vform"], "base")
        self.assertNotEqual(first_passive.features.as_dict().get("negation"), "true")
        self.assertEqual(second_passive.features.as_dict()["negation"], "true")
        self.assertEqual(text[second_passive.children[1].start:
                              second_passive.children[1].end], "never")

        prepared = prepare_corpus_input(cases[113])
        report = self.parser.parse(text, structural_constituents=prepared.structural_constituents,
                                   max_items=50_000, kbest_work_limit=500_000)
        graph = report.interpret().graph
        edges = {(r.relation, graph.nodes[r.source].surface,
                  graph.nodes[r.target].surface, graph.nodes[r.target].span)
                 for r in graph.relations}
        matrix_span = (subject.start, subject.end)
        inner_span = (comparison.children[2].start, comparison.children[2].end)
        for predicate in ("ceased", "looked", "snapping", "shutting"):
            self.assertIn(("AGENT", predicate, "she", matrix_span), edges)
        for predicate in ("broken", "bent"):
            self.assertIn(("THEME", predicate, "she", inner_span), edges)
            self.assertNotIn(("THEME", predicate, "she", matrix_span), edges)
        surfaces = {edge[:3] for edge in edges}
        for edge in (
            ("CONJUNCT", "ceased", "looked"),
            ("ADJUNCT", "looked", "snapping"), ("ADJUNCT", "looked", "shutting"),
            ("COMPARISON", "looked", "broken"), ("CONJUNCT", "broken", "bent"),
            ("MODALITY", "broken", "might"), ("MODALITY", "bent", "could"),
            ("NEGATION", "bent", "never"),
        ):
            self.assertIn(edge, surfaces)
        self.assertNotIn(("NEGATION", "broken", "never"), surfaces)

    def test_nested_coordination_accepts_a_different_embedded_subject(self):
        for source, embedded in (
            ("Then he paused; and folding his letter slowly, and closing his eyes, "
             "seemed as if he would be persuaded, but could never be deceived.", "he"),
            ("Now she stopped; and clutching her shawl tightly, and covering her face, "
             "appeared as if they might be startled, but would never be fooled.", "they"),
        ):
            with self.subTest(source=source):
                best = self.control(source).best()
                self.assertIsNotNone(best)
                self.assertEqual(best.rule_id, self.ROOT)
                matrix = best.children[0].children[-1]
                comparison = matrix.children[-1].children[-1].children[-1].children[-1]
                self.assertEqual(comparison.rule_id, "structural_as_if_shared_subject_comparison")
                inner = comparison.children[2]
                self.assertEqual(source[inner.start:inner.end], embedded)

    def test_nested_coordination_does_not_promote_unproved_conjuncts(self):
        source = ("Then he paused; and folding his letter slowly, and closing his eyes, "
                  "seemed as if he would be persuaded, but could never be deceived.")
        for before, after in (
            ("and folding", "and they folding"),
            ("could never", "they could never"),
            ("seemed as if", "worked as if"),
            ("he paused", "he pause"),
            ("be persuaded", "be slept"),
            ("be deceived", "be deceive"),
            ("never be", "often be"),
        ):
            with self.subTest(replacement=after):
                best = self.control(source.replace(before, after)).best()
                self.assertTrue(best is None or best.rule_id != self.ROOT)

    MANNER_CONTROLS = (
        "She asked how far the house was from the river; and, after reading his letter, "
        "wondered in a measured voice how long John had been working there.",
        "They heard with great surprise the account concerning the voyage and laughed "
        "at the descriptions of Alice Brown and Mary Smith, but without the bitterness "
        "that John had displayed.",
    )

    def test_interposed_manner_preserves_the_two_types_of_selected_complement(self):
        cases, _ = select_cases(500)
        text, clause = self.case_tree(226, cases[226], "22ebce05b8634656")
        subject, pair = clause.children
        self.assert_agreement(subject, pair, "singular")
        first, semicolon, _, _, temporal, _, second = pair.children
        self.assertEqual(semicolon.category, "SEMICOLON")
        self.assertEqual(self.parts(first, text), [
            ("V", "inquired"), ("WH-CLAUSE", "how far Netherfield was from Meryton"),
        ])
        self.assertEqual(self.parts(temporal, text), [
            ("PREP", "after"), ("TRANSITIVE-PARTICIPIAL", "receiving her answer"),
        ])
        self.assertEqual(self.parts(second, text), [
            ("V", "asked"), ("PP", "in a hesitating manner"),
            ("WH-CLAUSE", "how long Mr. Darcy had been staying there"),
        ])
        self.assertEqual(self.parts(second.children[-1], text), [
            ("WH-NOM", "how"), ("ADV", "long"), ("NP", "Mr. Darcy"),
            ("VP", "had been staying there"),
        ])
        self.assertEqual(second.children[-1].children[-1].features.as_dict()["aspect"],
                         "perfect-progressive")

        text, clause = self.case_tree(350, cases[350], "c2b96fbdff6cbd00")
        subject, pair = clause.children
        self.assert_agreement(subject, pair, "singular")
        first, _, second = pair.children
        self.assertEqual(self.parts(first, text), [
            ("V", "heard"), ("PP", "with attention"),
            ("NP", "the little narration concerning my studies"),
        ])
        smile, _, _, contrast = second.children
        self.assertEqual(self.parts(smile, text), [
            ("V", "smiled"), ("PREP", "at"),
            ("NAMED-LIST", "the names of Cornelius Agrippa and Paracelsus"),
        ])
        names = smile.children[-1].children[-1]
        self.assertEqual(self.parts(names, text), [
            ("NP", "Cornelius Agrippa"), ("COORD", "and"), ("NP", "Paracelsus"),
        ])
        relative = contrast.children[-1].children[-1]
        self.assertEqual(self.parts(relative, text), [
            ("COMP-THAT", "that"), ("NP", "M. Krempe"), ("VP-GAP", "had exhibited"),
        ])
        self.assertEqual(relative.children[-1].features.as_dict()["gap"], "object")

        for index, required_edges in (
            (226, {("MANNER", "asked", "in"), ("COMPLEMENT", "asked", "staying"),
                   ("TEMPORAL", "asked", "receiving"), ("AGENT", "staying", "Darcy")}),
            (350, {("MANNER", "heard", "with"), ("AFFECTED", "heard", "narration"),
                   ("CONTRAST", "smiled", "contempt"), ("AFFECTED", "exhibited", "contempt"),
                   ("CONJUNCT", "Cornelius", "Paracelsus")}),
        ):
            prepared = prepare_corpus_input(cases[index])
            report = self.parser.parse(
                prepared.analysis_text, structural_constituents=prepared.structural_constituents,
                max_items=50_000, kbest_work_limit=500_000,
            )
            graph = report.interpret().graph
            edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                     for r in graph.relations}
            self.assertTrue(required_edges <= edges, required_edges - edges)

    def test_interposed_manner_accepts_varied_sources_but_requires_its_own_span(self):
        for text, rule, mode, complement in (
            (self.MANNER_CONTROLS[0], "structural_measure_interrogative_with_interposed_manner",
             "in a measured voice", "how long John had been working there"),
            (self.MANNER_CONTROLS[1], "structural_transitive_with_interposed_manner",
             "with great surprise", "the account concerning the voyage"),
        ):
            with self.subTest(text=text):
                root = self.control(text).best()
                self.assertEqual(root.rule_id, self.ROOT)
                node, = [n for n in SubjectResumptionTests.walk(root) if n.rule_id == rule]
                self.assertEqual(self.parts(node, text)[1:], [
                    ("PP", mode), ("WH-CLAUSE" if text.startswith("She") else "NP", complement),
                ])

    def test_interposed_manner_rejects_wrong_valency_and_clause_scope(self):
        for i, before, after in (
            (0, "wondered in", "slept in"),
            (0, "wondered in", "they wondered in"),
            (0, "in a measured voice", "in a rented house"),
            (0, "had been working", "have been working"),
            (1, "heard with", "slept with"),
            (1, "laughed at", "they laughed at"),
            (1, "with great surprise", "with John"),
            (1, "had displayed", "had slept"),
        ):
            with self.subTest(after=after):
                best = self.control(self.MANNER_CONTROLS[i].replace(before, after)).best()
                self.assertTrue(best is None or best.rule_id != self.ROOT)

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


class AdjectiveInfinitiveScopeTests(unittest.TestCase):
    CONTROLS = (
        "Mrs. Brown and her friend hardly touched their food, except to nibble at the bread, "
        "and were clearly eager to keep the room to themselves.",
        "She was reluctant to open the door; a hundred visitors waited outside, and she spoke softly.",
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000, kbest_work_limit=500_000)

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=120)
        self.assertEqual([r["source_text"] for r in rows], [text])
        return self.parse(rows[0])[2]

    def original(self, case, sha_prefix):
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], sha_prefix)
        prepared, lattice, result = self.parse(case)
        self.assertEqual(prepared.analysis_text, text)
        self.assertEqual(lattice.text, text)
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        root = result.best()
        self.assertEqual(root.rule_id, ADJECTIVE_INFINITIVE_ROOT)
        self.assertEqual((root.start, root.end), (0, len(text)))
        return text, root.children[0]

    def test_coordinated_subject_controls_only_its_own_infinitive(self):
        case = select_cases(500)[0][228]
        text, clause = self.original(case, "700479afe09ec02c")
        parts = SharedSubjectCoordinationTests.parts
        subject, first, _, _, second = clause.children
        self.assertEqual(parts(subject, text), [
            ("NP", "Mrs. Hurst"), ("COORD", "and"), ("NP", "her sister"),
        ])
        self.assertEqual(parts(first, text), [
            ("ADV", "scarcely"), ("VP", "opened their mouths"), ("COMMA", ","),
            ("EXCEPTION-SUPPLEMENT", "except to complain of fatigue"),
        ])
        self.assertEqual(parts(second, text), [
            ("COPULA", "were"), ("ADV", "evidently"), ("ADJP", "impatient to have the house to themselves"),
        ])
        adjective = second.children[-1]
        self.assertEqual(parts(adjective, text), [
            ("ADJ", "impatient"), ("SELECTED-INFINITIVE", "to have the house to themselves"),
        ])
        infinitive = adjective.children[-1]
        self.assertEqual(parts(infinitive, text), [
            ("TO", "to"), ("V", "have"), ("NP", "the house"), ("EXCLUSIVE-PP", "to themselves"),
        ])
        self.assertEqual(infinitive.children[1].features.as_dict()["vform"], "base")
        for node in (subject, first, second, infinitive.children[-1].children[-1]):
            self.assertEqual(node.features.as_dict()["number"], "plural")

    def test_parataxis_cannot_become_part_of_the_infinitive(self):
        case = select_cases(500)[0][337]
        text, clause = self.original(case, "583db0f51d907c11")
        parts = SharedSubjectCoordinationTests.parts
        left, semicolon, continuation = clause.children
        self.assertEqual(semicolon.category, "SEMICOLON")
        self.assertEqual(parts(left, text), [
            ("NP", "I"), ("VP", "was unable to pursue the train of thought"),
        ])
        adjective = left.children[-1].children[-1]
        self.assertEqual(parts(adjective, text), [
            ("ADJ", "unable"), ("SELECTED-INFINITIVE", "to pursue the train of thought"),
        ])
        infinitive = adjective.children[-1]
        self.assertEqual(parts(infinitive, text), [
            ("TO", "to"), ("V", "pursue"), ("NP", "the train of thought"),
        ])
        self.assertEqual(infinitive.children[-1].children[0].rule_id, "np_det_n_of")
        self.assertLessEqual(infinitive.end, semicolon.start)
        self.assertEqual(parts(continuation, text), [
            ("COUNTED-CLAUSE", "a thousand feelings pressed upon me"),
            ("COMMA", ","), ("COORD", "and"), ("CLAUSE", "I wept bitterly"),
        ])
        counted = continuation.children[0].children[0]
        self.assertEqual(counted.features.as_dict()["number"], "plural")
        self.assertEqual(parts(counted, text)[-1], ("N", "feelings"))

    def test_scope_generalizes_to_new_adjectives_and_rejects_wrong_licensing(self):
        for text in self.CONTROLS:
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, ADJECTIVE_INFINITIVE_ROOT)
        for i, before, after in (
            (0, "clearly eager", "clearly wooden"),
            (0, "were clearly", "was clearly"),
            (0, "to themselves", "to herself"),
            (0, "to themselves", "to ourselves"),
            (0, "except to", "except for"),
            (1, "reluctant", "wooden"),
            (1, "was reluctant", "were reluctant"),
            (1, "door; a hundred", "door, a hundred"),
            (1, "visitors waited", "visitors waits"),
        ):
            with self.subTest(negative=after):
                best = self.control(self.CONTROLS[i].replace(before, after)).best()
                self.assertTrue(best is None or best.rule_id != ADJECTIVE_INFINITIVE_ROOT)

    def test_semantic_roles_preserve_both_controllers_and_clause_scope(self):
        cases = select_cases(500)[0]
        for index in (228, 337):
            with self.subTest(index=index):
                prepared = prepare_corpus_input(cases[index])
                report = self.parser.parse(
                    prepared.analysis_text, structural_constituents=prepared.structural_constituents,
                    max_items=50_000, kbest_work_limit=500_000,
                )
                graph = report.interpret().graph
                label = lambda n: n.surface or n.type_name
                edges = {(r.relation, label(graph.nodes[r.source]), label(graph.nodes[r.target]))
                         for r in graph.relations}
                required = ({
                    ("MEMBER", "COORDINATED_SUBJECT", "Hurst"),
                    ("MEMBER", "COORDINATED_SUBJECT", "sister"),
                    ("AGENT", "have", "COORDINATED_SUBJECT"),
                    ("EXCEPTION", "opened", "complain"),
                    ("COMPLEMENT", "impatient", "have"),
                    ("EXCLUSIVE_HOLDER", "have", "themselves"),
                } if index == 228 else {
                    ("COMPLEMENT", "unable", "pursue"), ("AFFECTED", "pursue", "train"),
                    ("AGENT", "pressed", "feelings"), ("PARATAXIS", "was", "pressed"),
                    ("CONJUNCT", "pressed", "wept"),
                })
                self.assertTrue(required <= edges, required - edges)


class EmbeddedRelativeScopeTests(unittest.TestCase):
    CONTROLS = (
        "These solemn and majestic landscapes offered us the greatest comfort that we were capable of finding.",
        "Three of the sacks, tied in a rope's loop, made a heavy burden for a tall worker--one that she was eager to walk quietly with.",
    )

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def parse(self, case):
        return parse_corpus_case(self.parser, case, max_items=50_000, kbest_work_limit=500_000)

    def control(self, text):
        rows, _ = extract(Book(999, "Synthetic", "Test", "train"), text,
                          length_min=1, length_max=120)
        self.assertEqual([row["source_text"] for row in rows], [text])
        return self.parse(rows[0])[2]

    def original(self, case, checksum):
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], checksum)
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        root = result.best()
        self.assertEqual(root.rule_id, EMBEDDED_RELATIVE_ROOT)
        self.assertEqual((root.start, root.end), (0, len(text)))
        return text, root.children[0]

    def test_gerund_fills_verb_object_not_the_preposition_of(self):
        text, matrix = self.original(select_cases(500)[0][328], "3ca68aab1902e8d7")
        parts = SharedSubjectCoordinationTests.parts
        self.assertEqual(parts(matrix, text), [
            ("NP", "These sublime and magnificent scenes"), ("V", "afforded"),
            ("NP", "me"), ("RELATIVE-HEAD", "the greatest consolation that I was capable of receiving"),
        ])
        head, relative = matrix.children[-1].children
        self.assertEqual(text[head.start:head.end], "the greatest consolation")
        self.assertEqual(parts(relative, text), [
            ("COMP-THAT", "that"), ("NP", "I"), ("COPULA", "was"),
            ("GAPPED-ADJP", "capable of receiving"),
        ])
        adjective = relative.children[-1]
        self.assertEqual(parts(adjective, text), [
            ("ADJ", "capable"), ("PREP", "of"), ("GAPPED-NONFINITE", "receiving"),
        ])
        self.assertEqual(adjective.children[-1].features.as_dict()["gap"], "object")
        self.assertEqual(parts(adjective.children[-1], text), [("V", "receiving")])

    def test_dashed_nominal_restatement_keeps_the_stranded_with(self):
        text, matrix = self.original(select_cases(500)[0][499], "831e1f5ff09a8b07")
        parts = SharedSubjectCoordinationTests.parts
        subject, _, _, dash, afterthought = matrix.children
        self.assertEqual(parts(subject, text), [
            ("PARTITIVE-SUBJECT", "Two of the bars"), ("COMMA", ","), ("V", "slung"),
            ("PP", "in a rope's end"), ("COMMA", ","),
        ])
        self.assertEqual(subject.features.as_dict()["number"], "plural")
        self.assertEqual(subject.children[2].features.as_dict()["vform"], "ed")
        self.assertEqual(text[dash.start:dash.end], "--")
        self.assertEqual(parts(afterthought, text), [
            ("NUM", "one"), ("EMBEDDED-RELATIVE", "that he was glad to walk slowly with"),
        ])
        adjective = afterthought.children[-1].children[-1]
        self.assertEqual(parts(adjective, text), [
            ("ADJ", "glad"), ("TO", "to"), ("GAPPED-NONFINITE", "walk slowly with"),
        ])
        inner = adjective.children[-1]
        self.assertEqual(inner.features.as_dict()["gap"], "pp_object")
        self.assertEqual(parts(inner, text), [("V", "walk"), ("ADV", "slowly"), ("PREP", "with")])

    def test_distinct_lexical_controls_and_invalid_gap_filling(self):
        for text in self.CONTROLS:
            with self.subTest(positive=text):
                self.assertEqual(self.control(text).best().rule_id, EMBEDDED_RELATIVE_ROOT)
        for index, old, new in (
            (0, "of finding", "of arriving"),
            (0, "capable of", "wooden of"),
            (0, "of finding", "of finding it"),
            (0, "offered us", "observed us"),
            (0, "we were", "we was"),
            (1, "with.", "with it."),
            (1, "walk quietly", "sleep quietly"),
            (1, "eager to", "wooden to"),
            (1, "she was", "she were"),
            (1, "worker--one", "worker, one"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.CONTROLS[index].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EMBEDDED_RELATIVE_ROOT)

    def test_relative_gap_semantics_links_to_the_correct_governor(self):
        cases = select_cases(500)[0]
        for index, expected in (
            (328, {("AFFECTED", "receiving", "consolation"), ("THEME", "afforded", "consolation"),
                   ("RECIPIENT", "afforded", "me"), ("AGENT", "receiving", "I")}),
            (499, {("COMPLEMENT", "with", "one"), ("RESTATEMENT", "load", "one"),
                   ("AGENT", "walk", "he"), ("MANNER", "walk", "slowly"),
                   ("THEME", "slung", "COUNTED_SUBSET")}),
        ):
            with self.subTest(index=index):
                p = prepare_corpus_input(cases[index])
                report = self.parser.parse(p.analysis_text, structural_constituents=p.structural_constituents,
                                           max_items=50_000, kbest_work_limit=500_000)
                graph = report.interpret().graph
                label = lambda n: n.surface or n.type_name
                edges = {(r.relation, label(graph.nodes[r.source]), label(graph.nodes[r.target]))
                         for r in graph.relations}
                self.assertTrue(expected <= edges, expected - edges)

    NESTED_CONTROLS = (
        "Often she sat with her hands folded on the table, fearing to move them lest they should touch the instrument which she so much dreaded to handle.",
        "The captain was kneeling down, as pale as a ghost, thinking of the place she had brought us to, the kind man!",
    )

    def test_control_relative_in_preventive_clause(self):
        text, matrix = self.original(select_cases(500)[0][363], "043d459b0ca079d5")
        parts = SharedSubjectCoordinationTests.parts
        self.assertEqual([c.category for c in matrix.children], [
            "ADV", "NP", "V", "WITH-ABSOLUTE", "COMMA", "CONTROL-SUPPLEMENT",
        ])
        absolute, supplement = matrix.children[3], matrix.children[-1]
        self.assertEqual(parts(absolute, text), [
            ("PREP", "with"), ("ABSOLUTE-SUBJECT", "my eyes"),
            ("V", "fixed"), ("PP", "on the ground"),
        ])
        self.assertEqual(absolute.children[1].features.as_dict()["number"], "plural")
        action = supplement.children[-1]
        self.assertEqual(parts(action, text)[:2], [("V", "raise"), ("NP", "them")])
        preventive = action.children[-1]
        self.assertEqual(parts(preventive, text)[:4], [
            ("PREVENTIVE-CONJ", "lest"), ("NP", "they"), ("MODAL", "should"), ("V", "encounter"),
        ])
        head, relative = preventive.children[-1].children
        self.assertEqual(text[head.start:head.end], "the object")
        self.assertEqual(parts(relative, text)[:2], [("WH-REL-OBL", "which"), ("NP", "I")])
        control = relative.children[-1]
        self.assertEqual(parts(control, text), [
            ("ADVP", "so much"), ("V", "dreaded"), ("TO", "to"), ("GAPPED-NONFINITE", "behold"),
        ])
        self.assertEqual(parts(control.children[-1], text), [("V", "behold")])

    def test_stranded_direction_and_matrix_apposition(self):
        text, matrix = self.original(select_cases(500)[0][480], "d72d4dec205d9250")
        parts = SharedSubjectCoordinationTests.parts
        self.assertEqual(parts(matrix, text), [
            ("NP", "The squire"), ("PARTICLE-PROGRESSIVE", "was sitting down"), ("COMMA", ","),
            ("ADJP", "as white as a sheet"), ("COMMA", ","),
            ("RELATIVE-TOPIC-SUPPLEMENT", "thinking of the harm he had led us to"),
            ("COMMA", ","), ("NP", "the good soul"),
        ])
        self.assertEqual(parts(matrix.children[1], text), [
            ("AUX-BE", "was"), ("V", "sitting"), ("PARTICLE", "down"),
        ])
        topic = matrix.children[5]
        self.assertEqual(parts(topic, text)[:2], [("V", "thinking"), ("PREP", "of")])
        head, relative = topic.children[-1].children
        self.assertEqual(text[head.start:head.end], "the harm")
        self.assertEqual(relative.features.as_dict()["gap"], "directional_pp_object")
        self.assertEqual(parts(relative, text), [
            ("NP", "he"), ("HAVE", "had"), ("V", "led"), ("NP", "us"), ("PREP", "to"),
        ])

    def test_nested_relative_controls_and_counterexamples(self):
        for text in self.NESTED_CONTROLS:
            with self.subTest(positive=text):
                self.assertEqual(self.control(text).best().rule_id, EMBEDDED_RELATIVE_ROOT)
        for index, old, new in (
            (0, "to handle.", "to handle it."),
            (0, "to handle.", "to arrive."),
            (0, "so much dreaded", "so much watched"),
            (0, "should touch", "should sleep"),
            (1, "us to,", "us to it,"),
            (1, "brought us", "slept us"),
            (1, "captain was", "captain were"),
            (1, "us to, the kind", "us to the kind"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.NESTED_CONTROLS[index].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EMBEDDED_RELATIVE_ROOT)

    def test_nested_relative_semantics_respect_exact_governors(self):
        cases = select_cases(500)[0]
        for index, expected, forbidden in (
            (363, {("THEME", "fixed", "eyes"), ("ADJUNCT", "fixed", "on"),
                   ("AGENT", "fearing", "I"), ("AGENT", "raise", "I"),
                   ("AFFECTED", "raise", "them"), ("PREVENTIVE_CONSEQUENCE", "raise", "encounter"),
                   ("AGENT", "encounter", "they"), ("AFFECTED", "encounter", "object"),
                   ("DEGREE", "dreaded", "much"), ("COMPLEMENT", "dreaded", "behold"),
                   ("AGENT", "behold", "I"), ("AFFECTED", "behold", "object")},
                  {("AFFECTED", "dreaded", "object"), ("PREVENTIVE_CONSEQUENCE", "fearing", "encounter"),
                   ("AGENT", "fixed", "I")}),
            (480, {("ASPECT", "sitting", "was"), ("PARTICLE", "sitting", "down"),
                   ("DEPICTIVE", "squire", "white"), ("AGENT", "thinking", "squire"),
                   ("COMPLEMENT", "of", "harm"), ("AGENT", "led", "he"),
                   ("AFFECTED", "led", "us"), ("COMPLEMENT", "to", "harm"),
                   ("APPOSITION", "squire", "soul")},
                  {("AFFECTED", "led", "harm"), ("COMPLEMENT", "to", "soul"),
                   ("APPOSITION", "harm", "soul")}),
        ):
            with self.subTest(index=index):
                p = prepare_corpus_input(cases[index])
                report = self.parser.parse(p.analysis_text, structural_constituents=p.structural_constituents,
                                           max_items=50_000, kbest_work_limit=500_000)
                graph = report.interpret().graph
                label = lambda n: n.surface or n.type_name
                edges = {(r.relation, label(graph.nodes[r.source]), label(graph.nodes[r.target]))
                         for r in graph.relations}
                self.assertTrue(expected <= edges, expected - edges)
                self.assertFalse(forbidden & edges, forbidden & edges)


if __name__ == "__main__":
    unittest.main()
