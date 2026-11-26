"""Independent grammatical contracts for the multi-resource POC."""
import unittest
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from research.typed_resource_poc.resources import load_verbnet
from research.typed_resource_poc.core import (
    TYPES, TypeConflict, TypeDef, TypeHierarchy, Word, classify_attestation,
    grammatical_observations, induce_evidence, nonwhitespace_coverage,
    unify, validate_dependency_tree,
)


class FeatureSystemTests(unittest.TestCase):
    def test_inherited_adjective_valence(self):
        typ = TYPES.effective("adjective-with-to-pp")
        self.assertEqual(typ["HEAD"]["pos"], "ADJ")
        self.assertEqual(typ["VALENCE"], {"category": "PP", "preposition": "to"})
        self.assertNotEqual(typ["VALENCE"], TYPES.effective("adjective-with-to-infinitive")["VALENCE"])

    def test_general_adjective_modifier_is_not_necessarily_degree(self):
        general = TYPES.effective("adjective-modifying-adverb")
        self.assertEqual(general["MODIFIES"], "ADJ")
        self.assertNotIn("DEGREE", general)
        self.assertTrue(TYPES.effective("degree-adverb")["DEGREE"])

    def test_compiled_verbnet_frames_provide_lexical_class_candidates(self):
        sample = {"schema": "test", "frames": [
            {"lemma": "abandon", "class": "leave-51.2", "symbols": [["NP"]], "roles": ["Source"]},
            {"lemma": "abandon", "class": "leave-51.2", "symbols": [["NP", "NP"]], "roles": ["Source"]},
            {"lemma": "leave", "class": "escape-51.1", "symbols": [], "roles": []},
        ]}
        with TemporaryDirectory() as folder:
            path = Path(folder) / "verbnet.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as out:
                json.dump(sample, out)
            loaded = load_verbnet(path)
        self.assertEqual(loaded["frame_count"], 3)
        self.assertEqual(loaded["lemma_count"], 2)
        self.assertEqual(loaded["lemmas"]["abandon"], ["leave-51.2"])
        self.assertEqual(loaded["lemmas"]["leave"], ["escape-51.1"])

    def test_unification_rejects_incompatible_claims(self):
        with self.assertRaises(TypeConflict):
            unify(TYPES.effective("adjective-with-to-pp"),
                  TYPES.effective("adjective-with-to-infinitive"))

    def test_inheritance_cycle_is_detected(self):
        with self.assertRaises(TypeConflict):
            TypeHierarchy([TypeDef("a", ("b",), {}), TypeDef("b", ("a",), {})]).effective("a")

    def test_pp_and_infinitive_are_distinct_grammatical_operations(self):
        pp = [Word(1, "averse", "averse", "ADJ", 0, "root"),
              Word(2, "to", "to", "ADP", 3, "case"),
              Word(3, "delay", "delay", "NOUN", 1, "obl")]
        infinitive = [Word(1, "happy", "happy", "ADJ", 0, "root"),
                      Word(2, "to", "to", "PART", 3, "mark"),
                      Word(3, "help", "help", "VERB", 1, "xcomp")]
        self.assertEqual([r["kind"] for r in grammatical_observations(pp)],
                         ["adjective_to_pp_candidate"])
        self.assertEqual([r["kind"] for r in grammatical_observations(infinitive)],
                         ["adjective_to_infinitive_candidate"])

    def test_nonlocal_word_match_does_not_count_as_valence(self):
        unrelated = [Word(1, "averse", "averse", "ADJ", 0, "root"),
                     Word(2, "to", "to", "ADP", 4, "case"),
                     Word(3, "delay", "delay", "NOUN", 4, "compound"),
                     Word(4, "event", "event", "NOUN", 1, "parataxis")]
        self.assertEqual(grammatical_observations(unrelated), [])

    def test_lexical_trait_is_induced_from_training_annotation(self):
        rows = [
            "1\taverse\taverse\tADJ\t_\t_\t0\troot\t_\t_",
            "2\tto\tto\tADP\t_\t_\t3\tcase\t_\t_",
            "3\tdelay\tdelay\tNOUN\t_\t_\t1\tobl\t_\t_",
            "",
        ]
        source = induce_evidence("\n".join(rows))
        self.assertEqual(classify_attestation("averse", "adjective_to_pp_candidate", source)
                         ["attestation_count"], 1)
        self.assertEqual(classify_attestation("prone", "adjective_to_pp_candidate", source)
                         ["level"], "unattested")

    def test_tree_validation_and_source_roundtrip(self):
        words = [Word(1, "they", "they", "PRON", 2, "nsubj"),
                 Word(2, "read", "read", "VERB", 0, "root")]
        self.assertTrue(validate_dependency_tree(words)[0])
        self.assertFalse(validate_dependency_tree([Word(1, "loop", "loop", "NOUN", 1, "root")])[0])
        self.assertTrue(nonwhitespace_coverage("They read.", [(0, 4), (5, 9), (9, 10)]))
        self.assertFalse(nonwhitespace_coverage("They read.", [(0, 4), (5, 9)]))


if __name__ == "__main__":
    unittest.main()
