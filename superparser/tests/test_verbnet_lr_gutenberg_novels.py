"""Novel corpus extraction is deterministic and does not train on headers."""
import unittest
from research.verbnet_lr.gutenberg_novels import (
    START,END,Book,TRAIN_BOOKS,TEST_BOOKS,strip_gutenberg,
    sentences,extract,length_band,spread_training,holdout_stratified
)


class GutenbergNovelTests(unittest.TestCase):
    def test_author_holdout(self):
        self.assertFalse({b.ebook_id for b in TRAIN_BOOKS} &
                         {b.ebook_id for b in TEST_BOOKS})
        self.assertFalse({b.author for b in TRAIN_BOOKS} &
                         {b.author for b in TEST_BOOKS})

    def test_boilerplate_excluded(self):
        book=("DO NOT TRAIN THIS HEADER\n"
              "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
              + ("Elizabeth went to the garden. Darcy stayed inside.\n\n"*600)
              + "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
              "DO NOT TRAIN THIS LICENSE")
        core=strip_gutenberg(book)
        self.assertNotIn("LICENSE",core)
        self.assertNotIn("HEADER",core)
        rows,counts=extract(Book(9,"Test","Author","train"),core)
        self.assertGreater(counts["fragments"],0)
        self.assertTrue(all("HEADER" not in r["text"] for r in rows))
        with self.assertRaises(ValueError):
            strip_gutenberg("A novel without markers")

    def test_abbreviations_not_split_into_fake_sentences(self):
        core=("Dr. Watson saw Mr. Holmes approaching the house. "
              "They entered and discussed their strange visitor.\n\n"*400)
        parts=list(sentences(core))
        self.assertIn("Dr. Watson saw Mr. Holmes approaching the house.",parts)
        self.assertIn("They entered and discussed their strange visitor.",parts)
        self.assertNotIn("Dr.",parts)

    def test_full_length_strata_and_determinism(self):
        a=[{"book_id":1,"author":"A","ordinal":i,"text":f"A {i}.","tokens":5}
           for i in range(70)]
        b=[{"book_id":2,"author":"B","ordinal":i,"text":f"B {i}.","tokens":30}
           for i in range(30)]
        selected=spread_training({1:a,2:b},80)
        self.assertEqual(selected,spread_training({1:a,2:b},80))
        self.assertEqual(len(selected),80)
        self.assertGreater(sum(x["book_id"]==2 for x in selected),15)
        test=holdout_stratified({1:a,2:b},per_book_per_band=10)
        self.assertEqual(len(test),20)
        self.assertEqual(length_band(5),"04-12")
        self.assertEqual(length_band(19),"13-24")
        self.assertEqual(length_band(30),"25-40")
        self.assertEqual(length_band(41),"41+")


if __name__=="__main__":
    unittest.main()
