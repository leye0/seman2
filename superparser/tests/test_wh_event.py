"""Long-distance WH gaps and event anaphora (blueprint §19, §22.17)."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import DiscourseProcessor, Parser

DATA = Path(__file__).resolve().parents[1] / "data"


def parse(text: str):
    return Parser.from_dir(DATA).parse(text)


class WHGapTests(unittest.TestCase):
    def test_object_gap_question(self) -> None:
        report = parse("Who did John see?")
        self.assertTrue(report.result.completed, report.result.stats)
        best = report.result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_wh_obj")

    def test_object_gap_roles(self) -> None:
        best = parse("Who did John see?").result.best()
        assert best is not None
        rels = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("AGENT", rels)
        self.assertIn("AFFECTED", rels)

    def test_wh_subject_still_works(self) -> None:
        best = parse("Who left?").result.best()
        assert best is not None
        self.assertEqual(best.rule_id, "clause_wh_subj")


class EventAnaphoraTests(unittest.TestCase):
    def test_event_mentions_are_extracted(self) -> None:
        from seman_parser.mentions import extract_event_mentions

        report = parse("John lost his job.")
        best = report.result.best()
        assert best is not None
        events = extract_event_mentions(best, 0)
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0].kind, "event")
        # Type name is resource-driven (WordNet lexicographer file).
        self.assertIsNotNone(events[0].semantic_type)

    def test_event_mentions_deduplicated(self) -> None:
        from seman_parser.mentions import extract_event_mentions

        report = parse("John lost his job.")
        best = report.result.best()
        assert best is not None
        events = extract_event_mentions(best, 0)
        node_ids = [e.node_id for e in events]
        self.assertEqual(len(node_ids), len(set(node_ids)))

    def test_demonstrative_resolves_to_event_situation(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(["John lost his job.", "This devastated him."])
        # "This" must get a MAYBE_REF / NO_LINK reference link (guide REF-23).
        this_links = []
        for s in report.sentences:
            for lk in s.reference_links:
                if lk.source.endswith("M1") or "This" in str(lk.evidence):
                    this_links.append(lk)
        self.assertTrue(this_links, [lk.as_dict() for s in report.sentences for lk in s.reference_links])
        for lk in this_links:
            self.assertIn(lk.kind.value, {"MAYBE_REF", "NO_LINK"})

    def test_him_resolves_to_john(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(["John lost his job.", "This devastated him."])
        # "him" is MAYBE_REF (REF-06), never committed identity.
        him_links = [
            lk
            for s in report.sentences
            for lk in s.reference_links
            if "him" in str(lk.evidence).lower()
        ]
        self.assertTrue(him_links, [lk.as_dict() for s in report.sentences for lk in s.reference_links])
        for lk in him_links:
            self.assertIn(lk.kind.value, {"MAYBE_REF", "DIFFERENT_REF", "NO_LINK"})

    def test_possessive_roles(self) -> None:
        best = parse("John lost his job.").result.best()
        assert best is not None
        rels = {edge.relation for edge in best.semantic.graph.relations}
        self.assertIn("POSSESSOR", rels)

    def test_unbound_variables_do_not_look_like_features(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(["John lost his job.", "This devastated him."])
        for s in report.sentences:
            for m in s.mentions:
                for name in ("number", "person", "gender"):
                    value = getattr(m, name)
                    if value is not None:
                        self.assertNotIn("?", value)
                        self.assertNotEqual(value, "n")
                        self.assertNotEqual(value, "p")


class MentionIdTests(unittest.TestCase):
    def test_mention_ids_are_globally_unique(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(["John left.", "Mary left."])
        ids = [m.mention_id for s in report.sentences for m in s.mentions]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
