"""Gold evaluation and atomic-composition tests independent of external models."""
import unittest

from research.typed_resource_poc.core import Word
from research.typed_resource_poc.composition import (
    compose_adjective_projections, composition_gold_keys,
)
from research.typed_resource_poc.evaluation import (
    GoldSentence, compare_to_gold, observation_keys, read_conllu,
)


def word(i, text, pos, head, rel):
    return Word(i, text, text.lower(), pos, head, rel)


class AtomicCompositionTests(unittest.TestCase):
    def test_modifier_plus_pp_preserves_adjective_head_and_does_not_claim_valence(self):
        words = (
            word(1, "extremely", "ADV", 2, "advmod"),
            word(2, "averse", "ADJ", 0, "root"),
            word(3, "to", "ADP", 4, "case"),
            word(4, "delay", "NOUN", 2, "obl"),
        )
        result, = compose_adjective_projections(
            words, {"source": "UD_train", "patterns": {
                "adjective_to_pp_candidate": {"averse": 2}}})
        self.assertEqual(result.lexical_head_id, 2)
        self.assertEqual(result.features["HEAD"]["pos"], "ADJ")
        self.assertEqual(
            [o.kind for o in result.operations],
            ["head_modifier", "head_pp_attachment_candidate"])
        self.assertEqual(result.lexical_hypotheses[0]["type"],
                         "adjective-with-to-pp")
        self.assertEqual(result.lexical_hypotheses[0]["ud_train_attestation"]
                         ["attestation_count"], 2)
        self.assertFalse(result.lexical_hypotheses[0]["selected_complement_proven"])

    def test_infinitive_contrasts_with_pp(self):
        words = (
            word(1, "happy", "ADJ", 0, "root"),
            word(2, "to", "PART", 3, "mark"),
            word(3, "help", "VERB", 1, "xcomp"),
        )
        result, = compose_adjective_projections(words)
        self.assertEqual([o.kind for o in result.operations],
                         ["head_infinitival_attachment_candidate"])
        self.assertEqual(result.lexical_hypotheses[0]["type"],
                         "adjective-with-to-infinitive")

    def test_unrelated_to_phrase_does_not_fill_valence(self):
        words = (
            word(1, "averse", "ADJ", 0, "root"),
            word(2, "to", "ADP", 4, "case"),
            word(3, "delay", "NOUN", 4, "compound"),
            word(4, "event", "NOUN", 1, "parataxis"),
        )
        self.assertEqual(compose_adjective_projections(words), ())

    def test_same_operations_apply_to_any_lexeme(self):
        words = (
            word(1, "remarkably", "ADV", 2, "advmod"),
            word(2, "prone", "ADJ", 0, "root"),
            word(3, "to", "ADP", 4, "case"),
            word(4, "errors", "NOUN", 2, "obl"),
        )
        result, = compose_adjective_projections(words)
        self.assertEqual(result.lexical_head_lemma, "prone")
        self.assertEqual(len(result.operations), 2)
        self.assertFalse(result.lexical_hypotheses[0]["selected_complement_proven"])


class HeldOutGoldTests(unittest.TestCase):
    def test_reader_skips_ud_multiword_surface_and_enhanced_empty_nodes(self):
        example = "\n".join([
            "# sent_id = unit_1", "# text = We do not.",
            "1\tWe\twe\tPRON\t_\t_\t2\tnsubj\t_\t_",
            "2-3\tdon't\t_\t_\t_\t_\t_\t_\t_\t_",
            "2\tdo\tdo\tAUX\t_\t_\t0\troot\t_\t_",
            "3\tnot\tnot\tPART\t_\t_\t2\tadvmod\t_\t_",
            "4\t.\t.\tPUNCT\t_\t_\t2\tpunct\t_\t_",
        ])
        s, = read_conllu(example)
        self.assertEqual(s.sent_id, "unit_1")
        self.assertEqual(len(s.tokens), 4)
        self.assertEqual(s.tokens[0].text, "We")

    def test_exact_scores_and_relation_p_r_have_gold_denominator(self):
        gold_words = (
            word(1, "very", "ADV", 2, "advmod"),
            word(2, "averse", "ADJ", 0, "root"),
            word(3, "to", "ADP", 4, "case"),
            word(4, "delay", "NOUN", 2, "obl"),
        )
        gold = [GoldSentence("x", gold_words, "very averse to delay")]
        pred = [(
            word(1, "very", "ADV", 2, "advmod"),
            word(2, "averse", "ADJ", 0, "root"),
            word(3, "to", "ADP", 4, "case"),
            word(4, "delay", "NOUN", 2, "obj"),
        )]
        o = compare_to_gold(gold, pred)
        self.assertEqual(o["metrics"]["strict_uas_all"], 1.0)
        self.assertEqual(o["metrics"]["strict_las_all"], .75)
        self.assertEqual(o["adjectival_relations"]["adjective_adverb_modification"]["f1"],1.0)
        self.assertEqual(o["adjectival_relations"]["adjective_to_pp_candidate"]["recall"],0.0)

    def test_unaligned_sentence_does_not_disappear_from_metrics(self):
        gold_words = (word(1, "beautiful", "ADJ", 0, "root"),)
        gold = [GoldSentence("x", gold_words, "beautiful")]
        observed = compare_to_gold(gold, [()])
        self.assertEqual(observed["metrics"]["strict_uas_all"],0.0)
        self.assertEqual(observed["counts"]["unaligned_gold_tokens"],1)
        self.assertEqual(observed["metrics"]["alignment_rate"],0.0)


if __name__ == "__main__":
    unittest.main()
