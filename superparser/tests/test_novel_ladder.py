from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

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
    return {"index": index, "status": "complete", "rank_one_sha256": ladder.digest(["tree", index]),
            "selected_graph_sha256": ladder.digest(["graph", index]),
            "root_rule": "example", "forest_budget_exceeded": False, "kbest_budget_exceeded": False}


def result(cohort, *, incomplete=False):
    begin = cohort["first_index"]
    rows = [complete_row(i) for i in range(begin, begin + 100)]
    if incomplete:
        rows[-1] = {**rows[-1], "status": "no_structural_root",
                    "root_rule": None, "rank_one_sha256": None, "selected_graph_sha256": None}
    return {"schema": "seman2-novel-ladder-result-v1", "limits": ladder.LIMITS,
            "cohort_sha256": cohort["cohort_sha256"],
            "counts": dict(Counter(r["status"] for r in rows)), "cases": rows}


def review_doc(cohort, rows, verdict="verified"):
    return {"schema": ladder.REVIEW_SCHEMA, "cohort_sha256": cohort["cohort_sha256"],
            "cases": [{"index": r["index"], "verdict": verdict, "evidence": "Gold attachment",
                       "rank_one_sha256": r["rank_one_sha256"],
                       "selected_graph_sha256": r["selected_graph_sha256"]} for r in rows]}


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
            accepted["rank_one_reviewed"] = list(range(501, 601))  # IDs are not evidence.
            ladder.write_json(directory / "novel-600-accepted.json", accepted)
            with self.assertRaisesRegex(ValueError, "reviewed before expanding"):
                ladder.freeze(directory, src)
            ladder.write_json(directory / "novel-600-review.json", review_doc(cohort, accepted["cases"]))
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

    def test_quality_does_not_count_wrong_or_unreviewed_trees(self):
        src = sources()
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            cohort = ladder.read_json(ladder.freeze(directory, src))
            data = result(cohort)
            ladder.write_json(directory / "novel-600-current.json", data)
            review = review_doc(cohort, data["cases"][:2])
            review["cases"][1]["verdict"] = "needs_fix"
            ladder.write_json(directory / "novel-600-review.json", review)
            cohorts, _, _ = ladder.read_ladder(directory, src)
            output = StringIO()
            with redirect_stdout(output):
                ladder.quality(cohorts, directory)
            self.assertIn("1/100 verified; 1 need a fix; 98 unreviewed", output.getvalue())
            output = StringIO()
            with redirect_stdout(output):
                ladder.print_queue(cohorts, directory, 500)
            self.assertEqual(json.loads(output.getvalue())["index"], 502)
            review["cases"].pop()
            ladder.write_json(directory / "novel-600-review.json", review)
            output = StringIO()
            with redirect_stdout(output):
                ladder.print_queue(cohorts, directory, 500)
            self.assertEqual(json.loads(output.getvalue())["index"], 502)

    def test_stale_semantic_review_is_not_accepted(self):
        cohort = {"cohort_sha256": "same", "first_index": 501}
        original = result(cohort)
        observed = result(cohort)
        observed["cases"][0]["selected_graph_sha256"] = "different"
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            ladder.write_json(directory / "novel-600-review.json", review_doc(cohort, original["cases"][:1]))
            with self.assertRaisesRegex(ValueError, "selected_graph_sha256 changed"):
                ladder.load_review(directory, 600, cohort, observed)

    def test_confirmed_defects_block_semantic_acceptance_despite_all_green_reviews(self):
        """The default ladder must not accept a known bad rank-one interpretation."""
        cohort={"cohort_sha256":"pinned-700","first_index":601}
        data=result(cohort)
        complete=ladder.result_cases(data,cohort,700)
        verified={r["index"]:{"index":r["index"],"verdict":"verified"}
                  for r in data["cases"]}
        with TemporaryDirectory() as temp:
            ledger=Path(temp)/"confirmed_selected_defects.json"
            ladder.write_json(ledger,{
                "schema":"seman2-selected-semantic-defect-ledger-v1",
                "cases":[{
                    "index":629,"status":"needs_fix",
                    "selected_tree_sha256":complete[629]["rank_one_sha256"],
                    "selected_graph_sha256":complete[629]["selected_graph_sha256"],
                    "observed_defect":"Wrong selected agent",
                    "required_linguistic_correction":"The doctor is the agent",
                }],
            })
            with patch.object(ladder,"SEMANTIC_DEFECTS",ledger):
                with self.assertRaisesRegex(ValueError,"semantic acceptance blocked"):
                    ladder.accepted_cases(data,cohort,700,verified)
                # A correctly sealed older rung remains accepted.
                old={"cohort_sha256":"pinned-600","first_index":501}
                data600=result(old)
                self.assertEqual(len(ladder.accepted_cases(
                    data600,old,600,
                    {r["index"]:{"index":r["index"],"verdict":"verified"}
                     for r in data600["cases"]}
                )),100)
            # Removing the outstanding defect after a separate source
            # review is the explicit route to eventual promotion.
            ladder.write_json(ledger,{
                "schema":"seman2-selected-semantic-defect-ledger-v1",
                "cases":[],
            })
            with patch.object(ladder,"SEMANTIC_DEFECTS",ledger):
                self.assertEqual(len(ladder.accepted_cases(
                    data,cohort,700,verified
                )),100)

    def test_graph_hash_ignores_ids_but_not_attachment(self):
        def package(a, b, *, reversed_edge=False):
            return {"handles": {"head": a}, "graph": {
                "nodes": [{"id": a, "span": [0, 3]}, {"id": b, "span": [4, 7]}],
                "relations": [{"relation": "AGENT", "source": b if reversed_edge else a,
                               "target": a if reversed_edge else b}]}}
        self.assertEqual(ladder.graph_digest(package("a", "b")), ladder.graph_digest(package("c", "d")))
        self.assertNotEqual(ladder.graph_digest(package("a", "b")),
                            ladder.graph_digest(package("a", "b", reversed_edge=True)))
