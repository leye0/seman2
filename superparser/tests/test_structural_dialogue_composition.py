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
from seman_parser.finite_temporal_scope import ROOT as FINITE_TEMPORAL_ROOT
from seman_parser.engine import ParseReport, Parser
from seman_parser.negative_perfect import ROOT as NEGATIVE_PERFECT_ROOT
from seman_parser.coordinated_gerund_effect import ROOT as GERUND_EFFECT_ROOT
from seman_parser.passive_and_perfect_extraposition import ROOT as PASSIVE_EXTRAPOSITION_ROOT
from seman_parser.subject_question_ability import ROOT as QUESTION_ABILITY_ROOT
from seman_parser.causal_posture_response import ROOT as CAUSAL_POSTURE_ROOT
from seman_parser.exclamative_infinitive_contrast import ROOT as EXCLAMATIVE_CONTRAST_ROOT
from seman_parser.modal_context_free_relative import ROOT as MODAL_CONTEXT_ROOT
from seman_parser.integrated_role_apposition import ROOT as ROLE_APPOSITION_ROOT
from seman_parser.conditional_ellipsis_series import ROOT as CONDITIONAL_SERIES_ROOT
from seman_parser.shared_comparative_reply import ROOT as COMPARATIVE_REPLY_ROOT
from seman_parser.copular_resolution_content import ROOT as RESOLUTION_CONTENT_ROOT
from seman_parser.comparative_content_coordination import ROOT as COMPARATIVE_CONTENT_ROOT
from seman_parser.extraposed_object_relative import ROOT as EXTRAPOSED_OBJECT_ROOT
from seman_parser.extraposed_scalar_content import ROOT as EXTRAPOSED_SCALAR_ROOT
from seman_parser.degree_concessive import ROOT as DEGREE_CONCESSIVE_ROOT
from seman_parser.paired_clause_supplements import ROOT as PAIRED_SUPPLEMENTS_ROOT
from seman_parser.parenthetical_alternative import ROOT as PARENTHETICAL_ALTERNATIVE
from seman_parser.shared_by_coordination import ROOT as SHARED_BY_ROOT
from seman_parser.semicolon_triplet import ROOT as TRIPLET_ROOT
from seman_parser.inverted_object_control import ROOT as INVERTED_CONTROL_ROOT
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

class ParentheticalAlternativeTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    CONTROL = (
        "Or (so she imagined) a reversal might soon happen to defeat them "
        "and put an end to the dispute permanently."
    )
    SIMPLE_CONTROL = (
        "Or (so he thought) a storm could later arise to wreck the bridge "
        "and damage the road."
    )

    def test_case_360_preserves_both_finite_scopes_and_one_infinitival_marker(self):
        case = select_cases(500)[0][360]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "74fc9f769935201a")
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        tree = result.best()
        self.assertEqual((tree.rule_id, tree.start, tree.end),
                         (PARENTHETICAL_ALTERNATIVE, 0, len(text)))
        self.assertEqual(self.spans(tree.children, text), [
            ("COORD", "Or"),
            ("ALTERNATIVE-COGNITION", "(so my fond fancy imaged)"),
            ("ALTERNATIVE-HOST", "some accident might meanwhile occur to destroy him and put an end to my slavery forever"),
            ("SPEECH-STOP", "."),
        ])
        _, aside, host, _ = tree.children
        self.assertEqual(prepared.source_component(f"p{aside.start}"), "(so my fond fancy imaged)")
        self.assertEqual(self.spans(aside.children, text), [
            ("OPEN-PAREN", "("), ("ADV", "so"), ("NP", "my fond fancy"),
            ("V", "imaged"), ("CLOSE-PAREN", ")"),
        ])
        self.assertEqual(self.spans(host.children[:4], text), [
            ("NP", "some accident"), ("MODAL", "might"), ("ADV", "meanwhile"), ("V", "occur"),
        ])
        coordinated = host.children[-1]
        self.assertEqual(self.spans(coordinated.children, text), [
            ("TO", "to"), ("VP-NP", "destroy him"), ("COORD", "and"),
            ("TERMINATION-VP", "put an end to my slavery forever"),
        ])
        self.assertEqual(self.spans(coordinated.children[-1].children, text), [
            ("V", "put"), ("NP", "an end"), ("TERMINATION-TARGET", "to my slavery"),
            ("ADV", "forever"),
        ])

    def test_case_360_semantics_do_not_promote_the_aside_or_the_infinitives(self):
        case = select_cases(500)[0][360]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, PARENTHETICAL_ALTERNATIVE)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                 for r in graph.relations}
        expected = {
            ("DISCOURSE", "occur", "Or"), ("AGENT", "imaged", "fancy"),
            ("COMPLEMENT", "imaged", "occur"), ("CONTENT", "so", "occur"),
            ("THEME", "occur", "accident"), ("MODALITY", "occur", "might"),
            ("TIME", "occur", "meanwhile"), ("CONSEQUENCE", "occur", "destroy"),
            ("CONSEQUENCE", "occur", "put"), ("CONJUNCT", "destroy", "put"),
            ("AFFECTED", "destroy", "him"), ("TERMINATES", "put", "slavery"),
            ("DURATION", "put", "forever"),
        }
        forbidden = {
            ("AGENT", "occur", "fancy"), ("COMPLEMENT", "imaged", "destroy"),
            ("TIME", "imaged", "meanwhile"), ("DURATION", "occur", "forever"),
            ("DURATION", "destroy", "forever"), ("PURPOSE", "occur", "destroy"),
        }
        self.assertTrue(expected <= edges, expected - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_alternative_uses_lexically_proven_cognition_and_bare_conjuncts(self):
        for text in (self.CONTROL, self.SIMPLE_CONTROL):
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, PARENTHETICAL_ALTERNATIVE)
        for old, new in (
            ("she imagined", "she laughed"), ("soon happen", "soon happens"),
            ("and put", "and puts"), ("(so she imagined)", "so she imagined"),
            ("and put", "and to put"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != PARENTHETICAL_ALTERNATIVE)


class SharedByCoordinationTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    CONTROL = (
        "She liked the visit, and yet her mood was troubled both by the noise and the delay."
    )
    SECOND_CONTROL = (
        "I enjoyed the visit, but my friend was troubled both by the cost of the journey "
        "and the loss of her notes."
    )

    def test_case_362_shared_by_and_independent_of_complements(self):
        case = select_cases(500)[0][362]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "33e4ba2f255c0841")
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end),
                         (SHARED_BY_ROOT, 0, len(text)))
        left, _, contrast, right, _ = root.children
        self.assertEqual(text[left.start:left.end], "I enjoyed this scene")
        self.assertEqual(self.spans(contrast.children, text), [("COORD", "and"), ("COORD", "yet")])
        passive, pp = right.children
        self.assertEqual(text[passive.start:passive.end], "my enjoyment was embittered")
        self.assertEqual(prepared.source_component("b0"), text[pp.start:pp.end])
        both, by, pair = pp.children
        self.assertEqual(self.spans((both, by), text), [("DET", "both"), ("PREP-BY", "by")])
        first, coord, second = pair.children
        self.assertEqual(self.spans((first, coord, second), text), [
            ("CAUSE-NOMINAL", "the memory of the past"), ("COORD", "and"),
            ("CAUSE-NOMINAL", "the anticipation of the future"),
        ])
        for nominal, head, content in (
            (first, "the memory", "the past"), (second, "the anticipation", "the future"),
        ):
            self.assertEqual(self.spans(nominal.children, text),
                             [("NP", head), ("PREP", "of"), ("NP", content)])

    def test_case_362_semantics_keeps_both_causes_under_the_second_predicate(self):
        case = select_cases(500)[0][362]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, SHARED_BY_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                 for r in graph.relations}
        required = {
            ("CONTRAST", "enjoyed", "embittered"), ("THEME", "embittered", "enjoyment"),
            ("AFFECTED", "enjoyed", "scene"), ("ADJUNCT", "embittered", "by"),
            ("CAUSE", "embittered", "memory"), ("CAUSE", "embittered", "anticipation"),
            ("COMPLEMENT", "by", "memory"), ("COMPLEMENT", "by", "anticipation"),
            ("FOCUS", "memory", "both"), ("FOCUS", "anticipation", "both"),
        }
        forbidden = {
            ("CAUSE", "enjoyed", "memory"), ("CAUSE", "embittered", "past"),
            ("CAUSE", "embittered", "future"), ("CONJUNCT", "past", "anticipation"),
            ("PARTITIVE", "memory", "past"), ("PARTITIVE", "anticipation", "future"),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)
        for head, particle, complement in (("memory", "of the past", "past"),
                                             ("anticipation", "of the future", "future")):
            offset = case["source_text"].index(particle)
            of, = [i for i, n in graph.nodes.items() if n.surface == "of" and n.span[0] == offset]
            links = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                     for r in graph.relations if of in (r.source, r.target)}
            self.assertEqual(links, {("MODIFIER", head, "of"), ("COMPLEMENT", "of", complement)})

    def test_shared_preposition_independent_positives_and_near_misses(self):
        positives = (self.CONTROL, self.SECOND_CONTROL)
        for text in positives:
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, SHARED_BY_ROOT)
        for old, new in (
            ("and yet", "and but"), ("was troubled", "were troubled"),
            ("was troubled", "was interviewed"), ("both by", "both at"),
            ("and the delay", "and by the delay"), ("and the delay", "and she left"),
            ("both by", "by"),
        ):
            with self.subTest(negative=new):
                best = self.control(positives[0].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != SHARED_BY_ROOT)


class SemicolonTripletTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    SOUND = (
        "It resounded on my ears briefly and sharply; the walls echoed it, "
        "and I felt as if the crowd surrounded me with whispers and cries."
    )
    PREVENTION = (
        "Dr. Green was stopped speaking by the arrival of the messenger with a letter "
        "for Miss Clarke; it came from London, and the messenger waited for a reply."
    )

    def test_originals_preserve_typed_semicolon_and_the_two_right_conjuncts(self):
        cases = select_cases(500)[0]
        for index, digest in ((221, "139e328f9c65aef8"), (371, "725d7c392db73387")):
            with self.subTest(index=index):
                text = cases[index]["source_text"]
                self.assertEqual(sha256(text.encode()).hexdigest()[:16], digest)
                prepared, lattice, result = self.parse(cases[index])
                self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats["budget_exceeded"])
                self.assertFalse(result.stats["kbest_budget_exceeded"])
                root = result.best()
                self.assertEqual((root.rule_id, root.start, root.end), (TRIPLET_ROOT, 0, len(text)))
                left, semi, post, stop = root.children
                middle, comma, and_, right = post.children
                self.assertEqual(self.spans((semi, comma, and_, stop), text), [
                    ("SEMICOLON", ";"), ("COMMA", ","), ("COORD", "and"), ("SPEECH-STOP", "."),
                ])
                self.assertEqual(prepared.source_component("st0"), text[middle.start:middle.end])
                self.assertEqual(prepared.source_component("st1"), text[right.start:right.end])
                parts = {x["id"]: x for x in prepared.structural_constituents}
                self.assertEqual((parts["st0"]["governor"], parts["st1"]["governor"]), ("s1", "st0"))
                if index == 221:
                    who, be, prevent, reply, cause = left.children
                    self.assertEqual(self.spans((who, be, prevent, reply), text), [
                        ("TITLED-SUBJECT", "Mrs. Bennet"), ("AUX-BE", "was"),
                        ("V", "prevented"), ("V", "replying"),
                    ])
                    arrival = cause.children[-1]
                    carrier = arrival.children[-1]
                    letter = carrier.children[-1]
                    self.assertEqual(self.spans(letter.children, text), [
                        ("NP", "a note"), ("PREP", "for"), ("TITLED-SUBJECT", "Miss Bennet"),
                    ])
                else:
                    adverbs = left.children[-1]
                    self.assertEqual(self.spans(adverbs.children, text),
                                     [("ADV", "long"), ("COORD", "and"), ("ADV", "heavily")])
                    comparison = right.children[-1]
                    self.assertEqual(self.spans(comparison.children[:2], text),
                                     [("ADV", "as"), ("CONJ", "if")])
                    manner = comparison.children[-1].children[-1]
                    self.assertEqual(self.spans(manner.children, text),
                                     [("PREP", "with"), ("NP", "mockery"),
                                      ("COORD", "and"), ("NP", "laughter")])

    def test_local_attachments_do_not_cross_the_semicolon_or_the_comparison(self):
        cases = select_cases(500)[0]
        for i, expected, forbidden in (
            (221, {("PREVENTED_ACTION", "prevented", "replying"),
                   ("AGENT", "replying", "Bennet"), ("CAUSE", "prevented", "entrance"),
                   ("AGENT", "entrance", "footman"), ("CARRIER", "note", "footman"),
                   ("RECIPIENT", "note", "Bennet"), ("SOURCE", "came", "Netherfield"),
                   ("PARATAXIS", "prevented", "came"), ("CONJUNCT", "came", "waited")},
                  {("CAUSE", "replying", "entrance"), ("CAUSE", "prevented", "footman"),
                   ("CONJUNCT", "prevented", "waited"), ("SOURCE", "waited", "Netherfield")}),
            (371, {("DURATION", "rang", "long"), ("MANNER", "rang", "heavily"),
                   ("PARATAXIS", "rang", "re-echoed"), ("CONJUNCT", "re-echoed", "felt"),
                   ("COMPARISON", "felt", "surrounded"), ("HYPOTHETICAL", "surrounded", "as"),
                   ("AGENT", "surrounded", "hell"), ("QUANTIFIER", "hell", "all"),
                   ("AFFECTED", "surrounded", "me"), ("MANNER", "surrounded", "with"),
                   ("COMPLEMENT", "with", "mockery"), ("COMPLEMENT", "with", "laughter")},
                  {("MANNER", "re-echoed", "heavily"), ("CONDITION", "felt", "surrounded"),
                   ("CONJUNCT", "felt", "surrounded"), ("MANNER", "felt", "with"),
                   ("AGENT", "surrounded", "all")}),
        ):
            with self.subTest(index=i):
                _, lattice, result = self.parse(cases[i])
                self.assertEqual(result.best().rule_id, TRIPLET_ROOT)
                graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
                edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                         for r in graph.relations}
                self.assertTrue(expected <= edges, expected - edges)
                self.assertFalse(forbidden & edges, forbidden & edges)
                if i == 221:
                    for relation, event, title in (("AGENT", "replying", "Mrs."),
                                                   ("RECIPIENT", "note", "Miss")):
                        target, = [graph.nodes[r.target] for r in graph.relations
                                   if r.relation == relation and graph.nodes[r.source].surface == event]
                        offset = cases[i]["source_text"].index(title) + len(title) + 1
                        self.assertEqual(target.span[0], offset)

    def test_controls_vary_both_internal_hosts_and_reject_missing_finite_evidence(self):
        for text in (self.SOUND, self.PREVENTION):
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, TRIPLET_ROOT)
        for text, old, new in (
            (self.SOUND, "briefly and sharply", "brief and sharply"),
            (self.SOUND, "echoed it", "echoed he"),
            (self.SOUND, "felt as if", "felt as when"),
            (self.SOUND, "it, and I", "it, and"),
            (self.PREVENTION, "was stopped", "were stopped"),
            (self.PREVENTION, "stopped speaking", "praised speaking"),
            (self.PREVENTION, "stopped speaking", "stopped spoke"),
            (self.PREVENTION, "Clarke; it", "Clarke, it"),
        ):
            with self.subTest(negative=new):
                best = self.control(text.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != TRIPLET_ROOT)


class InvertedObjectControlTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    CONTROL = (
        "We hope to help her, yet could we persuade someone so deeply exhausted, "
        "so bereft of any sense of safety, to rest?"
    )

    def test_case_373_question_and_object_scope_are_source_exact(self):
        case = select_cases(500)[0][373]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "df685628548f2648")
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (INVERTED_CONTROL_ROOT, 0, len(text)))
        statement, comma, adversative, question = root.children
        self.assertEqual(self.spans((statement, comma, adversative), text),
                         [("CLAUSE", "I wish to soothe him"), ("COMMA", ","), ("COORD", "yet")])
        self.assertEqual(question.features.as_dict()["stype"], "question")
        modal, subject, counsel, obj, comma, to, live, stop = question.children
        self.assertEqual(self.spans((modal, subject, counsel, comma, to, live, stop), text),
                         [("MODAL", "can"), ("NP", "I"), ("V", "counsel"), ("COMMA", ","),
                          ("TO", "to"), ("V", "live"), ("QMARK", "?")])
        self.assertEqual(self.spans(obj.children, text), [
            ("CONTROL-OBJECT-HEAD", "one"), ("CONTROL-OBJECT-DEGREE", "so infinitely miserable"),
            ("COMMA", ","), ("CONTROL-OBJECT-DEGREE-OF", "so destitute of every hope of consolation"),
        ])
        self.assertEqual(prepared.source_component("iq0"), text[question.start:question.end])
        self.assertEqual(prepared.source_component("iq1"), text[obj.start:obj.end])
        parts = {x["id"]:x for x in prepared.structural_constituents}
        self.assertEqual(parts["iq1"]["governor"], "iq0")

    def test_case_373_two_of_dependencies_and_the_infinitival_controller(self):
        case = select_cases(500)[0][373]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, INVERTED_CONTROL_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                 for r in graph.relations}
        preferred = {
            ("COMPLEMENT", "wish", "soothe"), ("AFFECTED", "soothe", "him"),
            ("CONTRAST", "wish", "counsel"), ("MODALITY", "counsel", "can"),
            ("AFFECTED", "counsel", "one"), ("MODIFIER", "one", "miserable"),
            ("SUPPLEMENT", "one", "destitute"), ("CONTENT", "hope", "consolation"),
            ("COMPLEMENT", "counsel", "live"), ("AGENT", "live", "one"),
        }
        forbidden = {
            ("AGENT", "live", "I"), ("COMPLEMENT", "destitute", "live"),
            ("COMPLEMENT", "wish", "live"), ("PARTITIVE", "hope", "consolation"),
            ("MODIFIER", "counsel", "miserable"), ("SUPPLEMENT", "counsel", "destitute"),
        }
        self.assertTrue(preferred <= edges, preferred - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)
        for start, expected in (
            ("of every hope", {("COMPLEMENT", "destitute", "of"), ("COMPLEMENT", "of", "hope")}),
            ("of consolation", {("MODIFIER", "hope", "of"), ("COMPLEMENT", "of", "consolation")}),
        ):
            offset = case["source_text"].index(start)
            of, = [key for key, node in graph.nodes.items() if node.surface == "of" and node.span[0] == offset]
            self.assertEqual({(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                              for r in graph.relations if of in (r.source, r.target)}, expected)

    def test_controls_require_inversion_and_object_control_valency(self):
        for text in (self.CONTROL, self.CONTROL.replace("yet", "but").replace("so deeply exhausted", "so tired")):
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, INVERTED_CONTROL_ROOT)
        for old, new in (
            ("could we", "we could"), ("could we", "could us"),
            ("persuade someone", "admire someone"), ("to rest", "to rested"),
            ("bereft of", "happy of"), ("safety, to", "safety to"),
            ("could we persuade", "could we persuaded"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != INVERTED_CONTROL_ROOT)


class MeasuredVoiceCoordinationTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    POSITIVE = ("The boats were pushed two yards closer to the dock and then followed "
                "a channel that could almost skirt the reef on the west.")

    @staticmethod
    def coordination(result):
        root = result.best()
        if root is not None and root.rule_id == "structural_shared_subject_source_sentence":
            host = root.children[0]
            if host.rule_id == "structural_measured_voice_coordination":
                return host
        return None

    def test_case_477_keeps_the_named_subject_and_two_finite_voices(self):
        case = select_cases(500)[0][477]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "1a8e1aa200463f0d")
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        self.assertEqual((result.best().start, result.best().end), (0, len(text)))
        host = self.coordination(result)
        self.assertIsNotNone(host)
        subject, passive, conjunction, active = host.children
        self.assertEqual(self.spans(subject.children, text), [("DET", "The"), ("PROPER-NOUN", "HISPANIOLA")])
        self.assertEqual(self.spans((conjunction,), text), [("COORD", "and")])
        self.assertEqual(prepared.source_component("mv0"), text[passive.start:passive.end])
        self.assertEqual(prepared.source_component("mv1"), text[active.start:active.end])
        for vp, voice in ((passive, "passive"), (active, "active")):
            self.assertEqual(vp.features.as_dict()["voice"], voice)
            self.assertEqual(vp.features.as_dict()["vform"], "finite")
            self.assertEqual(vp.features.as_dict()["number"], "singular")
        self.assertEqual(self.spans(passive.children, text), [
            ("AUX-BE", "was"), ("V", "laid"), ("DISTANCE-PREDICATE", "a couple of points nearer the wind"),
        ])
        self.assertEqual(self.spans(passive.children[-1].children, text), [
            ("SPATIAL-MEASURE", "a couple of points"), ("ADV", "nearer"), ("NP", "the wind"),
        ])
        route = active.children[-1]
        self.assertEqual(self.spans(route.children, text), [
            ("NP", "a course"), ("ROUTE-SUBJECT-RELATIVE", "that would just clear the island on the east"),
        ])
        self.assertEqual(self.spans(route.children[-1].children, text), [
            ("WH-PRONOUN", "that"), ("MODAL", "would"), ("DEGREE", "just"),
            ("V", "clear"), ("NP", "the island"), ("PP", "on the east"),
        ])

    def test_case_477_places_degree_time_and_location_on_distinct_heads(self):
        case = select_cases(500)[0][477]
        _, lattice, result = self.parse(case)
        self.assertIsNotNone(self.coordination(result))
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].surface, graph.nodes[r.target].surface)
                 for r in graph.relations}
        required = {
            ("THEME", "laid", "HISPANIOLA"), ("AGENT", "sailed", "HISPANIOLA"),
            ("CONJUNCT", "laid", "sailed"), ("TIME", "sailed", "now"),
            ("RESULT", "laid", "nearer"), ("MEASURE", "nearer", "points"),
            ("LANDMARK", "nearer", "wind"), ("QUANTIFIER", "points", "couple"),
            ("THEME", "sailed", "course"), ("THEME", "clear", "course"),
            ("MODIFIER", "course", "clear"), ("MODALITY", "clear", "would"),
            ("DEGREE", "clear", "just"), ("AFFECTED", "clear", "island"),
            ("LOCATION", "clear", "on"), ("COMPLEMENT", "on", "east"),
        }
        self.assertTrue(required <= edges, required - edges)
        forbidden = {
            ("AGENT", "laid", "HISPANIOLA"), ("AGENT", "sailed", "now"),
            ("TIME", "laid", "now"), ("MEASURE", "laid", "points"), ("TIME", "clear", "just"),
            ("THEME", "clear", "HISPANIOLA"), ("MODIFIER", "island", "on"),
            ("LOCATION", "sailed", "on"),
        }
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_plural_with_overt_landmark_preposition(self):
        result = self.control(self.POSITIVE)
        self.assertTrue(result.completed, result.stats)
        host = self.coordination(result)
        self.assertIsNotNone(host)
        subject, passive, _, active = host.children
        self.assertEqual(subject.features.as_dict()["number"], "plural")
        self.assertEqual(passive.features.as_dict()["number"], "plural")
        self.assertEqual(active.features.as_dict()["number"], "plural")
        distance = passive.children[-1]
        self.assertEqual(self.spans(distance.children, self.POSITIVE), [
            ("SPATIAL-MEASURE", "two yards"), ("ADV", "closer"), ("PREP", "to"), ("NP", "the dock"),
        ])

    def test_wrong_voice_agreement_measure_and_relative_do_not_get_this_analysis(self):
        for old, new in (
            ("boats were", "boats was"), ("were pushed", "were push"),
            ("were pushed", "were ran"), ("two yards", "two yard"),
            ("closer to", "closer from"), ("then followed", "then follow"),
            ("then followed", "then she followed"),
            ("that could almost skirt", "that she could almost skirt"),
            ("could almost skirt", "could almost skirted"),
            ("a channel", "him"), ("the reef on the west", "the reef from the west"),
        ):
            with self.subTest(replacement=new):
                self.assertIsNone(self.coordination(self.control(self.POSITIVE.replace(old, new))))


class PairedClauseSupplementTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    CONTROL = ("These roads, furthermore, were quiet and dry, and that, beneath the trees, "
               "was a real comfort to the visitors.")

    def test_case_496_keeps_two_finite_clauses_and_separate_source_governors(self):
        case = select_cases(500)[0][496]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "238d6ed29a444f6d")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (PAIRED_SUPPLEMENTS_ROOT, 0, len(text)))
        first, comma, and_, second, stop = root.children
        self.assertEqual(self.spans((first, second), text), [
            ("CLAUSE", "The air, besides, was fresh and stirring"),
            ("CLAUSE", "this, under the sheer sunbeams, was a wonderful refreshment to our senses"),
        ])
        self.assertEqual(self.spans(first.children, text), [
            ("NP", "The air"), ("COMMA", ","), ("ADV", "besides"), ("COMMA", ","),
            ("COPULA", "was"), ("ADJP", "fresh and stirring"),
        ])
        self.assertEqual(self.spans(first.children[-1].children, text),
                         [("ADJ", "fresh"), ("COORD", "and"), ("ADJ", "stirring")])
        self.assertEqual(self.spans(second.children, text), [
            ("PRONOUN", "this"), ("COMMA", ","), ("PP", "under the sheer sunbeams"), ("COMMA", ","),
            ("COPULA", "was"), ("NP", "a wonderful refreshment to our senses"),
        ])
        self.assertEqual(self.spans(second.children[-1].children, text),
                         [("NP", "a wonderful refreshment"), ("PP", "to our senses")])
        self.assertEqual(self.spans((comma, and_, stop), text), [("COMMA", ","), ("COORD", "and"), ("SPEECH-STOP", ".")])
        by_id = {c["id"]: c for c in pre.structural_constituents}
        for supplement, governor, expected in (("csd", "cs0", "besides"), ("csp", "cs1", "under the sheer sunbeams")):
            self.assertEqual(by_id[supplement]["governor"], governor)
            self.assertEqual(pre.source_component(supplement), expected)

    def test_case_496_links_this_to_first_predication_and_localizes_both_supplements(self):
        case = select_cases(500)[0][496]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, PAIRED_SUPPLEMENTS_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].span[0], graph.nodes[r.target].span[0])
                 for r in graph.relations}
        left, right = text.index("was"), text.rindex("was")
        discourse, place, anaphor = (text.index(w) for w in ("besides", "under", "this"))
        attr, affected, senses = (text.index(w) for w in ("refreshment", "to our", "senses"))
        required = {
            ("CONJUNCT", left, right), ("CONTENT", anaphor, left),
            ("DISCOURSE", left, discourse), ("CIRCUMSTANCE", right, place),
            ("THEME", left, text.index("air")), ("THEME", right, anaphor),
            ("ATTRIBUTE", left, text.index("fresh")), ("ATTRIBUTE", left, text.index("stirring")),
            ("ATTRIBUTE", right, attr), ("MODIFIER", attr, affected),
            ("COMPLEMENT", affected, senses), ("COMPLEMENT", place, text.index("sunbeams")),
        }
        forbidden = {
            ("CONTENT", anaphor, text.index("air")), ("CONTENT", anaphor, right),
            ("DISCOURSE", right, discourse), ("CIRCUMSTANCE", left, place),
            ("MODIFIER", anaphor, place), ("MODIFIER", right, affected),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_plural_subject_does_not_share_second_copulas_agreement(self):
        result = self.control(self.CONTROL)
        self.assertTrue(result.completed, result.stats)
        root = result.best()
        self.assertEqual(root.rule_id, PAIRED_SUPPLEMENTS_ROOT)
        first, _, _, second, _ = root.children
        self.assertEqual(first.children[-2].features.as_dict()["number"], "plural")
        self.assertEqual(second.children[-2].features.as_dict()["number"], "singular")
        self.assertEqual(self.spans(second.children[:3:2], self.CONTROL),
                         [("PRONOUN", "that"), ("PP", "beneath the trees")])

    def test_nonparallel_and_incomplete_variants_do_not_get_the_scoped_tree(self):
        for old, new in (
            ("These roads, furthermore, were", "They, furthermore, was"),
            ("These roads, furthermore, were", "These roads, furthermore, was"),
            ("trees, was", "trees, were"),
            ("quiet and dry", "quiet and danced"),
            ("and that,", "and the roads,"),
            ("and that,", "and that"),
            ("beneath the trees,", "beneath visited,"),
            ("furthermore,", "rapidly,"),
            ("to the visitors", "to arrive"),
        ):
            with self.subTest(replacement=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != PAIRED_SUPPLEMENTS_ROOT)


class CoordinatedGerundEffectTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("The sound of the strange and beautiful in music had certainly often the effect of "
               "calming her nerves and causing her to ignore the daily worries of work.")

    def test_case_358_preserves_both_gerunds_and_local_control(self):
        case = select_cases(500)[0][358]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "6ba22d6151fcb22c")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (GERUND_EFFECT_ROOT, 0, len(text)))
        subject, have, stance, frequency, effect, stop = root.children
        self.assertEqual(self.spans((have, stance, frequency), text),
                         [("V", "had"), ("ADV", "indeed"), ("ADV", "always")])
        self.assertEqual(self.spans(subject.children, text), [
            ("NP", "The sight"), ("PREP", "of"), ("NP", "the awful and majestic in nature"),
        ])
        self.assertEqual(self.spans(subject.children[-1].children, text), [
            ("DET", "the"), ("ADJ", "awful"), ("COORD", "and"), ("ADJ", "majestic"),
            ("PREP", "in"), ("N", "nature"),
        ])
        self.assertEqual(self.spans(effect.children, text), [
            ("NP", "the effect"), ("PREP", "of"), ("GERUND-CLAUSE", "solemnizing my mind"),
            ("COORD", "and"), ("GERUND-CLAUSE", "causing me to forget the passing cares of life"),
        ])
        self.assertEqual(self.spans(effect.children[2].children, text),
                         [("V", "solemnizing"), ("NP", "my mind")])
        self.assertEqual(self.spans(effect.children[-1].children, text), [
            ("V", "causing"), ("PRONOUN", "me"), ("INF-CLAUSE", "to forget the passing cares of life"),
        ])
        self.assertEqual(self.spans(effect.children[-1].children[-1].children, text), [
            ("TO", "to"), ("V", "forget"), ("NP", "the passing cares of life"),
        ])

    def test_case_358_links_the_passage_to_me_and_not_mind(self):
        case = select_cases(500)[0][358]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, GERUND_EFFECT_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("THEME", p("had"), p("sight")), ("FREQUENCY", p("had"), p("always")),
            ("STANCE", p("had"), p("indeed")),
            ("CONTENT", p("effect"), p("solemnizing")), ("CONTENT", p("effect"), p("causing")),
            ("CONJUNCT", p("solemnizing"), p("causing")), ("AFFECTED", p("solemnizing"), p("mind")),
            ("AFFECTED", p("causing"), p("me to")), ("AGENT", p("forget"), p("me to")),
            ("THEME", p("forget"), p("cares")), ("MODIFIER", p("cares"), p("passing")),
            ("COMPLEMENT", p("cares"), p("life")),
        }
        forbidden = {
            ("AGENT", p("forget"), p("mind")), ("AGENT", p("forget"), p("sight")),
            ("CONTENT", p("solemnizing"), p("forget")), ("FREQUENCY", p("causing"), p("always")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_gerunds_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, GERUND_EFFECT_ROOT)
        for old, new in (
            ("strange and", "strange or"), ("music had", "music have"),
            ("effect of", "effect with"), ("of calming", "of calmed"),
            ("and causing", "and caused"), ("causing her", "causing she"),
            ("to ignore", "to ignored"), ("worries of", "worries on"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != GERUND_EFFECT_ROOT)


class PassivePerfectExtrapositionTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = "Then our requests were agreed to, and it might, surely, have been a mistake to object."

    def test_case_319_keeps_the_stranded_passive_and_modal_perfect(self):
        case = select_cases(500)[0][319]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "7ee87a8a9ac10b1f")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (PASSIVE_EXTRAPOSITION_ROOT, 0, len(text)))
        first, comma, and_, second, stop = root.children
        self.assertEqual(self.spans((comma, and_, stop), text),
                         [("COMMA", ","), ("COORD", "and"), ("SPEECH-STOP", ".")])
        self.assertEqual(first.features.as_dict()["voice"], "passive")
        self.assertEqual(self.spans(first.children, text), [
            ("ADV", "Now"), ("NP", "my desires"), ("AUX-BE", "were"), ("V", "complied"), ("PREP", "with"),
        ])
        self.assertEqual(self.spans(second.children, text), [
            ("EXTRAPOSITION-IT", "it"), ("MODAL", "would"), ("STANCE-SUPPLEMENT", ", indeed,"),
            ("VP-NP", "have been folly to repent"),
        ])
        self.assertEqual(self.spans(second.children[2].children, text),
                         [("COMMA", ","), ("ADV", "indeed"), ("COMMA", ",")])
        self.assertEqual(self.spans(second.children[-1].children, text), [
            ("HAVE", "have"), ("COPULA", "been"), ("NP", "folly"), ("INF-CLAUSE", "to repent"),
        ])

    def test_case_319_distinguishes_evaluated_action_and_preposition_object(self):
        case = select_cases(500)[0][319]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, PASSIVE_EXTRAPOSITION_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("COMPLEMENT", p("with"), p("desires")), ("AFFECTED", p("complied"), p("desires")),
            ("TIME", p("complied"), 0), ("VOICE", p("complied"), p("were")),
            ("CONJUNCT", p("complied"), p("been")), ("MODALITY", p("been"), p("would")),
            ("ASPECT", p("been"), p("have")), ("STANCE", p("been"), p("indeed")),
            ("ATTRIBUTE", p("been"), p("folly")), ("EXTRAPOSED_SUBJECT", p("been"), p("repent")),
        }
        forbidden = {("AGENT", p("repent"), p("it would")), ("STANCE", p("complied"), p("indeed")),
                     ("COMPLEMENT", p("with"), p("it would"))}
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_preposition_and_perfect_frames(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, PASSIVE_EXTRAPOSITION_ROOT)
        for old, new in (
            ("requests were", "requests was"), ("were agreed", "were agree"),
            ("agreed to", "agreed with"), ("and it", "and he"), ("might, surely,", "might surely"),
            ("have been", "had been"), ("have been", "have be"), ("to object", "to objected"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != PASSIVE_EXTRAPOSITION_ROOT)


class SubjectQuestionAbilityTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = "Who would stop a climber capable of crossing the rising ridges of Mount Rainier?"

    def test_case_294_keeps_the_subject_question_and_nominal_internal_gerund(self):
        case = select_cases(500)[0][294]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "d656e31fd97d4e08")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (QUESTION_ABILITY_ROOT, 0, len(text)))
        self.assertEqual(root.features.as_dict()["stype"], "question")
        self.assertEqual(self.spans(root.children[:3], text),
                         [("WH-PRONOUN", "Who"), ("MODAL", "could"), ("V", "arrest")])
        obj = root.children[3]
        self.assertEqual(self.spans(obj.children, text), [
            ("NP", "a creature"), ("ADJP", "capable of scaling the overhanging sides of Mont Saleve"),
        ])
        self.assertEqual(self.spans(obj.children[-1].children, text), [
            ("ADJ", "capable"), ("PREP", "of"), ("GERUND-CLAUSE", "scaling the overhanging sides of Mont Saleve"),
        ])
        terrain = obj.children[-1].children[-1].children[-1]
        self.assertEqual(self.spans(terrain.children, text), [
            ("DET", "the"), ("V", "overhanging"), ("N", "sides"), ("PREP", "of"), ("TOPONYM", "Mont Saleve"),
        ])

    def test_case_294_uses_the_creature_as_scaling_agent(self):
        case = select_cases(500)[0][294]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, QUESTION_ABILITY_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("AGENT", p("arrest"), 0), ("AFFECTED", p("arrest"), p("creature")),
            ("MODALITY", p("arrest"), p("could")), ("MODIFIER", p("creature"), p("capable")),
            ("CONTENT", p("capable"), p("scaling")), ("AGENT", p("scaling"), p("creature")),
            ("AFFECTED", p("scaling"), p("sides")), ("MODIFIER", p("sides"), p("overhanging")),
            ("COMPLEMENT", p("sides"), p("Saleve")),
        }
        forbidden = {
            ("AGENT", p("scaling"), 0), ("AGENT", p("arrest"), p("creature")),
            ("MODIFIER", p("creature"), p("Saleve")), ("AFFECTED", p("arrest"), p("sides")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_subject_questions_and_near_misses(self):
        for text in (self.CONTROL, "Who can catch an animal capable of climbing the sloping walls of Mount Royal?"):
            self.assertEqual(self.control(text).best().rule_id, QUESTION_ABILITY_ROOT)
        for old, new in (
            ("Who would", "Whom would"), ("would stop", "would stopped"),
            ("capable of", "capable for"), ("of crossing", "of crossed"),
            ("rising ridges", "rise ridges"), ("Mount Rainier", "mount Rainier"),
            ("would stop", "would sleep"), ("Rainier?", "Rainier."),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != QUESTION_ABILITY_ROOT)


class CausalPostureResponseTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("The impact was quite remarkable; for upon first reading it, "
               "Dr. Brown stood perfectly silent, and unable to speak a word.")

    def test_case_249_has_a_causal_clause_and_local_coordinated_adjectives(self):
        case = select_cases(500)[0][249]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "35097475da3bca83")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (CAUSAL_POSTURE_ROOT, 0, len(text)))
        assessment, semi, cause, reaction, stop = root.children
        self.assertEqual(self.spans((semi, cause, stop), text),
                         [("SEMICOLON", ";"), ("COORD", "for"), ("SPEECH-STOP", ".")])
        self.assertEqual(self.spans(assessment.children, text),
                         [("NP", "Its effect"), ("COPULA", "was"), ("ADJP", "most extraordinary")])
        self.assertEqual(self.spans(reaction.children, text), [
            ("TEMPORAL-PP", "on first hearing it"), ("COMMA", ","), ("NP", "Mrs. Bennet"),
            ("V", "sat"), ("ADJP", "quite still, and unable to utter a syllable"),
        ])
        self.assertEqual(self.spans(reaction.children[0].children, text), [
            ("PREP", "on"), ("ADV", "first"), ("V", "hearing"), ("PRONOUN", "it"),
        ])
        self.assertEqual(self.spans(reaction.children[-1].children, text), [
            ("ADJP", "quite still"), ("COMMA", ","), ("COORD", "and"), ("ADJP", "unable to utter a syllable"),
        ])
        self.assertEqual(self.spans(reaction.children[-1].children[-1].children, text),
                         [("ADJ", "unable"), ("INF-CLAUSE", "to utter a syllable")])

    def test_case_249_semantics_do_not_assert_that_a_syllable_was_uttered(self):
        case = select_cases(500)[0][249]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, CAUSAL_POSTURE_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("CAUSE", p("was"), p("sat")), ("TIME", p("sat"), p("hearing")),
            ("TIME", p("hearing"), p("first")), ("AGENT", p("hearing"), p("Bennet")),
            ("DEPICTIVE", p("Bennet"), p("still")), ("DEPICTIVE", p("Bennet"), p("unable")),
            ("CONJUNCT", p("still"), p("unable")), ("CONTENT", p("unable"), p("utter")),
            ("THEME", p("utter"), p("syllable")), ("AGENT", p("utter"), p("Bennet")),
        }
        forbidden = {
            ("CONJUNCT", p("sat"), p("utter")), ("CAUSE", p("was"), p("utter")),
            ("TIME", p("was"), p("hearing")), ("CONTENT", p("still"), p("utter")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_causal_chain_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, CAUSAL_POSTURE_ROOT)
        for old, new in (
            ("impact was", "impact were"), ("remarkable; for", "remarkable; and"),
            ("first reading", "first read"), ("reading it,", "reading it"),
            ("stood perfectly", "stood perfect"), ("perfectly silent", "perfectly manager"),
            ("unable to speak", "unable to spoke"), ("unable to speak", "unable to sleep"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != CAUSAL_POSTURE_ROOT)


class ExclamativeInfinitiveContrastTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("That she should even talk to him was astonishing!—but to talk with such warmth, "
               "to enquire about his sister!")

    def test_case_238_preserves_the_clausal_subject_and_detached_details(self):
        case = select_cases(500)[0][238]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "08d6a393247bacc2")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (EXCLAMATIVE_CONTRAST_ROOT, 0, len(text)))
        main, exclamation, dash, but, details, stop = root.children
        self.assertEqual(self.spans((exclamation, dash, but, stop), text),
                         [("EXCL", "!"), ("DASH", "--"), ("COORD", "but"), ("SPEECH-STOP", "!")])
        self.assertEqual(self.spans(main.children, text), [
            ("THAT-CLAUSE", "That he should even speak to her"), ("COPULA", "was"), ("ADJ", "amazing"),
        ])
        subject = main.children[0]
        self.assertEqual(self.spans(subject.children, text), [
            ("COMP-THAT", "That"), ("NP", "he"), ("MODAL", "should"), ("ADV", "even"),
            ("V", "speak"), ("ADDRESS-PP", "to her"),
        ])
        self.assertEqual(self.spans(details.children, text), [
            ("INF-CLAUSE", "to speak with such civility"), ("COMMA", ","),
            ("INF-CLAUSE", "to inquire after her family"),
        ])
        self.assertEqual(self.spans(details.children[0].children[-1].children, text),
                         [("PREP", "with"), ("DEGREE", "such"), ("N", "civility")])
        self.assertEqual(self.spans(details.children[-1].children[-1].children, text),
                         [("PREP", "after"), ("NP", "her family")])

    def test_case_238_scope_and_elaboration_do_not_invent_a_second_matrix(self):
        case = select_cases(500)[0][238]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, EXCLAMATIVE_CONTRAST_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        first, second = p("speak to"), p("speak with")
        required = {
            ("THEME", p("was"), first), ("ATTRIBUTE", p("was"), p("amazing")),
            ("FOCUS", first, p("even")), ("RECIPIENT", first, p("her was")),
            ("CONTRAST", p("was"), second), ("ELABORATION", first, second),
            ("MANNER", second, p("civility")), ("DEGREE", p("civility"), p("such")),
            ("ELABORATION", second, p("inquire")), ("TOPIC", p("inquire"), p("family")),
            ("AGENT", p("inquire"), p("he should")),
        }
        forbidden = {
            ("TOPIC", second, p("family")), ("MANNER", first, p("civility")),
            ("TIME", p("inquire"), p("after")), ("THEME", p("was"), p("he should")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_exclamation_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, EXCLAMATIVE_CONTRAST_ROOT)
        for old, new in (
            ("she should", "her should"), ("should even talk", "should even talked"),
            ("was astonishing", "were astonishing"), ("!—but", "!—and"),
            ("to talk with", "to write with"), ("with such", "with herself"),
            ("to enquire", "to enquired"), ("enquire about", "walk about"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EXCLAMATIVE_CONTRAST_ROOT)


class ModalContextFreeRelativeTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("But, possibly she might not in his sister’s presence "
               "be what she was before his mother and father.")

    def test_case_213_keeps_the_two_social_settings_separate(self):
        case = select_cases(500)[0][213]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "48e79a37d0f3c544")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (MODAL_CONTEXT_ROOT, 0, len(text)))
        self.assertEqual(self.spans(root.children[:4], text),
                         [("COORD", "But"), ("COMMA", ","), ("ADV", "perhaps"), ("NP", "he")])
        vp = root.children[4]
        self.assertEqual(self.spans(vp.children[:2], text), [("MODAL", "could"), ("NEG", "not")])
        copular = vp.children[-1]
        self.assertEqual(self.spans(copular.children, text), [
            ("PRESENCE-PP", "in her mother's presence"), ("COPULA", "be"),
            ("NP", "what he was before her uncle and aunt"),
        ])
        relative = copular.children[-1]
        self.assertEqual(relative.features.as_dict()["gap"], "predicative")
        self.assertEqual(self.spans(relative.children, text), [
            ("WH-NOM", "what"), ("NP", "he"), ("COPULA", "was"), ("AUDIENCE-PP", "before her uncle and aunt"),
        ])
        self.assertEqual(self.spans(relative.children[-1].children[-1].children, text), [
            ("POSS", "her"), ("N", "uncle"), ("COORD", "and"), ("N", "aunt"),
        ])

    def test_case_213_scopes_modal_negation_and_internal_audience(self):
        case = select_cases(500)[0][213]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, MODAL_CONTEXT_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("CIRCUMSTANCE", p("be what"), p("in her")), ("CIRCUMSTANCE", p("was"), p("before")),
            ("ATTRIBUTE", p("be what"), p("what")), ("ATTRIBUTE", p("was"), p("what")),
            ("THEME", p("was"), p("he was")), ("MODALITY", p("be what"), p("could")),
            ("NEGATION", p("could"), p("not")), ("STANCE", p("be what"), p("perhaps")),
            ("POSSESSOR", p("uncle"), p("her uncle")), ("POSSESSOR", p("aunt"), p("her uncle")),
        }
        forbidden = {
            ("CIRCUMSTANCE", p("be what"), p("before")), ("CIRCUMSTANCE", p("was"), p("in her")),
            ("STANCE", p("was"), p("perhaps")), ("TIME", p("was"), p("before")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_settings_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, MODAL_CONTEXT_ROOT)
        for old, new in (
            ("But,", "And,"), ("she might", "her might"), ("might not", "might"),
            ("presence be", "presence was"), ("what she", "that she"), ("she was", "she were"),
            ("before his", "after his"), ("mother and", "mother or"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != MODAL_CONTEXT_ROOT)


class IntegratedRoleAppositionTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = "Helen the daughter of Dr. Brown was a familiar sight."

    def test_case_166_preserves_the_role_and_degree_attribute(self):
        case = select_cases(500)[0][166]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "fea088254f0ae7bd")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (ROLE_APPOSITION_ROOT, 0, len(text)))
        subject, copula, attribute, stop = root.children
        self.assertEqual(self.spans((copula, stop), text), [("COPULA", "was"), ("SPEECH-STOP", "!")])
        self.assertEqual(self.spans(subject.children, text),
                         [("PROPER-NOUN", "Charlotte"), ("ROLE-NP", "the wife of Mr. Collins")])
        self.assertEqual(self.spans(subject.children[1].children, text), [
            ("DET", "the"), ("N", "wife"), ("PREP", "of"), ("PARTNER-NP", "Mr. Collins"),
        ])
        self.assertEqual(self.spans(subject.children[1].children[-1].children, text),
                         [("TITLE", "Mr"), ("ABBREVIATION-STOP", "."), ("PROPER-NOUN", "Collins")])
        self.assertEqual(self.spans(attribute.children, text),
                         [("DET", "a"), ("ADJP", "most humiliating"), ("N", "picture")])
        self.assertEqual(self.spans(attribute.children[1].children, text),
                         [("ADV", "most"), ("ADJ", "humiliating")])

    def test_case_166_predicates_the_picture_of_charlotte_not_collins(self):
        case = select_cases(500)[0][166]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, ROLE_APPOSITION_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("APPOSITION", 0, p("wife")), ("COMPLEMENT", p("wife"), p("Collins")),
            ("THEME", p("was"), 0), ("ATTRIBUTE", p("was"), p("picture")),
            ("MODIFIER", p("picture"), p("humiliating")), ("DEGREE", p("humiliating"), p("most")),
        }
        forbidden = {("THEME", p("was"), p("Collins")), ("MODIFIER", p("picture"), p("most"))}
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_appositions_and_near_misses(self):
        for text in (self.CONTROL, "Robert the brother of Alice was an unlikely ally."):
            self.assertEqual(self.control(text).best().rule_id, ROLE_APPOSITION_ROOT)
        for old, new in (
            ("daughter of", "daughter from"), ("daughter of", "book of"), ("the daughter", "a daughter"),
            ("Brown was", "Brown were"), ("a familiar sight", "many familiar sights"), ("Brown", "brown"),
            ("Helen the", "Helen, the"), ("familiar sight", "quietly sight"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != ROLE_APPOSITION_ROOT)


class ConditionalEllipsisSeriesTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("If that were so, her effort was nothing; her duty to them unmet; "
               "and every task she had shrunk from, she was daily repeating.")

    def test_case_124_preserves_three_consequences_and_distinct_gaps(self):
        case = select_cases(500)[0][124]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "e5f30c6dd18d4da6")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (CONDITIONAL_SERIES_ROOT, 0, len(text)))
        condition, _, series, _ = root.children
        self.assertEqual(condition.features.as_dict()["irrealis"], "true")
        self.assertEqual(self.spans(condition.children, text), [
            ("CONJ", "If"), ("PRONOUN", "that"), ("COPULA", "were"), ("ADV", "so"),
        ])
        first, semi1, middle, semi2, coord, last = series.children
        self.assertEqual(self.spans((semi1, semi2, coord), text),
                         [("SEMICOLON", ";"), ("SEMICOLON", ";"), ("COORD", "and")])
        self.assertEqual(self.spans(first.children, text),
                         [("NP", "my sacrifice"), ("COPULA", "was"), ("PRONOUN", "nothing")])
        self.assertEqual(self.spans(middle.children, text),
                         [("NP", "my plainest obligation to her"), ("ADJ", "unfulfilled")])
        self.assertEqual(middle.features.as_dict()["ellipsis"], "copula")
        self.assertEqual(self.spans(middle.children[0].children, text),
                         [("NP", "my plainest obligation"), ("PREP", "to"), ("PRONOUN", "her")])
        topic, comma, subject, pred = last.children
        self.assertEqual(self.spans((comma, subject), text), [("COMMA", ","), ("NP", "I")])
        self.assertEqual(self.spans(topic.children, text),
                         [("NP", "every poor action"), ("REL-CLAUSE-OBJ", "I had shrunk from")])
        self.assertEqual(self.spans(topic.children[-1].children, text), [
            ("NP", "I"), ("HAVE", "had"), ("V", "shrunk"), ("PREP", "from"),
        ])
        self.assertEqual(pred.features.as_dict()["gap"], "object")
        self.assertEqual(self.spans(pred.children, text),
                         [("COPULA", "was"), ("ADV", "hourly"), ("V", "doing")])

    def test_case_124_condition_reaches_every_consequence(self):
        case = select_cases(500)[0][124]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, CONDITIONAL_SERIES_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("CONDITION", p("was nothing"), p("were")), ("CONDITION", p("unfulfilled"), p("were")),
            ("CONDITION", p("doing"), p("were")),
            ("ELLIPSIS_ANTECEDENT", p("unfulfilled"), p("was nothing")),
            ("ATTRIBUTE", p("obligation"), p("unfulfilled")), ("MODIFIER", p("action"), p("shrunk")),
            ("COMPLEMENT", p("from"), p("action")), ("AFFECTED", p("doing"), p("action")),
            ("TIME", p("doing"), p("hourly")), ("AGENT", p("doing"), p("I was")),
        }
        forbidden = {
            ("AFFECTED", p("shrunk"), p("action")), ("TIME", p("shrunk"), p("hourly")),
            ("CONDITION", p("shrunk"), p("were")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_ellipsis_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, CONDITIONAL_SERIES_ROOT)
        for old, new in (
            ("If that", "Because that"), ("were so", "are so"), ("effort was", "effort were"),
            ("unmet; and", "unmet and"), ("and every", "and some"), ("had shrunk", "had shrink"),
            ("shrunk from", "slept from"), ("from, she", "from, her"),
            ("she was daily", "she were daily"), ("daily repeating", "daily sleeping"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != CONDITIONAL_SERIES_ROOT)


class SharedComparativeReplyTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("Dr. Brown judged it prudent to warn either her colleague or their manager, "
               "with care, and replied, earlier than she had anticipated yesterday.")

    def test_case_122_preserves_shared_subject_and_reported_fragment(self):
        case = select_cases(500)[0][122]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "fb2158d6e71fe059")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (COMPARATIVE_REPLY_ROOT, 0, len(text)))
        speaker, evaluation, coord, reply, end = root.children
        self.assertEqual(self.spans((speaker, coord, end), text),
                         [("NP", "Mr. Micawber"), ("COORD", "and"), ("SPEECH-STOP", ".")])
        self.assertEqual(self.spans(speaker.children, text),
                         [("TITLE", "Mr"), ("ABBREVIATION-STOP", "."), ("PROPER-NOUN", "Micawber")])
        self.assertEqual(self.spans(evaluation.children[:3], text),
                         [("V", "considered"), ("EXTRAPOSITION-IT", "it"), ("ADJ", "necessary")])
        prep = evaluation.children[-1]
        self.assertEqual(self.spans(prep.children, text), [
            ("TO", "to"), ("V", "prepare"), ("NP", "either my aunt or his wife"),
            ("COMMA", ","), ("PP", "by degrees"), ("COMMA", ","),
        ])
        self.assertEqual(self.spans(prep.children[2].children, text),
                         [("ADV", "either"), ("NP", "my aunt"), ("COORD", "or"), ("NP", "his wife")])
        self.assertEqual(self.spans(reply.children, text), [
            ("V", "said"), ("COMMA", ","), ("ADVP", "sooner than he had expected yesterday"),
        ])
        head, standard = reply.children[-1].children
        self.assertEqual(self.spans((head,), text), [("ADV", "sooner")])
        self.assertEqual(standard.features.as_dict()["ellipsis"], "true")
        self.assertEqual(self.spans(standard.children, text), [
            ("CONJ", "than"), ("NP", "he"), ("HAVE", "had"), ("V", "expected"), ("ADV", "yesterday"),
        ])

    def test_case_122_edges_mark_an_answer_and_an_unresolved_alternative(self):
        case = select_cases(500)[0][122]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, COMPARATIVE_REPLY_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("AGENT", p("considered"), p("Micawber")), ("AGENT", p("said"), p("Micawber")),
            ("AGENT", p("prepare"), p("Micawber")), ("AFFECTED", p("prepare"), p("either")),
            ("ALTERNATIVE", p("either"), p("aunt")), ("ALTERNATIVE", p("either"), p("wife")),
            ("MANNER", p("prepare"), p("by degrees")), ("REPORTED_CONTENT", p("said"), p("sooner")),
            ("COMPARISON", p("sooner"), p("expected")), ("TIME", p("expected"), p("yesterday")),
        }
        forbidden = {
            ("TIME", p("said"), p("sooner")), ("TIME", p("said"), p("yesterday")),
            ("AFFECTED", p("prepare"), p("aunt")), ("AFFECTED", p("prepare"), p("wife")),
            ("MANNER", p("said"), p("by degrees")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_reply_and_near_misses(self):
        self.assertEqual(self.control(self.CONTROL).best().rule_id, COMPARATIVE_REPLY_ROOT)
        for old, new in (
            ("judged it", "judged him"), ("prudent to", "blue to"), ("to warn", "to warned"),
            ("or their", "and their"), ("manager, with", "manager with"), ("care, and", "care and"),
            ("and replied", "and slept"), ("replied, earlier", "replied earlier"),
            ("she had", "her had"), ("had anticipated", "had anticipate"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != COMPARATIVE_REPLY_ROOT)


class CopularResolutionContentTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("This requirement is, that she must make a pledge to give "
               "no more grants of her estate, or anything else, to Alice.")

    def test_case_111_preserves_the_three_attached_content_levels(self):
        case = select_cases(500)[0][111]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "a7d236f294fefa98")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (RESOLUTION_CONTENT_ROOT, 0, len(text)))
        self.assertEqual(self.spans(root.children[:3], text),
                         [("NP", "That condition"), ("COPULA", "was"), ("COMMA", ",")])
        content = root.children[3]
        self.assertEqual(self.spans(content.children[:4], text),
                         [("COMP-THAT", "that"), ("NP", "he"), ("MODAL", "should"), ("V", "make")])
        decision = content.children[-1]
        self.assertEqual(self.spans(decision.children[:1], text), [("NP", "a solemn resolution")])
        act = decision.children[-1]
        self.assertEqual(self.spans(act.children, text), [
            ("TO", "to"), ("V", "grant"), ("NP", "no more loans of his name, or anything else,"),
            ("RECIPIENT-PP", "to Mr. Micawber"),
        ])
        themes = act.children[2]
        self.assertEqual(self.spans(themes.children, text), [
            ("NP", "no more loans of his name"), ("COMMA", ","), ("COORD", "or"),
            ("NP", "anything else"), ("COMMA", ","),
        ])
        self.assertEqual(self.spans(themes.children[0].children, text), [
            ("DET", "no"), ("DEGREE", "more"), ("N", "loans"), ("PREP", "of"), ("NP", "his name"),
        ])
        self.assertEqual(self.spans(themes.children[3].children, text),
                         [("INDEF-PRONOUN", "anything"), ("ADJ", "else")])
        self.assertEqual(self.spans(act.children[-1].children[-1].children, text),
                         [("TITLE", "Mr"), ("ABBREVIATION-STOP", "."), ("PROPER-NOUN", "Micawber")])

    def test_case_111_scopes_the_nominal_content_recipient_and_negation(self):
        case = select_cases(500)[0][111]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, RESOLUTION_CONTENT_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("CONTENT", p("condition"), p("make")), ("CONTENT", p("resolution"), p("grant")),
            ("MODALITY", p("make"), p("should")), ("AGENT", p("grant"), p("he should")),
            ("RECIPIENT", p("grant"), p("Micawber")), ("THEME", p("grant"), p("loans")),
            ("QUANTITY", p("loans"), p("more")), ("NEGATION", p("more"), p("no more")),
            ("NEGATION", p("anything"), p("no more")), ("ALTERNATIVE", p("loans"), p("anything")),
            ("MODIFIER", p("anything"), p("else")), ("COMPLEMENT", p("loans"), p("name")),
        }
        forbidden = {
            ("CONTENT", p("make"), p("grant")), ("RECIPIENT", p("make"), p("Micawber")),
            ("RECIPIENT", p("loans"), p("Micawber")), ("NEGATION", p("make"), p("no more")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_nominal_and_transfer_frames_and_near_misses(self):
        for source in (self.CONTROL,
                       "That stipulation was, that they should make a firm commitment to offer "
                       "no more advances of their funds, or anything else, to Dr. Brown."):
            self.assertEqual(self.control(source).best().rule_id, RESOLUTION_CONTENT_ROOT)
        for old, new in (
            ("requirement is", "requirement are"), ("is, that", "is, which"),
            ("is, that", "is that"), ("she must", "her must"),
            ("must make", "must made"), ("a pledge", "a chair"), ("give no", "sleep no"),
            ("more grants", "more grant"), ("or anything else", "and anything else"),
            ("else, to", "else to"), ("to Alice", "for Alice"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != RESOLUTION_CONTENT_ROOT)


class ComparativeContentCoordinationTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("They understood no more than we did, where she was heading, "
               "but they believed she had a route mapped out in her mind.")

    def test_case_110_separates_the_comparison_question_and_conjecture(self):
        case = select_cases(500)[0][110]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "c31971a0a1ada1d9")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (COMPARATIVE_CONTENT_ROOT, 0, len(text)))
        knowledge, comma, coordinator, thought, stop = root.children
        self.assertEqual(self.spans((comma, coordinator, stop), text),
                         [("COMMA", ","), ("COORD", "but"), ("SPEECH-STOP", ".")])
        self.assertEqual(self.spans(knowledge.children, text), [
            ("NP", "She"), ("V", "knew"), ("DEGREE-COMPARISON", "no more than I did"),
            ("COMMA", ","), ("WH-CLAUSE", "where he was going"),
        ])
        standard = knowledge.children[2].children[-1]
        self.assertEqual(self.spans(standard.children, text),
                         [("CONJ", "than"), ("NP", "I"), ("AUX", "did")])
        self.assertEqual(standard.features.as_dict()["ellipsis"], "true")
        self.assertEqual(self.spans(knowledge.children[-1].children, text), [
            ("WH-NOM", "where"), ("NP", "he"), ("COPULA", "was"), ("V", "going"),
        ])
        have = thought.children[-1]
        self.assertEqual(self.spans(have.children, text), [
            ("NP", "he"), ("V", "had"), ("NP", "some project"),
            ("RESULT-STATE", "shaped out in his mind"),
        ])
        state = have.children[-1]
        self.assertEqual(self.spans(state.children, text),
                         [("V", "shaped"), ("PARTICLE", "out"), ("MENTAL-LOCATION", "in his mind")])
        self.assertEqual(state.features.as_dict()["voice"], "passive")
        parts = {part["id"]: part for part in pre.structural_constituents}
        self.assertEqual([parts[key]["governor"] for key in ("kc1", "kc2", "kc3")], ["kc0", "kc0", "s0"])

    def test_case_110_semantic_scope_preserves_the_ellipsis_and_local_result(self):
        case = select_cases(500)[0][110]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, COMPARATIVE_CONTENT_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("NEGATION", p("more"), p("no more")), ("DEGREE", p("knew"), p("more")),
            ("COMPARISON", p("more"), p("did")), ("ELLIPSIS_ANTECEDENT", p("did"), p("knew")),
            ("CONTENT", p("knew"), p("going")), ("GOAL", p("going"), p("where")),
            ("CONTRAST", p("knew"), p("thought")), ("CONTENT", p("thought"), p("had")),
            ("THEME", p("had"), p("project")), ("RESULT", p("project"), p("shaped")),
            ("PARTICLE", p("shaped"), p("out in")), ("LOCATION", p("shaped"), p("in his")),
            ("POSSESSOR", p("mind"), p("his")),
        }
        forbidden = {
            ("NEGATION", p("knew"), p("no more")), ("CONTENT", p("did"), p("going")),
            ("CONTENT", p("thought"), p("going")), ("AGENT", p("shaped"), p("he had")),
            ("LOCATION", p("had"), p("in his")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_lexical_frames_and_invalid_near_misses(self):
        result = self.control(self.CONTROL)
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id, COMPARATIVE_CONTENT_ROOT)
        for old, new in (
            ("we did", "we does"), ("she was", "she were"), ("she had", "she have"),
            ("did, where", "did where"), ("where she", "that she"),
            ("she was heading", "she was knowing"), ("but they", "and they"),
            ("they believed", "they slept"), ("mapped out", "mapping out"),
            ("mapped out", "mapped up"), ("mapped out", "slept out"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != COMPARATIVE_CONTENT_ROOT)


class ExtraposedObjectRelativeTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans
    CONTROL = ("They deemed it wise, then, to show him everything they found; "
               "which she described in detail.")

    def test_case_87_preserves_the_evaluation_and_both_object_gaps(self):
        case = select_cases(500)[0][87]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "1d4f2bfad396bcbd")
        prepared, lattice, result = self.parse(case)
        self.assertEqual((prepared.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (EXTRAPOSED_OBJECT_ROOT, 0, len(text)))
        matrix, semicolon, relative, stop = root.children
        self.assertEqual(self.spans((semicolon, stop), text), [("SEMICOLON", ";"), ("SPEECH-STOP", ".")])
        self.assertEqual(self.spans(matrix.children[:2], text), [("NP", "We"), ("V", "judged")])
        quality = matrix.children[-1]
        self.assertEqual(self.spans(quality.children, text), [
            ("EXTRAPOSITION-IT", "it"), ("ADJ", "expedient"),
            ("TEMPORAL-SUPPLEMENT", ", now,"), ("INF-CLAUSE", "to tell her all we knew"),
        ])
        self.assertEqual(self.spans(quality.children[2].children, text),
                         [("COMMA", ","), ("ADV", "now"), ("COMMA", ",")])
        transfer = quality.children[-1]
        self.assertEqual(self.spans(transfer.children, text),
                         [("TO", "to"), ("V", "tell"), ("PRONOUN", "her"), ("NP", "all we knew")])
        theme = transfer.children[-1]
        self.assertEqual(self.spans(theme.children, text),
                         [("PRONOUN", "all"), ("REL-CLAUSE-OBJ", "we knew")])
        zero_relative = theme.children[-1]
        self.assertEqual(self.spans(zero_relative.children, text), [("NP", "we"), ("VP-GAP", "knew")])
        self.assertEqual(zero_relative.children[-1].features.as_dict()["gap"], "object")
        self.assertEqual(self.spans(relative.children, text), [
            ("WH-REL-OBL", "which"), ("NP", "I"), ("VP-GAP", "recounted at length"),
        ])
        report = relative.children[-1]
        self.assertEqual(report.features.as_dict()["gap"], "object")
        self.assertEqual(self.spans(report.children, text), [("V", "recounted"), ("PP", "at length")])
        by_id = {node["id"]: node for node in prepared.structural_constituents}
        self.assertEqual(by_id["s1"]["governor"], "s0")
        self.assertEqual(prepared.source_component("s1"), "which I recounted at length.")

    def test_case_87_semantics_distinguish_control_recipient_and_reprise(self):
        case = select_cases(500)[0][87]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, EXTRAPOSED_OBJECT_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(link.relation, graph.nodes[link.source].span[0], graph.nodes[link.target].span[0])
                 for link in graph.relations}
        p = text.index
        required = {
            ("AGENT", p("judged"), 0), ("CONTENT", p("judged"), p("tell")),
            ("AGENT", p("tell"), 0), ("ATTRIBUTE", p("tell"), p("expedient")),
            ("TIME", p("judged"), p("now")), ("RECIPIENT", p("tell"), p("her all")),
            ("THEME", p("tell"), p("all")), ("AGENT", p("knew"), p("we knew")),
            ("THEME", p("knew"), p("all")), ("MODIFIER", p("all"), p("knew")),
            ("SUPPLEMENT", p("judged"), p("recounted")), ("AGENT", p("recounted"), p("I recounted")),
            ("AFFECTED", p("recounted"), p("which")), ("COREFERENCE", p("which"), p("all")),
            ("MANNER", p("recounted"), p("at length")),
        }
        forbidden = {
            ("AGENT", p("tell"), p("it expedient")), ("AGENT", p("tell"), p("her all")),
            ("THEME", p("tell"), p("her all")), ("COREFERENCE", p("which"), p("judged")),
            ("COREFERENCE", p("which"), p("her all")), ("TIME", p("knew"), p("now")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_evaluation_changes_all_major_lexical_heads(self):
        parsed = self.control(self.CONTROL)
        self.assertTrue(parsed.completed, parsed.stats)
        root = parsed.best()
        self.assertEqual(root.rule_id, EXTRAPOSED_OBJECT_ROOT)
        transfer = root.children[0].children[-1].children[-1]
        self.assertEqual(self.spans(transfer.children, self.CONTROL), [
            ("TO", "to"), ("V", "show"), ("PRONOUN", "him"), ("NP", "everything they found"),
        ])
        self.assertEqual(root.children[0].children[0].features.as_dict()["number"], "plural")

    def test_requires_the_overt_delimiters_and_licensed_lexical_frames(self):
        for old, new in (
            ("They deemed", "They deems"), ("it wise", "him wise"), ("wise, then,", "wise then,"),
            ("show him", "explained him"), ("show him", "show he"), ("show him", "sleep him"),
            ("they found", "they slept"), ("they found", "they discovers"),
            ("; which", "; who"), ("; which", "; and"), ("described in detail", "slept in detail"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EXTRAPOSED_OBJECT_ROOT)


class ExtraposedScalarContentTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    CONTROL = ("It is easy to imagine that those mountains so small to us, "
               "might be large to someone else.")

    def test_case_80_preserves_extraposition_and_the_historical_subject_pause(self):
        case = select_cases(500)[0][80]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "57dba5c2e4bb4629")
        pre, lattice, parsed = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, parsed.text), (text, text, text))
        self.assertTrue(parsed.completed, parsed.stats)
        self.assertFalse(parsed.stats["budget_exceeded"])
        self.assertFalse(parsed.stats["kbest_budget_exceeded"])
        root = parsed.best()
        self.assertEqual((root.rule_id, root.start, root.end), (EXTRAPOSED_SCALAR_ROOT, 0, len(text)))
        self.assertEqual(self.spans(root.children, text), [
            ("EXTRAPOSITION-IT", "It"), ("COPULA", "was"), ("ADJ", "difficult"),
            ("INF-CLAUSE", text[17:-1]), ("SPEECH-STOP", "."),
        ])
        infinitive = root.children[3]
        self.assertEqual(self.spans(infinitive.children, text),
                         [("TO", "to"), ("V", "believe"), ("THAT-CLAUSE", text[28:-1])])
        _, subject, comma, vp = infinitive.children[-1].children
        self.assertEqual(self.spans((subject, comma, vp), text), [
            ("NP", "a night so long to me"), ("COMMA", ","), ("VP", "could be short to anybody else"),
        ])
        self.assertEqual(self.spans(subject.children, text),
                         [("NP", "a night"), ("ADJP", "so long to me")])
        self.assertEqual(subject.features.as_dict()["person"], "3")
        self.assertEqual(self.spans(subject.children[1].children, text),
                         [("DEGREE", "so"), ("ADJP", "long to me")])
        self.assertEqual(self.spans(subject.children[1].children[1].children, text),
                         [("ADJ", "long"), ("PERSPECTIVE-PP", "to me")])
        self.assertEqual(self.spans(vp.children, text),
                         [("MODAL", "could"), ("COPULA", "be"), ("ADJP", "short to anybody else")])
        self.assertEqual(self.spans(vp.children[-1].children, text),
                         [("ADJ", "short"), ("PERSPECTIVE-PP", "to anybody else")])
        self.assertEqual(self.spans(vp.children[-1].children[-1].children[-1].children, text),
                         [("PRONOUN", "anybody"), ("ADJ", "else")])
        source = {node["id"]: node for node in pre.structural_constituents}
        for node, governor in (("xs0", "s0"), ("xs1", "xs0"), ("xs2", "xs1")):
            self.assertEqual(source[node]["governor"], governor)
        self.assertEqual(pre.source_component("xs2"), "a night so long to me")

    def test_case_80_semantic_edges_keep_the_two_perspectives_distinct(self):
        case = select_cases(500)[0][80]
        text = case["source_text"]
        _, lattice, result = self.parse(case)
        self.assertEqual(result.best().rule_id, EXTRAPOSED_SCALAR_ROOT)
        graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(rel.relation, graph.nodes[rel.source].span[0], graph.nodes[rel.target].span[0])
                 for rel in graph.relations}
        p = text.index
        expected = {
            ("EXTRAPOSED_SUBJECT", p("was"), p("believe")),
            ("ATTRIBUTE", p("was"), p("difficult")),
            ("CONTENT", p("believe"), p("be short")),
            ("THEME", p("be short"), p("night")),
            ("MODALITY", p("be short"), p("could")),
            ("MODIFIER", p("night"), p("long")),
            ("DEGREE", p("long"), p("so long")),
            ("PERSPECTIVE", p("long"), p("me,")),
            ("ATTRIBUTE", p("be short"), p("short")),
            ("PERSPECTIVE", p("short"), p("anybody")),
            ("MODIFIER", p("anybody"), p("else")),
        }
        forbidden = {
            ("PERSPECTIVE", p("short"), p("me,")),
            ("PERSPECTIVE", p("long"), p("anybody")),
            ("AGENT", p("believe"), 0),
        }
        self.assertTrue(expected <= edges, expected - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_plural_subject_with_and_without_the_comma(self):
        for text in (self.CONTROL, self.CONTROL.replace("us,", "us")):
            with self.subTest(source=text):
                parsed = self.control(text)
                self.assertTrue(parsed.completed, parsed.stats)
                self.assertEqual(parsed.best().rule_id, EXTRAPOSED_SCALAR_ROOT)
                content = parsed.best().children[3].children[-1]
                self.assertEqual(content.children[1].features.as_dict()["number"], "plural")
                self.assertEqual(content.children[-1].children[0].category, "MODAL")

    def test_extraposition_cannot_erase_valency_case_or_punctuation(self):
        for old, new in (
            ("It is", "It are"), ("It is", "This is"), ("easy to", "blue to"),
            ("imagine that", "sleep that"), ("us,", "we,"), ("us,", "us else,"),
            ("us,", "us;"), ("might be", "might was"), ("those mountains", "those mountain"),
        ):
            with self.subTest(contrast=new):
                best = self.control(self.CONTROL.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EXTRAPOSED_SCALAR_ROOT)


class DegreeConcessiveAttitudeTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    INTENSIFIED = ("However much alarmed she might be, I was aware that they had no authority "
                   "to demand compliance with the new rules.")
    SIMPLE = ("However worried they may be, they are certain that we have no permission "
              "to require cooperation with the committee.")

    def test_case_74_uses_a_preposed_attribute_and_nested_content(self):
        case = select_cases(500)[0][74]
        text = case["source_text"]
        self.assertEqual(sha256(text.encode()).hexdigest()[:16], "a4b638e307998ebb")
        pre, lattice, result = self.parse(case)
        self.assertEqual((pre.analysis_text, lattice.text, result.text), (text, text, text))
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual((root.rule_id, root.start, root.end), (DEGREE_CONCESSIVE_ROOT, 0, len(text)))
        front, _, matrix, _ = root.children
        self.assertEqual(self.spans(front.children, text), [
            ("ADJP", "However much astonished"), ("NP", "I"), ("MODAL", "might"), ("COPULA", "be"),
        ])
        self.assertEqual(self.spans(front.children[0].children, text),
                         [("ADV", "However"), ("ADV", "much"), ("ADJ", "astonished")])
        self.assertEqual(front.children[-1].features.as_dict()["vform"], "base")
        attitude, content = matrix.children[-1].children
        self.assertEqual(self.spans((attitude,), text), [("ADJ", "sensible")])
        self.assertEqual(self.spans(content.children[:3], text),
                         [("COMP-THAT", "that"), ("NP", "I"), ("V", "had")])
        right = content.children[-1]
        infinitive = right.children[-1]
        self.assertEqual(self.spans(right.children[:2], text), [("DET", "no"), ("N", "right")])
        self.assertEqual(self.spans(infinitive.children, text), [
            ("TO", "to"), ("V", "refuse"), ("NP", "compliance with such a peremptory command"),
        ])
        self.assertEqual(self.spans(infinitive.children[-1].children, text),
                         [("N", "compliance"), ("PP", "with such a peremptory command")])
        by_id = {c["id"]: c for c in pre.structural_constituents}
        self.assertEqual(by_id["gc1"]["governor"], "gc2")
        self.assertEqual(pre.source_component("gc0"), "However much astonished I might be")
        self.assertEqual(pre.source_component("gc2"), "sensible")

    def test_case_74_semantic_edges_do_not_flatten_the_aligned_scopes(self):
        case = select_cases(500)[0][74]
        text = case["source_text"]
        _, lattice, rr = self.parse(case)
        self.assertEqual(rr.best().rule_id, DEGREE_CONCESSIVE_ROOT)
        graph = ParseReport(rr, self.parser._quoted_sentence_resources, lattice).interpret().graph
        edges = {(r.relation, graph.nodes[r.source].span[0], graph.nodes[r.target].span[0])
                 for r in graph.relations}
        pos = text.index
        front, main, inner = pos("be,"), pos("was"), pos("had")
        agent = pos("I had")
        required = {
            ("CONCESSION", main, front), ("DEGREE", pos("astonished"), pos("much")),
            ("DEGREE", pos("much"), 0), ("MODALITY", front, pos("might")),
            ("THEME", front, pos("I might")), ("ATTRIBUTE", front, pos("astonished")),
            ("ATTRIBUTE", main, pos("sensible")), ("CONTENT", pos("sensible"), inner),
            ("THEME", inner, pos("right")), ("NEGATION", pos("right"), pos("no right")),
            ("COMPLEMENT", pos("right"), pos("refuse")), ("AGENT", pos("refuse"), agent),
            ("AFFECTED", pos("refuse"), pos("compliance")), ("COMPLEMENT", pos("compliance"), pos("with")),
            ("COMPLEMENT", pos("with"), pos("command")),
        }
        forbidden = {
            ("CONCESSION", inner, front), ("CONTENT", main, inner),
            ("AGENT", pos("refuse"), pos("right")), ("COMPLEMENT", inner, pos("refuse")),
            ("COMPLEMENT", pos("refuse"), pos("with")), ("NEGATION", pos("refuse"), pos("no right")),
        }
        self.assertTrue(required <= edges, required - edges)
        self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_concessions_with_and_without_much(self):
        for source in (self.INTENSIFIED, self.SIMPLE):
            with self.subTest(source=source):
                r = self.control(source)
                self.assertTrue(r.completed, r.stats)
                self.assertEqual(r.best().rule_id, DEGREE_CONCESSIVE_ROOT)
                front, _, main, _ = r.best().children
                self.assertEqual(len(front.children[0].children), 3 if source == self.INTENSIFIED else 2)
                self.assertEqual(main.children[-1].rule_id, "structural_degree_concessive_attitude_attribute")

    def test_bad_modal_agreement_lexical_selection_and_boundaries_do_not_get_tree(self):
        for old, new in (
            ("might be,", "might was,"), ("might be,", "might be"),
            ("alarmed she", "alarmed her"), ("I was aware", "I were aware"),
            ("I was aware", "I was wooden"), ("they had no", "they has no"),
            ("no authority", "no table"), ("to demand", "to demanded"),
            ("demand compliance with", "demand bread with"),
        ):
            with self.subTest(replacement=new):
                best = self.control(self.INTENSIFIED.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != DEGREE_CONCESSIVE_ROOT)


class NegativePerfectInversionTests(unittest.TestCase):
    setUpClass = classmethod(SourceParentheticalModalTests.setUpClass.__func__)
    parse = SourceParentheticalModalTests.parse
    control = SourceParentheticalModalTests.control
    spans = SourceParentheticalModalTests.spans

    FREQUENCY = "Never, had she admired the singer so openly and warmly, as she admired him that evening."
    COORDINATION = "At least, and at last, we were off the island, nor had we departed thence unharmed."

    def test_originals_keep_the_perfect_inverted_and_declarative(self):
        cases = select_cases(500)[0]
        for index, digest, kind in ((84, "895b8100ffcc44d0", "never"), (462, "891db2bd005ff977", "nor")):
            with self.subTest(index=index):
                text = cases[index]["source_text"]
                self.assertEqual(sha256(text.encode()).hexdigest()[:16], digest)
                prepared, lattice, result = self.parse(cases[index])
                self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats["budget_exceeded"])
                self.assertFalse(result.stats["kbest_budget_exceeded"])
                root = result.best()
                self.assertEqual((root.rule_id, root.start, root.end), (NEGATIVE_PERFECT_ROOT, 0, len(text)))
                self.assertEqual(root.features.as_dict()["stype"], "declarative")
                host, stop = root.children
                self.assertEqual(text[stop.start:stop.end], ".")
                inversion = host.children[-1]
                self.assertEqual(inversion.features.as_dict()["kind"], kind)
                self.assertEqual(inversion.features.as_dict()["aspect"], "perfect")
                self.assertEqual(inversion.features.as_dict()["inversion"], "negative")
                licensor, aux, subject, vp = inversion.children
                self.assertEqual(self.spans((aux, subject), text), [("HAVE", "had"), ("NP", "I")])
                self.assertEqual(prepared.source_component("ni0"), text[inversion.start:inversion.end])
                self.assertEqual(vp.children[0].features.as_dict()["vform"], "ed")
                if index == 84:
                    self.assertEqual(self.spans(licensor.children, text),
                                     [("DEGREE", "Never"), ("COMMA", ","), ("DEGREE", "never"), ("COMMA", ",")])
                    self.assertEqual(self.spans(vp.children, text), [
                        ("V", "loved"), ("NP", "Dora"), ("NEGATIVE-EQUATIVE-DEGREE", "so deeply and truly"),
                        ("COMMA", ","), ("NEGATIVE-EQUATIVE-STANDARD", "as I loved her that night"),
                    ])
                    self.assertEqual(vp.children[-1].children[2].features.as_dict()["vform"], "finite")
                else:
                    self.assertEqual(self.spans(vp.children, text),
                                     [("V", "returned"), ("ADV", "thence"), ("ADJ", "empty-handed")])
                    self.assertEqual(self.spans(host.children[0].children[-1].children, text),
                                     [("PREP", "off"), ("NP", "the sea")])

    def test_scope_uses_distinct_events_and_subject_spans(self):
        cases = select_cases(500)[0]
        for i in (84, 462):
            case = cases[i]
            text = case["source_text"]
            _, lattice, result = self.parse(case)
            self.assertEqual(result.best().rule_id, NEGATIVE_PERFECT_ROOT)
            graph = ParseReport(result, self.parser._quoted_sentence_resources, lattice).interpret().graph
            edges = {(r.relation, graph.nodes[r.source].span[0], graph.nodes[r.target].span[0])
                     for r in graph.relations}
            if i == 84:
                matrix, standard = text.index("loved"), text.rindex("loved")
                required = {
                    ("NEGATION", matrix, 0), ("EMPHASIS", 0, text.index("never")),
                    ("ASPECT", matrix, text.index("had")), ("AFFECTED", matrix, text.index("Dora")),
                    ("TIME", standard, text.index("night")), ("AFFECTED", standard, text.index("her that")),
                    ("MANNER", matrix, text.index("deeply")), ("MANNER", matrix, text.index("truly")),
                    ("COMPARISON", text.index("deeply"), standard),
                }
                forbidden = {("NEGATION", standard, 0), ("TIME", matrix, text.index("night")),
                             ("NEGATION", matrix, text.index("never"))}
            else:
                left, right, subject = text.index("was"), text.index("returned"), text.rindex("I")
                required = {
                    ("NEGATION", right, text.index("nor")), ("ASPECT", right, text.index("had")),
                    ("CONJUNCT", left, right), ("LOCATION", left, text.index("off")),
                    ("TIME", left, text.index("at last")), ("SOURCE", right, text.index("thence")),
                    ("AGENT", right, subject), ("DEPICTIVE", subject, text.index("empty-handed")),
                }
                forbidden = {("NEGATION", left, text.index("nor")), ("SOURCE", left, text.index("thence")),
                             ("DEPICTIVE", text.index("I"), text.index("empty-handed"))}
            self.assertTrue(required <= edges, required - edges)
            self.assertFalse(forbidden & edges, forbidden & edges)

    def test_independent_variants_and_invalid_negative_perfects(self):
        for text in (self.FREQUENCY, self.COORDINATION):
            with self.subTest(positive=text):
                result = self.control(text)
                self.assertTrue(result.completed, result.stats)
                self.assertEqual(result.best().rule_id, NEGATIVE_PERFECT_ROOT)
        for text, old, new in (
            (self.FREQUENCY, "Never,", "Once,"),
            (self.FREQUENCY, "had she", "she had"),
            (self.FREQUENCY, "admired the singer", "admire the singer"),
            (self.FREQUENCY, "as she admired", "as her admired"),
            (self.COORDINATION, "nor had we", "and had we"),
            (self.COORDINATION, "nor had we", "nor we had"),
            (self.COORDINATION, "were off", "was off"),
            (self.COORDINATION, "had we departed", "had we depart"),
        ):
            with self.subTest(negative=new):
                best = self.control(text.replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != NEGATIVE_PERFECT_ROOT)


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

    INTERNAL_NOMINAL_CONTROLS = (
        "He had never learned of her having owned any cousins, except a brother and sister, both of whom had been sick many weeks.",
        "She remembered the colour of her dress, which she mended herself upstairs in her room, and which, before the party, was nothing but rags.",
    )

    def test_partitive_relative_modifies_the_two_exceptions(self):
        text, matrix = self.original(select_cases(500)[0][242], "921895028f592bb3")
        parts = SharedSubjectCoordinationTests.parts
        gerund = matrix.children[-1]
        self.assertEqual(parts(matrix, text)[:5], [
            ("NP", "She"), ("HAVE", "had"), ("DEGREE", "never"), ("V", "heard"), ("PREP", "of"),
        ])
        self.assertEqual(parts(gerund, text)[:3], [("POSS", "his"), ("HAVE", "having"), ("V", "had")])
        obj = gerund.children[-1]
        self.assertEqual(obj.children[1].features.as_dict()["number"], "plural")
        self.assertEqual(parts(obj, text)[:4], [
            ("DET", "any"), ("N", "relations"), ("COMMA", ","), ("EXCEPTIVE", "except"),
        ])
        supplement = obj.children[-1]
        self.assertEqual(supplement.rule_id, "structural_bind_supplement_to_internal_nominal")
        self.assertEqual(parts(supplement, text), [
            ("SUPPLEMENT-BASE", "a father and mother"), ("COMMA", ","),
            ("NOMINAL-RELATIVE", "both of whom had been dead many years"),
        ])
        pair, _, relative = supplement.children
        self.assertEqual(parts(pair, text), [("DET", "a"), ("N", "father"), ("COORD", "and"), ("N", "mother")])
        self.assertEqual(parts(relative, text), [
            ("PARTITIVE-REL-SUBJECT", "both of whom"), ("HAVE", "had"),
            ("COPULA", "been"), ("ADJ", "dead"), ("NP", "many years"),
        ])

    def test_coordinated_subject_and_object_gaps_modify_inner_nominal(self):
        text, matrix = self.original(select_cases(500)[0][469], "113f1648c549bbbe")
        parts = SharedSubjectCoordinationTests.parts
        nominal = matrix.children[-1]
        self.assertEqual(parts(matrix, text)[:2], [("NP", "I"), ("V", "remember")])
        self.assertEqual(parts(nominal, text)[:2], [("NP", "the appearance"), ("PREP", "of")])
        supplement = nominal.children[-1]
        self.assertEqual(supplement.rule_id, "structural_bind_supplement_to_internal_nominal")
        self.assertEqual(parts(supplement, text)[:2], [("SUPPLEMENT-BASE", "his coat"), ("COMMA", ",")])
        object_rel, comma, coord, subject_rel = supplement.children[-1].children
        self.assertEqual((text[comma.start:comma.end], text[coord.start:coord.end]), (",", "and"))
        self.assertEqual(parts(object_rel, text), [
            ("WH-REL-OBL", "which"), ("NP", "he"), ("V", "patched"), ("EMPHATIC-REFLEXIVE", "himself"),
            ("ADV", "upstairs"), ("PREP", "in"), ("NP", "his room"),
        ])
        self.assertEqual(parts(subject_rel, text), [
            ("WH-REL-OBL", "which"), ("COMMA", ","), ("PREP", "before"), ("NP", "the end"),
            ("COMMA", ","), ("COPULA", "was"), ("EXCLUSIVE-NOMINAL", "nothing but patches"),
        ])

    def test_nominal_supplement_controls_and_counterexamples(self):
        for text in self.INTERNAL_NOMINAL_CONTROLS:
            with self.subTest(positive=text):
                self.assertEqual(self.control(text).best().rule_id, EMBEDDED_RELATIVE_ROOT)
        for index, old, new in (
            (0, "a brother and sister", "a brother"),
            (0, "a brother and sister", "a rock and sister"),
            (0, "having owned", "having slept"),
            (0, "had been sick", "had was sick"),
            (1, "mended herself", "mended it herself"),
            (1, "mended herself", "mended himself"),
            (1, "which, before the party, was", "which, before the party, were"),
            (1, "which, before the party, was", "which, before the party was"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.INTERNAL_NOMINAL_CONTROLS[index].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != EMBEDDED_RELATIVE_ROOT)

    def test_internal_nominal_semantic_attachments(self):
        cases = select_cases(500)[0]
        pair = "COORDINATED_ANTECEDENT"
        for index, expected, forbidden in (
            (242, {("MEMBER", pair, "father"), ("MEMBER", pair, "mother"),
                   ("EXCEPTION", "relations", pair), ("MODIFIER", pair, "been"),
                   ("COMPLEMENT", "of", pair), ("THEME", "been", "COUNTED_SUBSET"),
                   ("DURATION", "been", "years"), ("AGENT", "had", "his"),
                   ("AFFECTED", "had", "relations"), ("COMPLEMENT", "of", "had"),
                   ("NEGATION", "heard", "never")},
                  {("MODIFIER", "relations", "been"), ("MODIFIER", "father", "been"),
                   ("MODIFIER", "mother", "been"), ("EXCEPTION", "heard", pair)}),
            (469, {("AFFECTED", "remember", "appearance"), ("MODIFIER", "appearance", "of"),
                   ("COMPLEMENT", "of", "coat"), ("AFFECTED", "patched", "coat"),
                   ("AGENT", "patched", "he"), ("EMPHASIS", "he", "himself"),
                   ("MODIFIER", "coat", "patched"), ("MODIFIER", "coat", "was"),
                   ("THEME", "was", "coat"), ("ADJUNCT", "was", "before"),
                   ("ATTRIBUTE", "was", "patches")},
                  {("AFFECTED", "patched", "himself"), ("AFFECTED", "patched", "appearance"),
                   ("THEME", "was", "appearance"), ("ADJUNCT", "patched", "before")}),
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

class FiniteTemporalScopeTests(unittest.TestCase):
    setUpClass = classmethod(EmbeddedRelativeScopeTests.setUpClass.__func__)
    parse = EmbeddedRelativeScopeTests.parse
    control = EmbeddedRelativeScopeTests.control

    TEMPORAL_CASES = (
        (73, "d42bea92dd357fce", "as they came towards us", "structural_temporal_scope_interposed_before_content"),
        (95, "16ef86f47f909d4b", "when Mr. Peggotty came home about nine o’clock", "structural_temporal_scope_progressive_with_connective"),
        (348, "a40661181be78fa8", "When I mingled with other families", "structural_temporal_scope_two_conjuncts"),
    )
    TEMPORAL_CONTROLS = (
        "She believed, as we walked towards them, that they were neatly dressed even in that photograph.",
        "Therefore, when Dr. Carter went home around seven o’clock, that cheerful Mrs. Green was sewing in her room, in a very calm and peaceful mood.",
        "When she walked with old friends she clearly noticed how strangely silent her house was, and fear altered the course of her journey.",
    )

    def test_temporal_scope_sources_and_selected_predicates(self):
        cases = select_cases(500)[0]
        parts = SharedSubjectCoordinationTests.parts
        for index, digest, expected_time, rule in self.TEMPORAL_CASES:
            with self.subTest(index=index):
                text = cases[index]["source_text"]
                self.assertEqual(sha256(text.encode()).hexdigest()[:16], digest)
                prepared, lattice, result = self.parse(cases[index])
                self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                spans = [x for x in prepared.structural_constituents
                         if x["function"] == "adverbial_subordinate_clause"]
                self.assertEqual([(text[x["start"]:x["end"]], x["governor"]) for x in spans],
                                 [(expected_time, "s0")])
                root = result.best()
                self.assertEqual(root.rule_id, FINITE_TEMPORAL_ROOT)
                self.assertEqual((root.start, root.end), (0, len(text)))
                matrix = root.children[0]
                self.assertEqual(matrix.rule_id, rule)
                if index == 73:
                    self.assertEqual(parts(matrix, text)[:6], [
                        ("NP", "I"), ("V", "thought"), ("COMMA", ","),
                        ("FINITE-TEMPORAL", expected_time), ("COMMA", ","),
                        ("FINITE-THAT-CONTENT", "that they were well matched even in that particular"),
                    ])
                    self.assertEqual([c.category for c in matrix.children[-1].children],
                                     ["COMP-THAT", "NP", "AUX-BE", "ADV", "V", "PP"])
                elif index == 95:
                    self.assertEqual(parts(matrix, text)[2:8], [
                        ("FINITE-TEMPORAL", expected_time), ("COMMA", ","),
                        ("DESCRIBED-SUBJECT", "this unfortunate Mrs. Gummidge"), ("AUX-BE", "was"),
                        ("V", "knitting"), ("PP", "in her corner"),
                    ])
                    arrival = matrix.children[2].children[1]
                    self.assertEqual(parts(arrival, text), [
                        ("TITLED-SUBJECT", "Mr. Peggotty"), ("V", "came"),
                        ("ADV", "home"), ("CLOCK-PP", "about nine o’clock"),
                    ])
                    self.assertEqual(parts(arrival.children[-1].children[-1], text),
                                     [("NUM", "nine"), ("ADV", "o’clock")])
                    self.assertEqual(matrix.children[-1].category, "COORDINATED-STATE-PP")
                else:
                    first, _, _, second = matrix.children
                    self.assertEqual(parts(first, text)[:4], [
                        ("FINITE-TEMPORAL", expected_time), ("NP", "I"),
                        ("ADV", "distinctly"), ("V", "discerned"),
                    ])
                    self.assertEqual(parts(first.children[-1], text), [
                        ("WH-NOM", "how"), ("ADV", "peculiarly"), ("ADJ", "fortunate"),
                        ("NP", "my lot"), ("COPULA", "was"),
                    ])
                    self.assertEqual(parts(second, text), [
                        ("NP", "gratitude"), ("V", "assisted"), ("NOMINAL-OF-THEME", "the development of filial love"),
                    ])

    def test_temporal_scope_independent_controls_and_rejections(self):
        for t in self.TEMPORAL_CONTROLS:
            with self.subTest(positive=t):
                self.assertEqual(self.control(t).best().rule_id, FINITE_TEMPORAL_ROOT)
        for index, old, new in (
            (0, "them, that", "them that"),
            (0, "they were", "they was"),
            (0, "we walked", "we painted"),
            (1, "seven o’clock", "trees o’clock"),
            (1, "Green was", "Green were"),
            (1, "Carter went", "Carter painted"),
            (2, "how strangely silent", "how strangely quietly"),
            (2, "she clearly noticed", "she clearly slept"),
            (2, "her house was", "her house were"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.TEMPORAL_CONTROLS[index].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != FINITE_TEMPORAL_ROOT)

    def test_temporal_scope_exact_semantic_governors(self):
        cases = select_cases(500)[0]
        for index, expected, forbidden in (
            (73, {("TIME", "thought", "came"), ("COMPLEMENT", "thought", "matched"),
                  ("THEME", "matched", "they"), ("MANNER", "matched", "well")},
                 {("TIME", "matched", "came"), ("COMPLEMENT", "thought", "came")}),
            (95, {("TIME", "knitting", "came"), ("TIME", "came", "about"),
                  ("AGENT", "knitting", "Gummidge"), ("AGENT", "came", "Peggotty"),
                  ("DESTINATION", "came", "home"), ("ASPECT", "knitting", "was"),
                  ("DEPICTIVE", "Gummidge", "in"), ("COMPLEMENT", "in", "condition"),
                  ("MODIFIER", "condition", "miserable")},
                 {("TIME", "knitting", "about"), ("DEPICTIVE", "Peggotty", "in"),
                  ("AGENT", "was", "Gummidge")}),
            (348, {("TIME", "discerned", "mingled"), ("COMPLEMENT", "discerned", "was"),
                   ("THEME", "was", "lot"), ("ATTRIBUTE", "was", "fortunate"),
                   ("DEGREE", "fortunate", "how"), ("CONJUNCT", "discerned", "assisted"),
                   ("THEME", "development", "love"), ("AFFECTED", "assisted", "development")},
                  {("TIME", "assisted", "mingled"), ("TIME", "was", "mingled"),
                   ("AFFECTED", "assisted", "love")}),
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
                if index == 95:
                    for rel, phrase in (("ADJUNCT", "in her corner"), ("DEPICTIVE", "in a very wretched")):
                        target, = [graph.nodes[r.target] for r in graph.relations
                                   if r.relation == rel and label(graph.nodes[r.target]) == "in"]
                        self.assertEqual(target.span[0], p.analysis_text.index(phrase))

    NOMINAL_TEMPORAL_CONTROLS = (
        "Dr. Carter then directed their attention to one of Miss Green, painted when she was only seven years old.",
        "Worried and restless, the hour which passed in the library, before the guests arrived, was tedious and dull to a degree that almost made him rude.",
    )

    def test_nominal_temporals_are_inside_the_selected_modifier(self):
        cases = select_cases(500)[0]
        parts = SharedSubjectCoordinationTests.parts
        for index, digest, nominal_text, temporal_text in (
            (206, "fe7102c065aebf90", "drawn when she was only eight years old",
             "when she was only eight years old"),
            (246, "f696ae0852e22ab4", "which passed in the drawing-room, before the gentlemen came",
             "before the gentlemen came"),
        ):
            with self.subTest(index=index):
                text = cases[index]["source_text"]
                self.assertEqual(sha256(text.encode()).hexdigest()[:16], digest)
                prepared, lattice, result = self.parse(cases[index])
                self.assertEqual((prepared.analysis_text, lattice.text), (text, text))
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                root = result.best()
                self.assertEqual(root.rule_id, FINITE_TEMPORAL_ROOT)
                self.assertEqual((root.start, root.end), (0, len(text)))
                source = {x["id"]: x for x in prepared.structural_constituents}
                self.assertEqual(source["a0"]["governor"], "n0")
                self.assertEqual(source["n0"]["governor"], "s0")
                for key, value in (("n0", nominal_text), ("a0", temporal_text)):
                    self.assertEqual(text[source[key]["start"]:source[key]["end"]], value)
                matrix = root.children[0]
                if index == 206:
                    self.assertEqual(matrix.rule_id, "structural_temporal_scope_directed_depiction")
                    depiction = matrix.children[-1].children[-1]
                    self.assertEqual(parts(depiction, text), [
                        ("DEPICTED-ONE", "one of Miss Darcy"), ("COMMA", ","),
                        ("TIMED-NOMINAL-MODIFIER", nominal_text),
                    ])
                    modifier = depiction.children[-1]
                    self.assertEqual(parts(modifier, text), [("V", "drawn"), ("FINITE-TEMPORAL", temporal_text)])
                    age = modifier.children[-1].children[-1]
                    self.assertEqual(parts(age, text), [
                        ("NP", "she"), ("COPULA", "was"), ("ADV", "only"), ("NUM", "eight"),
                        ("N", "years"), ("ADJ", "old"),
                    ])
                    self.assertEqual(age.children[-2].features.as_dict()["number"], "plural")
                else:
                    self.assertEqual(matrix.rule_id, "structural_temporal_scope_experiencer_interval")
                    interval = matrix.children[2]
                    self.assertEqual(parts(interval, text), [
                        ("NP", "the period"), ("TIMED-NOMINAL-MODIFIER", nominal_text),
                    ])
                    self.assertEqual(parts(interval.children[-1], text), [
                        ("WH-REL-OBL", "which"), ("V", "passed"), ("PP", "in the drawing-room"),
                        ("COMMA", ","), ("FINITE-TEMPORAL", temporal_text),
                    ])
                    arrival = interval.children[-1].children[-1].children[-1]
                    self.assertEqual(parts(arrival, text), [("PLURAL-TEMPORAL-SUBJECT", "the gentlemen"), ("V", "came")])
                    self.assertEqual(arrival.children[0].features.as_dict()["number"], "plural")
                    self.assertEqual(matrix.children[-1].category, "INTERVAL-ATTRIBUTE")

    def test_nominal_temporal_independent_controls(self):
        for text in self.NOMINAL_TEMPORAL_CONTROLS:
            with self.subTest(positive=text):
                self.assertEqual(self.control(text).best().rule_id, FINITE_TEMPORAL_ROOT)
        for index, old, new in (
            (0, "painted when", "arrived when"),
            (0, "she was", "she were"),
            (0, "seven years", "seven people"),
            (0, "Green, painted", "Green painted"),
            (1, "guests arrived", "guest arrived"),
            (1, "guests arrived", "guests painted"),
            (1, "arrived, was", "arrived was"),
            (1, "made him rude", "slept him rude"),
        ):
            with self.subTest(negative=new):
                best = self.control(self.NOMINAL_TEMPORAL_CONTROLS[index].replace(old, new)).best()
                self.assertTrue(best is None or best.rule_id != FINITE_TEMPORAL_ROOT)

    def test_nominal_temporal_semantics_distinguish_the_two_levels(self):
        cases = select_cases(500)[0]
        for index, expected, forbidden in (
            (206, {("AFFECTED", "directed", "attention"), ("GOAL", "directed", "to"),
                   ("COMPLEMENT", "to", "one"), ("DEPICTS", "one", "Darcy"),
                   ("THEME", "drawn", "one"), ("TIME", "drawn", "was"),
                   ("THEME", "was", "she"), ("ATTRIBUTE", "was", "old"),
                   ("QUANTITY", "years", "eight"), ("FOCUS", "eight", "only")},
                  {("TIME", "directed", "was"), ("THEME", "drawn", "Darcy"),
                   ("AFFECTED", "directed", "one")}),
            (246, {("THEME", "passed", "period"), ("MODIFIER", "period", "passed"),
                   ("BEFORE", "passed", "came"), ("AGENT", "came", "gentlemen"),
                   ("THEME", "was", "period"), ("ATTRIBUTE", "was", "wearisome"),
                   ("DEGREE", "wearisome", "degree"), ("CAUSE", "made", "degree"),
                   ("AFFECTED", "made", "her"), ("RESULT", "her", "uncivil"),
                   ("DEPICTIVE", "her", "Anxious")},
                  {("BEFORE", "was", "came"), ("BEFORE", "made", "came"),
                   ("DEPICTIVE", "period", "Anxious"), ("CAUSE", "made", "period")}),
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


class SpokenStatementQuestionSequenceTests(unittest.TestCase):
    TWO = "dialogue_structural_statement_then_wh_question"
    THREE = "dialogue_structural_two_statements_then_wh_question"
    ROOTS = {TWO, THREE}

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def _parse(self, source, max_items=50_000, kbest_work_limit=500_000):
        cases, _ = extract(
            Book(45, "Anne of Green Gables", "L. M. Montgomery", "test"),
            source, length_min=1, length_max=120,
        )
        self.assertEqual(len(cases), 1, source)
        return parse_corpus_case(
            self.parser, cases[0], max_items=max_items,
            kbest_work_limit=kbest_work_limit,
        )

    def test_attested_transfer_case_keeps_all_three_acts_and_roles(self):
        # Gutenberg #45, diagnostic case T45-0545. Preserve source punctuation.
        source = (
            "“So you do know something then, thank goodness! "
            "You’re not quite a heathen. Where did you learn that?”"
        )
        prepared, lattice, result = self._parse(source)
        root = result.best()
        self.assertEqual(prepared.analysis_text, source)
        self.assertEqual(result.text, source)
        self.assertEqual(lattice.text, source)
        self.assertTrue(result.completed)
        self.assertEqual(root.rule_id, self.THREE)

        def spans(nodes):
            return [source[node.start:node.end] for node in nodes]

        self.assertEqual(spans(root.children), [
            "“", "So you do know something then, thank goodness", "!",
            "You’re not quite a heathen", ".", "Where did you learn that?", "”",
        ])
        first, second, question = (root.children[i] for i in (1, 3, 5))
        self.assertEqual(spans(first.children), [
            "So", "you do know something", "then", ",", "thank goodness",
        ])
        self.assertEqual(first.children[1].children[0].children[1].rule_id, "vp_emphatic")
        self.assertEqual(spans(second.children), ["You", "’re", "not", "quite a heathen"])
        self.assertEqual(second.children[-1].children[0].rule_id, "np_such")
        self.assertEqual(question.category, "WH-QUESTION")
        self.assertEqual(question.features.as_dict()["stype"], "question")
        self.assertEqual(spans(question.children), ["Where", "did", "you", "learn that", "?"])
        self.assertEqual(spans(question.children[3].children[0].children), ["learn", "that"])
        self.assertEqual(result.stats["structural_clause_count"], 3)
        self.assertEqual(
            [source[a:b] for a, b in result.stats["source_punctuation_spans"]],
            ["“", ",", "!", ".", "?", "”"],
        )
        self.assertEqual(result.stats["max_items_total_across_segments"], 50_000)
        self.assertEqual(result.stats["kbest_work_limit_total_across_segments"], 500_000)
        report = ParseReport(result, self.parser._quoted_sentence_resources, lattice)
        semantic = report.best_semantic_graph()
        h = semantic["handles"]
        edges = {(r["relation"], r["source"], r["target"])
                 for r in semantic["graph"]["relations"]}
        self.assertIn(("CONTINUED_SPEECH", h["speech_1"], h["speech_2"]), edges)
        self.assertIn(("CONTINUED_SPEECH", h["speech_2"], h["speech_3"]), edges)
        self.assertIn(("ATTRIBUTE", h["speech_2"], h["attribute"]), edges)
        self.assertIn(("NEGATION", h["speech_2"], h["negation"]), edges)
        self.assertIn(("INTERROGATIVE_ADJUNCT", h["speech_3"], h["interrogative_adjunct"]), edges)

    def test_generalizes_across_one_or_two_statements_and_an_abbreviation(self):
        for source, rule, question in [
            ("“You have a map. Where did you find it?”", self.TWO, "Where did you find it?"),
            ("“Dr. Gray is here. Where did you meet him?”", self.TWO, "Where did you meet him?"),
            ("“The clock stopped. He left. When did he leave?”", self.THREE, "When did he leave?"),
            ("“She reads. How does she find it?”", self.TWO, "How does she find it?"),
            ("“So you found it then, thank heavens! Where did you find it?”",
             self.TWO, "Where did you find it?"),
            ("“They’re not the owners. Why do they work here?”", self.TWO, "Why do they work here?"),
        ]:
            with self.subTest(source=source):
                _, _, result = self._parse(source)
                self.assertTrue(result.completed)
                root = result.best()
                self.assertEqual(root.rule_id, rule)
                tail = root.children[-2]
                self.assertEqual(source[tail.start:tail.end], question)
                self.assertEqual(source[tail.children[-1].start:tail.children[-1].end], "?")
                if "Dr." in source:
                    statement = root.children[1]
                    self.assertEqual(source[statement.start:statement.end], "Dr. Gray is here")

    def test_does_not_promote_incomplete_or_unlicensed_units(self):
        for source in (
            "“Because she left. Where did you find it?”",
            "“You have a map. Where does you find it?”",
            "“You have a map. Where did you went?”",
            "“You is not a thief. Where did you find it?”",
            "“You have a map. What did you find?”",  # object WH, not adjunct
            "“You have a map. Where did you find it.”",  # no question stop
            "“You have a ‘map’. Where did you find it?”",  # nested quotation
            "“You found a map,” said Jane, “Where did you find it?”",  # two source quotes
        ):
            with self.subTest(source=source):
                _, _, result = self._parse(source)
                self.assertNotIn(result.best().rule_id if result.best() else None, self.ROOTS)

    def test_composition_does_not_bypass_small_budgets(self):
        _, _, result = self._parse(
            "“You have a map. Where did you find it?”",
            max_items=10, kbest_work_limit=10,
        )
        self.assertNotIn(result.best().rule_id if result.best() else None, self.ROOTS)


class TransferSpokenActsAndCoordinationTests(unittest.TestCase):
    COMMAND = "dialogue_structural_command_then_closing"
    MODAL = "dialogue_structural_contracted_negative_modal_perfect_question"
    ADVERBS = "dialogue_structural_adverb_coordination_auxiliary_ellipsis"
    CHEER = "dialogue_structural_reported_cheer"
    PROGRESSIVE = "dialogue_structural_reported_progressive_with_weekday"
    COORD = "structural_coordinated_clauses_with_right_initial_pp"
    POSSESSION = "structural_negative_possession_with_locative_exception"
    POINT = "structural_pointing_to_target_with_body_instrument"
    SHARED_MODAL = "dialogue_structural_exemplified_shared_modal"
    NEGATIVE_COGNITION = "dialogue_structural_negative_cognition_then_contrast"

    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def _parse(self, source, max_items=50_000, work=500_000):
        cases, _ = extract(
            Book(999, "Grammar probes", "Test", "test"),
            source, length_min=1, length_max=100,
        )
        self.assertEqual(len(cases), 1, source)
        prepared, lattice, result = parse_corpus_case(
            self.parser, cases[0], max_items=max_items, kbest_work_limit=work,
        )
        self.assertEqual((source, source, source),
                         (prepared.analysis_text, lattice.text, result.text))
        return prepared, lattice, result

    @staticmethod
    def _spans(source, children):
        return [source[node.start:node.end] for node in children]

    def _semantic(self, result, lattice):
        package = ParseReport(result, self.parser._quoted_sentence_resources, lattice).best_semantic_graph()
        handles = package["handles"]
        edges = {(r["relation"], r["source"], r["target"])
                 for r in package["graph"]["relations"]}
        return handles, edges

    def test_attested_command_and_closing_are_separate_acts(self):
        source = "“Go to sleep now like a good child. Good night.”"
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.COMMAND)
        self.assertEqual([c.category for c in root.children],
                         ["OPEN-QUOTE", "COMMAND", "SPEECH-STOP", "CLOSING", "SPEECH-STOP", "CLOSE-QUOTE"])
        self.assertEqual(self._spans(source, root.children),
                         ["“", "Go to sleep now like a good child", ".", "Good night", ".", "”"])
        command, closing = root.children[1], root.children[3]
        self.assertEqual(self._spans(source, command.children), ["Go to sleep now", "like a good child"])
        self.assertEqual(command.features.as_dict()["stype"], "imperative")
        self.assertEqual(closing.features.as_dict()["minor_utterance"], "true")
        self.assertEqual([c.category for c in closing.children], ["CLOSING-FORMULA"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("COMPARISON", h["command"], h["comparison"]), e)
        self.assertIn(("CONTINUED_SPEECH", h["command"], h["closing"]), e)

    def test_attested_modal_negation_is_not_a_subject_modifier(self):
        source = "“Couldn’t you have sent her back?”"
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.MODAL)
        self.assertEqual(self._spans(source, root.children),
                         ["“", "Could", "n’t", "you", "have sent her back", "?", "”"])
        self.assertEqual(root.features.as_dict()["aspect"], "perfect")
        self.assertEqual(root.features.as_dict()["stype"], "question")
        self.assertEqual(root.children[3].children[0].rule_id, "np_indef_pron")
        h, e = self._semantic(result, lattice)
        self.assertIn(("NEGATION", h["modal"], h["negation"]), e)
        self.assertIn(("AGENT", h["event"], h["subject"]), e)

    def test_attested_adverbs_modify_one_elliptical_proposition(self):
        source = "“Really and truly I do.”"
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.ADVERBS)
        self.assertEqual(self._spans(source, root.children), ["“", "Really and truly", "I do", ".", "”"])
        self.assertEqual([c.category for c in root.children[1].children], ["ADV", "COORD", "ADV"])
        self.assertEqual(root.children[2].children[0].rule_id, "clause_aux_ellipsis")
        h, e = self._semantic(result, lattice)
        self.assertIn(("ADJUNCT", h["event"], h["manner"]), e)
        self.assertIn(("CONJUNCT", h["manner"], h["right"]), e)

    def test_attested_cheer_and_single_full_name_speaker(self):
        source = "“Hurrah!” said Moody Spurgeon."
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.CHEER)
        self.assertEqual(root.children[1].category, "CHEER")
        name = root.children[4].children[1]
        self.assertEqual(source[name.start:name.end], "Moody Spurgeon")
        self.assertEqual([c.category for c in name.children], ["PROPER-NOUN", "PROPER-NOUN"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("AGENT", h["report"], h["speaker"]), e)
        self.assertIn(("REPORTED_CONTENT", h["report"], h["content"]), e)
        self.assertNotIn("target", h)

    def test_attested_weekday_modifies_event_not_object(self):
        source = "“I’ll be haunting the post office Wednesday,” vowed Diana."
        prepared, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        self.assertEqual(prepared.source_component("r0"), "vowed Diana")
        root = result.best()
        self.assertEqual(root.rule_id, self.PROGRESSIVE)
        speech = root.children[1]
        self.assertEqual(speech.features.as_dict()["aspect"], "progressive")
        self.assertEqual(self._spans(source, speech.children),
                         ["I", "’ll", "be", "haunting", "the post office", "Wednesday"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("TIME", h["content"], h["time"]), e)
        self.assertIn(("AFFECTED", h["content"], h["object"]), e)
        self.assertIn(("ASPECT", h["content"], h["progressive_auxiliary"]), e)
        self.assertIn(("AGENT", h["report"], h["speaker"]), e)

    def test_attested_initial_pp_governs_only_the_right_conjunct(self):
        source = "He took up the lamp, and, in an absolute silence, we returned to the smoking-room."
        prepared, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        self.assertEqual(prepared.source_component("rcp"), "in an absolute silence")
        self.assertEqual(prepared.source_component("rc1"), "we returned to the smoking-room")
        pp = next(c for c in prepared.structural_constituents if c["id"] == "rcp")
        self.assertEqual(pp["governor"], "rc1")
        root = result.best()
        self.assertEqual(root.rule_id, self.COORD)
        first, right = root.children[0], root.children[3]
        self.assertEqual(self._spans(source, first.children), ["He", "took", "up", "the lamp"])
        self.assertEqual(first.children[2].category, "PARTICLE")
        self.assertEqual(self._spans(source, right.children), [",", "in an absolute silence", ",",
                                                            "we returned to the smoking-room"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("ADJUNCT", h["right"], h["adjunct"]), e)
        self.assertIn(("AFFECTED", h["left"], h["object"]), e)
        self.assertNotIn(("ADJUNCT", h["left"], h["adjunct"]), e)

    def test_attested_modal_scopes_over_both_bare_predicates(self):
        source = (
            "“One might travel back and verify the accepted account of "
            "the Battle of Hastings, for instance!”"
        )
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.SHARED_MODAL)
        self.assertEqual(root.children[1].features.as_dict()["generic"], "true")
        self.assertEqual(root.children[1].features.as_dict()["pronominal"], "true")
        pair = root.children[3]
        self.assertEqual(self._spans(source, pair.children),
                         ["travel back", "and", "verify the accepted account of the Battle of Hastings"])
        obj = pair.children[-1].children[-1]
        self.assertEqual(source[obj.start:obj.end], "the accepted account of the Battle of Hastings")
        self.assertEqual(obj.children[0].rule_id, "np_det_n_of")
        h, e = self._semantic(result, lattice)
        self.assertIn(("MODALITY", h["left"], h["modal"]), e)
        self.assertIn(("MODALITY", h["right"], h["modal"]), e)
        self.assertIn(("AFFECTED", h["right"], h["object"]), e)

    def test_attested_do_negation_and_contrast_do_not_extend_complement(self):
        source = (
            "“I don’t think it’s as pretty as my blue-flowered muslin"
            "--and it certainly isn’t so fashionable.”"
        )
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.NEGATIVE_COGNITION)
        self.assertEqual(self._spans(source, root.children[1].children),
                         ["I", "do", "n’t", "think", "it’s as pretty as my blue-flowered muslin"])
        self.assertEqual(self._spans(source, root.children[2:5]),
                         ["--", "and", "it certainly isn’t so fashionable"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("NEGATION", h["left"], h["negation"]), e)
        self.assertIn(("COMPLEMENT", h["left"], h["complement"]), e)
        self.assertNotIn(("COMPLEMENT", h["left"], h["right"]), e)

    def test_attested_exceptive_scopes_over_the_negative_domain(self):
        source = "He had nothing on them but a pair of tattered, blood-stained socks."
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.POSSESSION)
        self.assertEqual(self._spans(source, root.children), [
            "He", "had", "nothing", "on them", "but", "a pair of tattered, blood-stained socks", ".",
        ])
        self.assertEqual(root.children[4].category, "EXCEPTIVE")
        h, e = self._semantic(result, lattice)
        self.assertIn(("EXCEPTION", h["negative_domain"], h["exception"]), e)
        self.assertIn(("LOCATION", h["event"], h["location"]), e)
        self.assertNotIn(("CONJUNCT", h["location"], h["exception"]), e)

    def test_attested_body_part_is_instrument_of_pointing(self):
        source = "He pointed to the part with his finger."
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, self.POINT)
        self.assertEqual(self._spans(source, root.children),
                         ["He", "pointed", "to the part", "with his finger", "."])
        h, e = self._semantic(result, lattice)
        self.assertIn(("INSTRUMENT", h["event"], h["instrument"]), e)
        self.assertIn(("DIRECTION", h["event"], h["destination"]), e)
        self.assertNotIn(("MODIFIER", h["destination"], h["instrument"]), e)

    def test_independent_positive_controls(self):
        for source, expected in (
            ("“Speak softly like a professional. Goodbye!”", self.COMMAND),
            ("“Close the door. Farewell!”", self.COMMAND),
            ("“Wouldn’t she have arrived?”", self.MODAL),
            ("“Slowly and silently he did.”", self.ADVERBS),
            ("“Hooray!” cried Mary Jane.", self.CHEER),
            ("“She will be reading the letters on Wednesday,” promised Mary Jane.", self.PROGRESSIVE),
            ("She opened the window, and, without a word, he left the room.", self.COORD),
            ("I put down the glass, but, after a long pause, she spoke.", self.COORD),
            ("“We could leave early and visit the old town, for example.”", self.SHARED_MODAL),
            ("“They may sing or read the letters, for example.”", self.SHARED_MODAL),
            ("“She doesn’t believe the clock stopped—and she saw it.”", self.NEGATIVE_COGNITION),
            ("She had nothing on her but a red scarf.", self.POSSESSION),
            ("They have nothing on them but their coats.", self.POSSESSION),
            ("She pointed to the exit with her right hand.", self.POINT),
        ):
            with self.subTest(source=source):
                _, _, result = self._parse(source)
                self.assertTrue(result.completed)
                self.assertEqual(result.best().rule_id, expected)

    def test_near_misses_do_not_enter_the_scoped_rules(self):
        for source, disallowed in (
            ("“She spoke softly. Goodbye!”", self.COMMAND),
            ("“Like a child. Good night.”", self.COMMAND),
            ("“Sit down. The good night.”", self.COMMAND),
            ("“Wouldn’t she have arrive?”", self.MODAL),
            ("“Couldn’t your have gone?”", self.MODAL),
            ("“Really and truly she do.”", self.ADVERBS),
            ("“Slowly and Silvia he did.”", self.ADVERBS),
            ("“Hurrah!” said Moody to Spurgeon.", self.CHEER),
            ("“Magnificent!” said Mary Jane.", self.CHEER),
            ("“I’ll be seeing Wednesday,” said Diana.", self.PROGRESSIVE),
            ("“I’ll be friendly on Wednesday,” said Diana.", self.PROGRESSIVE),
            ("“I’ll be reading the letters on Monday,” disobeyed Diana.", self.PROGRESSIVE),
            ("She opened the window, and, he left the room.", self.COORD),
            ("She opened the window, and, without a word, closed the door.", self.COORD),
            ("She opened the window, and, after he spoke, they left.", self.COORD),
            ("She opened the window, and he left the room.", self.COORD),
            ("“We could leave early and he visited the town, for example.”", self.SHARED_MODAL),
            ("“We could leave early and visited the town, for example.”", self.SHARED_MODAL),
            ("“I don’t think it was ready—and because she left.”", self.NEGATIVE_COGNITION),
            ("“I don’t carry it was ready—and she thought so.”", self.NEGATIVE_COGNITION),
            ("She had nothing on her but she found a scarf.", self.POSSESSION),
            ("She has nothing on the shelf but a book.", self.POSSESSION),
            ("They has nothing on them but their coats.", self.POSSESSION),
            ("She pointed to the statue with a broken arm.", self.POINT),
            ("She looked to the exit with her right hand.", self.POINT),
            ("She pointed to the exit with his right hand.", self.POINT),
        ):
            with self.subTest(source=source):
                _, _, result = self._parse(source)
                self.assertNotEqual(result.best().rule_id if result.best() else None, disallowed)

    def test_source_ditransitive_command_proves_recipient_and_theme(self):
        source = "“Lend me your hand.”"  # Gutenberg #35, U35-0095.
        _, lattice, result = self._parse(source)
        self.assertTrue(result.completed)
        root = result.best()
        self.assertEqual(root.rule_id, "dialogue_structural_ditransitive_command")
        self.assertEqual(self._spans(source, root.children),
                         ["“", "Lend me your hand", ".", "”"])
        command = root.children[1]
        self.assertEqual(command.features.as_dict()["stype"], "imperative")
        self.assertEqual(self._spans(source, command.children), ["Lend", "me", "your hand"])
        h, e = self._semantic(result, lattice)
        self.assertIn(("RECIPIENT", h["event"], h["recipient"]), e)
        self.assertIn(("THEME", h["event"], h["theme"]), e)

    def test_ditransitive_command_controls(self):
        rule = "dialogue_structural_ditransitive_command"
        for source, accepted in (
            ("“Give me the key.”", True), ("“Pass her the book.”", True),
            ("“Send him a message.”", True), ("“Tell us a story!”", True),
            ("“Arrive him the book.”", False), ("“Give he the key.”", False),
            ("“He gave her a book.”", False), ("“He might send her a message.”", False),
            ("“Give her red dress.”", False),
        ):
            with self.subTest(source=source):
                _, _, result = self._parse(source)
                root = result.best()
                self.assertEqual(root is not None and root.rule_id == rule, accepted)

    def test_scoped_proofs_respect_small_budgets(self):
        _, _, result = self._parse("“Couldn’t you have sent her back?”", max_items=10, work=10)
        self.assertNotEqual(result.best().rule_id if result.best() else None, self.MODAL)


    def test_transfer_followup_selected_attachments(self):
        from seman_parser.scoped_discourse_followup import (
            ELAPSED, EMPHATIC_MODAL_CONTRAST, EMPHATIC_QUESTION_TURN, EXTRAPOSED_PASSIVE_REPORT,
            REPORTED_EMPHATIC_OPINIONS, TELLING,
        )
        from seman_parser.scoped_narrative_followup import EQUATIVE_DOUBT, INVERTED_EXTENT

        cases = (
            ("“That is what I want to tell you, Anne, if you’ll ever give me a chance to get a word in edgewise. She was talking about you.”",
             TELLING, (("VOCATIVE", "pseudocleft", "addressee"), ("CONDITION", "tell", "condition"),
                       ("TOPIC", "followup", "topic"))),
            ("The Time Traveller vanished three years ago.", ELAPSED,
             (("THEME", "event", "subject"), ("TIME", "event", "time"))),
            ("“You _can_ move about in all directions of Space, but you cannot move about in Time.”",
             EMPHATIC_MODAL_CONTRAST, (("CONTRAST", "positive", "negative"),)),
            ("“Josie Pye told me you did. Josie said you were _infatuated_ with her.”",
             REPORTED_EMPHATIC_OPINIONS, (("RECIPIENT", "first", "recipient"),)),
            ("“Now, it is very remarkable that this is so extensively overlooked,” continued the Time Traveller, with a slight accession of cheerfulness.",
             EXTRAPOSED_PASSIVE_REPORT, (("REPORTED_CONTENT", "report", "content"),
                                          ("MANNER", "report", "speaker_manner"))),
            ("“Oh, Diana,” cried Anne, clasping her hands, “do you _love_ me?”",
             EMPHATIC_QUESTION_TURN, (("VOCATIVE", "question", "addressee"),
                                      ("AGENT", "gesture", "speaker"), ("REPORTED_CONTENT", "report", "question"))),
            ("She wore a faded brown sailor hat and beneath the hat, extending down her back, were two braids of very thick, decidedly red hair.",
             INVERTED_EXTENT, (("AGENT", "wear", "wearer"), ("MODIFIER", "subject", "extent"))),
            ("Previously the rivalry had been rather one-sided, but there was no longer any doubt that Gilbert was as determined to be first in class as Anne was.",
             EQUATIVE_DOUBT, (("CONTRAST", "prior", "after"),)),
        )
        for source, expected, links in cases:
            with self.subTest(source=source):
                _, lattice, result = self._parse(source)
                self.assertTrue(result.completed)
                root = result.best()
                self.assertEqual(expected, root.rule_id)
                self.assertEqual((0, len(source)), (root.start, root.end))
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                h, relations = self._semantic(result, lattice)
                for rel, a, b in links:
                    self.assertIn((rel, h[a], h[b]), relations)

    def test_transfer_followup_generalization_and_near_misses(self):
        from seman_parser.scoped_discourse_followup import (
            ELAPSED, EMPHATIC_MODAL_CONTRAST, EMPHATIC_QUESTION_TURN, EXTRAPOSED_PASSIVE_REPORT,
            REPORTED_EMPHATIC_OPINIONS, TELLING,
        )
        from seman_parser.scoped_narrative_followup import EQUATIVE_DOUBT, INVERTED_EXTENT

        for source, expected, accepted in (
            ("“This is what I meant to tell her, Mary, if you’ll ever give me a chance to get a word in edgeways. He was speaking about us.”", TELLING, True),
            ("“This is what I meant to tell her, Mary, if you’ll ever give us a chance to get a word in edgeways. He was speaking about us.”", TELLING, False),
            ("She arrived two weeks ago.", ELAPSED, True),
            ("She arrived two week ago.", ELAPSED, False),
            ("“We _can_ walk about in the garden, but we cannot walk about in the house.”", EMPHATIC_MODAL_CONTRAST, True),
            ("“We _can_ walk about in the garden, but they cannot walk about in the house.”", EMPHATIC_MODAL_CONTRAST, False),
            ("“Mary Brown told me she did. Mary said she was _enchanted_ with him.”", REPORTED_EMPHATIC_OPINIONS, True),
            ("“Mary Brown told me she did. Mary said she were _enchanted_ with him.”", REPORTED_EMPHATIC_OPINIONS, False),
            ("“Now, it was quite surprising that it was so widely ignored,” said Mary, with a smile.", EXTRAPOSED_PASSIVE_REPORT, True),
            ("“Now, it was quite surprising that it was so widely ignore,” said Mary, with a smile.", EXTRAPOSED_PASSIVE_REPORT, False),
            ("“Oh, John,” asked Mary, folding her hands, “do you _trust_ him?”", EMPHATIC_QUESTION_TURN, True),
            ("“Oh, John,” asked Mary, folding her hands, “does you _trust_ him?”", EMPHATIC_QUESTION_TURN, False),
            ("She wore a straw hat and under the hat, hanging down her back, were two curls of very thick, distinctly brown hair.", INVERTED_EXTENT, True),
            ("She wore a straw hat and under the hat, hanging down his back, were two curls of very thick, distinctly brown hair.", INVERTED_EXTENT, False),
            ("Formerly the contest had been quite uneven, but there was no longer any question that Mary was as eager to be first in school as Edward was.", EQUATIVE_DOUBT, True),
            ("Formerly the contest had been quite uneven, but there was no longer any question that Mary was as eager to be first in school as Edward were.", EQUATIVE_DOUBT, False),
        ):
            with self.subTest(source=source, expected=expected):
                _, _, result = self._parse(source)
                root = result.best()
                self.assertEqual(accepted, root is not None and root.rule_id == expected)

    def test_independent_genitive_origin_preserves_possessor_but_not_a_fabricated_noun(self):
        from seman_parser.scoped_narrative_followup import GENITIVE_ORIGIN

        for source, accepted in (
            ("She came home from Mrs. Lynde’s and called Anne to account.", True),
            ("He returned home from John’s and called Mary to account.", True),
            ("She came home from Mrs. Lynde and called Anne to account.", False),
            ("She came home from Mrs. Lynde’s and called Anne to apologize.", False),
        ):
            with self.subTest(source=source):
                _, lattice, result = self._parse(source)
                root = result.best()
                self.assertEqual(accepted, root is not None and root.rule_id == GENITIVE_ORIGIN)
                if not accepted:
                    continue
                self.assertEqual((0, len(source)), (root.start, root.end))
                possessive = root.children[1].children[-1].children[-1]
                self.assertEqual([child.category for child in possessive.children], ["NP", "POSS"])
                self.assertEqual(self._spans(source, possessive.children)[-1], "’s")
                h, links = self._semantic(result, lattice)
                self.assertNotEqual(h["possessor"], h["origin"])
                for rel, a, b in (
                    ("POSSESSOR", "origin", "possessor"), ("SOURCE", "motion", "origin"),
                    ("DESTINATION", "motion", "destination"), ("AGENT", "motion", "subject"),
                    ("AGENT", "calling", "subject"), ("AFFECTED", "calling", "questioned"),
                    ("CONJUNCT", "motion", "calling"),
                ):
                    self.assertIn((rel, h[a], h[b]), links)
                self.assertNotIn(("SOURCE", h["calling"], h["origin"]), links)

    def test_observed_attempt_keeps_both_controllers_and_local_result_goal(self):
        from seman_parser.scoped_narrative_followup import PERCEIVED_ATTEMPT

        for source, coordinated, goal, accepted in (
            ("They found Anne and Marilla distractedly trying to restore Matthew to consciousness.",
             "Anne and Marilla", "to consciousness", True),
            ("We saw Mary and John desperately trying to pull him to safety.",
             "Mary and John", "to safety", True),
            ("We saw Mary and John desperately tried to pull him to safety.", "", "", False),
            ("We saw Mary and John desperately trying to pull him in safety.", "", "", False),
            ("We told Mary and John desperately trying to pull him to safety.", "", "", False),
        ):
            with self.subTest(source=source):
                _, lattice, result = self._parse(source)
                root = result.best()
                self.assertEqual(accepted, root is not None and root.rule_id == PERCEIVED_ATTEMPT)
                if not accepted:
                    continue
                self.assertEqual((0, len(source)), (root.start, root.end))
                self.assertEqual(source[root.children[2].start:root.children[2].end], coordinated)
                tail = root.children[3].children[-1].children[-1]
                self.assertEqual(source[tail.start:tail.end], goal)
                h, links = self._semantic(result, lattice)
                self.assertIn(("COMPLEMENT", h["perception"], h["attempt"]), links)
                self.assertIn(("MANNER", h["attempt"], h["attempt_manner"]), links)
                self.assertIn(("CONTROL_COMPLEMENT", h["attempt"], h["action"]), links)
                self.assertIn(("RESULT_GOAL", h["action"], h["goal"]), links)
                self.assertNotIn(("RESULT_GOAL", h["perception"], h["goal"]), links)
                for agent in (h["participant1"], h["participant2"]):
                    self.assertIn(("AGENT", h["attempt"], agent), links)
                    self.assertIn(("AGENT", h["action"], agent), links)
                self.assertNotIn(("AGENT", h["action"], h["observer"]), links)

    def test_verse_condition_needs_original_line_break_and_preserves_roles(self):
        from seman_parser.scoped_discourse_followup import CONDITIONAL_VERSE

        for raw, accepted in (
            ("“If you love me as I love you\n      Nothing but death can part us two.”", True),
            ("“If you trust us as we trust you\n      Nothing but silence could separate us two.”", True),
            ("“If you love me as I love you Nothing but death can part us two.”", False),
            ("“If you love me as I love you\n Nothing but death can part us two.”", False),
            ("“If you love me as I love you\n      Nothing and death can part us two.”", False),
        ):
            with self.subTest(raw=raw):
                normalized = " ".join(raw.split())
                cases, _ = extract(Book(999, "Grammar probes", "Test", "test"), raw, length_min=1)
                case, = cases
                prepared, lattice, result = parse_corpus_case(
                    self.parser, case, max_items=50_000, kbest_work_limit=500_000,
                )
                root = result.best()
                self.assertEqual(normalized, prepared.analysis_text)
                self.assertEqual([0, len(raw)], case["structural_core_source_span"])
                self.assertEqual(accepted, root is not None and root.rule_id == CONDITIONAL_VERSE)
                if accepted:
                    self.assertFalse(case["synthetic_prefix"])
                    self.assertFalse(case["synthetic_suffix"])
                    self.assertFalse(case["synthetic_terminal"])
                    h, links = self._semantic(result, lattice)
                    self.assertIn(("CONDITION", h["consequent"], h["condition"]), links)
                    self.assertIn(("COMPARISON", h["condition"], h["standard"]), links)
                    self.assertIn(("EXCEPTION", h["domain"], h["exception"]), links)
                    self.assertIn(("QUANTIFIER", h["parted_pair"], h["count"]), links)
                    self.assertIn(("THEME", h["consequent"], h["parted_pair"]), links)

    def test_literary_markup_is_not_a_syntactic_attachment(self):
        from seman_parser.scoped_narrative_followup import EMPHASIS_CLOSURE, EMPHATIC_NARRATIVE, EXPLAINED_QUOTED_THEME

        paragraph = ("_The Time Traveller paused, put his hand into his pocket, and silently placed two withered flowers, "
                     "not unlike very large white mallows, upon the little table. Then he resumed his narrative._")
        cases, _ = extract(Book(999, "Grammar probes", "Test", "test"), paragraph, length_min=1, length_max=100)
        self.assertEqual(len(cases), 2)
        self.assertEqual(" ".join(c["source_text"] for c in cases), paragraph)
        for case, expected in zip(cases, (EMPHATIC_NARRATIVE, EMPHASIS_CLOSURE)):
            prepared, lattice, result = parse_corpus_case(
                self.parser, case, max_items=50_000, kbest_work_limit=500_000,
            )
            self.assertTrue(result.completed)
            root = result.best()
            self.assertEqual(root.rule_id, expected)
            self.assertEqual(root.end, len(prepared.source_text))
            self.assertFalse(prepared.synthetic_suffix)
            if expected == EMPHATIC_NARRATIVE:
                h, relations = self._semantic(result, lattice)
                self.assertIn(("DIRECTION", h["third"], h["goal"]), relations)
                self.assertIn(("MODIFIER", h["theme"], h["similarity"]), relations)
        _, _, orphan = self._parse(cases[0]["source_text"])
        self.assertNotEqual(orphan.best().rule_id if orphan.best() else None, EMPHATIC_NARRATIVE)

        source = ("The Editor wanted that explained to him, and the Psychologist volunteered a wooden account "
                  "of the “ingenious paradox and trick” we had witnessed that day week.")
        _, lattice, result = self._parse(source)
        self.assertEqual(result.best().rule_id, EXPLAINED_QUOTED_THEME)
        h, relations = self._semantic(result, lattice)
        self.assertIn(("CONJUNCT", h["want"], h["report"]), relations)
        self.assertIn(("COMPLEMENT", h["want"], h["request"]), relations)
        self.assertIn(("THEME", h["relative"], h["topic"]), relations)
        self.assertIn(("TIME", h["relative"], h["time"]), relations)
        near_miss = source.replace("we had witnessed", "we had witnessed it")
        _, _, wrong = self._parse(near_miss)
        self.assertNotEqual(wrong.best().rule_id if wrong.best() else None, EXPLAINED_QUOTED_THEME)

    def test_transfer_narrative_scope_repairs(self):
        from seman_parser.scoped_transfer_clauses import (
            CAUSAL_PERFECT, CONTRASTIVE_SERIES, NEGATIVE_PROFORM, NOMINAL_EXCLAMATION,
            PROGRESSIVE_REPORT, PROGRESSIVE_PERCEPTION, RESULTATIVE_PURPOSE,
        )
        from seman_parser.scoped_transfer_clauses import DASH_REFORMULATION, PARENTHETICAL_PURPOSE
        from seman_parser.scoped_motion_supplements import (
            APPOSITIVE, CARRY, CAUSATIVE_RESPONSE, COORDINATED_PARTICIPLES,
            PARTITIVE_LOCATION, RISE, SPELLING_RESULT,
        )

        cases = (
            ("An Avery scholarship!", NOMINAL_EXCLAMATION, (("MODIFIER", "content", "modifier"),)),
            ("For Anne’s eyes had suddenly filled with tears.", CAUSAL_PERFECT,
             (("THEME", "event", "subject"), ("ASPECT", "event", "perfect_aux"),
              ("OBLIQUE", "event", "oblique"))),
            ("But none developed.", NEGATIVE_PROFORM, (("THEME", "event", "subject"),)),
            ("He said not a word, but came painfully to the table, and made a motion towards the wine.",
             CONTRASTIVE_SERIES, (("AGENT", "left", "subject"), ("AGENT", "middle", "subject"),
                                  ("AGENT", "right", "subject"), ("MANNER", "middle", "manner"))),
            ("The Medical Man looked into his face and, with a certain hesitation, told him he was suffering from overwork, at which he laughed hugely.",
             PROGRESSIVE_REPORT, (("RECIPIENT", "report", "recipient"), ("REPORTED_CONTENT", "report", "report_content"),
                                  ("RELATIVE", "report", "reaction"))),
            ("Then he turned over the hand holding his pipe, and I saw he was looking at some half-healed scars on his knuckles.",
             PROGRESSIVE_PERCEPTION, (("PARTICLE", "movement", "particle"), ("COMPLEMENT", "perception", "perceived"))),
            ("But she went away kindly, leaving Anne alone to keep her first vigil with sorrow.",
             RESULTATIVE_PURPOSE, (("RESULT", "event", "result"), ("AGENT", "result", "subject"))),
            ("He caught up the lamp swiftly, and carried it, flaring red, through the door into the corridor.",
             CARRY, (("THEME", "supplement", "carried"), ("PATH", "carry", "route"),
                     ("DIRECTION", "carry", "goal"))),
            ("Then, getting up, he went to the tobacco jar on the mantel, and with his back to us began to fill his pipe.",
             RISE, (("AGENT", "prior", "subject"), ("CIRCUMSTANCE", "right", "circumstance"))),
            ("Then Diana’s cousins, the Murrays from Newbridge, came; they all crowded into the big pung sleigh, among straw and furry robes.",
             APPOSITIVE, (("APPOSITION", "subject", "appositive"), ("QUANTIFIER", "group", "quantifier"))),
            ("He took one of the small octagonal tables that were scattered about the room, and set it in front of the fire, with two legs on the hearthrug.",
             PARTITIVE_LOCATION, (("DIRECTION", "place", "goal"), ("CIRCUMSTANCE", "place", "support"))),
            ("(The Psychologist, to show that he was not unhinged, helped himself to a cigar and tried to light it uncut.)",
             PARENTHETICAL_PURPOSE, (("AGENT", "action", "subject"), ("PURPOSE", "left", "purpose"))),
            ("Gilbert Blythe spelled her down in class and left her clear out of sight in mental arithmetic.",
             SPELLING_RESULT, (("PARTICLE", "spell", "particle"), ("PREDICATE", "affected", "result"))),
            ("Miss Barry actually laughed--a sound which caused Diana, waiting in speechless anxiety in the kitchen outside, to give a great gasp of relief.",
             CAUSATIVE_RESPONSE, (("APPOSITION", "matrix", "sound"), ("CAUSER", "cause", "sound"))),
            ("Anne lighted the lamp, oversetting the match safe and using up half a dozen matches before her shaking hands could accomplish the task.",
             COORDINATED_PARTICIPLES, (("CONJUNCT", "first", "second"), ("ANTERIOR", "second", "boundary"))),
            ("In writing it down I feel with only too much keenness the inadequacy of pen and ink—and, above all, my own inadequacy—to express its quality.",
             DASH_REFORMULATION, (("CIRCUMSTANCE", "event", "context"), ("AGENT", "context", "subject"))),
        )
        for source, expected, links in cases:
            with self.subTest(source=source):
                _, lattice, result = self._parse(source)
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertEqual(root.rule_id, expected)
                self.assertEqual((root.start, root.end), (0, len(source)))
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                h, relations = self._semantic(result, lattice)
                for rel, a, b in links:
                    self.assertIn((rel, h[a], h[b]), relations)

    def test_transfer_quoted_scope_repairs(self):
        from seman_parser.scoped_literary_quotes import (
            DOUBLE_PERFECT_PERSPECTIVE, HESITANT_ADMISSION, HESITANT_RESUMPTION, INTERRUPTED_CLOCK,
            NOR_POSSESSION, REPORTED_INVERTED_CONTROL, REPORTED_OPINION, REPORTED_REGRET, SPLIT_SELF_IDENTIFICATION,
        )
        from seman_parser.spoken_three_acts import DIALECTAL_EVIDENCE, MODAL_ECHO_REBUKE, NEGATIVE_REPLY, WAIT_QUESTION

        for source, expected, spans, links in (
            ("“So most people think. But wait a moment. Can an _instantaneous_ cube exist?”",
             WAIT_QUESTION, ("So most people think", "But wait a moment", "Can an _instantaneous_ cube exist"),
             (("MODALITY", "question", "modal"), ("DURATION", "directive", "duration"))),
            ("“No, sir. No one has come out this way. I was expecting to find him here.”",
             NEGATIVE_REPLY, ("No, sir", "No one has come out this way", "I was expecting to find him here"),
             (("ASPECT", "movement", "aux"), ("AGENT", "action", "expecter"))),
            ("“Nor, having only length, breadth, and thickness, can a cube have a real existence.”",
             NOR_POSSESSION, ("having only length, breadth, and thickness", "a real existence"),
             (("NEGATION", "modal", "negation"), ("POSSESSOR", "supplement", "subject"))),
            ("I looked round for the Time Traveller, and—“It’s half-past seven now,” said the Medical Man.",
             INTERRUPTED_CLOCK, ("It’s half-past seven now", "the Medical Man"),
             (("INTERRUPTION", "look", "report"), ("REPORTED_CONTENT", "report", "clock"))),
            ("“But I shouldn’t think she was the sort of girl Gilbert would like,” whispered Jane to Anne.",
             REPORTED_OPINION, ("But I shouldn’t think she was the sort of girl Gilbert would like", "to Anne"),
             (("REPORTED_CONTENT", "report", "opinion"), ("RECIPIENT", "report", "recipient"))),
            ("“Is not that rather a large thing to expect us to begin upon?” said Filby, an argumentative person with red hair.",
             REPORTED_INVERTED_CONTROL, ("Is not that rather a large thing to expect us to begin upon", "Filby"),
             (("REPORTED_CONTENT", "report", "content"), ("APPOSITION", "speaker", "appositive"))),
            ("“To tell you the truth... I hardly believe it myself..... And yet...”",
             HESITANT_ADMISSION, ("To tell you the truth", "I hardly believe it myself", "And yet"),
             (("STANCE", "admission", "preface"), ("DISCOURSE", "admission", "unfinished"))),
            ("“Diana might just have smiled at me once, I think,” she mourned to Marilla that night.",
             REPORTED_REGRET, ("Diana might just have smiled at me once", "I think", "that night"),
             (("REPORTED_CONTENT", "report", "content"), ("STANCE", "content", "stance"),
              ("TIME", "report", "time"))),
            ("“Oh, I must, hey? I rather think Diana did her share of the jumping at least. Such carryings on in a respectable house!”",
             MODAL_ECHO_REBUKE, ("Oh, I must, hey", "I rather think Diana did her share of the jumping at least",
                                 "Such carryings on in a respectable house"),
             (("TAG", "echo", "tag"), ("LOCATION", "conduct", "setting"))),
            ("“Well now, you’ve guessed it! But I reckon Mrs. Spencer described it so’s you could tell.”",
             DIALECTAL_EVIDENCE, ("Well now, you’ve guessed it", "But I reckon Mrs. Spencer described it so’s you could tell"),
             (("RESULT", "description", "result"), ("COMPLEMENT", "belief", "description"))),
            ("“Anne Shirley,” faltered the shrinking child, not daring to make any stipulations regarding the spelling thereof, “and I’m eleven years old.”",
             SPLIT_SELF_IDENTIFICATION, ("Anne Shirley", "the shrinking child", "and I’m eleven years old"),
             (("AGENT", "potential_action", "speaker"), ("REPORTED_CONTENT", "report", "age_statement"))),
            ("“I never would have thought she’d have turned out so well that first day I was here three years ago,” said Mrs. Rachel.",
             DOUBLE_PERFECT_PERSPECTIVE, ("I never would have thought she’d have turned out so well that first day I was here three years ago", "Mrs. Rachel"),
             (("REPORTED_CONTENT", "report", "content"), ("TIME", "content", "perspective"))),
            ("“That,” said a very young man, making spasmodic efforts to relight his cigar over the lamp; “that . . . very clear indeed.”",
             HESITANT_RESUMPTION, ("That", "a very young man", "that . . . very clear indeed"),
             (("RESUMPTION", "abandoned", "resumed"), ("AGENT", "intention", "speaker"))),

        ):
            with self.subTest(source=source):
                _, lattice, result = self._parse(source)
                self.assertTrue(result.completed, result.stats)
                root = result.best()
                self.assertEqual(root.rule_id, expected)
                self.assertEqual((root.start, root.end), (0, len(source)))
                self.assertTrue(set(spans).issubset(self._spans(source, root.children)))
                h, relations = self._semantic(result, lattice)
                for rel, a, b in links:
                    self.assertIn((rel, h[a], h[b]), relations)

    def test_transfer_scoped_positive_variants_and_near_misses(self):
        from seman_parser.scoped_transfer_clauses import (
            CAUSAL_PERFECT, CONTRASTIVE_SERIES, NEGATIVE_PROFORM, NOMINAL_EXCLAMATION,
            PROGRESSIVE_PERCEPTION, PROGRESSIVE_REPORT, RESULTATIVE_PURPOSE,
        )
        from seman_parser.scoped_motion_supplements import APPOSITIVE, CARRY, PARTITIVE_LOCATION, RISE
        from seman_parser.scoped_literary_quotes import INTERRUPTED_CLOCK, NOR_POSSESSION, REPORTED_OPINION
        from seman_parser.spoken_three_acts import NEGATIVE_REPLY, WAIT_QUESTION

        from seman_parser.scoped_literary_quotes import (
            DOUBLE_PERFECT_PERSPECTIVE, HESITANT_ADMISSION, HESITANT_RESUMPTION,
            REPORTED_INVERTED_CONTROL, REPORTED_REGRET, SPLIT_SELF_IDENTIFICATION,
        )
        from seman_parser.scoped_motion_supplements import CAUSATIVE_RESPONSE, COORDINATED_PARTICIPLES, SPELLING_RESULT
        from seman_parser.scoped_transfer_clauses import DASH_REFORMULATION, PARENTHETICAL_PURPOSE
        from seman_parser.spoken_three_acts import DIALECTAL_EVIDENCE, MODAL_ECHO_REBUKE

        for source, expected, accepted in (
            ("A Parker fellowship!", NOMINAL_EXCLAMATION, True),
            ("A Parker walked!", NOMINAL_EXCLAMATION, False),
            ("For his face had suddenly filled with blood.", CAUSAL_PERFECT, True),
            ("For his face had suddenly to fill with blood.", CAUSAL_PERFECT, False),
            ("But none returned.", NEGATIVE_PROFORM, True),
            ("But none developed a plan.", NEGATIVE_PROFORM, False),
            ("She took not a step, but walked slowly to the door, and made a sound.", CONTRASTIVE_SERIES, True),
            ("She said not a word, but left painfully to the table, and made a motion.", CONTRASTIVE_SERIES, False),
            ("He looked into her eyes and, with a sigh, told her she were suffering from overwork, at which she laughed loudly.",
             PROGRESSIVE_REPORT, False),
            ("Then she turned over the hand holding her pipe, and I saw she was looking at a scar.",
             PROGRESSIVE_PERCEPTION, True),
            ("Then she turned over the hand holding her pipe, and I saw she were looking at a scar.",
             PROGRESSIVE_PERCEPTION, False),
            ("But he went away softly, leaving Mary alone to read her book with pleasure.",
             RESULTATIVE_PURPOSE, True),
            ("But he go away softly, leaving Mary alone to read her book with pleasure.",
             RESULTATIVE_PURPOSE, False),
            ("She picked up the lantern quickly, and carried it, glowing blue, through the door into the room.",
             CARRY, True),
            ("She picked up the lantern quickly, and carried it, holding blue, through the door into the room.",
             CARRY, False),
            ("Then, standing up, she went to the table, and with her back to us began to read her book.", RISE, True),
            ("Then, standing up, she went to the table, and with his back to us began to read her book.", RISE, False),
            ("Then Mary’s brothers, the Smiths from London, arrived; they all climbed into the wagon, among hay and woolen blankets.",
             APPOSITIVE, True),
            ("Then Mary’s brothers, the Smiths from London, arrived, they all climbed into the wagon, among hay and woolen blankets.",
             APPOSITIVE, False),
            ("She picked one of the tables that were placed around the room, and put it in front of the door, with two legs on the carpet.",
             PARTITIVE_LOCATION, True),
            ("She picked one of the tables that was placed around the room, and put it in front of the door, with two legs on the carpet.",
             PARTITIVE_LOCATION, False),
            ("“So many people believe. But wait a minute. Could a _different_ result occur?”", WAIT_QUESTION, True),
            ("“So many people believe. But wait a minute. Could a different result occur?”", WAIT_QUESTION, False),
            ("“No, sir. No one had come out that way. She was hoping to meet them there.”", NEGATIVE_REPLY, True),
            ("“No, sir. No one has came out that way. She was hoping to meet them there.”", NEGATIVE_REPLY, False),
            ("“Nor, having only flour, water and salt, could a baker have a real cake.”", NOR_POSSESSION, True),
            ("“Nor, having only flour, water and salt, a baker could have a real cake.”", NOR_POSSESSION, False),
            ("I looked around for Mary, and—“It’s half-past six now,” said John.", INTERRUPTED_CLOCK, True),
            ("I looked around for Mary, and—“It’s half-past thirteen now,” said John.", INTERRUPTED_CLOCK, False),
            ("“But I wouldn’t think it was the sort of book Mary would choose,” whispered Jane to Anne.",
             REPORTED_OPINION, True),
            ("“But I wouldn’t think it was the sort of book Mary would choose it,” whispered Jane to Anne.",
             REPORTED_OPINION, False),
            ("(The Doctor, to prove that he was not afraid, helped himself to a drink and tried to eat it raw.)",
             PARENTHETICAL_PURPOSE, True),
            ("(The Doctor, to prove that he was not afraid, helped herself to a drink and tried to eat it raw.)",
             PARENTHETICAL_PURPOSE, False),
            ("Mary Smith spelt him down in class and left him far out of sight in written arithmetic.",
             SPELLING_RESULT, True),
            ("Mary Smith spelt him down in class and left her far out of sight in written arithmetic.",
             SPELLING_RESULT, False),
            ("Miss Smith suddenly shouted—a sound which caused Mary, sitting in great fear in the room upstairs, to utter a cry.",
             CAUSATIVE_RESPONSE, True),
            ("Miss Smith suddenly shouted—a sound which caused Mary, sitting in great fear in the room upstairs, uttered a cry.",
             CAUSATIVE_RESPONSE, False),
            ("“Was not this quite a heavy task to expect them to begin on?” said Mary, a girl with black hair.",
             REPORTED_INVERTED_CONTROL, True),
            ("“Was not this quite a heavy task to expect they to begin on?” said Mary, a girl with black hair.",
             REPORTED_INVERTED_CONTROL, False),
            ("“To tell you the truth... I scarcely believe it myself... And yet...”", HESITANT_ADMISSION, True),
            ("“To tell you the truth... I scarcely believe it himself... And yet...”", HESITANT_ADMISSION, False),
            ("“Mary could just have smiled at us twice, I suppose,” she mourned to John that morning.",
             REPORTED_REGRET, True),
            ("“Mary could just have smiled at us twice, I suppose,” she mourned him that morning.",
             REPORTED_REGRET, False),
            ("“Oh, I should, eh? I rather think Mary did her share of the shouting at least. Such carryings on in a quiet room!”",
             MODAL_ECHO_REBUKE, True),
            ("“Oh, I should, eh? I rather think Mary did her share of the shouting at least. Such carryings on in a quiet room.”",
             MODAL_ECHO_REBUKE, False),
            ("“Well now, you’ve guessed it! But I suppose Mr. Brown explained it so’s we might understand.”",
             DIALECTAL_EVIDENCE, True),
            ("“Well now, you’ve guessed it! But I suppose Mr. Brown explained it so’s we might understand it.”",
             DIALECTAL_EVIDENCE, False),
            ("“Mary Brown,” stammered the trembling girl, not daring to make any comments regarding the pronunciation thereof, “and I’m twelve years old.”",
             SPLIT_SELF_IDENTIFICATION, True),
            ("“Mary Brown,” stammered the trembling girl, not daring to make any comments regarding the pronunciation thereof, “and I’m twelve year old.”",
             SPLIT_SELF_IDENTIFICATION, False),
            ("In setting it down I feel with only too much sadness the failure of speech—and, above all, my own failure—to describe its beauty.",
             DASH_REFORMULATION, True),
            ("In setting it down I feel with only too much sadness the failure of speech—and, above all, my own inability—to describe its beauty.",
             DASH_REFORMULATION, False),
            ("“I never would have guessed he’d have turned out so badly that second morning I was there four months ago,” replied Mr. Smith.",
             DOUBLE_PERFECT_PERSPECTIVE, True),
            ("“I never would have guessed he’d have turned out so badly that second morning I was there four month ago,” replied Mr. Smith.",
             DOUBLE_PERFECT_PERSPECTIVE, False),
            ("“This,” said a very young girl, making desperate efforts to light her pipe over the fire; “this . . . very simple indeed.”",
             HESITANT_RESUMPTION, True),
            ("“This,” said a very young girl, making desperate efforts to light her pipe over the fire; “that . . . very simple indeed.”",
             HESITANT_RESUMPTION, False),
            ("Mary lit the candle, upsetting the box and using up half a dozen matches before her trembling fingers could finish the task.",
             COORDINATED_PARTICIPLES, True),
            ("Mary lit the candle, upsetting the box and using up half a dozen matches before her trembling fingers finished.",
             COORDINATED_PARTICIPLES, False),
        ):
            with self.subTest(source=source, expected=expected):
                _, _, result = self._parse(source)
                root = result.best()
                self.assertEqual(root is not None and root.rule_id == expected, accepted)


if __name__ == "__main__":
    unittest.main()
