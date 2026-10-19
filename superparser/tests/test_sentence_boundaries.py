"""Sentence boundaries must never manufacture initial-only sentences or drop quotes."""
from __future__ import annotations

import unittest

from seman_parser.coverage import _split_sentences
from seman_parser.sentence_boundaries import (
    has_final_punctuation, split_prose_sentences, split_analysis_units,
)
from research.verbnet_lr.gutenberg_novels import Book, extract, sentences


class SentenceBoundaryTests(unittest.TestCase):
    def test_dialogue_and_initials(self):
        examples = [
            ("J. R. R. Tolkien entered. He sat.",
             ["J. R. R. Tolkien entered.", "He sat."]),
            ("Mr. A. B. Smith visited Dr. Watson. Then he left.",
             ["Mr. A. B. Smith visited Dr. Watson.", "Then he left."]),
            ("R. Walton wrote to Mrs. Saville. She replied.",
             ["R. Walton wrote to Mrs. Saville.", "She replied."]),
            ("He worked for Mr. Dickens. Mrs. Smith agreed.",
             ["He worked for Mr. Dickens.", "Mrs. Smith agreed."]),
            ("It happened in the U.S. He returned.",
             ["It happened in the U.S.", "He returned."]),
            ("The ratio was 3.14. After that, he paused.",
             ["The ratio was 3.14.", "After that, he paused."]),
            ('"Hello!" she cried. "Come back," he said.',
             ['"Hello!" she cried.', '"Come back," he said.']),
            ("“Hello!” she cried. “Come back,” he said.",
             ["“Hello!” she cried.", "“Come back,” he said."]),
            ("“I am here.” She turned.",
             ["“I am here.”", "She turned."]),
            ("“What?” “Nothing!”",
             ["“What?”", "“Nothing!”"]),
            ("“My dear Mr. Bennet,” said his lady, “have you heard?” Mr. Bennet replied.",
             ["“My dear Mr. Bennet,” said his lady, “have you heard?”",
              "Mr. Bennet replied."]),
            ('"Wait!" He yelled.', ['"Wait!"', "He yelled."]),
        ]
        for paragraph, expected in examples:
            with self.subTest(paragraph=paragraph):
                self.assertEqual(split_prose_sentences(paragraph), expected)
                self.assertEqual(_split_sentences(paragraph), expected)
                self.assertEqual(list(sentences(paragraph)), expected)
                self.assertEqual(" ".join(expected), paragraph)
                self.assertTrue(all(has_final_punctuation(s) for s in expected))

    def test_short_dialogue_survives_coverage(self):
        from seman_parser.coverage import extract_sentences
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as folder:
            p = Path(folder) / "dialogue.txt"
            p.write_text("“No!”\n\n“Yes?”\n\n“Go!”\n\n“STOP!”\n\nPart of the crew marched.\n", encoding="utf-8")
            self.assertEqual(
                [r.text for r in extract_sentences(p)],
                ["“No!”", "“Yes?”", "“Go!”", "“STOP!”", "Part of the crew marched."],
            )

    def test_research_extract_keeps_quote_marks(self):
        sample = "“Wait!” she cried. Mr. A. Smith stayed. “No!” he shouted."
        cases, counts = extract(Book(999, "Demo", "Anon", "train"),
                                sample, length_min=1, length_max=99)
        self.assertEqual(counts["non_ascii"], 0)
        self.assertEqual([c["text"] for c in cases], [
            "“Wait!” she cried.", "Mr. A. Smith stayed.", "“No!” he shouted."
        ])


    def test_semicolon_split_is_lossless_with_quote_restoration(self):
        cases = [
            ("“I came; I saw; I conquered.”",
             ["“I came.”", "“I saw.”", "“I conquered.”"],
             ["“I came;", "I saw;", "I conquered.”"]),
            ("He arrived; she left.",
             ["He arrived.", "she left."],
             ["He arrived;", "she left."]),
            ('"I said"; she listened.',
             ['"I said."', 'she listened.'],
             ['"I said";', 'she listened.']),
            ("‘I’m here; don’t go.’",
             ["‘I’m here.’", "‘don’t go.’"],
             ["‘I’m here;", "don’t go.’"]),
            ("He stayed; she called; they laughed.",
             ["He stayed.", "she called.", "they laughed."],
             ["He stayed;", "she called;", "they laughed."]),
        ]
        for original, expected, sources in cases:
            with self.subTest(original=original):
                units = split_analysis_units(original)
                self.assertEqual([u.text for u in units], expected)
                self.assertEqual([u.source_text for u in units], sources)
                self.assertEqual(" ".join(u.source_text for u in units), original)
                self.assertTrue(all(";" not in u.text for u in units))
                self.assertTrue(all(has_final_punctuation(u.text) for u in units))
                self.assertTrue(all(u.semicolon_split for u in units))

    def test_semicolon_units_reach_corpus_and_coverage(self):
        original = "“I came; I saw; I conquered.”"
        expected = ["“I came.”", "“I saw.”", "“I conquered.”"]
        self.assertEqual(list(sentences(original)), expected)
        self.assertEqual(_split_sentences(original), expected)
        rows, counts = extract(
            Book(999, "Example", "Example", "train"),
            original, length_min=1, length_max=100,
        )
        self.assertEqual([r["text"] for r in rows], expected)
        self.assertEqual(rows[0]["source_text"], "“I came;")
        self.assertTrue(rows[1]["synthetic_prefix"])
        self.assertTrue(rows[0]["synthetic_terminal"])
        self.assertEqual(counts["eligible"], 3)

    def test_ambiguous_initial_prefers_not_to_split(self):
        text = "The witness was A. B. Carter. She knew D. E. Shaw."
        self.assertEqual(len(split_prose_sentences(text)), 2)


if __name__ == "__main__":
    unittest.main()
