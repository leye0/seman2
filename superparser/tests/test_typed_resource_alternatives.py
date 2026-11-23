"""Positive, negative and head-invariance contracts for edge-independent search."""
import unittest
from dataclasses import replace

from research.typed_resource_poc.core import Word
from research.typed_resource_poc.alternatives import (
    evaluate_alternatives, propose_alternative_attachments
)


def w(i, text, pos, head=0, rel="dep", feats=""):
    return Word(i, text, text.casefold(), pos, head, rel, feats)


class AlternativeSearchTests(unittest.TestCase):
    def test_averse_pp_recovered_even_when_dependency_is_wrong(self):
        words = (
            w(1, "extremely", "ADV", 2, "advmod"),
            w(2, "averse", "ADJ", 0, "root"),
            w(3, "to", "ADP", 4, "case"),
            w(4, "delay", "NOUN", 1, "obl"),
        )
        alternatives = propose_alternative_attachments(words)
        self.assertEqual(len(alternatives), 1)
        a, = alternatives
        self.assertEqual((a.head,a.dependent,a.marker), (2,4,3))
        self.assertEqual(a.head_features["HEAD"]["pos"],"ADJ")
        self.assertFalse(a.as_dict()["selected_complement_proven"])
        self.assertEqual(a.status,"unlicensed_structural_candidate")

    def test_grammar_does_not_depend_on_stanza_edges(self):
        original = (w(1,"prone","ADJ",0,"root"),
                    w(2,"to","ADP",3,"case"),
                    w(3,"errors","NOUN",1,"obl"))
        scrambled = tuple(replace(x,head=999,deprel="discourse") for x in original)
        left = propose_alternative_attachments(original)
        right = propose_alternative_attachments(scrambled)
        self.assertEqual(left,right)

    def test_lexical_traits_are_soft_evidence_not_a_word_whitelist(self):
        words=(w(1,"remarkably","ADV"),w(2,"prone","ADJ"),
               w(3,"to","ADP"),w(4,"errors","NOUN"))
        a,=propose_alternative_attachments(
            words,{"source":"UD_train","patterns":{
                "adjective_to_pp_candidate":{"prone":3}}},
            {"prone":["aj_pp_i-obl_le","aj_cp_i_le"]})
        self.assertEqual(a.external_attestation_count,3)
        self.assertEqual(a.status,"externally_attested_candidate")
        self.assertEqual(a.erg_compatible_types,("aj_pp_i-obl_le",))
        self.assertFalse(a.as_dict()["selected_complement_proven"])

    def test_infinitive_and_pp_are_distinct_grammatical_candidates(self):
        inf=(w(1,"happy","ADJ"),w(2,"to","PART"),
             w(3,"help","VERB",feats="VerbForm=Inf"))
        cand,=propose_alternative_attachments(inf)
        self.assertEqual(cand.kind,"adjective_to_infinitive_candidate")
        self.assertEqual(cand.unsatisfied_valence["category"],"INFINITIVE")
        pp=(w(1,"prone","ADJ"),w(2,"to","ADP"),
            w(3,"error","NOUN"))
        candidate,=propose_alternative_attachments(pp)
        self.assertEqual(candidate.kind,"adjective_to_pp_candidate")
        self.assertEqual(candidate.unsatisfied_valence["category"],"PP")

    def test_negative_cases_do_not_make_spurious_edge(self):
        negatives=[
          (w(1,"averse","ADJ"),w(2,"from","ADP"),w(3,"error","NOUN")),
          (w(1,"averse","ADJ"),w(2,",","PUNCT"),w(3,"to","ADP"),w(4,"error","NOUN")),
          (w(1,"averse","ADJ"),w(2,"to","ADP"),w(3,"make","VERB",feats="VerbForm=Fin")),
          (w(1,"prone","ADJ"),w(2,"to","ADP"),w(3,"quickly","ADV"),w(4,".","PUNCT")),
          (w(1,"happy","ADJ"),w(2,"to","PART"),w(3,"did","AUX",feats="VerbForm=Fin")),
        ]
        for words in negatives:
            with self.subTest(text=" ".join(w.text for w in words)):
                self.assertEqual(propose_alternative_attachments(words),())

    def test_valid_recovery_is_counted_and_false_attempt_is_visible(self):
        gold=(w(1,"averse","ADJ",0,"root"),
              w(2,"to","ADP",3,"case"),
              w(3,"delay","NOUN",1,"obl"))
        erroneous=(w(1,"averse","ADJ",0,"root"),
                   w(2,"to","ADP",3,"case"),
                   w(3,"delay","NOUN",0,"parataxis"))
        candidates=propose_alternative_attachments(erroneous)
        score=evaluate_alternatives(gold,erroneous,candidates)
        self.assertEqual(score["new_correct"],1)
        self.assertEqual(score["new_false"],0)
        self.assertEqual(score["supported_new_correct"],0)


if __name__=="__main__":
    unittest.main()
