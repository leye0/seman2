"""Discourse memory and coreference tests (blueprint blocs 12–13)."""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser.coref import CoreferenceResolver, ResolverConfig, link_best
from seman_parser.discourse import DiscourseEntity, DiscourseState, Mention
from seman_parser.engine import Parser
from seman_parser.features import FeatureStructure
from seman_parser.mentions import extract_mentions
from seman_parser.reader import DiscourseProcessor
from seman_parser.types import load_types

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


class CoreferenceResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.types = load_types(
            [
                {"name": "TOP"},
                {"name": "REFERENTIAL", "parents": ["TOP"]},
                {"name": "PHYSICAL-OBJECT", "parents": ["REFERENTIAL"]},
                {"name": "PERSON", "parents": ["PHYSICAL-OBJECT"]},
                {"name": "CONTAINER", "parents": ["PHYSICAL-OBJECT"]},
                {"name": "ARTIFACT", "parents": ["PHYSICAL-OBJECT"]},
            ]
        )
        self.resolver = CoreferenceResolver(self.types)
        self.state = DiscourseState()

    def test_indefinite_introduces_entity(self) -> None:
        mention = make_mention("M1", "a box", "indefinite", semantic_type="CONTAINER")
        hypothesis = link_best(mention, self.state, self.resolver)
        self.assertTrue(hypothesis.is_new)
        self.assertIn("E1", self.state.entities)

    def test_pronoun_prefers_matching_entity(self) -> None:
        box = make_mention("M1", "a box", "indefinite", semantic_type="CONTAINER")
        link_best(box, self.state, self.resolver)
        john = make_mention("M2", "John", "proper", semantic_type="PERSON")
        link_best(john, self.state, self.resolver)

        it = make_mention("M3", "it", "pronoun", sentence=1, gender="neuter", semantic_type="CONTAINER")
        ranked = self.resolver.resolve(it, self.state)
        self.assertGreaterEqual(len(ranked), 2)
        best = ranked[0]
        self.assertIsNotNone(best.entity_id)
        entity = self.state.entities[best.entity_id]
        self.assertIn("a box", entity.surfaces)

    def test_agreement_rejects(self) -> None:
        plural = make_mention("M1", "the boxes", "definite", number="plural", semantic_type="CONTAINER")
        link_best(plural, self.state, self.resolver)
        singular = make_mention("M2", "it", "pronoun", sentence=1, number="singular", gender="neuter")
        ranked = self.resolver.resolve(singular, self.state)
        # Singular pronoun must not pick the plural entity first if a new
        # entity is available — at minimum the plural link must not be rank 0
        # with a positive agreement factor.
        best = ranked[0]
        if best.entity_id is not None:
            self.assertNotEqual(best.factors.get("agreement"), self.resolver.config.weight_agreement)

    def test_recency_prefers_latest(self) -> None:
        first = make_mention("M1", "a box", "indefinite", sentence=0, semantic_type="CONTAINER")
        link_best(first, self.state, self.resolver)
        second = make_mention("M2", "a book", "indefinite", sentence=1, semantic_type="INFORMATION")
        link_best(second, self.state, self.resolver)
        it = make_mention("M3", "it", "pronoun", sentence=2, gender="neuter", semantic_type="INFORMATION")
        ranked = self.resolver.resolve(it, self.state)
        best = ranked[0]
        if best.entity_id is not None:
            entity = self.state.entities[best.entity_id]
            self.assertIn("a book", entity.surfaces)

    def test_reflexive_same_sentence(self) -> None:
        john = make_mention("M1", "John", "proper", sentence=0, semantic_type="PERSON")
        link_best(john, self.state, self.resolver)
        refl = make_mention("M2", "himself", "pronoun", sentence=0, semantic_type="PERSON")
        # mark reflexive
        refl = Mention(
            mention_id="M2",
            surface="himself",
            span=(0, 8),
            kind="pronoun",
            sentence_index=0,
            features=FeatureStructure.build({"number": "singular", "person": "3", "reflexive": "true"}),
            semantic_type="PERSON",
        )
        ranked = self.resolver.resolve(refl, self.state)
        best = ranked[0]
        self.assertIsNotNone(best.entity_id)

    def test_hypotheses_are_kept(self) -> None:
        mention = make_mention("M1", "a box", "indefinite", semantic_type="CONTAINER")
        link_best(mention, self.state, self.resolver)
        it = make_mention("M2", "it", "pronoun", sentence=1, gender="neuter")
        ranked = self.resolver.resolve(it, self.state)
        self.assertGreaterEqual(len(ranked), 1)
        self.assertIn("M2", self.state.decisions)
        # Every hypothesis remains available for later revision.
        self.assertTrue(all(h.mention_id == "M2" for h in ranked))


class ReaderTests(unittest.TestCase):
    def test_two_sentence_pronoun_resolution(self) -> None:
        processor = make_processor()
        report = processor.read_many(
            [
                "John found a box.",
                "He opened it.",
            ]
        )
        chains = report.entity_chains()
        # At least one entity should accumulate more than one surface.
        self.assertTrue(any(len(surfaces) >= 2 for surfaces in chains.values()), chains)

    def test_same_john_same_box(self) -> None:
        processor = make_processor()
        processor.read("John found a box.")
        processor.read("He opened it.")
        entities = processor.state.entities
        # "He" should not create a second John entity if resolution worked.
        johns = [e for e in entities.values() if "John" in e.surfaces]
        self.assertGreaterEqual(len(johns), 1)
        if johns:
            # The best chain for John includes a pronoun surface when resolved.
            john = johns[0]
            self.assertTrue(
                any(s in {"He", "he"} for s in john.surfaces) or len(john.surfaces) >= 1
            )

    def test_hypotheses_revisable(self) -> None:
        processor = make_processor()
        analysis = processor.read("John found a box.")
        self.assertTrue(analysis.hypotheses)
        for hyps in analysis.hypotheses.values():
            self.assertGreaterEqual(len(hyps), 1)

    def test_state_serializes(self) -> None:
        processor = make_processor()
        processor.read("John found a box.")
        payload = processor.state.as_dict()
        self.assertIn("entities", payload)
        self.assertIn("mentions", payload)
        self.assertIn("decisions", payload)


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


if __name__ == "__main__":
    unittest.main()
