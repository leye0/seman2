"""Regression tests for source-frozen Novel-1500 and coverage-only reporting."""
from collections import Counter
from copy import deepcopy
import unittest
from unittest.mock import call, patch

from scripts import novel1500_exploratory as novel
from scripts import novel_ladder as ladder
from scripts import novel_source_reporting_v3 as parent


class Novel1500Sources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = ladder.load_source_inventory()
        cls.manifest, cls.groups = novel.prepare(inventory=cls.inventory)
        _, cls.predecessors, _ = parent.prepare(inventory=cls.inventory)

    def test_frozen_sources_are_additive_and_balanced(self):
        self.assertEqual(self.manifest, ladder.read_json(novel.DIRECTORY / "source-manifest.json"))
        self.assertEqual(tuple(self.groups), novel.ENDS)
        predecessors = [c for _, cases in self.predecessors.values() for c in cases]
        self.assertEqual(len(predecessors), 1030)
        paragraphs = {ladder.source_id(c) for c in predecessors}
        texts = {ladder.source_key(c) for c in predecessors}
        for end, (cohort, cases) in self.groups.items():
            with self.subTest(end=end):
                self.assertEqual([c["ladder_index"] for c in cases], list(range(end - 99, end + 1)))
                self.assertEqual([c["transfer_id"] for c in cases], [f"N{i}" for i in range(end - 99, end + 1)])
                quotas = novel.FIRST_RUNG_QUOTAS if end == novel.ENDS[0] else novel.QUOTAS
                by_cell = Counter((c["book_id"], c["band"]) for c in cases)
                self.assertEqual(by_cell, {(b, band): count for b, counts in quotas.items()
                                          for (band, _, _), count in zip(ladder.BANDS, counts)
                                          if count})
                self.assertEqual(cohort["anchors"],
                                 [ladder.anchor(c["ladder_index"], c["band"], c) for c in cases])
                for c in cases:
                    self.assertNotIn(ladder.source_id(c), paragraphs)
                    self.assertNotIn(ladder.source_key(c), texts)
                    paragraphs.add(ladder.source_id(c))
                    texts.add(ladder.source_key(c))

    def test_short_frankenstein_source_scarcity_is_measured_before_parsing(self):
        cases = [c for _, rows in self.predecessors.values() for c in rows]
        paragraphs = {ladder.source_id(c) for c in cases}
        texts = {ladder.source_key(c) for c in cases}
        pool = {ladder.source_id(c) for c in self.inventory[0][84]
                if 4 <= c["tokens"] <= 8 and ladder.source_id(c) not in paragraphs
                and ladder.source_key(c) not in texts}
        self.assertEqual(len(pool), 1)
        self.assertEqual(novel.FIRST_RUNG_QUOTAS[84][0], 1)
        self.assertEqual(novel.QUOTAS[84][0], 0)

    def test_repair_queue_matches_every_incomplete_frozen_anchor(self):
        queue = ladder.read_json(novel.DIRECTORY / "repair-queue.json")
        self.assertEqual(queue["manifest_sha256"], ladder.digest(self.manifest))
        expected = []
        for end, (cohort, _) in self.groups.items():
            result = ladder.read_json(novel.DIRECTORY / f"novel-{end}-initial.json")
            signatures = ladder.result_cases(result, cohort, end)
            for index, book, paragraph, begin, stop, band, sha in cohort["anchors"]:
                status = signatures[index]["status"]
                if status != "complete":
                    expected.append({"index": index, "status": status, "book_id": book,
                                     "paragraph": paragraph, "source_span": [begin, stop],
                                     "band": band, "source_sha256": sha})
        self.assertEqual(queue["unresolved"], expected)


class Novel1500Replay(unittest.TestCase):
    def test_each_group_uses_a_fresh_parser(self):
        a, b = object(), object()
        with patch.object(ladder, "run") as run:
            novel.replay({1100: a, 1200: b}, "wordnet", "out")
        self.assertEqual(run.call_args_list,
                         [call([a], "wordnet", "out"), call([b], "wordnet", "out")])

    def setUp(self):
        self.end = 1100
        self.cohort = {"cohort_sha256": "fixed-test-cohort"}
        self.initial = {
            "schema": "seman2-novel-ladder-result-v1", "limits": ladder.LIMITS,
            **self.cohort, "counts": {"complete": 98, "timeout": 1, "no_structural_root": 1},
            "cases": [
                {"index": i, "status": "complete", "rank_one_sha256": "tree",
                 "selected_graph_sha256": "graph", "root_rule": "root",
                 "forest_budget_exceeded": False, "kbest_budget_exceeded": False}
                for i in range(1001, 1101)
            ],
        }
        for i, status in enumerate(("timeout", "no_structural_root")):
            self.initial["cases"][i].update(status=status, rank_one_sha256=None,
                                            selected_graph_sha256=None, root_rule=None)

    def check(self, observed):
        novel.check_result(self.end, self.cohort, self.initial, observed)

    def test_resource_stop_is_still_incomplete(self):
        new = deepcopy(self.initial)
        new["cases"][0].update(status="forest_budget_exceeded", forest_budget_exceeded=True)
        del new["counts"]["timeout"]
        new["counts"]["forest_budget_exceeded"] = 1
        self.check(new)

    def test_conclusive_failure_cannot_be_reclassified_as_timeout(self):
        new = deepcopy(self.initial)
        new["cases"][1]["status"] = "timeout"
        del new["counts"]["no_structural_root"]
        new["counts"]["timeout"] = 2
        with self.assertRaisesRegex(ValueError, "1002"):
            self.check(new)

    def test_protected_completed_analyses_require_same_tree_graph_and_limits(self):
        for field, change in (("rank_one_sha256", "new tree"),
                              ("selected_graph_sha256", "new graph"),
                              ("forest_budget_exceeded", True),
                              ("kbest_budget_exceeded", True)):
            new = deepcopy(self.initial)
            new["cases"][2][field] = change
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "1003"):
                self.check(new)


if __name__ == "__main__":
    unittest.main()
