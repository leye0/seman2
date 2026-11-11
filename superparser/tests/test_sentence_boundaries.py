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
        # The historical typographic helper can still expose proposals.
        self.assertEqual(_split_sentences(original),
                         ["“I came.”", "“I saw.”", "“I conquered.”"])
        # The active corpus extractor sends ONE complete utterance with
        # subordinate/independent clause references to the parse gateway.
        self.assertEqual(list(sentences(original)), [original])
        rows, counts = extract(
            Book(999, "Example", "Example", "train"),
            original, length_min=1, length_max=100,
        )
        self.assertEqual([r["text"] for r in rows], [original])
        self.assertEqual(rows[0]["source_text"], original)
        self.assertFalse(rows[0]["synthetic_prefix"])
        self.assertFalse(rows[0]["synthetic_terminal"])
        self.assertTrue(rows[0]["structural_constituents"])
        self.assertEqual(counts["eligible"], 1)

    def test_sentential_relative_keeps_its_event_antecedent(self):
        # David Copperfield, Gutenberg 766: historical case 8 used to become
        # the orphan "which I accordingly did." after semicolon splitting.
        source = ("I could do no less, under these circumstances, than make "
                  "Mr. Micawber known to Uriah Heep and his mother; "
                  "which I accordingly did.")
        improved = split_prose_analysis_units(source)
        self.assertEqual([u.text for u in improved], [source])
        self.assertEqual([u.source_text for u in improved], [source])
        self.assertFalse(improved[0].semicolon_split)

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

    def test_attested_shared_subject_coordination_keeps_its_subject(self):
        # David Copperfield, frozen case 94: the shared subject is "She".
        source = ("She gently chid me for being rude; and, keeping me close "
                  "to her shawl, turned to thank the gentleman for taking "
                  "so much trouble as to bring her home.")
        self.assertEqual([u.text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertEqual([u.source_text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertFalse(split_prose_analysis_units(source)[0].synthetic_terminal)
        independent = "She stood; and, keeping me close, she turned toward the door."
        self.assertEqual(len(split_prose_analysis_units(independent)), 2)
        independent_np = "She stood; and, keeping me close, the woman turned away."
        self.assertEqual(len(split_prose_analysis_units(independent_np)), 2)

    def test_attested_parallel_comparatives_keep_shared_predicate(self):
        # Pride and Prejudice, frozen case 182: both adjectives complement
        # the same preceding verb, "He found her ...".
        source = ("He found her as handsome as she had been last year; "
                  "as good natured, and as unaffected, though not quite so chatty.")
        self.assertEqual([u.text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertEqual([u.source_text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertFalse(split_prose_analysis_units(source)[0].synthetic_terminal)
        separate = "He found her as happy as ever; as the rain fell, she left."
        self.assertEqual(len(split_prose_analysis_units(separate)), 2)

    def test_attested_participle_series_keeps_governing_clause(self):
        # Pride and Prejudice, frozen case 194: this is a nonfinite sequence
        # sharing the subject of "they paid little attention".
        source = ("To the rest of the family they paid little attention; "
                  "avoiding Mrs. Bennet as much as possible, saying not much "
                  "to Elizabeth, and nothing at all to the others.")
        self.assertEqual([u.text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertEqual([u.source_text for u in split_prose_analysis_units(source)],
                         [source])
        self.assertFalse(split_prose_analysis_units(source)[0].synthetic_terminal)
        independent = "They hurried; walking home, talking softly, she left."
        proper_name = "They hurried; walking home, talking softly, Mary left."
        for sentence in (independent, proper_name):
            with self.subTest(sentence=sentence):
                self.assertEqual(len(split_prose_analysis_units(sentence)), 2)

    def test_extraction_always_uses_the_current_boundaries(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units

        source = "He returned; which I accordingly did."
        units = list(analysis_units(source))
        self.assertEqual([u.text for u in units], [source])
        self.assertEqual(units[0].source_text, source)
        self.assertFalse(units[0].semicolon_split)
        cases, counts = extract(Book(999, "Demo", "Anon", "train"),
                                source, length_min=1)
        self.assertEqual(counts["eligible"], 1)
        self.assertEqual(cases[0]["balanced_analysis_text"], source)
        # There is no v1/v2 switch in the active extraction API.
        with self.assertRaises(TypeError):
            list(analysis_units(source, segmentation_version=1))
        with self.assertRaises(TypeError):
            extract(Book(999, "Demo", "Anon", "train"), source,
                    segmentation_version=1)


    def test_keeps_quoted_question_with_following_shared_predicate(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units

        source = (
            "Mr. Creakle whispered, ‘Hah! What’s this?’ and bent his eyes "
            "upon me, as if he would have burnt me up with them."
        )
        units = list(analysis_units(source))
        self.assertEqual([unit.source_text for unit in units], [source])
        self.assertEqual(units[0].text, source)
        self.assertEqual(split_prose_sentences(source), [source])
        book = Book(766, "David Copperfield", "Dickens", "train")
        cases, _ = extract(book, source, length_min=1, length_max=100)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["source_text"], source)
        self.assertEqual(cases[0]["balanced_analysis_text"], source)


    def test_quoted_coordination_positive_and_independent_controls(self):
        independent_positive = (
            "The captain murmured, “Ah! Is anyone there?” and turned "
            "toward the door."
        )
        self.assertEqual(
            [unit.source_text for unit in split_prose_analysis_units(
                independent_positive)],
            [independent_positive],
        )
        for source in (
            "He whispered, ‘Oh! What now?’ Then he left.",
            "‘What? Why?’ She turned.",
            "“I came. I saw.”",
            "“What?” “Nothing!”",
            "“Hello!” she cried. “Come back,” he said.",
        ):
            with self.subTest(source=source):
                units = split_prose_analysis_units(source)
                self.assertGreater(len(units), 1)
                self.assertEqual(" ".join(unit.source_text for unit in units),
                                 source)

    def test_keeps_case_105_nested_question_and_dash_for_aside(self):
        from research.verbnet_lr.gutenberg_novels import analysis_units

        source = (
            "‘Says Em’ly, “Martha, is it you? Oh, Martha, can it be you?”"
            "--for they had sat at work together, many a day, at Mr. Omer’s.’"
        )
        units = list(analysis_units(source))
        self.assertEqual([u.source_text for u in units], [source])
        self.assertEqual(units[0].text, source)
        self.assertEqual([u.source_text for u in split_prose_analysis_units(
            source)], [source])
        self.assertEqual(split_prose_sentences(source), [source])
        book = Book(766, "David Copperfield", "Dickens", "train")
        cases, counts = extract(book, source, length_min=1, length_max=100)
        self.assertEqual(counts["eligible"], 1)
        self.assertEqual(cases[0]["balanced_analysis_text"], source)
        self.assertEqual(cases[0]["source_text"], source)


    def test_causal_quote_aside_generalizes_but_does_not_merge_independents(self):
        positives = [
            "‘She whispered, “Is that Jane? Has she returned?”"
            "—for she had not expected her.’",
            "“He asked, 'Is it you? Can you stay?'"
            "—because he had waited so long.”",
        ]
        for source in positives:
            with self.subTest(positive=source):
                self.assertEqual([u.source_text for u in
                                  split_prose_analysis_units(source)], [source])
                self.assertEqual(len(split_prose_sentences(source)), 1)

        negatives = [
            "‘She whispered, “Is that Jane? Has she returned?” Then she smiled.’",
            "‘She whispered, “Is that Jane? Has she returned?”"
            "--fortunately, she was wrong.’",
            "‘She whispered, “Is that Jane? Has she returned?”"
            "--forgone chances haunted her.’",
            "“What? Why?” Then she turned.",
        ]
        for source in negatives:
            with self.subTest(negative=source):
                units = split_prose_analysis_units(source)
                self.assertGreater(len(units), 1)
                self.assertEqual(" ".join(u.source_text for u in units), source)


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
        self.assertEqual([u.text for u in raw], [sample])
        self.assertEqual([u.text for u in balanced], [sample])
        self.assertEqual([u.source_text for u in raw],
                         [u.source_text for u in balanced])
        self.assertEqual(balanced[0].synthetic_suffix, "")
        self.assertEqual(balanced[0].synthetic_prefix, "")
        self.assertEqual(balanced[0].quotation_status, "balanced")

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
