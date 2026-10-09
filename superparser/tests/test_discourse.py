"""Discourse memory and reference-commit tests.

Base: plans/coreference-guide.md. Identity comes only from SAME_REF /
ASSERTED_IDENTITY; MAYBE_REF stays open; DIFFERENT_REF blocks a pair.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.coref import (
    commit_link,
    commit_links,
    introduce,
    is_blocked,
    open_candidates,
)
from seman_parser.discourse import DiscourseEntity, DiscourseState, Mention
from seman_parser.engine import Parser
from seman_parser.features import FeatureStructure
from seman_parser.mentions import extract_mentions
from seman_parser.reader import DiscourseProcessor
from seman_parser.reference import ReferenceKind, ReferenceLink

DATA = Path(__file__).resolve().parents[1] / "data"


def make_processor() -> DiscourseProcessor:
    return DiscourseProcessor.from_dir(DATA)


def make_mention(
    mention_id: str,
    surface: str,
    kind: str,
    *,
    sentence: int = 0,
    number: str | None = "singular",
    person: str | None = "3",
    gender: str | None = None,
    semantic_type: str | None = None,
    node_id: str | None = None,
) -> Mention:
    feats = {}
    if number:
        feats["number"] = number
    if person:
        feats["person"] = person
    if gender:
        feats["gender"] = gender
    return Mention(
        mention_id=mention_id,
        surface=surface,
        span=(0, len(surface)),
        kind=kind,
        sentence_index=sentence,
        features=FeatureStructure.build(feats),
        semantic_type=semantic_type,
        node_id=node_id,
        head_lemma=surface.lower(),
    )


def link(
    source: str,
    target: str | None,
    kind: ReferenceKind,
    rule: str = "TEST:unit",
) -> ReferenceLink:
    return ReferenceLink(source=source, target=target, kind=kind, rule_id=rule)


class MentionExtractionTests(unittest.TestCase):
    def test_extract_from_transitive(self) -> None:
        parser = Parser.from_dir(DATA)
        report = parser.parse("John opened the box.")
        best = report.result.best()
        assert best is not None
        mentions = extract_mentions(best, 0)
        surfaces = [m.surface for m in mentions]
        self.assertIn("John", surfaces)
        self.assertIn("the box", surfaces)
        kinds = {m.surface: m.kind for m in mentions}
        self.assertEqual(kinds.get("John"), "proper")
        self.assertEqual(kinds.get("the box"), "definite")

    def test_pronoun_mention_kind(self) -> None:
        parser = Parser.from_dir(DATA)
        report = parser.parse("He left.")
        best = report.result.best()
        assert best is not None
        mentions = extract_mentions(best, 0)
        self.assertTrue(any(m.kind == "pronoun" for m in mentions))


class ReferenceCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = DiscourseState()

    def test_introduce_opens_entity(self) -> None:
        m = make_mention("M1", "a box", "indefinite", semantic_type="CONTAINER")
        ent = introduce(m, self.state)
        self.assertIsNotNone(ent)
        self.assertIn(ent.entity_id, self.state.entities)
        self.assertEqual(self.state.links["M1"], ent.entity_id)

    def test_same_ref_merges_entities(self) -> None:
        introduce(make_mention("M1", "John", "proper", semantic_type="PERSON"), self.state)
        introduce(make_mention("M2", "He", "pronoun", sentence=1), self.state)
        commit_link(link("M2", "M1", ReferenceKind.SAME_REF), self.state)
        # one entity remains, holding both mentions
        self.assertEqual(len(self.state.entities), 1)
        ent = next(iter(self.state.entities.values()))
        self.assertEqual(sorted(ent.mentions), ["M1", "M2"])
        self.assertEqual(self.state.links["M1"], self.state.links["M2"])

    def test_asserted_identity_merges(self) -> None:
        introduce(make_mention("M1", "John", "proper"), self.state)
        introduce(make_mention("M2", "Jack", "proper"), self.state)
        commit_link(link("M2", "M1", ReferenceKind.ASSERTED_IDENTITY, "REF-16:aka"), self.state)
        self.assertEqual(len(self.state.entities), 1)

    def test_maybe_ref_does_not_merge(self) -> None:
        introduce(make_mention("M1", "John", "proper"), self.state)
        introduce(make_mention("M2", "He", "pronoun", sentence=1), self.state)
        commit_link(link("M2", "M1", ReferenceKind.MAYBE_REF, "REF-06:personal"), self.state)
        self.assertEqual(len(self.state.entities), 2)
        self.assertEqual(len(open_candidates(self.state, "M2")), 1)

    def test_different_ref_blocks_pair(self) -> None:
        introduce(make_mention("M1", "John", "proper"), self.state)
        introduce(make_mention("M2", "him", "pronoun"), self.state)
        commit_link(link("M2", "M1", ReferenceKind.DIFFERENT_REF, "REF-05:object-vs-subject"), self.state)
        self.assertTrue(is_blocked(self.state, "M1", "M2"))
        self.assertEqual(len(self.state.entities), 2)

    def test_bound_variable_does_not_create_individual(self) -> None:
        introduce(make_mention("M1", "Every student", "definite"), self.state)
        introduce(make_mention("M2", "themselves", "pronoun"), self.state)
        commit_link(link("M2", "M1", ReferenceKind.BOUND_VARIABLE, "REF-19"), self.state)
        self.assertEqual(len(self.state.bound_variables), 1)
        # no identity merge
        self.assertNotEqual(self.state.links["M1"], self.state.links["M2"])

    def test_no_link_is_recorded_not_merged(self) -> None:
        introduce(make_mention("M1", "It", "pronoun"), self.state)
        commit_link(link("M1", None, ReferenceKind.NO_LINK, "REF-10:expletive"), self.state)
        self.assertEqual(len(self.state.entities), 1)  # only its own
        self.assertEqual(len(self.state.maybe_links), 0)


class ReaderTests(unittest.TestCase):
    def test_read_many_records_reference_links(self) -> None:
        processor = make_processor()
        report = processor.read_many(["John found a box.", "He opened it."])
        total = sum(len(s.reference_links) for s in report.sentences)
        self.assertGreater(total, 0, "expected at least one REF link")

    def test_entities_accumulate_surfaces(self) -> None:
        processor = make_processor()
        report = processor.read_many(["John found a box.", "He opened it."])
        chains = report.entity_chains()
        self.assertTrue(any(len(surfaces) >= 1 for surfaces in chains.values()), chains)

    def test_state_serializes(self) -> None:
        processor = make_processor()
        processor.read("John found a box.")
        payload = processor.state.as_dict()
        self.assertIn("entities", payload)
        self.assertIn("mentions", payload)
        self.assertIn("reference_links", payload)
        self.assertIn("links", payload)


class NoDomainCodeTests(unittest.TestCase):
    def test_coref_module_avoids_word_list_dispatch(self) -> None:
        import ast

        root = Path(__file__).resolve().parents[1] / "seman_parser"
        violations: list[str] = []
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                            if comparator.value.lower() in {"he", "she", "it", "they", "him"}:
                                violations.append(f"{path.name}:{node.lineno}")
        self.assertEqual(violations, [])


class ProperNameSeparationTests(unittest.TestCase):
    """Two distinct names are two entities unless a link asserts identity."""

    TEXTS = [
        "John found a box.",
        "He opened it.",
        "Mary watched him.",
        "She closed the box.",
    ]

    def _report(self):
        proc = DiscourseProcessor.from_dir(DATA)
        return proc.read_many(self.TEXTS)

    def test_john_and_mary_are_distinct_entities(self) -> None:
        report = self._report()
        chains = report.entity_chains()
        johns = [s for s in chains.values() if "John" in s]
        marys = [s for s in chains.values() if "Mary" in s]
        self.assertEqual(len(johns), 1)
        self.assertEqual(len(marys), 1)
        self.assertNotEqual(johns, marys)

    def test_events_are_distinct_entities(self) -> None:
        report = self._report()
        event_entities = [
            s
            for s in report.entity_chains().values()
            if any(w in s for w in ("found", "opened", "watched", "closed"))
        ]
        self.assertGreaterEqual(len(event_entities), 2, report.entity_chains())


if __name__ == "__main__":
    unittest.main()
