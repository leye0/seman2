from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import novel_ladder as ladder


def sources():
    rows, bodies, editions = {}, {}, []
    base = None
    for book in (84, 120, 766, 1342):
        rows[book] = []
        blocks = []
        offset = 0
        for band, lo, _ in ladder.BANDS:
            for i in range(40):
                text = f"Book {book} band {band} passage {i}."
                rows[book].append({
                    "book_id": book, "structural_paragraph_index": len(blocks),
                    "structural_core_source_span": [offset, offset + len(text)],
                    "source_text": text, "text": text, "tokens": lo,
                    "synthetic_prefix": "", "synthetic_suffix": "", "synthetic_terminal": False,
                })
                blocks.append(text)
                offset += len(text) + 2
        bodies[book] = "\n\n".join(blocks)
        editions.append({"book_id": book, "sha256": ladder.digest(bodies[book])})
        if base is None:
            base = rows[book][0]
    return [base], rows, bodies, editions


def complete_row(index):
    return {"index": index, "status": "complete", "rank_one_sha256": f"tree-{index}",
            "root_rule": "example", "forest_budget_exceeded": False, "kbest_budget_exceeded": False}


def result(cohort, *, incomplete=False):
    begin = cohort["first_index"]
    rows = [complete_row(i) for i in range(begin, begin + 100)]
    if incomplete:
        rows[-1] = {**rows[-1], "status": "no_structural_root",
                    "root_rule": None, "rank_one_sha256": None}
    return {"schema": "seman2-novel-ladder-result-v1", "limits": ladder.LIMITS,
            "cohort_sha256": cohort["cohort_sha256"],
            "counts": dict(Counter(r["status"] for r in rows)), "cases": rows}


class NovelLadderTests(unittest.TestCase):
    def test_frozen_prefix_and_balanced_independent_paragraphs(self):
        src = sources()
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            path = ladder.freeze(directory, src)
            first = path.read_bytes()
            cohort = ladder.read_json(path)
            (entry,), _, _ = ladder.read_ladder(directory, src)
            _, cases = entry
            self.assertEqual(set(Counter(r["book_id"] for r in cases).values()), {25})
            self.assertEqual(set(Counter(r["band"] for r in cases).values()), {25})
            self.assertEqual(len({ladder.source_id(r) for r in cases}), 100)
            self.assertNotIn(ladder.source_id(src[0][0]), {ladder.source_id(r) for r in cases})
            accepted = result(cohort)
            ladder.write_json(directory / "novel-600-accepted.json", accepted)
            with self.assertRaisesRegex(ValueError, "reviewed before expanding"):
                ladder.freeze(directory, src)
            accepted["rank_one_reviewed"] = list(range(501, 601))
            ladder.write_json(directory / "novel-600-accepted.json", accepted)
            next_path = ladder.freeze(directory, src)
            self.assertEqual(next_path.name, "novel-700-cohort.json")
            self.assertEqual(path.read_bytes(), first)
            _, paragraphs, _ = ladder.read_ladder(directory, src)
            self.assertEqual(len(paragraphs), 201)

    def test_identity_validation_rejects_drift_even_if_digest_is_recalculated(self):
        src = sources()
        with TemporaryDirectory() as temp:
            manifest = ladder.read_json(ladder.freeze(Path(temp), src))
            manifest["anchors"][0][-1] = "wrong source"
            with self.assertRaisesRegex(ValueError, "do not match their pin"):
                ladder.resolve(manifest, 501, src)
            manifest["cohort_sha256"] = ladder.digest(manifest["anchors"])
            with self.assertRaisesRegex(ValueError, "source no longer resolves"):
                ladder.resolve(manifest, 501, src)

    def test_comparison_distinguishes_changing_tree_from_adding_coverage(self):
        cohort = {"cohort_sha256": "same", "first_index": 501}
        a = ladder.result_cases(result(cohort, incomplete=True), cohort, 600)
        b = ladder.result_cases(result(cohort), cohort, 600)
        self.assertEqual(ladder.compare_rows(a, b), [])
        self.assertTrue(ladder.compare_rows(a, b, sealed=True))
        b[501]["rank_one_sha256"] = "different"
        b[600]["forest_budget_exceeded"] = True
        self.assertEqual(ladder.compare_rows(a, b), [
            (501, "selected tree changed"), (600, "new forest_budget_exceeded"),
        ])

    def test_source_fingerprint_is_from_an_ordered_anchor_list(self):
        self.assertEqual(ladder.digest({"b": 2, "a": 1}), ladder.digest({"a": 1, "b": 2}))
        self.assertNotEqual(ladder.digest([501, 502]), ladder.digest([502, 501]))
