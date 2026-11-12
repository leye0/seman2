"""Source-true selected-tree tests for the 422-baseline multi-family batch.

Do not count a successful fragment as a full correction. Enforce original
500-case source strings, public parse_corpus_case route and rank-one trees.
"""
from __future__ import annotations
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import Parser
from scripts.diagnose_novel_parses import select_cases

DATA = Path(__file__).resolve().parents[1] / "data"


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


class Batch422GrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)
        cls.cases = select_cases(500)[0]

    def actual(self, index, source):
        case = self.cases[index]
        self.assertEqual(case["source_text"], source)
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000,
            kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.source_text, source)
        self.assertEqual(prepared.analysis_text, source)
        self.assertEqual(lattice.text, source)
        self.assertEqual(result.text, source)
        self.assertTrue(result.completed, (index, result.stats))
        self.assertIsNotNone(result.best())
        return result

    def selected(self, result, rule, surface=None):
        matches = [n for n in walk(result.best()) if n.rule_id == rule]
        self.assertTrue(matches, (rule, result.stats))
        if surface is not None:
            matches = [n for n in matches
                       if result.text[n.start:n.end] == surface]
            self.assertTrue(matches, (rule, surface, result.stats))
        return matches[0]

    def test_41_curly_aint_negative_copular_echo_and_reporter(self):
        source = "‘Ain’t I what?’ said the gentleman behind."
        result = self.actual(41, source)
        question = self.selected(
            result, "clause_copular_echo_predicate_wh_question",
            "Ain’t I what?",
        )
        self.assertEqual(
            [source[n.start:n.end] for n in question.children],
            ["Ain’t", "I", "what", "?"],
        )
        self.assertEqual(question.children[0].features.as_dict()
                         .get("negation"), "true")
        self.assertTrue(any(
            n.category == "SPEECH-TAG" and
            source[n.start:n.end] == "said the gentleman behind"
            for n in walk(result.best())
        ))

    def test_175_absolute_intransitive_doubt_in_shared_subject_coordination(self):
        source = ("Elizabeth listened, wondered, doubted, "
                  "and was impatient for more.")
        result = self.actual(175, source)
        self.selected(result, "clause_np_vp", source[:-1])
        member = self.selected(result, "vp_intransitive", "doubted")
        self.assertEqual(member.children[0].features.as_dict()
                         .get("subcat"), "intransitive")
        self.assertEqual(member.children[0].features.as_dict()
                         .get("vform"), "finite")
        self.assertTrue(any(
            n.rule_id in ("vp_finite_comma_coord_shared_subject",
                          "vp_comma_coord")
            for n in walk(result.best())
        ))

    def test_315_classifying_copular_pp_and_nominal_predicate(self):
        source = ("I am by birth a Genevese, and my family is one of "
                  "the most distinguished of that republic.")
        result = self.actual(315, source)
        vp = self.selected(result, "vp_cop_classifier_pp_nominal",
                           "am by birth a Genevese")
        self.assertEqual([n.category for n in vp.children],
                         ["COPULA", "PP", "NP"])
        self.assertEqual(
            [source[n.start:n.end] for n in vp.children],
            ["am", "by birth", "a Genevese"],
        )
        self.assertEqual(vp.children[1].rule_id,
                         "pp_classifier_by_nominal")
        self.assertEqual(vp.children[2].rule_id, "np_det_n")

    def test_384_contracted_modal_licenses_overt_zero_finite_complement(self):
        source = "\"You'll find I do my duty.\""
        result = self.actual(384, source)
        root = self.selected(
            result, "dialogue_structural_quoted_modal_zero_clausal_complement",
            source,
        )
        self.assertEqual([n.category for n in root.children],
                         ["OPEN-QUOTE", "NP", "MODAL", "V", "CLAUSE",
                          "SPEECH-STOP", "CLOSE-QUOTE"])
        self.assertEqual(
            [source[n.start:n.end] for n in root.children],
            ['"', "You", "'ll", "find", "I do my duty", ".", '"'],
        )
        self.assertEqual(root.children[1].children[0].rule_id,
                         "np_indef_pron")
        self.assertEqual(root.children[3].features.as_dict().get("vform"),
                         "base")
        self.assertEqual(root.children[3].features.as_dict().get("subcat"),
                         "clausal")
        self.assertEqual(root.children[4].children[0].category, "CLAUSE")
        self.assertTrue(result.stats["structural_composition"])
        self.assertTrue(result.stats["dialogue_scoped"])
        self.assertEqual(result.stats["structural_segment_count"], 2)

    def test_independent_positives(self):
        scenarios = (
            ("Ain't she what?", "clause_copular_echo_predicate_wh_question"),
            ("He is by trade a carpenter.", "vp_cop_classifier_pp_nominal"),
            ("Mary hesitated, wondered, doubted, and smiled.",
             "vp_intransitive"),
            ("\"She'll believe the train left.\"",
             "dialogue_structural_quoted_modal_zero_clausal_complement"),
        )
        for source, rule in scenarios:
            with self.subTest(source=source):
                extracted, _ = extract(Book(999, "Grammar", "Test", "train"),
                                       source, length_min=1, length_max=80)
                self.assertEqual(len(extracted), 1)
                _, _, result = parse_corpus_case(
                    self.parser, extracted[0], max_items=50_000,
                    kbest_work_limit=500_000,
                )
                self.assertTrue(result.completed, (source, result.stats))
                target = [n for n in walk(result.best()) if n.rule_id == rule]
                self.assertTrue(target, (source, rule))
                if source.startswith("Mary"):
                    self.assertTrue(any(
                        source[n.start:n.end] == "doubted"
                        for n in target
                    ))

    def test_negative_controls(self):
        scenarios = (
            ("Ain't I certain?", "clause_copular_echo_predicate_wh_question"),
            ("He is by chance a carpenter.", "vp_cop_classifier_pp_nominal"),
            ("Mary hesitated, wondered, doubted, and slowly.", "clause_np_vp"),
            ("\"She'll vanish the train left.\"",
             "dialogue_structural_quoted_modal_zero_clausal_complement"),
        )
        for source, rule in scenarios:
            with self.subTest(source=source):
                extracted, _ = extract(Book(999, "Grammar", "Test", "train"),
                                       source, length_min=1, length_max=80)
                self.assertEqual(len(extracted), 1)
                _, _, result = parse_corpus_case(
                    self.parser, extracted[0], max_items=50_000,
                    kbest_work_limit=500_000,
                )
                for candidate in result.alternatives(limit=8):
                    for node in walk(candidate):
                        if node.rule_id == rule:
                            self.fail(f"Unlicensed {rule} for {source}")


if __name__ == "__main__":
    unittest.main()
