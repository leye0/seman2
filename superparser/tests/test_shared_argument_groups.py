from __future__ import annotations

import os
from pathlib import Path
import signal
import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts import novel_source_reporting_v3 as novel
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources


class SharedArgumentGroupsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(
            ROOT / "data", wordnet_dict=Path(os.environ["WORDNET_DICT"]),
        ), cache_size=0, max_items=50_000)
        cls.parser.parse("John opened the box.")
        _, groups, _ = novel.prepare()
        cls.cases = {c["transfer_id"]: c for name, (_, rows) in groups.items()
                     if name != "witnesses" for c in rows}
        original = signal.signal(signal.SIGALRM, _deadline)
        cls.addClassCleanup(signal.signal, signal.SIGALRM, original)

    def graph(self, case):
        result = measure(self.parser, case, with_semantics=True)
        self.assertEqual(result["status"], "complete", case["source_text"])
        graph = result["selected_graph"]["graph"]
        nodes = {node["id"]: tuple(node["span"]) for node in graph["nodes"] if node["span"]}
        return {(edge["relation"], nodes[edge["source"]], nodes[edge["target"]])
                for edge in graph["relations"] if edge["source"] in nodes and edge["target"] in nodes}

    def independent(self, text):
        book = Book(99010, "Independent argument scope controls", "Audit", "syntax")
        cases, _ = extract(book, text, length_min=1, length_max=120)
        self.assertEqual([r["source_text"] for r in cases], [text])
        return self.graph(cases[0])

    @staticmethod
    def edge(text, relation, source, target):
        def span(part):
            start = text.index(part)
            return start, start + len(part)

        return relation, span(source), span(target)

    def assert_links(self, graph, text, expected):
        for role, source, target in expected:
            self.assertIn(self.edge(text, role, source, target), graph, text)

    def test_two_and_three_finite_predicates_share_one_overt_subject(self):
        for text, subject, events in (
            ("The sailor shouted and rang the bell.", "sailor", ("shouted", "rang")),
            ("The child shouted, sang, and danced.", "child", ("shouted", "sang", "danced")),
        ):
            with self.subTest(text=text):
                graph = self.independent(text)
                self.assert_links(graph, text, [("SUBJECT", v, subject) for v in events])
                self.assert_links(graph, text, [("CONJUNCT", events[0], v) for v in events[1:]])
                if len(events) == 3:
                    self.assertNotIn(self.edge(text, "CONJUNCT", events[1], events[2]), graph)

    def test_finite_carrier_is_not_the_lexical_owner(self):
        for text, predicate, helper in (
            ("The sailor shouted and could swim.", "swim", "could"),
            ("The sailor shouted and was singing.", "singing", "was"),
            ("The sailor had departed and returned in silence.", "departed", "had"),
        ):
            with self.subTest(text=text):
                graph = self.independent(text)
                self.assert_links(graph, text, [("SUBJECT", predicate, "sailor")])
                self.assertNotIn(self.edge(text, "SUBJECT", helper, "sailor"), graph)

    def test_same_contract_binds_the_overt_antecedent_of_a_subject_relative(self):
        for text, head, marker, predicate in (
            ("The sailor who rang the bell departed.", "sailor", "who", "rang"),
            ("The child that broke the glass ran.", "child", "that", "broke"),
            ("A clerk who had locked the door answered.", "clerk", "who", "locked"),
        ):
            with self.subTest(text=text):
                graph = self.independent(text)
                self.assert_links(graph, text, [("SUBJECT", predicate, head),
                                               ("RELATIVE_REF", marker, head)])
                self.assertNotIn(self.edge(text, "SUBJECT", predicate, marker), graph)
                if "had" in text:
                    self.assertNotIn(self.edge(text, "SUBJECT", "had", head), graph)

    def test_different_subjects_nonfinite_control_and_passive_do_not_inherit(self):
        for text, predicate, wrong_subject in (
            ("She told him to wait and listen.", "listen", "She"),
            ("She helped and he left.", "left", "She"),
            ("The bell broke and was replaced.", "replaced", "bell"),
        ):
            with self.subTest(text=text):
                graph = self.independent(text)
                self.assertNotIn(self.edge(text, "SUBJECT", predicate, wrong_subject), graph)

    def test_relative_contrasts_are_not_local_subject_gaps(self):
        for text in (
            "I know what happened.",
            "The sailor, who rang the bell, departed.",
            "The sailor at the gate who rang the bell departed.",
            "I spoke to them that lived beyond the river.",
            "A clerk who had a key answered.",
        ):
            with self.subTest(text=text):
                self.assertFalse(any(role == "RELATIVE_REF" for role, _, _ in self.independent(text)))

    def test_literal_source_boundary_and_full_name_are_not_guessed(self):
        for text, predicate, target in (
            ("The old boat rocked; and fell into the water.", "fell", "boat"),
            ("Miss Clara listened, and returned.", "returned", "Miss"),
        ):
            with self.subTest(text=text):
                self.assertNotIn(self.edge(text, "SUBJECT", predicate, target),
                                 self.independent(text))

    def test_exact_novel_sources_in_four_books(self):
        for index, edges in (
            (56, (("SUBJECT", "changed", "He"), ("SUBJECT", "wetted", "He"))),
            (129, (("SUBJECT", "looked", "Elizabeth"), ("SUBJECT", "turned", "Elizabeth"))),
            (786, (("SUBJECT", "went", "Jane"), ("SUBJECT", "kissed", "Jane"),
                   ("SUBJECT", "thanked", "Jane"))),
            (818, (("SUBJECT", "weighed", "load"), ("RELATIVE_REF", "that", "load"))),
            (833, (("SUBJECT", "praying", "Dick"),)),
            (846, (("SUBJECT", "loosed", "coxswain"), ("SUBJECT", "plunged", "coxswain"))),
        ):
            with self.subTest(index=index):
                case = self.cases[f"Q3-{index}"]
                self.assert_links(self.graph(case), case["source_text"], edges)

    def test_exact_novel_contrasts_cover_bad_scope_not_only_surface_patterns(self):
        for index, predicate, subject in (
            (407, "leave", "He"), (431, "lightened", "heart"), (449, "skulk", "It"),
            (454, "looked", "we"), (460, "land", "it"), (472, "carried", "it"),
            (831, "fitted", "ship"), (369, "fill", "secret"),
        ):
            with self.subTest(index=index):
                case = self.cases[f"Q3-{index}"]
                graph = self.graph(case)
                self.assertNotIn(self.edge(case["source_text"], "SUBJECT", predicate, subject), graph)
