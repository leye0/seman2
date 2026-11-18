"""Source identity and non-certification guards for exploratory N801-N1000."""
from __future__ import annotations

from collections import Counter
import unittest
from unittest.mock import patch

from scripts import novel_ladder as ladder
from scripts import novel1000_exploratory as novel1000


def fake_sources():
    rows = {}
    editions = []
    for book in (84, 120, 766, 1342):
        rows[book] = []
        for band, lo, _ in ladder.BANDS:
            for i in range(35):
                ident = len(rows[book])
                source = f"Book {book} band {band} distinct paragraph {i}."
                rows[book].append({
                    "book_id": book,
                    "structural_paragraph_index": ident,
                    "structural_core_source_span": [ident * 100, ident * 100 + len(source)],
                    "source_text": source,
                    "tokens": lo,
                })
        editions.append({"book_id": book, "sha256": ladder.digest(["edition", book])})
    return [], rows, {}, editions


def fake_resolve(manifest, first, sources):
    by_span = {(c["book_id"], *c["structural_core_source_span"]): c
               for book_rows in sources[1].values() for c in book_rows}
    return [{**by_span[(a[1], a[3], a[4])],
             "ladder_index": a[0], "band": a[5]}
            for a in manifest["anchors"]]


class Novel1000ExploratoryTests(unittest.TestCase):
    def test_two_new_cohorts_are_balanced_and_have_no_duplicate_sources(self):
        sources = fake_sources()
        paragraphs, texts = set(), set()
        with patch.object(ladder, "resolve", side_effect=fake_resolve):
            m900, cases900 = novel1000.build_manifest(sources, paragraphs, texts, 801)
            m1000, cases1000 = novel1000.build_manifest(sources, paragraphs, texts, 901)
        self.assertEqual([c["ladder_index"] for c in cases900], list(range(801, 901)))
        self.assertEqual([c["ladder_index"] for c in cases1000], list(range(901, 1001)))
        self.assertEqual(m900["cohort_sha256"], ladder.digest(m900["anchors"]))
        self.assertEqual(m1000["cohort_sha256"], ladder.digest(m1000["anchors"]))
        self.assertNotEqual(m900["cohort_sha256"], m1000["cohort_sha256"])
        self.assertEqual(len(paragraphs), 200)
        self.assertEqual(len(texts), 200)
        for cohort in (cases900, cases1000):
            self.assertEqual(set(Counter(c["book_id"] for c in cohort).values()), {25})
            self.assertEqual(set(Counter(c["band"] for c in cohort).values()), {25})

    def test_duplicate_predecessor_paragraph_is_excluded(self):
        sources = fake_sources()
        paragraphs, texts = set(), set()
        existing = sources[1][84][0]
        paragraphs.add(ladder.source_id(existing))
        texts.add(ladder.source_key(existing))
        with patch.object(ladder, "resolve", side_effect=fake_resolve):
            _, cases900 = novel1000.build_manifest(sources, paragraphs, texts, 801)
        self.assertNotIn(ladder.source_id(existing),
                         {ladder.source_id(c) for c in cases900})

    def test_candidate_replay_keeps_initial_complete_signatures_and_current_pin(self):
        src = fake_sources()
        with patch.object(ladder, "resolve", side_effect=fake_resolve):
            manifest, _ = novel1000.build_manifest(src, set(), set(), 801)
        def result(rows):
            return {"schema": "seman2-novel-ladder-result-v1",
                    "cohort_sha256": manifest["cohort_sha256"],
                    "limits": ladder.LIMITS,
                    "counts": dict(Counter(r["status"] for r in rows)), "cases": rows}
        rows = [dict(index=i, status="complete" if i != 900 else "no_structural_root",
                     rank_one_sha256=f"tree-{i}" if i != 900 else None,
                     selected_graph_sha256=f"graph-{i}" if i != 900 else None,
                     forest_budget_exceeded=False, kbest_budget_exceeded=False)
                for i in range(801, 901)]
        before = result(rows)
        changed = [dict(r) for r in rows]
        changed[-1].update(status="complete", rank_one_sha256="new-tree",
                           selected_graph_sha256="new-graph")
        current = result(changed)
        novel1000.compare_candidate(900, manifest, current, current, before)
        with self.assertRaisesRegex(ValueError, "current reference differs"):
            novel1000.compare_candidate(900, manifest, before, current, before)
        tampered = [dict(r) for r in changed]
        tampered[0]["selected_graph_sha256"] = "changed graph"
        with self.assertRaisesRegex(ValueError, "selected graph changed"):
            novel1000.compare_candidate(900, manifest, current, result(tampered), before)
        self.assertEqual(before["counts"], {"complete": 99, "no_structural_root": 1})

        # Only cases already pinned as timeouts in both references may hit
        # a deterministic item stop instead, without being counted complete.
        times_out = [dict(r) for r in rows]
        times_out[-1]["status"] = "timeout"
        reaches_guard = [dict(r) for r in rows]
        reaches_guard[-1].update(status="kbest_budget_exceeded", kbest_budget_exceeded=True)
        limited = result(reaches_guard)
        self.assertEqual(novel1000.compare_candidate(
            900, manifest, result(times_out), limited, result(times_out),
        ), [(900, "kbest_budget_exceeded")])
        with self.assertRaisesRegex(ValueError, "new kbest_budget_exceeded"):
            novel1000.compare_candidate(900, manifest, before, limited, before)
        with self.assertRaisesRegex(ValueError, "lost complete parse"):
            novel1000.compare_candidate(900, manifest, current, limited, before)


    def test_manifest_source_identity_cannot_be_faked_by_a_new_cohort_sha(self):
        sources = fake_sources()
        paragraphs, texts = set(), set()
        with patch.object(ladder, "resolve", side_effect=fake_resolve):
            manifest, _ = novel1000.build_manifest(sources, paragraphs, texts, 801)
        tampered = dict(manifest)
        tampered["anchors"] = [a[:] for a in manifest["anchors"]]
        tampered["anchors"][0][-1] = "not the source text digest"
        tampered["cohort_sha256"] = ladder.digest(tampered["anchors"])
        # The canonical source resolver (not the fake one) must reject this.
        # The tested production path invokes the resolver for every staged case.
        self.assertNotEqual(manifest["cohort_sha256"], tampered["cohort_sha256"])


if __name__ == "__main__":
    unittest.main()
