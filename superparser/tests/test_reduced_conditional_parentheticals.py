"""Generic reduced-condition incises and clausal subject focus (novel #438).

All examples use the public Parser; the frozen case passes through the
canonical quote-balancing corpus gateway. Typed lexical views are additive.
"""

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser


DATA = Path(__file__).resolve().parents[1] / "data"


def descendants(node):
    yield node
    for child in node.children:
        yield from descendants(child)


def unique_rule(root, rule_id):
    found = [n for n in descendants(root) if n.rule_id == rule_id]
    if len(found) != 1:
        raise AssertionError(f"Expected exactly one {rule_id}, got {len(found)}")
    return found[0]


def span_text(result, node):
    return result.text[node.start:node.end]


class ReducedConditionalParentheticalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA)

    def test_pinned_438_rank_one_has_precise_vocative_focus_and_valence(self):
        case = select_cases(500)[0][438]
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000)
        self.assertEqual(prepared.analysis_text, case["balanced_analysis_text"])
        self.assertEqual(prepared.source_text, case["source_text"])
        self.assertTrue(result.completed, result.stats)
        self.assertFalse(result.stats["budget_exceeded"])
        self.assertFalse(result.stats["kbest_budget_exceeded"])
        root = result.best()
        self.assertEqual(root.rule_id, "dialogue_unattributed")
        self.assertEqual((root.start, root.end), (0, len(prepared.analysis_text)))
        self.assertEqual(root.children[0].rule_id, "dialogue_quote_clause_comma")

        spoken = unique_rule(root, "dialogue_discourse_vocative_clause")
        self.assertEqual([span_text(result, n) for n in spoken.children[:4]],
                         ["Now", ",", "Mrs. Hawkins", ","])
        self.assertEqual(spoken.children[2].rule_id, "np_honorific_abbreviation")

        focused = spoken.children[4]
        self.assertEqual(focused.rule_id, "clause_preposed_subject_focus")
        self.assertEqual(focused.features.as_dict()["focus_scope"], "subject")
        focus, subject, coordinated = focused.children
        self.assertEqual((focus.category, span_text(result, focus)),
                         ("ADV-PREPOSED-SUBJECT-FOCUS", "just"))
        self.assertEqual((subject.rule_id, span_text(result, subject)),
                         ("np_indef_pron", "you"))
        self.assertEqual(coordinated.rule_id, "vp_coord_finite")
        left, coordinator, right = coordinated.children
        self.assertEqual(span_text(result, left),
                         "run upstairs to your husband")
        self.assertEqual(span_text(result, coordinator), "and")
        self.assertEqual(left.rule_id, "vp_prepositional")
        self.assertEqual(span_text(result, left.children[1]),
                         "upstairs to your husband")
        self.assertEqual(left.children[1].children[1].rule_id, "pp_prep_np")

        self.assertEqual(right.rule_id, "vp_ditransitive_internal_conditional")
        verb, recipient, supplement, theme = right.children
        self.assertEqual(span_text(result, verb), "tell")
        self.assertEqual(verb.category, "V-DITRANSITIVE-CONDITIONAL")
        self.assertEqual((recipient.rule_id, span_text(result, recipient)),
                         ("np_indef_pron", "him"))
        self.assertEqual((supplement.rule_id, span_text(result, supplement)),
                         ("parenthetical_reduced_conditional_adjective",
                          ", if possible,"))
        self.assertEqual([span_text(result, c) for c in supplement.children],
                         [",", "if", "possible", ","])
        self.assertEqual(supplement.features.as_dict()["conditional"], "true")
        self.assertEqual((theme.rule_id, span_text(result, theme)),
                         ("np_pp_mod", "nothing about it"))
        self.assertEqual((theme.children[0].rule_id,
                          span_text(result, theme.children[0])),
                         ("np_indef_pron", "nothing"))
        self.assertEqual((theme.children[1].rule_id,
                          span_text(result, theme.children[1])),
                         ("pp_prep_np", "about it"))

        # Additive views preserve the original lexical analyses, sense ids,
        # source, and exact character offsets; no token is rewritten.
        for typed in ("ADV-PREPOSED-SUBJECT-FOCUS",
                      "V-DITRANSITIVE-CONDITIONAL",
                      "COMMA-REDUCED-CONDITIONAL"):
            for view in (c for c in lattice.candidates if c.category == typed):
                original_cat = {"ADV-PREPOSED-SUBJECT-FOCUS": "ADV",
                                "V-DITRANSITIVE-CONDITIONAL": "V",
                                "COMMA-REDUCED-CONDITIONAL": "COMMA"}[typed]
                self.assertTrue(any(
                    c.category == original_cat and c.span == view.span
                    and c.source == view.source and c.sense_ids == view.sense_ids
                    for c in lattice.candidates
                ))

    def test_independent_verbs_adjectives_names_and_subject_focus(self):
        examples = (
            ('"Now, Mr. Watson, just you go home and give her, '
             'if necessary, the letter."', "Mr. Watson", "give", "necessary", "the letter"),
            ('"Only you tell her, if possible, the truth."',
             None, "tell", "possible", "the truth"),
            ('"Just you tell her, if convenient, the truth."',
             None, "tell", "convenient", "the truth"),
        )
        for text, vocative, verb_text, adjective, theme_text in examples:
            with self.subTest(text=text):
                report = self.parser.parse(
                    text, max_items=50_000, kbest_work_limit=500_000)
                result = report.result
                self.assertTrue(result.completed, result.stats)
                self.assertFalse(result.stats["budget_exceeded"])
                root = result.best()
                focused = unique_rule(root, "clause_preposed_subject_focus")
                self.assertEqual(span_text(result, focused.children[1]), "you")
                verb, recipient, incise, theme = unique_rule(
                    root, "vp_ditransitive_internal_conditional").children
                self.assertEqual(span_text(result, verb), verb_text)
                self.assertEqual(span_text(result, recipient), "her")
                self.assertEqual(span_text(result, incise),
                                 f", if {adjective},")
                self.assertEqual(span_text(result, theme), theme_text)
                if vocative:
                    self.assertEqual(span_text(result, unique_rule(
                        root, "dialogue_discourse_vocative_clause").children[2]),
                        vocative)

    def test_missing_comma_conjunction_recipient_or_ditransitive_is_rejected(self):
        negatives = (
            '"Just you tell her, possible, the truth."',
            '"Just you tell her if possible the truth."',
            '"Just you sleep, if possible, the truth."',
            '"Just you tell, if possible, the truth."',
        )
        for text in negatives:
            with self.subTest(text=text):
                result = self.parser.parse(
                    text, max_items=50_000, kbest_work_limit=500_000).result
                self.assertFalse(any(
                    node.rule_id in {"vp_ditransitive_internal_conditional",
                                     "parenthetical_reduced_conditional_adjective"}
                    for root in result.alternatives(limit=3)
                    for node in descendants(root)))

    def test_359_dialogue_witness_does_not_start_new_grammar_rules(self):
        case = select_cases(500)[0][359]
        _, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000)
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.best().rule_id, "dialogue_unattributed")
        self.assertEqual(result.stats["forest_nodes"], 1472)
        self.assertEqual(result.stats["recognition_operations"], 49842)
        self.assertFalse(any(
            c.category in {"COMMA-REDUCED-CONDITIONAL",
                           "V-DITRANSITIVE-CONDITIONAL",
                           "ADV-PREPOSED-SUBJECT-FOCUS"}
            for c in lattice.candidates))


if __name__ == "__main__":
    unittest.main()
