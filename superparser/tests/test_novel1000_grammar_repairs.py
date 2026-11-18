"""Source-ranked parses plus independent positive and negative construction controls."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import unittest

from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts import novel1000_exploratory as novel
from scripts import novel_ladder as ladder
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources
from seman_parser import scoped_novel_1000 as scoped

BOOK = Book(91991, "Independent Novel-1000 controls", "Audit", "syntax")


# index, root, independent grammatical witness, one rejected near-miss,
# followed by selected graph edges in the source and independent witness.
CONTROLS = (
    (813, scoped.REPORTED_COPULAR_QUESTION, '"Were they ready, my dears?" asked she.',
     '"Were they ready my dears?" asked she.',
     (("SUBJECT", "Are", "you"), ("PREDICATE", "Are", "mad"), ("VOCATIVE", "Are", "friend"),
      ("REPORTED_CONTENT", "said", "Are"), ("SPEAKER", "said", "he")),
     (("SUBJECT", "Were", "they"), ("PREDICATE", "Were", "ready"), ("SPEAKER", "asked", "she"))),
    (814, scoped.REPORTED_ASSURED_PASSIVE,
     '"Be assured, sir," said she, "no expense on my part shall be spared to discover the culprit."',
     '"Be assured, sir," said she, "no expense on my part shall be sparing to discover the culprit."',
     (("PASSIVE_PATIENT", "spared", "pains"), ("REPORTED_CONTENT", "said", "spared"),
      ("PURPOSE", "spared", "discover"), ("PATIENT", "discover", "villain")),
     (("SPEAKER", "said", "she"), ("PASSIVE_PATIENT", "spared", "expense"),
      ("PATIENT", "discover", "culprit"))),
    (827, scoped.COMPARATIVE_PARTICIPIAL_ELLIPSIS,
     'No sooner settled upon than finished.', 'No sooner settled upon than finishing.',
     (("ANTERIORITY", "thought", "done"), ("TEMPORAL_COMPARATIVE", "sooner", "than")),
     (("ANTERIORITY", "settled", "finished"),)),
    (872, scoped.FOUR_TURN_SPEECH,
     '‘The mail arrived at noon. The pupils waited by the gate. The man walked with a stick. Nobody in the kitchen.’',
     '‘The mail arrived at noon. The pupils waited by the gate. The man walked with a stick. Somebody was in the kitchen.’',
     (("DISCOURSE_NEXT", "went", "stopped"), ("DISCOURSE_NEXT", "went", "Nobody"),
      ("MODIFIER", "Nobody", "in")),
     (("DISCOURSE_NEXT", "arrived", "waited"), ("DISCOURSE_NEXT", "walked", "Nobody"),
      ("MODIFIER", "Nobody", "in"))),
    (885, scoped.SUPPLEMENTAL_STATE,
     'The night passed slowly, uninterrupted by any sound.',
     'The night passed slowly, uninterrupted on any sound.',
     (("DEPICTIVE", "passed", "unmarked"), ("BY_COMPLEMENT", "unmarked", "by"),
      ("PREDICATE_OF", "unmarked", "evening")),
     (("DEPICTIVE", "passed", "uninterrupted"), ("BY_COMPLEMENT", "uninterrupted", "by"),
      ("PREDICATE_OF", "uninterrupted", "night"))),
    (911, scoped.COPULAR_INF_PURPOSE,
     'But we were eager to return to our home.', 'But we were eager to returned to our home.',
     (("CONTROL_COMPLEMENT", "impatient", "arrive"), ("AGENT", "arrive", "I"),
      ("GOAL", "arrive", "at")),
     (("CONTROL_COMPLEMENT", "eager", "return"), ("AGENT", "return", "we"),
      ("GOAL", "return", "to"))),
    (937, scoped.SHARED_RETURN_STATE,
     'The boys fetched some wood, and came up again soaked and dripping.',
     'The boys fetched some wood, and they came up again soaked and dripping.',
     (("SHARED_SUBJECT_CONJUNCT", "took", "came"), ("DEPICTIVE", "came", "drenched"),
      ("AGENT", "came", "three"), ("AGENT", "bubbling", "three")),
     (("SHARED_SUBJECT_CONJUNCT", "fetched", "came"), ("DEPICTIVE", "came", "soaked"),
      ("AGENT", "came", "boys"), ("AGENT", "dripping", "boys"))),
    (950, 'structural_parallel_motion_to_locative_relative_with_depictives',
     'We picked up the lamp at once, crossed the hall, and walked right up to the woman where she sat, seated on a bench, speaking to her friend.',
     'We picked up the lamp at once, crossed the hall, and walked right up to the woman where she sits, seated on a bench, speaking to her friend.',
     (("AGENT", "walked", "I"), ("LOCATIVE_RELATIVE", "man", "stood"),
      ("PASSIVE_PATIENT", "propped", "he"), ("AGENT", "talking", "he")),
     (("AGENT", "walked", "We"), ("LOCATIVE_RELATIVE", "woman", "sat"),
      ("AGENT", "speaking", "she"))),
    (960, scoped.ELLIPTIC_GERUND_REPORT,
     '‘What! Following the stranger?’ asked the farmer.',
     '‘What! Followed the stranger?’ asked the farmer.',
     (("PATIENT", "Bewitching", "encumbrance"), ("REPORTED_CONTENT", "cried", "Bewitching")),
     (("PATIENT", "Following", "stranger"), ("REPORTED_CONTENT", "asked", "Following"))),
    (965, "dialogue_intercalated_permission_with_elliptical_condition",
     '‘But please let us keep the chair,’ asked Mary, in her gentle way, ‘if you can!’',
     '‘But please let us kept the chair,’ asked Mary, in her gentle way, ‘if you can!’',
     (("AGENT", "have", "me"), ("CONDITION", "let", "can"), ("SPEAKER", "said", "Dora"),
      ("MANNER", "said", "in"), ("SUBJECT", "can", "you")),
     (("AGENT", "keep", "us"), ("CONDITION", "let", "can"), ("SPEAKER", "asked", "Mary"))),
    (970, 'structural_negative_coordination_with_shared_perception',
     'For a few days afterwards, she was absorbed in her thoughts; but she neither saw him in the park, nor when she called.',
     'For a few days afterwards, she was absorbed in her thoughts; but she neither saw him in the park, and when she called.',
     (("NEGATION", "see", "neither"), ("NEGATIVE_COORDINATION", "neither", "nor"),
      ("TIME", "see", "call"), ("THEME", "see", "her")),
     (("NEGATION", "saw", "neither"), ("TIME", "saw", "called"), ("THEME", "saw", "him"))),
    (984, scoped.QUOTED_ASSURANCE_INCISE,
     '“And his assurance of safety, I think, carried immediate relief to her.”',
     '“And his assurance of safety, I think carried immediate relief to her.”',
     (("AGENT", "carried", "assurance"), ("EPISTEMIC_PARENTHESESIS", "carried", "suppose"),
      ("RECIPIENT", "carried", "him")),
     (("EPISTEMIC_PARENTHESESIS", "carried", "think"), ("RECIPIENT", "carried", "her"))),
    (990, scoped.SEMICOLON_MODAL_PASSIVE,
     "She could not deny such a claim; and from that day Mary's name was hardly ever repeated among them.",
     "She could not deny such a claim; and from that day Mary's name was hardly ever repeating among them.",
     (("NEGATION", "oppose", "not"), ("PASSIVE_PATIENT", "mentioned", "name"),
      ("FREQUENCY", "mentioned", "ever")),
     (("NEGATION", "deny", "not"), ("PASSIVE_PATIENT", "repeated", "name"),
      ("FREQUENCY", "repeated", "ever"))),
    (992, 'dialogue_intercalated_copular_comma_adjectives_and_coordinated_nominals',
     '“Mary is a very quiet, sensible girl indeed,” said Jane, “and a most amiable friend.”',
     '“Mary is a very quietly, sensible girl indeed,” said Jane, “and a most amiable friend.”',
     (("ATTRIBUTE", "woman", "respectable"), ("ATTRIBUTE", "woman", "sensible"),
      ("PREDICATE", "is", "neighbour"), ("SPEAKER", "added", "Charlotte")),
     (("ATTRIBUTE", "girl", "quiet"), ("PREDICATE", "is", "friend"), ("SPEAKER", "said", "Jane"))),
    (996, 'dialogue_split_contrast_with_independent_gerund_negation',
     '“We did not mind her not speaking to Mrs. Green,” said Miss Jane, “but we wish she had talked with Mary.”',
     '“We did not mind her speaking to Mrs. Green,” said Miss Jane, “but we wish she had talked with Mary.”',
     (("NEGATION", "mind", "not"), ("NEGATION", "talking", "not"), ("SPEAKER", "said", "Lucas"),
      ("RECIPIENT", "talking", "Long"), ("ASPECT_PERFECT", "danced", "had")),
     (("NEGATION", "mind", "not"), ("NEGATION", "speaking", "not"),
      ("SPEAKER", "said", "Jane"), ("ASPECT_PERFECT", "talked", "had"))),
    (890, 'dialogue_perfect_location_duration_and_followup_question',
     '“Our sister has been in York these two weeks. Have you never managed to find her there?”',
     '“Our sister has been in York these two weeks. Have you never managed to found her there?”',
     (("DURATION", "been", "months"), ("NEGATION", "happened", "never"),
      ("ASPECT_PERFECT", "happened", "Have"), ("AGENT", "see", "you"), ("LOCATION", "see", "there")),
     (("DURATION", "been", "weeks"), ("NEGATION", "managed", "never"),
      ("CONTROL_COMPLEMENT", "managed", "find"), ("AGENT", "find", "you"))),
    (898, 'structural_temporal_locative_antecedent_and_future_departure',
     'When the meeting ended, Mary returned with her father to London, from whence they were to set out early the next day.',
     'When the meeting ended, Mary returned with her father to London, from whence they were to sets out early the next day.',
     (("TIME", "returned", "broke"), ("GOAL", "returned", "Meryton"), ("SOURCE", "set", "Meryton"),
      ("LOCATIVE_RELATIVE", "Meryton", "set"), ("AGENT", "set", "they")),
     (("TIME", "returned", "ended"), ("GOAL", "returned", "London"),
      ("SOURCE", "set", "London"), ("LOCATIVE_RELATIVE", "London", "set"))),
    (919, 'dialogue_assertion_and_fronted_negative_modal_after_dismissal',
     '"Away! I do keep my word; never shall I make another like him, similar in design and function."',
     '"Away! I do keep my word; never I shall make another like him, similar in design and function."',
     (("NEGATION", "create", "never"), ("COMPARISON", "another", "yourself"),
      ("PREDICATE_OF", "equal", "another"), ("MODALITY", "create", "will")),
     (("NEGATION", "make", "never"), ("COMPARISON", "another", "him"),
      ("PREDICATE_OF", "similar", "another"), ("MODALITY", "make", "shall"))),
    (961, 'structural_continuative_particle_and_negative_gerund_supplement',
     'Then he went on calmly reading, but without lifting his eyes from the desk.',
     'Then he went on calmly reading, but without lifted his eyes from the desk.',
     (("CONTINUATIVE_ASPECT", "playing", "went"), ("MANNER", "playing", "softly"),
      ("NEGATION", "removing", "without"), ("AGENT", "removing", "she"), ("THEME", "removing", "eyes")),
     (("CONTINUATIVE_ASPECT", "reading", "went"), ("MANNER", "reading", "calmly"),
      ("NEGATION", "lifting", "without"), ("AGENT", "lifting", "he"), ("THEME", "lifting", "eyes"))),
    (981, 'dialogue_surprise_question_with_negative_partitive',
     '“What, none of them?”', '“What, none to them?”',
     (("SURPRISED_QUESTION", "What", "none"), ("PARTITIVE", "none", "you")),
     (("SURPRISED_QUESTION", "What", "none"), ("PARTITIVE", "none", "them"))),
    (993, 'dialogue_conditional_copular_ellipsis_and_temporal_comparison',
     '“I should be glad indeed, if it were. They were always good neighbours; and now they are better.”',
     '“I should be glad indeed, if it were. They were always good neighbours; and now they is better.”',
     (("CONDITION", "be", "were"), ("PREDICATE", "be", "sorry"), ("PREDICATE", "were", "friends"),
      ("PREDICATE", "are", "better"), ("ELLIPTIC_NOMINAL_HEAD", "better", "friends")),
     (("CONDITION", "be", "were"), ("PREDICATE", "be", "glad"), ("PREDICATE", "were", "neighbours"),
      ("PREDICATE", "are", "better"), ("ELLIPTIC_NOMINAL_HEAD", "better", "neighbours"))),
)


class Novel1000GrammarRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wordnet = Path(os.environ["WORDNET_DICT"])
        cls.parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet),
                            cache_size=0, max_items=ladder.MAX_ITEMS)
        cls.parser.parse("John opened the box.")
        sources = ladder.load_sources()
        cls.sources = {}
        for end in novel.ENDS:
            manifest = ladder.read_json(novel.candidate_path(end, "cohort"))
            cls.sources.update({c["ladder_index"]: c
                                for c in ladder.resolve(manifest, end - 99, sources)})
        handler = signal.signal(signal.SIGALRM, _deadline)
        cls.addClassCleanup(signal.signal, signal.SIGALRM, handler)

    def test_selected_spans_and_attachments(self):
        for index, root, positive, negative, real_edges, control_edges in CONTROLS:
            for source, links in ((index, real_edges), (positive, control_edges), (negative, None)):
                with self.subTest(index=index, source=source):
                    if isinstance(source, int):
                        case = self.sources[source]
                    else:
                        extracted, _ = extract(BOOK, source, length_min=1, length_max=45)
                        self.assertEqual([x["source_text"] for x in extracted], [source])
                        case, = extracted
                    row = measure(self.parser, case, with_semantics=True)
                    if links is None:
                        self.assertNotEqual(row.get("root_rule"), root)
                        continue
                    self.assertEqual(row["status"], "complete")
                    self.assertEqual(row["root_rule"], root)
                    self.assertFalse(row["forest_budget_exceeded"])
                    self.assertFalse(row["kbest_budget_exceeded"])
                    text = case["source_text"]
                    self.assertEqual(row["tree"]["span"], [0, len(text)])
                    graph = row["selected_graph"]["graph"]
                    nodes = {n["id"]: n for n in graph["nodes"]}
                    edges = {(e["relation"], nodes[e["source"]].get("surface"),
                              nodes[e["target"]].get("surface")) for e in graph["relations"]}
                    self.assertLessEqual(set(links), edges)
                    for node in nodes.values():
                        if node.get("span") and node.get("surface") is not None:
                            a, b = node["span"]
                            self.assertEqual(text[a:b], node["surface"])
                    if index == 996:
                        negated = [e for e in graph["relations"] if e["relation"] == "NEGATION"]
                        self.assertEqual(len(negated), 2)
                        self.assertEqual(len({tuple(nodes[e["target"]]["span"]) for e in negated}), 2)


if __name__ == "__main__":
    unittest.main()
