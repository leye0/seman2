"""Contract tests for the 5,000 x 2 cleaned four-novel structural replay."""
from __future__ import annotations
import unittest
from collections import Counter
from research.verbnet_lr.clean_novel_corpus import load_cleaned,read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS,extract
from scripts.benchmark_cleaned_four_novels_5k import (
    sample_spread,choose_cleaned_5000,cleaned_5k_source,dist
)


class CleanedSnapBenchmarkTests(unittest.TestCase):
    def test_even_spread_samples_entire_book_without_duplicates(self):
        self.assertEqual(sample_spread(list(range(10)),4),[1,3,6,8])
        self.assertEqual(sample_spread(list(range(4)),4),[0,1,2,3])
        with self.assertRaises(ValueError):
            sample_spread([0],2)

    def test_balanced_round_robin_preserves_each_books_order(self):
        book_rows={key:[{"book_id":key,"text":str(i),"ordinal":i} for i in range(50)]
                   for key in (766,1342,84,120)}
        rows,quotas=choose_cleaned_5000(book_rows,20)
        self.assertEqual(len(rows),20)
        self.assertEqual(quotas,{766:5,1342:5,84:5,120:5})
        self.assertEqual([r["book_id"] for r in rows[:8]],
                         [766,1342,84,120,766,1342,84,120])
        for key in quotas:
            ordinals=[r["ordinal"] for r in rows if r["book_id"]==key]
            self.assertEqual(ordinals,sorted(set(ordinals)))
            self.assertGreater(ordinals[-1],40)

    def test_actual_cleaned_sources_and_quota_5000(self):
        rows,books=cleaned_5k_source(5000,32)
        self.assertEqual(len(rows),5000)
        self.assertEqual(len(books),4)
        counts=Counter(r["book_id"] for r in rows)
        self.assertEqual(set(counts.values()),{1250})
        self.assertEqual(set(counts),{766,1342,84,120})
        self.assertTrue(all(x["local_cleaned"] for x in books))
        for book in books:
            self.assertEqual(book["selected"],1250)
            self.assertGreaterEqual(book["eligible"],1250)
            self.assertEqual(len(book["clean_git_blob_sha"]),40)
            self.assertEqual(len(book["sha256"]),64)
        # Even after punctuation heuristic, no ISBN/intro labels in this set.
        samples=[r["text"] for r in rows]
        self.assertTrue(all(r["tokens"]<=32 for r in rows))
        self.assertTrue(all(r["tokens"]>=4 for r in rows))
        self.assertTrue(all(s.endswith((".","!","?")) for s in samples))

    def test_combined_quantile_contract(self):
        self.assertEqual(dist([1.,2.,3.])["n"],3)
        self.assertEqual(dist([1.,2.,3.])["p50_ms"],2.0)
        self.assertEqual(dist([])["n"],0)


if __name__=="__main__":
    unittest.main()
