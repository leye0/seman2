from __future__ import annotations

import unittest

from seman2.learning.fragments import (
    fragment_signature,
    instantiate,
    linearize,
    match_fragment,
    parse_bracketed,
)


SENTENCE = ("the", "dog", "ran", "to", "the", "park")
HOST = (
    "(S (NP (DT 0) (NN 1)) (VP (VBD 2) (PP (IN 3) (NP (DT 4) (NN 5)))))"
)
FRAGMENT = "(S (NP (DT the) (NN )) (VP (VBD ran) (PP (IN to) (NP ))))"


class FragmentTests(unittest.TestCase):
    def test_parse_marks_empty_leaves_as_frontiers(self) -> None:
        node = parse_bracketed(FRAGMENT)
        self.assertEqual(node.label, "S")
        noun = node.children[0]
        self.assertTrue(noun.children[1].is_frontier)
        self.assertFalse(noun.children[0].is_frontier)
        self.assertEqual(noun.children[0].word, "the")

    def test_match_binds_frontier_subtrees(self) -> None:
        host = parse_bracketed(HOST, sentence=SENTENCE)
        fragment = parse_bracketed(FRAGMENT)
        matches = match_fragment(fragment, host, sentence=SENTENCE)
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match.root_path, "0")
        self.assertEqual(match.bindings["0.0.1"], "(NN dog)")
        self.assertEqual(match.bindings["0.1.1.1"], "(NP (DT the) (NN park))")
        self.assertEqual(match.covered_leaves, SENTENCE)

    def test_match_rejects_different_lexical_items(self) -> None:
        host = parse_bracketed(
            "(S (NP (DT 0) (NN 1)) (VP (VBD 2)))",
            sentence=("a", "cat", "slept"),
        )
        fragment = parse_bracketed(FRAGMENT)
        self.assertEqual(match_fragment(fragment, host, sentence=("a", "cat", "slept")), ())

    def test_instantiate_replaces_only_bound_frontiers(self) -> None:
        fragment = parse_bracketed(FRAGMENT)
        filled = instantiate(
            fragment,
            {
                "0.0.1": "(NN cat)",
                "0.1.1.1": parse_bracketed("(NP (DT a) (NN store))"),
            },
        )
        self.assertEqual(
            fragment_signature(filled),
            "(S (NP (DT the) (NN cat)) (VP (VBD ran) (PP (IN to) (NP (DT a) (NN store)))))",
        )
        self.assertEqual(linearize(filled), "the cat ran to a store")

    def test_instantiate_accepts_bare_word_for_frontier(self) -> None:
        fragment = parse_bracketed("(NP (DT the) (NN ))")
        filled = instantiate(fragment, {"0.1": "cat"})
        self.assertEqual(linearize(filled), "the cat")

    def test_unbound_frontiers_yield_no_invented_words(self) -> None:
        fragment = parse_bracketed(FRAGMENT)
        filled = instantiate(fragment, {"0.0.1": "cat"})
        self.assertEqual(linearize(filled), "the cat ran to")

    def test_roundtrip_leaves_with_sentence_indices(self) -> None:
        host = parse_bracketed(HOST, sentence=SENTENCE)
        self.assertEqual(
            host.to_bracketed(resolve=SENTENCE),
            "(S (NP (DT the) (NN dog)) (VP (VBD ran) (PP (IN to) (NP (DT the) (NN park)))))",
        )


if __name__ == "__main__":
    unittest.main()
