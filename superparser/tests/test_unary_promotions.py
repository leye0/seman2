"""Research-only auto promotion: no sentence-specific grammar patches."""
from pathlib import Path
import unittest

from seman_parser.grammar import Grammar, parse_rule, load_grammar
from research.verbnet_lr.unary_promotions import (
    propose_unary_head_promotions, with_unary_head_promotions,
)


def rule(name, lhs, *rhs):
    return parse_rule({
        "id": name, "lhs": {"category": lhs},
        "rhs": [{"category": x} for x in rhs], "score": 1.0,
    })


class UnaryPromotionTests(unittest.TestCase):
    def test_only_missing_lexical_head_phrase_rules(self):
        grammar = Grammar((
            rule("np_n", "NP", "N"),
            rule("vp_v", "VP", "V"),
            rule("adjp_adj", "ADJP", "ADJ"),
            rule("advp_adv_adv", "ADVP", "ADV", "ADV"),
            rule("pp_prep_np", "PP", "PREP", "NP"),
            rule("n_adjn", "N", "ADJ", "N"),
            rule("adj_comp", "ADJ", "DEGREE", "ADJ"),
        ))
        suggestions = propose_unary_head_promotions(grammar)
        self.assertEqual(
            [(r.lhs.category, tuple(x.category for x in r.rhs)) for r in suggestions],
            [("ADVP", ("ADV",))],
        )
        self.assertTrue(all(r.provenance["requires_validation"] for r in suggestions))
        new, new_rules = with_unary_head_promotions(grammar)
        self.assertEqual(len(new.rules), len(grammar.rules) + 1)
        self.assertEqual(new_rules, suggestions)
        self.assertEqual(len(grammar.rules), 7)

    def test_existing_direct_unary_never_duplicated(self):
        grammar = Grammar((
            rule("existing", "ADVP", "ADV"),
            rule("composed", "ADVP", "ADV", "ADV"),
        ))
        self.assertEqual(propose_unary_head_promotions(grammar), ())

    def test_actual_grammar_has_only_expected_proposal(self):
        source = Path(__file__).resolve().parents[1] / "data" / "grammar.jsonl"
        grammar = load_grammar(source)
        additions = propose_unary_head_promotions(grammar)
        self.assertEqual([(r.lhs.category, r.rhs[0].category) for r in additions],
                         [("ADVP", "ADV")])


if __name__ == "__main__":
    unittest.main()
