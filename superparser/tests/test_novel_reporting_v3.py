"""Original reporting and clause-scope repairs with independent contrasts."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import unittest

from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import Book, TRAIN_BOOKS, extract
from scripts import novel_source_reporting_v3 as v3
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources
from seman_parser.structural_preanalysis import analyze_paragraph

BOOK = Book(99000, "Independent discourse and attachment controls", "Audit", "syntax")
CONTROLS = (
    (5, "dialogue_copular_question_with_reporting_participial_supplement",
     "‘Are you ready?’ I asked, closing the door.",
     "‘Is you ready?’ I asked, closing the door.",
     (("REPORTED_CONTENT", "said", "Am"), ("SIMULTANEOUS_SUPPLEMENT", "said", "drying"),
      ("PATIENT", "drying", "eyes"), ("POSSESSOR", "eyes", "my")),
     (("REPORTED_CONTENT", "asked", "Are"), ("SIMULTANEOUS_SUPPLEMENT", "asked", "closing"),
      ("PATIENT", "closing", "door"))),
    (9, "dialogue_echo_response_with_manner_pp",
     "‘Yes?’ with suspicion.", "‘Yes?’ despite suspicion.",
     (("MANNER", "No", "astonishment"),), (("MANNER", "Yes", "suspicion"),)),
    (13, "dialogue_response_particle_with_emphasis_and_report",
     "‘Yes, certainly,’ replied she.", "‘Yes, rarely,’ replied she.",
     (("EMPHASIS", "No", "indeed"), ("REPORTED_CONTENT", "said", "No"), ("SPEAKER", "said", "I")),
     (("EMPHASIS", "Yes", "certainly"), ("REPORTED_CONTENT", "replied", "Yes"), ("SPEAKER", "replied", "she"))),
    (14, "dialogue_interjection_with_postposed_reporter_supplement",
     "‘Oh dear!’ she exclaimed, sighing.", "‘Oh dear!’ she exclaimed, sighed.",
     (("REPORTED_CONTENT", "said", "Dear me"), ("AGENT", "considering", "he"),
      ("SIMULTANEOUS_SUPPLEMENT", "said", "considering")),
     (("REPORTED_CONTENT", "exclaimed", "Oh dear"), ("AGENT", "sighing", "she"))),
    (20, "dialogue_formulaic_assent_with_report",
     "‘By all means,’ replied the captain.", "‘By all roads,’ replied the captain.",
     (("REPORTED_CONTENT", "said", "Of course"), ("SPEAKER", "said", "Doctor")),
     (("REPORTED_CONTENT", "replied", "By all means"), ("SPEAKER", "replied", "captain"))),
    (44, "dialogue_intercalated_subject_control_with_addressee_pp",
     "‘Helen hopes,’ he replied to Mary, ‘to walk toward Dover.’",
     "‘Helen hopes,’ he replied to Mary, ‘to walked toward Dover.’",
     (("ADDRESSEE", "said", "Ham"), ("SPEAKER", "said", "she"),
      ("CONTROLLED_COMPLEMENT", "wants", "go"), ("AGENT", "go", "Martha"),
      ("DESTINATION", "go", "London")),
     (("ADDRESSEE", "replied", "Mary"), ("AGENT", "walk", "Helen"),
      ("DESTINATION", "walk", "Dover"))),
    (47, "structural_copular_origin_with_semicolon_nominal_apposition",
     "It was from Harriet; a letter more formal than usual, and concise.",
     "It was from Harriet; a letter more formally than usual, and concise.",
     (("ORIGIN", "was", "Peggotty"), ("APPOSITION", "It", "something"),
      ("DEGREE", "legible", "less"), ("COMPARATIVE_STANDARD", "legible", "usual"),
      ("PROPERTY", "something", "brief")),
     (("ORIGIN", "was", "Harriet"), ("APPOSITION", "It", "letter"),
      ("DEGREE", "formal", "more"), ("PROPERTY", "letter", "concise"))),
    (107, "structural_attempt_with_coordinated_infinitives_and_result",
     "She attempted, at his request, to open the box, and to see something of what was going on outside, but entirely in vain.",
     "She attempted, at his request, to opened the box, and to see something of what was going on outside, but entirely in vain.",
     (("CONTROLLED_COMPLEMENT", "tried", "fix"), ("CONTROLLED_COMPLEMENT", "tried", "hear"),
      ("AGENT", "hear", "I"), ("CONTENT", "something", "going"),
      ("LOCATION", "going", "there"), ("RESULT", "tried", "in vain")),
     (("MOTIVATION", "attempted", "request"), ("PATIENT", "open", "box"),
      ("CONTENT", "something", "going"), ("LOCATION", "going", "outside"),
      ("RESULT", "attempted", "in vain"))),
    (109, "structural_participial_incise_with_interrogative_purpose",
     "Harriet, knocking on the door again to see whether supper was ready, brought up the subject.",
     "Harriet, knocking on the door again to saw whether supper was ready, brought up the subject.",
     (("SIMULTANEOUS_SUPPLEMENT", "broke", "tapping"), ("LOCATION", "tapping", "wall"),
      ("PURPOSE", "tapping", "know"), ("INTERROGATIVE_CONTENT", "know", "were"),
      ("SUBJECT", "were", "tea"), ("PATIENT", "broke", "phase")),
     (("SIMULTANEOUS_SUPPLEMENT", "brought", "knocking"), ("PURPOSE", "knocking", "see"),
      ("INTERROGATIVE_CONTENT", "see", "was"), ("SUBJECT", "was", "supper"))),
    (111, "dialogue_optative_with_resumed_vocative_and_two_gesture_supplements",
     "‘Good fortune follow you, dear old friend,’ she said, hugging Harriet, ‘and you too, Master Henry!’ clasping hands with him.",
     "‘Good fortune follows you, dear old friend,’ she said, hugging Harriet, ‘and you too, Master Henry!’ clasping hands with him.",
     (("OPTATIVE_SUBJECT", "attend", "good"), ("TITLE", "Davy", "Mas’r"),
      ("AGENT", "embracing", "he"), ("PATIENT", "embracing", "Peggotty"),
      ("AGENT", "shaking", "he"), ("PARTNER", "shaking", "me")),
     (("OPTATIVE_SUBJECT", "follow", "fortune"), ("TITLE", "Henry", "Master"),
      ("AGENT", "hugging", "she"), ("PATIENT", "hugging", "Harriet"),
      ("AGENT", "clasping", "she"), ("PARTNER", "clasping", "him"))),
    (116, "structural_shared_agent_particle_predicate_with_passive_temporal_condition",
     "At last, Harriet usually wrapped it in a blanket and locked it up inside, whenever the parcel was spotted by the gate.",
     "At last, Harriet usually wrapped it in a blanket and locked it up inside, whenever the parcel was spot by the gate.",
     (("AGENT", "muffled", "Dora"), ("AGENT", "shut", "Dora"),
      ("TEMPORAL_CONDITION", "muffled", "reported"), ("TEMPORAL_CONDITION", "shut", "reported"),
      ("REPORTED_LOCATION", "aunt", "door"), ("LOCATION", "shut", "there")),
     (("AGENT", "wrapped", "Harriet"), ("AGENT", "locked", "Harriet"),
      ("TEMPORAL_CONDITION", "wrapped", "spotted"), ("TEMPORAL_CONDITION", "locked", "spotted"),
      ("REPORTED_LOCATION", "parcel", "gate"))),
    (383, "dialogue_nominal_recognition_question_with_reporting_gesture",
     "‘Dr. Allen, sir?’ I asked, holding out the letter.",
     "‘Dr. Allen, sir?’ I asked, holding beneath the letter.",
     (("REPORTED_CONTENT", "asked", "Silver"), ("VOCATIVE", "Silver", "sir"),
      ("SIMULTANEOUS_SUPPLEMENT", "asked", "holding"), ("PATIENT", "holding", "note")),
     (("REPORTED_CONTENT", "asked", "Allen"), ("VOCATIVE", "Allen", "sir"),
      ("SIMULTANEOUS_SUPPLEMENT", "asked", "holding"), ("PATIENT", "holding", "letter"))),
)


class ReportingSourceTests(unittest.TestCase):
    def test_real_reporter_with_capital_i_and_nonfinite_supplement_stays_attached(self):
        book = next(b for b in TRAIN_BOOKS if b.ebook_id == 766)
        body, _ = load_cleaned(book)
        a = body.index("‘Am I grown?’ I said, drying my eyes.")
        b = body.index("\n\n", a)
        paragraph = body[a:b]
        utterance, following = analyze_paragraph(paragraph)
        self.assertEqual(utterance.source_text, paragraph[utterance.source_start:utterance.source_end])
        self.assertTrue(following.source_text.startswith("I was not crying"))
        self.assertFalse(utterance.synthetic_prefix or utterance.synthetic_suffix
                         or utterance.synthetic_terminal)
        reporting = next(p for p in utterance.constituents if p.function == "reporting_clause")
        speech = next(p for p in utterance.constituents if p.function == "direct_speech")
        self.assertEqual(speech.governor, reporting.id)
        self.assertEqual(utterance.source_text[reporting.start:reporting.end], "I said, drying my eyes")

    def test_source_attachment_does_not_swallow_an_independent_clause_or_next_turn(self):
        for text, expected in (
            ("‘Are you ready?’ I asked, closing the door. Julia left.",
             ["‘Are you ready?’ I asked, closing the door.", "Julia left."]),
            ("‘Are you ready?’ I said nothing.",
             ["‘Are you ready?’", "I said nothing."]),
            ("‘Where?’ I asked Mary about the map.",
             ["‘Where?’", "I asked Mary about the map."]),
            ("‘Are you ready?’ ‘I replied last night,’ she said.",
             ["‘Are you ready?’", "‘I replied last night,’ she said."]),
        ):
            with self.subTest(text=text):
                self.assertEqual([r.source_text for r in analyze_paragraph(text)], expected)


class ReportingGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(
            ROOT / "data", wordnet_dict=Path(os.environ["WORDNET_DICT"]),
        ), cache_size=0, max_items=50_000)
        cls.parser.parse("John opened the box.")
        cls.addClassCleanup(signal.signal, signal.SIGALRM,
                            signal.signal(signal.SIGALRM, _deadline))
        _, groups, reference = v3.prepare()
        cls.targets = ({int(n[3:]) for n in reference["repair_targets"]}
                       | set(reference["source_boundary_repairs"]))
        cls.cases = {r["ladder_index"]: r for r in groups["500"][1]}

    def case(self, text):
        matches, _ = extract(BOOK, text, length_min=1, length_max=32)
        rows = [r for r in matches if r["source_text"] == text]
        self.assertEqual(len(rows), 1, (text, [r["source_text"] for r in matches]))
        return rows[0]

    def check(self, case, root, expected, index):
        text = case["source_text"]
        row = measure(self.parser, case, with_semantics=True)
        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["root_rule"], root)
        self.assertFalse(row["forest_budget_exceeded"] or row["kbest_budget_exceeded"])
        tree = row["tree"]
        self.assertEqual(tree["span"], [0, len(text)])
        previous = 0
        for child in tree["children"]:
            a, b = child["span"]
            self.assertFalse(text[previous:a].strip())
            self.assertGreaterEqual(a, previous)
            self.assertGreater(b, a)
            previous = b
        self.assertFalse(text[previous:].strip())
        graph = row["selected_graph"]["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        for node in nodes.values():
            if node.get("span") and node.get("surface") is not None:
                a, b = node["span"]
                self.assertEqual(text[a:b], node["surface"])
        edges = {(e["relation"], nodes[e["source"]].get("surface"),
                  nodes[e["target"]].get("surface")) for e in graph["relations"]}
        self.assertLessEqual(set(expected), edges)
        if index == 5:
            # The two I nodes have different source spans. The subject of
            # the drying gerund must be the reporting I, not the quoted I.
            isolated = [e for e in graph["relations"]
                        if e["relation"] == "AGENT" and nodes[e["source"]]["surface"] in ("drying", "closing")]
            agent, = isolated
            self.assertEqual(nodes[agent["target"]]["span"][0], text.index(" I ", text.index("?’")) + 1)
        if index == 111:
            beneficiaries = {tuple(nodes[e["target"]]["span"]) for e in graph["relations"]
                             if e["relation"] == "BENEFICIARY"}
            self.assertEqual(len(beneficiaries), 2)

    def test_all_repairs_and_independent_contrasts(self):
        self.assertEqual(self.targets, {x[0] for x in CONTROLS})
        for index, root, positive, negative, source_edges, independent_edges in CONTROLS:
            for mode, text, edges in (("source", None, source_edges),
                                      ("positive", positive, independent_edges),
                                      ("negative", negative, None)):
                with self.subTest(index=index, mode=mode):
                    case = self.cases[index] if mode == "source" else self.case(text)
                    if mode == "negative":
                        self.assertNotEqual(measure(self.parser, case)["root_rule"], root)
                    else:
                        self.check(case, root, edges, index)
