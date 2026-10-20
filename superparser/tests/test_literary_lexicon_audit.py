"""Corpus-based audit of explicitly registered literary spellings."""
from __future__ import annotations

import unittest

from scripts.audit_literary_lexicon import (
    attested_catalog, audit_corpora, scan_hyphenated,
)


class LiteraryLexiconAuditTests(unittest.TestCase):
    def test_extracts_single_hyphen_compounds_not_em_dash(self):
        text = ("his blood-stained knife--for it was Job--"
                "had broken his shoulder-blade and pick-axe.")
        counts = scan_hyphenated(text)
        self.assertEqual(counts["blood-stained"], 1)
        self.assertEqual(counts["shoulder-blade"], 1)
        self.assertEqual(counts["pick-axe"], 1)
        self.assertNotIn("knife--for", counts)
        self.assertNotIn("job--had", counts)

    def test_curated_words_are_explicitly_attested(self):
        inventory = attested_catalog()
        self.assertGreaterEqual(len(inventory), 80)
        for surface in ("blood-stained", "stage-cutch", "sperrits",
                        "unfort'nate", "shoulder-blade"):
            self.assertIn(surface, inventory)
            for row in inventory[surface]:
                self.assertTrue(row["senses"][0]["category"])
                self.assertIsInstance(row["provenance"]["ebook_id"], int)


    def test_frequent_attested_compounds_have_named_categories(self):
        lexicon = attested_catalog()
        for surface in ("drawing-room", "child-wife", "pocket-handkerchief",
                        "public-house", "dining-room", "good-natured",
                        "old-fashioned", "second-hand", "business-like",
                        "half-hour", "stage-coach"):
            with self.subTest(surface=surface):
                matches = lexicon[surface]
                self.assertTrue(matches, surface)
                categories = {sense["category"]
                              for entry in matches
                              for sense in entry["senses"]}
                self.assertIn("ADJ" if surface in (
                    "good-natured", "old-fashioned", "second-hand", "business-like",
                ) else "N", categories)

    def test_polyfunctional_good_bye_and_half_way_keep_alternatives(self):
        lexicon = attested_catalog()
        for surface, required in (
            ("good-bye", {"N", "INTERJECTION"}),
            ("half-way", {"ADV", "ADJ"}),
        ):
            cats = {sense["category"] for entry in lexicon[surface]
                    for sense in entry["senses"]}
            self.assertEqual(cats, required)

    def test_full_pinned_books_report_unlisted_compounds(self):
        report = audit_corpora(top=10)
        self.assertEqual(len(report["by_book"]), 4)
        self.assertGreater(report["total_compound_types"], 100)
        self.assertGreater(report["explicitly_listed_compound_types"], 20)
        self.assertGreater(report["unlisted_compound_types"], 0)
        self.assertEqual(len(report["unlisted_review_queue"]), 10)
        self.assertTrue(all("--" not in row["surface"]
                            for row in report["unlisted_review_queue"]))


if __name__ == "__main__":
    unittest.main()
