"""Sentence boundaries must never manufacture initial-only sentences or drop quotes."""
from __future__ import annotations

import unittest

from seman_parser.coverage import _split_sentences
from seman_parser.sentence_boundaries import (
    has_final_punctuation, split_prose_sentences, split_analysis_units,
    split_prose_analysis_units,
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

    def test_sentential_relative_keeps_its_event_antecedent(self):
        # David Copperfield, Gutenberg 766: historical case 8 used to become
        # the orphan "which I accordingly did." after semicolon splitting.
        source = ("I could do no less, under these circumstances, than make "
                  "Mr. Micawber known to Uriah Heep and his mother; "
                  "which I accordingly did.")
        improved = split_prose_analysis_units(source)
        historical = split_prose_analysis_units(
            source, preserve_dependent_continuations=False)
        self.assertEqual([u.text for u in improved], [source])
        self.assertEqual([u.source_text for u in improved], [source])
        self.assertFalse(improved[0].semicolon_split)
        self.assertEqual([u.source_text for u in historical], [
            "I could do no less, under these circumstances, than make "
            "Mr. Micawber known to Uriah Heep and his mother;",
            "which I accordingly did.",
        ])
        self.assertTrue(all(u.semicolon_split for u in historical))

    def test_relative_then_independent_semicolon_preserves_source_and_quotes(self):
        source = '“He promised to return; which he did; and we celebrated.”'
        units = split_prose_analysis_units(source)
        self.assertEqual([u.text for u in units], [
            '“He promised to return; which he did.”',
            '“and we celebrated.”',
        ])
        self.assertEqual([u.source_text for u in units], [
            '“He promised to return; which he did;', 'and we celebrated.”',
        ])
        self.assertEqual(" ".join(u.source_text for u in units), source)
        self.assertEqual(units[0].synthetic_suffix, "”")
        self.assertEqual(units[1].synthetic_prefix, "“")
        self.assertTrue(units[0].synthetic_terminal)

    def test_which_question_and_independent_clause_still_split(self):
        cases = [
            ("She left; which one should I choose?",
             ["She left.", "which one should I choose?"]),
            ("She left; which did he choose?",
             ["She left.", "which did he choose?"]),
            ("She left; then he returned.",
             ["She left.", "then he returned."]),
            ("She left; who was calling?",
             ["She left.", "who was calling?"]),
            ("She left; when will we meet again?",
             ["She left.", "when will we meet again?"]),
            ("She paused; when the guests arrived, she entered.",
             ["She paused.", "when the guests arrived, she entered."]),
            ("She paused; if the weather improves, we will leave.",
             ["She paused.", "if the weather improves, we will leave."]),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                units = split_prose_analysis_units(source)
                self.assertEqual([u.text for u in units], expected)
                self.assertEqual(" ".join(u.source_text for u in units), source)

    def test_unambiguous_subordinate_clause_is_not_orphaned(self):
        cases = [
            "She stayed; although the storm approached.",
            "He waited; while the others prepared.",
            "She hurried away; because the house was burning.",
            "He turned; as the bell began to ring.",
        ]
        for source in cases:
            with self.subTest(source=source):
                units = split_prose_analysis_units(source)
                self.assertEqual([u.text for u in units], [source])
                self.assertEqual([u.source_text for u in units], [source])
                self.assertFalse(units[0].semicolon_split)

    def test_versioned_extraction_rejects_rewriting_the_frozen_cohort(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units
        source = "He returned; which I accordingly did."
        legacy = list(analysis_units(source))
        v2 = list(analysis_units(source, segmentation_version=2))
        self.assertEqual([u.text for u in legacy],
                         ["He returned.", "which I accordingly did."])
        self.assertEqual([u.text for u in v2], [source])
        self.assertEqual(v2[0].source_text, source)
        self.assertFalse(v2[0].semicolon_split)
        legacy_cases, legacy_count = extract(
            Book(999, "Demo", "Anon", "train"), source, length_min=1)
        v2_cases, v2_count = extract(
            Book(999, "Demo", "Anon", "train"), source, length_min=1,
            segmentation_version=2)
        self.assertEqual(legacy_count["eligible"], 2)
        self.assertEqual(v2_count["eligible"], 1)
        self.assertEqual(v2_cases[0]["balanced_analysis_text"], source)
        self.assertEqual(v2_cases[0]["segmentation_version"], 2)
        self.assertNotIn("segmentation_version", legacy_cases[0])
        with self.assertRaises(ValueError):
            list(analysis_units(source, segmentation_version=3))

    def test_cross_sentence_quote_continuations_reuse_semicolon_balancer(self):
        cases = [
            ("“I came. I saw.”",
             ["“I came.”", "“I saw.”"],
             ["“I came.", "I saw.”"]),
            ("‘Come here. Prove it.’",
             ["‘Come here.’", "‘Prove it.’"],
             ["‘Come here.", "Prove it.’"]),
            ("“I came; I saw. I stayed.”",
             ["“I came.”", "“I saw.”", "“I stayed.”"],
             ["“I came;", "I saw.", "I stayed.”"]),
            ("‘I don’t know. I really don’t.’",
             ["‘I don’t know.’", "‘I really don’t.’"],
             ["‘I don’t know.", "I really don’t.’"]),
            ("“I came.” She left.",
             ["“I came.”", "She left."],
             ["“I came.”", "She left."]),
            ("John left. Mary arrived.",
             ["John left.", "Mary arrived."],
             ["John left.", "Mary arrived."]),
        ]
        for source, expected_text, expected_source in cases:
            with self.subTest(source=source):
                units = split_prose_analysis_units(source)
                self.assertEqual([u.text for u in units], expected_text)
                self.assertEqual([u.source_text for u in units], expected_source)
                self.assertEqual(" ".join(u.source_text for u in units), source)

    def test_clean_novel_quote_balancing_preserves_raw_case_selection(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units
        sample = "“I came. I saw.”"
        raw = list(analysis_units(sample))
        balanced = list(analysis_units(sample, balance_sentence_quotes=True))
        self.assertEqual([u.text for u in raw], ["“I came.", "I saw.”"])
        self.assertEqual([u.text for u in balanced],
                         ["“I came.”", "“I saw.”"])
        self.assertEqual([u.source_text for u in raw],
                         [u.source_text for u in balanced])
        self.assertEqual(balanced[0].synthetic_suffix, "”")
        self.assertEqual(balanced[1].synthetic_prefix, "“")

    def test_ambiguous_initial_prefers_not_to_split(self):
        text = "The witness was A. B. Carter. She knew D. E. Shaw."
        self.assertEqual(len(split_prose_sentences(text)), 2)



    def test_colloquial_trailing_apostrophe_inside_double_quotes(self):
        # Exact spelling from Treasure Island. "o'" is a clipped word,
        # not an opening of nested SINGLE-quoted speech.
        source = '"out o\' that! Off with you to the cook and get some work."'
        units = split_prose_analysis_units(source)
        self.assertEqual([u.source_text for u in units],
                         ['"out o\' that!', 'Off with you to the cook and get some work."'])
        self.assertEqual([u.text for u in units],
                         ['"out o\' that!"', '"Off with you to the cook and get some work."'])
        self.assertEqual(units[1].synthetic_prefix, '"')
        self.assertEqual(units[1].synthetic_suffix, '')
        self.assertEqual(" ".join(u.source_text for u in units), source)

    def test_inner_single_quote_is_genuine_in_frankenstein(self):
        source = ("The youth and his companion had each of them several names, "
                  "but the old man had only one, which was 'father.' "
                  "The girl was called 'sister' or 'Agatha'.")
        units = split_prose_analysis_units(source)
        self.assertEqual(len(units), 2)
        self.assertEqual(" ".join(u.source_text for u in units), source)
        self.assertTrue(all(not u.synthetic_prefix and not u.synthetic_suffix
                            for u in units))
        self.assertIn("'father.'", units[0].text)

    def test_closing_double_quote_from_prior_sentence_is_provenance_not_orphan(self):
        source = '"There are three tall trees. I\'ve half a mind to dine first."'
        units = split_prose_analysis_units(source)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[1].source_text, 'I\'ve half a mind to dine first."')
        self.assertEqual(units[1].synthetic_prefix, '"')
        self.assertEqual(units[1].text, '"I\'ve half a mind to dine first."')

    def test_double_hyphen_is_not_a_sentence_break(self):
        source = ("Anderson's ball--for it was Job that shot him first--"
                  "had broken his shoulder-blade and touched the lung, not badly.")
        self.assertEqual(split_prose_sentences(source), [source])

if __name__ == "__main__":
    unittest.main()
