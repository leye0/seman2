"""P3: explanations are deterministic renderings of actual grammar evidence.

These tests are WordNet-independent; corpus offsets and complete parse status
remain owned by the existing public diagnostic contract.
"""
from __future__ import annotations

import unittest

from seman_parser.nonstandard import UsageDeviation, collect_usage_deviations
from superparser.tests.test_usage_diagnostic_contract import leaf, reporting_tag


def witness(*, feature="number", expected="plural", observed="singular",
            subject="they", predicate="says", relation="speaker_to_reporting_verb",
            head_surface=None, head_features=None):
    return UsageDeviation(
        kind=f"subject_verb_{feature}_agreement",
        relation=relation, rule_id="test_explicit_marked_rule",
        parent_span=(0, 9), subject_span=(5, 9), predicate_span=(0, 4),
        subject_surface=subject, predicate_surface=predicate,
        feature=feature, expected=expected, observed=observed,
        subject_features={feature: expected},
        predicate_features={feature: observed},
        register="unknown", intent="unknown",
        predicate_head_span=(0, 2) if head_surface else None,
        predicate_head_surface=head_surface,
        predicate_head_features=head_features,
    )


class ProofDerivedExplanationsTests(unittest.TestCase):
    def test_number_with_inverted_reporting_tag_is_fully_evidenced(self):
        text = "says they"
        root = reporting_tag(0, 9, leaf(5, 9, "NP", "plural"),
                             leaf(0, 4, "V", "singular"), inverted=True)
        result = collect_usage_deviations(root, text)[0].as_dict()
        self.assertEqual(result["explanation"],
                         "In this parse, the subject 'they' is plural, "
                         "while the reporting verb 'says' is singular; "
                         "the marked rule records a number mismatch.")
        self.assertEqual(result["explanation_language"], "en")
        self.assertEqual(result["expected"], "plural")
        self.assertEqual(result["observed"], "singular")
        self.assertEqual(result["intent"], "unknown")

    def test_person_conflict_uses_only_lexically_licensed_head(self):
        evidence = witness(feature="person", expected="3", observed="1",
                           subject="She", predicate="am happy",
                           relation="subject_to_finite_predicate",
                           head_surface="am",
                           head_features={"person": "1", "vform": "finite"})
        rendered = evidence.as_dict()
        self.assertEqual(rendered["explanation"],
                         "In this parse, the subject 'She' is third person, "
                         "while the finite verb 'am' is first person; "
                         "the marked rule records a person mismatch.")
        self.assertEqual(rendered["intent"], "unknown")

    def test_unproven_head_does_not_replace_visible_predicate(self):
        evidence = witness(feature="person", expected="3", observed="1",
                           subject="She", predicate="am happy",
                           relation="subject_to_finite_predicate",
                           head_surface="am",
                           head_features={"person": "3", "vform": "finite"})
        text = evidence.explanation()
        self.assertIn("predicate 'am happy' is first person", text)
        self.assertNotIn("finite verb 'am'", text)

    def test_unknown_feature_uses_exact_values_without_language_inference(self):
        evidence = witness(feature="morph", expected="finite", observed="ed",
                           subject="this", predicate="gone",
                           relation="subject_to_predicate")
        self.assertEqual(evidence.explanation(),
                         "In this parse, the subject 'this' has morph='finite', "
                         "while the predicate 'gone' has morph='ed'; "
                         "the marked rule records a morph mismatch.")


if __name__ == "__main__":
    unittest.main()
