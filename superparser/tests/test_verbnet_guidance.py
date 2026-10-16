"""No pytest dependency: isolated tests for the opt-in L-R VerbNet guide."""
from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from research.verbnet_lr.compiler import Frame, PrefixIndex
from research.verbnet_lr.guidance import VerbNetRanker, project_postverb_events


@dataclass(frozen=True)
class Tok:
    text: str


def lattice(*words_and_cats):
    tokens = [Tok(word) for word, _ in words_and_cats]
    lex = {i: {cat: [object()]} for i, (_, cat) in enumerate(words_and_cats) if cat}
    return tokens, lex


def fixture_index():
    frames = [
        Frame("give", "give-13.1", "ditransitive", (("NP",), ("NP",)), ("Recipient", "Theme"),
              ("give%2:40:00",), (1234567,), "exact"),
        Frame("give", "give-13.1", "dative_pp",
              (("NP",), ("PREP:to",), ("NP",)), ("Theme", "", "Recipient"),
              ("give%2:40:00",), (1234567,), "exact"),
        Frame("give", "give-13.1", "other", (("NP",),), ("Theme",),
              (), (), "lemma_only"),
    ]
    return PrefixIndex(frames)


class TestGuide(unittest.TestCase):
    def test_two_nominal_complements(self):
        tok, lex = lattice(("gave", "V"), ("John", "PROPER-NOUN"),
                           ("a", "DET"), ("book", "N"), (".", None))
        self.assertEqual(project_postverb_events(tok, lex, 1), ("NP", "NP"))

    def test_prepositional_complement(self):
        tok, lex = lattice(("gave", "V"), ("a", "DET"), ("book", "N"),
                           ("to", "PREP"), ("John", "PROPER-NOUN"), (".", None))
        self.assertEqual(project_postverb_events(tok, lex, 1), ("NP", "PREP:to", "NP"))

    def test_to_infinitive(self):
        tok, lex = lattice(("helped", "V"), ("him", "PRON"), ("to", "PREP"),
                           ("finish", "V"), ("work", "N"))
        self.assertEqual(project_postverb_events(tok, lex, 1), ("NP", "TO_INF"))

    def test_unknown_lookahead_does_not_invent_np(self):
        tok, lex = lattice(("gave", "V"), ("the", "DET"), ("?", None))
        self.assertEqual(project_postverb_events(tok, lex, 1), ())

    def test_hard_bounds(self):
        tok, lex = lattice(("gave", "V"), ("John", "PROPER-NOUN"),
                           ("a", "DET"), ("book", "N"), ("to", "PREP"), ("Mary", "PROPER-NOUN"))
        self.assertEqual(project_postverb_events(tok, lex, 1, max_tokens=1), ("NP",))
        self.assertEqual(project_postverb_events(tok, lex, 1, max_events=1), ("NP",))

    def test_exact_sense_scored_and_wrong_sense_abstains(self):
        idx = fixture_index()
        tok, lex = lattice(("gave", "V"), ("John", "PROPER-NOUN"),
                           ("a", "DET"), ("book", "N"), (".", None))
        good = SimpleNamespace(category="V", lemma="give", sense_ids=("wn-1234567-v-finite",))
        wrong = SimpleNamespace(category="V", lemma="give", sense_ids=("wn-1234-v-finite",))
        guide = VerbNetRanker(idx, mode="exact")
        self.assertEqual(guide.score(good, tok, lex, 0), 2)
        self.assertEqual(guide.score(wrong, tok, lex, 0), 0)
        self.assertEqual(guide.score(SimpleNamespace(category="N", lemma="give"), tok, lex, 0), 0)

    def test_modes_are_explicit_and_zero_does_not_query(self):
        idx = fixture_index()
        tok, lex = lattice(("gave", "V"), ("John", "PROPER-NOUN"),
                           ("a", "DET"), ("book", "N"))
        mismatched = SimpleNamespace(category="V", lemma="give", sense_ids=("wn-8888-v-base",))
        self.assertEqual(VerbNetRanker(idx, mode="lemma").score(mismatched, tok, lex, 0), 2)
        self.assertEqual(VerbNetRanker(idx, mode="zero").score(mismatched, tok, lex, 0), 0)
        with self.assertRaises(ValueError):
            VerbNetRanker(idx, mode="reject_sentences")


if __name__ == "__main__":
    unittest.main()
