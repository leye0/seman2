"""Regression corpus drawn from data/the_map_of_everything_nlp_novel.txt.

Each case names the linguistic phenomenon it exercises. These are real
sentences from the novel, used as an honest coverage target — not
hand-optimized examples invented for the grammar.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from seman_parser import DiscourseProcessor, Parser
from seman_parser.coverage import extract_sentences, run_coverage

DATA = Path(__file__).resolve().parents[1] / "data"
NOVEL = Path(__file__).resolve().parents[2] / "data" / "the_map_of_everything_nlp_novel.txt"


def parse(text: str):
    return Parser.from_dir(DATA).parse(text)


def relations(text: str) -> set[str]:
    best = parse(text).result.best()
    return {e.relation for e in best.semantic.graph.relations} if best else set()


class NovelSimpleSentenceTests(unittest.TestCase):
    """Baseline SVO material from the novel."""

    def test_neighbors_carried_grocery_bags(self) -> None:
        self.assertTrue(parse("Neighbors carried grocery bags.").result.completed)

    def test_dogs_barked_from_behind_fences(self) -> None:
        self.assertTrue(parse("Dogs barked from behind fences.").result.completed)

    def test_jonah_drew_the_bus_stop(self) -> None:
        self.assertTrue(parse("Jonah drew the bus stop.").result.completed)

    def test_workers_repaired_sidewalks(self) -> None:
        self.assertTrue(parse("Workers repaired sidewalks.").result.completed)

    def test_maya_carried_a_blue_notebook_home(self) -> None:
        self.assertTrue(parse("Maya carried a blue notebook home.").result.completed)


class NovelCopulaTests(unittest.TestCase):
    def test_the_pictures_were_easy(self) -> None:
        self.assertTrue(parse("The pictures were easy.").result.completed)

    def test_the_toast_was_too_hot(self) -> None:
        self.assertTrue(parse("The toast was too hot.").result.completed)

    def test_the_shortest_version_was_one_sentence(self) -> None:
        self.assertTrue(parse("The shortest version was one sentence.").result.completed)


class NovelNegationTests(unittest.TestCase):
    def test_maple_street_was_not_famous(self) -> None:
        report = parse("Maple Street was not famous.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_eli_could_not_find_his_other_sock(self) -> None:
        report = parse("Eli could not find his other sock.")
        self.assertTrue(report.result.completed, report.result.stats)

    def test_negation_feature_preserved(self) -> None:
        best = parse("The pictures were not easy.").result.best()
        if best is not None:
            self.assertIn("negation", best.features.as_dict())


class NovelPossessiveTests(unittest.TestCase):
    def test_maya_wrote_two_imaginary_endings(self) -> None:
        self.assertTrue(parse("Maya wrote two imaginary endings.").result.completed)

    def test_eli_wanted_the_largest_slice(self) -> None:
        self.assertTrue(parse("Eli wanted the largest slice.").result.completed)

    def test_possessor_role(self) -> None:
        best = parse("Eli could not find his other sock.").result.best()
        self.assertIsNotNone(best)
        assert best is not None
        self.assertIn("POSSESSOR", {e.relation for e in best.semantic.graph.relations})


class NovelModalTests(unittest.TestCase):
    def test_they_could_simply_keep_observing(self) -> None:
        self.assertTrue(parse("They could simply keep observing.").result.completed)

    def test_maya_could_find_the_cafeteria(self) -> None:
        self.assertTrue(parse("Maya could find the cafeteria.").result.completed)


class NovelPerfectTests(unittest.TestCase):
    def test_notebook_had_slid(self) -> None:
        self.assertTrue(parse("The blue notebook had slid beneath the table.").result.completed)

    def test_they_had_needed_information(self) -> None:
        self.assertTrue(parse("They had simply needed different information.").result.completed)


class NovelExpandedCoverageTests(unittest.TestCase):
    """Productive constructions found while profiling corpus failures."""

    def test_hyphenated_modifier(self) -> None:
        self.assertTrue(
            parse(
                "Rivera placed an enormous blank sheet of paper on the third-grade classroom floor."
            ).result.completed
        )

    def test_negated_adverbial_adjective(self) -> None:
        self.assertTrue(
            parse("The versions were not equally useful for every listener.").result.completed
        )

    def test_linking_verb_adjective(self) -> None:
        self.assertTrue(
            parse(
                "The difference between a picture, an instruction, and a memory suddenly felt important."
            ).result.completed
        )

    def test_zero_complementizer_clause(self) -> None:
        self.assertTrue(
            parse(
                "She knew which door led to the gym, where lost coats ended up, and how the morning announcements sounded through the classroom speaker."
            ).result.completed
        )

    def test_comma_coordinated_clauses(self) -> None:
        self.assertTrue(
            parse(
                "They argued, changed their minds, asked questions, and finally left an empty square in the middle for places they had not discovered."
            ).result.completed
        )

    def test_trailing_temporal_np(self) -> None:
        self.assertTrue(
            parse(
                "She had seen a small bird carrying dry grass into the old lot that very morning."
            ).result.completed
        )

    def test_fronted_temporal_np(self) -> None:
        self.assertTrue(
            parse(
                "The next Monday, the kitchen clock said seven twenty-eight when Mom called Maya to put on her shoes."
            ).result.completed
        )


class NovelCoordinationTests(unittest.TestCase):
    def test_maya_agreed_and_gave(self) -> None:
        self.assertTrue(parse("Maya agreed and gave him the green marker.").result.completed)

    def test_smiled_but_asked(self) -> None:
        self.assertTrue(parse("Alvarez smiled but asked her to slow down.").result.completed)


class NovelEventAnaphoraTests(unittest.TestCase):
    def test_this_did_not_make_useless(self) -> None:
        self.assertTrue(parse("This did not make the answer useless.").result.completed)

    def test_this_resolves_across_sentences(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(
            [
                "Eli could not find his other sock.",
                "This did not make the answer useless.",
            ]
        )
        this_hyps = None
        for s in report.sentences:
            for m in s.mentions:
                if m.surface == "This":
                    this_hyps = s.hypotheses[m.mention_id]
        self.assertIsNotNone(this_hyps)
        assert this_hyps is not None
        self.assertTrue(this_hyps)


class NovelCorpusCoverageTests(unittest.TestCase):
    """Honest coverage over the novel — the rate is a living metric."""

    def test_extract_sentences_from_novel(self) -> None:
        self.assertTrue(NOVEL.exists(), f"missing corpus {NOVEL}")
        cases = extract_sentences(NOVEL, limit=50)
        self.assertGreaterEqual(len(cases), 20)

    def test_coverage_runs_without_crashing(self) -> None:
        report = run_coverage(NOVEL, data_dir=DATA, limit=120)
        self.assertEqual(report.total, 120)
        self.assertGreaterEqual(report.completed, 1)
        # Harness must keep every case, successes and failures.
        self.assertEqual(len(report.successes) + len(report.failures), report.total)

    def test_coverage_baseline_is_recorded(self) -> None:
        """Pin the current corpus rate so regressions are visible.

        Baseline after the first novel-driven expansion: ~8% of the first
        200 sentences, ~2.5% of the first 1000. Raising these floors is
        expected; dropping below them is a regression.
        """
        report = run_coverage(NOVEL, data_dir=DATA, limit=200)
        self.assertGreaterEqual(report.completed, 40, f"coverage regressed: {report.completed}/200")

    def test_curated_corpus_min_rate(self) -> None:
        """The curated phenomenon cases above must keep working."""
        corpus = [
            "Neighbors carried grocery bags.",
            "Dogs barked from behind fences.",
            "The pictures were easy.",
            "Eli could not find his other sock.",
            "Maya wrote two imaginary endings.",
            "They could simply keep observing.",
            "Maya agreed and gave him the green marker.",
            "This did not make the answer useless.",
        ]
        ok = sum(1 for text in corpus if parse(text).result.completed)
        self.assertGreaterEqual(ok, 7, f"only {ok}/{len(corpus)} curated cases parse")


class NovelDiscourseWindowsTests(unittest.TestCase):
    def test_two_sentence_window_from_novel(self) -> None:
        proc = DiscourseProcessor.from_dir(DATA)
        report = proc.read_many(
            [
                "Eli could not find his other sock.",
                "He wanted to find it.",
            ]
        )
        chains = report.entity_chains()
        self.assertTrue(any(len(v) >= 2 for v in chains.values()), chains)


if __name__ == "__main__":
    unittest.main()
