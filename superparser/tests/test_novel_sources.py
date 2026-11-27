"""The frozen corpus must resolve without loading unpinned training books."""
import unittest
from scripts.novel_sources import EXPECTED_MANIFEST, pinned_novel_sources


class FrozenNovelSourcesTests(unittest.TestCase):
    def test_all_pinned_sources_resolve(self):
        digest, cases = pinned_novel_sources()
        self.assertEqual(digest, EXPECTED_MANIFEST)
        self.assertEqual([case_id for case_id, _ in cases],
                         [f"Q3-{i}" for i in range(1, 1001)])
        self.assertEqual({case["book_id"] for _, case in cases},
                         {84, 120, 766, 1342})
