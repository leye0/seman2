"""Exact-source rank-one grammar, semantic attachment and contrast assertions."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts import novel1500_exploratory as novel
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.addressed_speech import ROOT as REPORTED_ADDRESS, UNATTRIBUTED as UNREPORTED_ADDRESS
from seman_parser.engine import Parser, ParserResources
from seman_parser import scoped_novel_1500 as rules
from seman_parser.reported_fragments import ROOT as REPORTED_FRAGMENT

BOOK = Book(99001, "Independent literary attachment controls", "Audit", "syntax")
# Each construction must recover an authentic source and a different lexical
# example. Invalid variants must never use the new root, even if an unrelated
# reading is returned by the ordinary grammar.
CONTRASTS = (
    (1006, rules.OBJECT_RELATIVE,
     "But why should we recall the burden which everyone has carried, and must bear?",
     "But why should we recall the burden which everyone have carried, and must bear?",
     (("AGENT", "felt", "all"), ("AGENT", "feel", "all"),
      ("PATIENT", "felt", "sorrow"), ("PATIENT", "feel", "sorrow"),
      ("QUESTION_REASON", "describe", "why")),
     (("AGENT", "carried", "everyone"), ("AGENT", "bear", "everyone"),
      ("PATIENT", "carried", "burden"), ("PATIENT", "bear", "burden")),
     (("AGENT", "felt", "which"), ("MANNER", "felt", "all"))),
    (1010, rules.JOURNEY_RELATIVE,
     "I had ample time for those and several other matters during my voyage to London, which was brief and exhausting.",
     "I had ample time for those and several other matters during my voyage to swim, which was brief and exhausting.",
     (("PURPOSE", "leisure", "these"), ("PURPOSE", "leisure", "reflections"),
      ("TIME", "had", "journey"), ("DESTINATION", "journey", "Ingolstadt"),
      ("RELATIVE_ANTECEDENT", "which", "journey"), ("ATTRIBUTE", "was", "fatiguing"),
      ("PROPERTY", "journey", "fatiguing")),
     (("PURPOSE", "time", "matters"), ("TIME", "had", "voyage"),
      ("DESTINATION", "voyage", "London"), ("RELATIVE_ANTECEDENT", "which", "voyage"),
      ("PROPERTY", "voyage", "exhausting")),
     (("RECIPIENT", "had", "Ingolstadt"), ("RELATIVE_ANTECEDENT", "which", "Ingolstadt"))),
    (1012, rules.PERCEPTION_GESTURE,
     "The guard noticed my alarm in my eyes and clenched his fists in frustration.",
     "The guard noticed my alarm in my eyes and clench his fists in frustration.",
     (("EXPERIENCER", "saw", "monster"), ("PERCEPT", "saw", "determination"),
      ("LOCATION", "determination", "face"), ("AGENT", "gnashed", "monster"),
      ("PATIENT", "gnashed", "teeth"), ("MANNER", "gnashed", "impotence")),
     (("PERCEPT", "noticed", "alarm"), ("LOCATION", "alarm", "eyes"),
      ("AGENT", "clenched", "guard"), ("MANNER", "clenched", "frustration")),
     (("RECIPIENT", "saw", "face"), ("MODIFIER", "teeth", "in"))),
    (1013, rules.PARALLEL_INVERSION,
     "Still do we seek justice; still do we consign you, cruel traitor, to exile.",
     "Still does we seek justice; still do we consign you, cruel traitor, to exile.",
     (("AGENT", "vow", "I"), ("AGENT", "devote", "I"), ("PATIENT", "devote", "thee"),
      ("VOCATIVE", "devote", "fiend"), ("RESULT", "devote", "torture"),
      ("RESULT", "devote", "death"), ("PARALLEL", "vow", "devote")),
     (("AGENT", "seek", "we"), ("PATIENT", "consign", "you"),
      ("VOCATIVE", "consign", "traitor"), ("RESULT", "consign", "exile")),
     (("AGENT", "devote", "fiend"),)),
    (1014, rules.REPORT_COMMAND,
     'I turned round and cried, "Traitor! Before you open my letter, be sure that you are yourself ready."',
     'I turned round and cried, "Traitor! Before you opened my letter, be sure that you are yourself ready."',
     (("AGENT", "started", "I"), ("SPEAKER", "exclaimed", "I"),
      ("REPORTED_CONTENT", "exclaimed", "be"), ("VOCATIVE", "be", "Villain"),
      ("TIME", "be", "sign"), ("TEMPORAL_MARKER", "sign", "Before"),
      ("PATIENT", "sign", "death-warrant"), ("CONTENT", "sure", "are"),
      ("ATTRIBUTE", "are", "safe"), ("EMPHASIS", "you", "yourself")),
     (("SPEAKER", "cried", "I"), ("REPORTED_CONTENT", "cried", "be"),
      ("VOCATIVE", "be", "Traitor"), ("TIME", "be", "open"),
      ("PATIENT", "open", "letter"), ("ATTRIBUTE", "are", "ready")),
     (("AGENT", "sign", "I"), ("AGENT", "sign", "Villain"))),
    (1015, rules.RECOVERY_RELATIVE,
     "The weight of grief weighed on her spirits, which had surely never fully recovered from the first blow she had received.",
     "The weight of grief weighed on her spirits, which had surely never fully recovered from the first blow she had receive.",
     (("DOMAIN", "state", "mind"), ("AFFECTED", "preyed", "health"),
      ("RELATIVE_ANTECEDENT", "which", "health"), ("NEGATION", "recovered", "never"),
      ("RECOVERY_FROM", "recovered", "shock"), ("EXPERIENCER", "sustained", "it"),
      ("PATIENT", "sustained", "shock")),
     (("RELATIVE_ANTECEDENT", "which", "spirits"), ("RECOVERY_FROM", "recovered", "blow"),
      ("EXPERIENCER", "received", "she"), ("PATIENT", "received", "blow")),
     (("RELATIVE_ANTECEDENT", "which", "mind"),)),
    (1021, rules.PERCEIVED_REACTION,
     "You have heard this awful account, Mary; and do you not feel your hands tremble with fear, like that which even now shakes mine?",
     "You have heard this awful account, Mary; and do you not feel your hands trembled with fear, like that which even now shakes mine?",
     (("VOCATIVE", "read", "Margaret"), ("NEGATION", "feel", "not"),
      ("PERCEPT", "feel", "congeal"), ("THEME", "congeal", "blood"),
      ("CAUSE", "congeal", "horror"), ("CAUSE", "curdles", "that"),
      ("NOMINAL_ELLIPSIS", "mine", "blood")),
     (("VOCATIVE", "heard", "Mary"), ("PERCEPT", "feel", "tremble"),
      ("THEME", "tremble", "hands"), ("CAUSE", "tremble", "fear"),
      ("NOMINAL_ELLIPSIS", "mine", "hands")),
     (("AGENT", "congeal", "Margaret"),)),
    (1024, rules.POSSESSIVE_COORDINATION,
     "Two months earlier, she was occupied in the same work and had raised a creature whose relentless cruelty had wounded her soul and filled it forever with the deepest shame.",
     "Two months earlier, she was occupied in the same work and had raised a creature whose relentless cruelty had wounded her soul and fill it forever with the deepest shame.",
     (("AGENT", "created", "I"), ("ANTERIOR_TO", "created", "was"),
      ("RELATIVE_ANTECEDENT", "whose", "fiend"), ("POSSESSOR", "barbarity", "fiend"),
      ("CAUSE", "desolated", "barbarity"), ("CAUSE", "filled", "barbarity"),
      ("PATIENT", "desolated", "heart"), ("COREFERENCE", "it", "heart"),
      ("CONTENT", "filled", "remorse")),
     (("AGENT", "raised", "she"), ("POSSESSOR", "cruelty", "creature"),
      ("CAUSE", "wounded", "cruelty"), ("CAUSE", "filled", "cruelty"),
      ("COREFERENCE", "it", "soul"), ("CONTENT", "filled", "shame")),
     (("PATIENT", "created", "heart"),)),
    (1025, rules.RECOGNITION_CONTEXT,
     "Her uncle was in the meantime delighted and in the bustle of departure only noticed in the anxiety of his daughter the hesitation of a traveller.",
     "Her uncle was in the meantime delighted and in the bustle of departure only notice in the anxiety of his daughter the hesitation of a traveller.",
     (("SUBJECT", "was", "father"), ("EXPERIENCER", "recognized", "father"),
      ("CONTEXT", "recognized", "bustle"), ("PERCEPT", "recognized", "diffidence"),
      ("EVIDENCE_LOCATION", "diffidence", "melancholy"),
      ("EXPERIENCER", "melancholy", "niece"), ("CHARACTERISTIC_OF", "diffidence", "bride")),
     (("EXPERIENCER", "noticed", "uncle"), ("PERCEPT", "noticed", "hesitation"),
      ("EVIDENCE_LOCATION", "hesitation", "anxiety"), ("EXPERIENCER", "anxiety", "daughter")),
     (("RECIPIENT", "recognized", "niece"), ("PARTITIVE", "melancholy", "niece"))),
    (1037, rules.DIALECT_CAUSE,
     '"Ah, there," answered Thomas, "this came of breaking promises."',
     '"Ah, there," answered Thomas, "this came of break promises."',
     (("SPEAKER", "said", "Morgan"), ("REPORTED_CONTENT", "said", "comed"),
      ("CAUSE", "comed", "sp'iling"), ("PATIENT", "sp'iling", "Bibles")),
     (("SPEAKER", "answered", "Thomas"), ("CAUSE", "came", "breaking"),
      ("PATIENT", "breaking", "promises")),
     (("AGENT", "sp'iling", "Morgan"),)),
    (1039, rules.NEGATIVE_REPRISE,
     "\"No,\" replied Alice, \"We didn't.\"",
     "\"No,\" replied Alice, \"We doesn't.\"",
     (("SPEAKER", "said", "Livesey"), ("REPORTED_CONTENT", "said", "No"),
      ("CONTINUED_SPEECH", "No", "do"), ("NEGATION", "do", "n't"),
      ("SUBJECT", "do", "I")),
     (("SPEAKER", "replied", "Alice"), ("REPORTED_CONTENT", "replied", "did"),
      ("NEGATION", "did", "n't"), ("SUBJECT", "did", "We")),
     (("PATIENT", "do", "I"),)),
    (1041, rules.ADMISSION,
     "Then Mr. Allen alighted, and bringing us along with him, was ushered at a nod into the hall.",
     "Then Mr. Allen alighted, and bringing us along with him, was usher at a nod into the hall.",
     (("AGENT", "dismounted", "Dance"), ("AGENT", "taking", "Dance"), ("PATIENT", "taking", "me"),
      ("PATIENT", "admitted", "Dance"), ("SIMULTANEOUS_SUPPLEMENT", "admitted", "taking"),
      ("ENABLING_CUE", "admitted", "word"), ("DESTINATION", "admitted", "house")),
     (("AGENT", "bringing", "Allen"), ("PATIENT", "ushered", "Allen"),
      ("ENABLING_CUE", "ushered", "nod"), ("DESTINATION", "ushered", "hall")),
     (("AGENT", "admitted", "Dance"),)),
    (1178, REPORTED_FRAGMENT,
     '"Not today," answered Helen.',
     '"Not, today," answered Helen.',
     (("SPEAKER", "replied", "Jane"), ("REPORTED_CONTENT", "replied", "yet"),
      ("NEGATION", "yet", "Not")),
     (("SPEAKER", "answered", "Helen"), ("REPORTED_CONTENT", "answered", "today"),
      ("NEGATION", "today", "Not")),
     (("NEGATION", "replied", "Not"), ("REPORTED_CONTENT", "replied", "Not"))),
    (1253, REPORTED_FRAGMENT,
     '"Quite dangerous," replied Laura.',
     '"Very quickly," replied Laura.',
     (("SPEAKER", "said", "Jorkins"), ("REPORTED_CONTENT", "said", "unpromising"),
      ("DEGREE", "unpromising", "Very")),
     (("SPEAKER", "replied", "Laura"), ("REPORTED_CONTENT", "replied", "dangerous"),
      ("DEGREE", "dangerous", "Quite")),
     (("DEGREE", "said", "Very"), ("REPORTED_CONTENT", "said", "Very"))),
    (1333, REPORTED_FRAGMENT,
     '"Mighty strange," said Thomas.',
     '"Mighty quiet," pushed George.',
     (("SPEAKER", "said", "George"), ("REPORTED_CONTENT", "said", "pretty"),
      ("DEGREE", "pretty", "Mighty")),
     (("SPEAKER", "said", "Thomas"), ("REPORTED_CONTENT", "said", "strange"),
      ("DEGREE", "strange", "Mighty")),
     (("MANNER", "pretty", "Mighty"), ("REPORTED_CONTENT", "said", "Mighty"))),
    (1329, UNREPORTED_ADDRESS,
     '"I think not, madam!"',
     '"I do not think, madam."',
     (("CONTENT_PROFORM", "believe", "not"), ("EXPERIENCER", "believe", "I"),
      ("ADDRESSEE", "believe", "sir")),
     (("CONTENT_PROFORM", "think", "not"), ("EXPERIENCER", "think", "I"),
      ("ADDRESSEE", "think", "madam")),
     (("NEGATION", "believe", "not"), ("SPEAKER", "believe", "sir"))),
    (1330, REPORTED_ADDRESS,
     '"Come in, Ruth," whispered Nora.',
     '"They waited, Ruth," whispered Nora.',
     (("SPEAKER", "said", "Morgan"), ("REPORTED_CONTENT", "said", "Go"),
      ("ADDRESSEE", "Go", "John")),
     (("SPEAKER", "whispered", "Nora"), ("REPORTED_CONTENT", "whispered", "Come"),
      ("ADDRESSEE", "Come", "Ruth")),
     (("SPEAKER", "said", "John"), ("AGENT", "Go", "Morgan"),
      ("REPORTED_CONTENT", "said", "John"))),
    (1461, REPORTED_ADDRESS,
     '"Now, Emma my darling," she replied.',
     '"Now, Emma my book," she replied.',
     (("SPEAKER", "said", "Murdstone"), ("REPORTED_CONTENT", "said", "Now"),
      ("ADDRESSEE", "Now", "Clara"), ("APPOSITION", "Clara", "dear")),
     (("SPEAKER", "replied", "she"), ("REPORTED_CONTENT", "replied", "Now"),
      ("ADDRESSEE", "Now", "Emma"), ("APPOSITION", "Emma", "darling")),
     (("SPEAKER", "said", "Clara"), ("ADDRESSEE", "Now", "dear"),
      ("MANNER", "said", "Now"), ("TIME", "said", "Now"))),
)


SOURCE_CONSTITUENTS = {
    1006: ("structural_parallel_object_gap_relative", "which all have felt, and must feel"),
    1010: ("structural_temporal_interval_with_relative",
           "during my journey to Ingolstadt, which was long and fatiguing"),
    1012: ("structural_gesture_with_complex_affective_manner",
           "gnashed his teeth in the impotence of anger"),
    1013: ("structural_inversion_with_parenthetic_vocative_and_coordinated_results",
           "again do I devote thee, miserable fiend, to torture and death"),
    1014: ("structural_command_temporal_clause", "Before you sign my death-warrant"),
    1015: ("structural_perfect_object_gap_cause", "the first shock it had sustained"),
    1021: ("structural_comparative_horror_relative", "like that which even now curdles mine"),
    1024: ("structural_coordinated_possessive_relative",
           "whose unparalleled barbarity had desolated my heart and filled it forever with the bitterest remorse"),
    1025: ("structural_observable_affective_evidence", "in the melancholy of his niece"),
    1037: ("structural_causal_gerund_reprise", '"that comed of sp\'iling Bibles."'),
    1039: ("structural_do_with_unresolved_predicate_ellipsis", '"I don\'t."'),
    1041: ("structural_admission_passive_with_cue_and_destination", "was admitted at a word into the house"),
    1178: ("structural_spoken_negated_adverbial", "Not yet"),
    1253: ("structural_spoken_degree_predicate", "Very unpromising"),
    1333: ("structural_spoken_degree_predicate", "Mighty pretty"),
    1329: ("structural_ladder_belief_with_negative_proform", "I believe not"),
    1330: ("vp_np_particle", "Go on"),
    1461: ("structural_vocative_name_with_endearment", "Clara my dear"),
}


def descendants(node):
    yield node
    for child in node["children"]:
        yield from descendants(child)


class Novel1500GrammarRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(
            ROOT / "data", wordnet_dict=Path(os.environ["WORDNET_DICT"]),
        ), cache_size=0, max_items=50_000)
        cls.parser.parse("John opened the box.")
        cls.addClassCleanup(signal.signal, signal.SIGALRM,
                            signal.signal(signal.SIGALRM, _deadline))
        cls.manifest, cls.groups = novel.prepare()
        cls.cases = {c["ladder_index"]: c for _, rows in cls.groups.values() for c in rows}

    def test_verified_deltas_match_the_reviewed_sources_and_leave_the_initial_queue(self):
        repairs = novel.read_repairs(self.manifest)
        self.assertEqual(set(repairs), {row[0] for row in CONTRASTS})
        for end, (cohort, _) in self.groups.items():
            novel.expected_result(end, cohort, repairs)
        pending = novel.current_queue(self.manifest, repairs)
        self.assertEqual(pending["coverage_repairs"],
                         sum(e["before"]["status"] != "complete" for e in repairs.values()))
        self.assertFalse(set(repairs) & {row["index"] for row in pending["unresolved"]})

    def synthetic(self, text):
        rows, _ = extract(BOOK, text, length_min=1, length_max=60)
        case, = (r for r in rows if r["source_text"] == text)
        return case

    def assert_selected(self, case, root, source_index=None):
        row = measure(self.parser, case, with_semantics=True)
        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["root_rule"], root)
        self.assertFalse(row["forest_budget_exceeded"] or row["kbest_budget_exceeded"])
        text = case["source_text"]
        self.assertEqual(row["tree"]["span"], [0, len(text)])
        previous = 0
        for child in row["tree"]["children"]:
            start, stop = child["span"]
            self.assertGreaterEqual(start, previous)
            self.assertFalse(text[previous:start].strip())
            previous = stop
        self.assertFalse(text[previous:].strip())
        if root in (REPORTED_ADDRESS, UNREPORTED_ADDRESS):
            turn = row["tree"]["children"][1]
            self.assertEqual(turn["rule_id"], "structural_spoken_turn_with_vocative")
            self.assertEqual([child["category"] for child in turn["children"]],
                             ["ADDRESSED-HEAD", "COMMA", "SOURCE-VOCATIVE"])
            self.assertEqual(turn["features"]["stype"], row["tree"]["features"]["stype"])
        if source_index is not None:
            segment_rule, expected = SOURCE_CONSTITUENTS[source_index]
            segment, = [c for c in descendants(row["tree"]) if c["rule_id"] == segment_rule]
            a, b = segment["span"]
            self.assertEqual(text[a:b], expected)
        graph = row["selected_graph"]["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        for node in nodes.values():
            if node.get("span") and node.get("surface") is not None:
                a, b = node["span"]
                self.assertEqual(text[a:b], node["surface"])
        return {(e["relation"], nodes[e["source"]].get("surface"),
                 nodes[e["target"]].get("surface")) for e in graph["relations"]}

    def test_repairs_at_rank_one_with_independent_contrasts(self):
        for index, root, positive, negative, target, contrast, forbidden in CONTRASTS:
            for mode, text, expected in (("source", None, target),
                                         ("positive", positive, contrast),
                                         ("negative", negative, None)):
                with self.subTest(index=index, mode=mode):
                    case = self.cases[index] if mode == "source" else self.synthetic(text)
                    if mode == "negative":
                        self.assertNotEqual(measure(self.parser, case)["root_rule"], root)
                        continue
                    edges = self.assert_selected(case, root, index if mode == "source" else None)
                    self.assertLessEqual(set(expected), edges)
                    if mode == "source":
                        self.assertFalse(set(forbidden) & edges)

    def test_fragment_reuses_postposed_tag_and_respects_report_boundary(self):
        edges = self.assert_selected(self.synthetic('"Very calm," she replied.'), REPORTED_FRAGMENT)
        self.assertIn(("SPEAKER", "replied", "she"), edges)
        self.assertIn(("REPORTED_CONTENT", "replied", "calm"), edges)
        self.assertNotEqual(measure(self.parser, self.synthetic('"Very calm," said him.'))["root_rule"],
                            REPORTED_FRAGMENT)

    def test_addressed_turn_keeps_head_address_and_reporting_independent(self):
        # Cross the two reported head types with both forms of address. This checks
        # composition rather than two fixes that happen to share a rule ID.
        for text, speech, name, reporter, speaker, endearment in (
            ('"Now, Victor," whispered Nora.', "Now", "Victor", "whispered", "Nora", None),
            ('"Wait, Alice my dear," said Charles.', "Wait", "Alice", "said", "Charles", "dear"),
        ):
            with self.subTest(text=text):
                edges = self.assert_selected(self.synthetic(text), REPORTED_ADDRESS)
                self.assertIn(("SPEAKER", reporter, speaker), edges)
                self.assertIn(("ADDRESSEE", speech, name), edges)
                self.assertIn(("REPORTED_CONTENT", reporter, speech), edges)
                if endearment:
                    self.assertIn(("APPOSITION", name, endearment), edges)
                else:
                    self.assertFalse(any(rel == "APPOSITION" for rel, _, _ in edges))
        unreported = self.assert_selected(self.synthetic('"I think not, madam."'), UNREPORTED_ADDRESS)
        reported = self.assert_selected(self.synthetic('"I think not, madam," she whispered.'),
                                        REPORTED_ADDRESS)
        self.assertEqual(reported - unreported, {
            ("AGENT", "whispered", "she"), ("SPEAKER", "whispered", "she"),
            ("REPORTED_CONTENT", "whispered", "think"),
        })
        self.assertLessEqual(unreported, reported)
        self.assertFalse({rel for rel, _, _ in unreported} & {"SPEAKER", "REPORTED_CONTENT"})
        for text in (
            '"Now, Emma my dear," pushed George.',
            '"Now, Emma my dear," said him.',
            '"Now, Emma my dear."',
            '"Wait, Ruth. Sit down," whispered Nora.',
            '"Wait, Ruth," she said, "until we are ready."',
            '"I think not, these people."',
        ):
            with self.subTest(text=text):
                self.assertNotIn(measure(self.parser, self.synthetic(text))["root_rule"],
                                 (REPORTED_ADDRESS, UNREPORTED_ADDRESS))


if __name__ == "__main__":
    unittest.main()
