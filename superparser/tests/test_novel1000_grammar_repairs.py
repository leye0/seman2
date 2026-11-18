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
    (815, "structural_nor_inversion_with_without_nominal_coordination",
     "We felt still frozen with fear, nor could we think on that night without trembling and dread.",
     "We felt still frozen with fear, nor we could think on that night without trembling and dread.",
     (("PREDICATE", "feel", "parched"), ("NEGATION", "reflect", "nor"),
      ("NEGATION", "shuddering", "without"), ("CONJUNCT", "shuddering", "agony")),
     (("PREDICATE", "felt", "frozen"), ("NEGATION", "think", "nor"),
      ("NEGATION", "trembling", "without"), ("CONJUNCT", "trembling", "dread"))),
    (820, "structural_coordinated_restoration_with_parallel_gerund_means",
     "They quickly brought her back to the house and restored her to health by washing her with water and persuading her to drink a little tea.",
     "They quickly brought her back to the house and restored her to health by washing her with water and persuading her to drank tea.",
     (("GOAL", "brought", "deck"), ("RESULT", "restored", "animation"), ("MEANS", "restored", "rubbing"),
      ("MEANS", "restored", "forcing"), ("INSTRUMENT", "rubbing", "brandy"), ("CONTROL_COMPLEMENT", "forcing", "swallow")),
     (("GOAL", "brought", "house"), ("RESULT", "restored", "health"),
      ("MEANS", "restored", "washing"), ("CONTROL_COMPLEMENT", "persuading", "drink"))),
    (830, "documentary_postscript_initials_signature",
     ("P.P.S.--The mail will arrive soon. G. W.", "G. W."),
     "G. W.",
     (("SIGNATURE_SEQUENCE", "J", "T"),),
     (("SIGNATURE_SEQUENCE", "G", "W"),)),
    (837, "dialogue_exclamation_with_shared_subject_postposed_report",
     '"Hush!" she cried and stared about her exactly like a bear.',
     '"Hush!" she crossed and stared about her exactly like a bear.',
     (("REPORTED_CONTENT", "roared", "Si-lence"), ("SPEAKER", "roared", "he"),
      ("AGENT", "looked", "he"), ("SIMILE", "looked", "like")),
     (("REPORTED_CONTENT", "cried", "Hush"), ("SPEAKER", "cried", "she"),
      ("AGENT", "stared", "she"), ("SIMILE", "stared", "like"))),
    (839, "structural_inverted_conditional_with_nominal_apposition",
     "Should the proposal they had drafted prove practical, Henry, already virtually an opponent, would not hesitate to accept it.",
     "Should the proposal they had drafted proved practical, Henry, already virtually an opponent, would not hesitate to accept it.",
     (("CONDITION", "hesitate", "prove"), ("APPOSITION", "Silver", "traitor"),
      ("NEGATION", "hesitate", "not"), ("AGENT", "adopt", "Silver")),
     (("CONDITION", "hesitate", "prove"), ("APPOSITION", "Henry", "opponent"),
      ("NEGATION", "hesitate", "not"), ("AGENT", "accept", "Henry"))),
    (845, "structural_existential_nominal_contrast_with_shared_head",
     "But there was no trace of returning anger in their faces, rather, indeed, of growing despair at the result.",
     "But there was no trace of returning anger in their faces, rather, indeed, by growing despair at the result.",
     (("NEGATIVE_QUANTIFIER", "sign", "no"), ("CORRECTION", "courage", "terror"),
      ("ELLIPTIC_NOMINAL_HEAD", "terror", "sign"), ("CAUSE", "terror", "at")),
     (("NEGATIVE_QUANTIFIER", "trace", "no"), ("CORRECTION", "anger", "despair"),
      ("ELLIPTIC_NOMINAL_HEAD", "despair", "trace"))),
    (869, "structural_equative_simile_with_passive_measure",
     "The cries of children and voices of men were as muted, as if the rooms had been lined that thickness with wool.",
     "The cries of children and voices of men were as muted, as if the rooms had been line that thickness with wool.",
     (("DEGREE_STANDARD", "hushed", "strewn"), ("PASSIVE_PATIENT", "strewn", "streets"),
      ("ASPECT_PERFECT", "strewn", "had"), ("MEASURE", "strewn", "depth")),
     (("DEGREE_STANDARD", "muted", "lined"), ("PASSIVE_PATIENT", "lined", "rooms"),
      ("MEASURE", "lined", "thickness"))),
    (899, "dialogue_fused_modal_stance_and_passive_negative_tag",
     '“But, my friend, your uncle cannot lend the tools, I am certain. They are needed at the station, Mr. Norton, are they not?”',
     '“But, my friend, your uncle cannot lend the tools, I am certain. They are needed at the station, Mr. Norton, they are not?”',
     (("NEGATION", "spare", "not"), ("EPISTEMIC_PARENTHESESIS", "spare", "am"),
      ("PASSIVE_PATIENT", "wanted", "They"), ("NEGATION", "are", "not")),
     (("NEGATION", "lend", "not"), ("EPISTEMIC_PARENTHESESIS", "lend", "am"),
      ("PASSIVE_PATIENT", "needed", "They"), ("NEGATION", "are", "not"))),
    (900, "structural_shared_agent_with_independent_genitive_destinations",
     "She met them on their leaving the office, and escorted them to their uncle's where her grief and disappointment, and the anxiety of everyone, was thoroughly talked over.",
     "She met them on their leaving the office, and escorted them to their uncle where her grief and disappointment, and the anxiety of everyone, was thoroughly talked over.",
     (("TEMPORAL_CLAUSE", "joined", "entering"), ("ELLIPTIC_POSSESSOR", "'s", "aunt"),
      ("PASSIVE_PATIENT", "talked", "regret"), ("CONJUNCT", "regret", "concern")),
     (("TEMPORAL_CLAUSE", "met", "leaving"), ("ELLIPTIC_POSSESSOR", "'s", "uncle"),
      ("PASSIVE_PATIENT", "talked", "grief"), ("CONJUNCT", "grief", "anxiety"))),
    (907, "documentary_narrator_resumption_before_date",
     ("Martin, in continuation.\n\nSeptember 14th, 1842.", "Martin, in continuation."),
     "Martin, in continuation.",
     (("NARRATOR_RESUMPTION", "Walton", "continuation"),),
     (("NARRATOR_RESUMPTION", "Martin", "continuation"),)),
    (918, "structural_locative_coordination_with_active_and_passive_relatives",
     "The tower of Oxford stood under the trees that sheltered it and the ridge of hill above hill by which it was enclosed.",
     "The tower of Oxford stood under the trees that sheltered it and the ridge of hill above hill by which it was enclose.",
     (("LOCATIVE_AFFILIATION", "spire", "Evian"), ("AGENT", "surrounded", "woods"),
      ("PASSIVE_AGENT", "overhung", "range"), ("PASSIVE_PATIENT", "overhung", "it")),
     (("LOCATIVE_AFFILIATION", "tower", "Oxford"), ("AGENT", "sheltered", "trees"),
      ("PASSIVE_AGENT", "enclosed", "ridge"), ("PASSIVE_PATIENT", "enclosed", "it"))),
    (943, "dialogue_dialectal_identity_reprise_with_negative_perfect",
     '"I\'m old John Norton, I am; and I haven\'t talked with a sailor these two months."',
     '"I\'m old John Norton, I am; and I haven\'t talk with a sailor these two months."',
     (("PREDICATE", "'m", "Ben"), ("ELLIPTIC_REPRISE", "am", "'m"),
      ("ASPECT_PERFECT", "spoke", "have"), ("NEGATION", "spoke", "n't"), ("DURATION", "spoke", "years")),
     (("PREDICATE", "'m", "John"), ("ASPECT_PERFECT", "talked", "have"),
      ("NEGATION", "talked", "n't"), ("DURATION", "talked", "months"))),
    (944, "structural_fronted_comparison_set_with_predicative_superlative",
     "Of all the signals of that difficult day, this obvious grief on the part of Alice seemed the worst.",
     "Of all the signals of that difficult day, this obvious grief on the part of Alice seemed the worse.",
     (("SUBJECT", "appeared", "anxiety"), ("PREDICATE", "appeared", "worst"),
      ("EXPERIENCER", "anxiety", "John")),
     (("SUBJECT", "seemed", "grief"), ("PREDICATE", "seemed", "worst"),
      ("EXPERIENCER", "grief", "Alice"))),
    (946, "dialogue_reported_polite_instruction_with_elliptic_target",
     '"Mr. Harrison, would you please pick us off one of those sentries, sir? Daniel, if possible," asked the lieutenant.',
     '"Mr. Harrison, would you please picked us off one of those sentries, sir? Daniel, if possible," asked the lieutenant.',
     (("SPEAKER", "said", "captain"), ("VOCATIVE", "pick", "Trelawney"),
      ("BENEFICIARY", "pick", "me"), ("PATIENT", "pick", "one"),
      ("ELLIPTIC_TARGET_REFINEMENT", "one", "Hands")),
     (("SPEAKER", "asked", "lieutenant"), ("VOCATIVE", "pick", "Harrison"),
      ("BENEFICIARY", "pick", "us"), ("ELLIPTIC_TARGET_REFINEMENT", "one", "Daniel"))),
    (962, "dialogue_epistemic_modal_content_with_titled_vocative",
     "‘I would imagine you might return to the office at last, Miss Jane!’",
     "‘I would imagine you might returned to the office at last, Miss Jane!’",
     (("CONTENT", "think", "come"), ("AGENT", "come", "YOU"),
      ("VOCATIVE", "think", "Copperfield"), ("HONORIFIC", "Copperfield", "Master")),
     (("CONTENT", "imagine", "return"), ("AGENT", "return", "you"),
      ("HONORIFIC", "Jane", "Miss"))),
    (964, "structural_shared_subject_order_with_genitive_shop_and_intensifier",
     "She acted on Mr. Brown’s suggestion, and placed the request at the shoe-maker’s herself.",
     "She acted on Mr. Brown’s suggestion, and placed the request at the shoe-maker herself.",
     (("BASIS", "acted", "opinion"), ("POSSESSOR", "opinion", "Crupp"),
      ("ELLIPTIC_POSSESSOR", "’s", "cook"), ("AGENT_EMPHASIS", "I", "myself")),
     (("BASIS", "acted", "suggestion"), ("POSSESSOR", "suggestion", "Brown"),
      ("ELLIPTIC_POSSESSOR", "’s", "maker"), ("AGENT_EMPHASIS", "She", "herself"))),
    (974, "structural_elliptic_genitive_location_and_emphatic_simile",
     "She was always prompt at the workshop; at the Lawyer’s too: and she indeed did labour, as the usual saying is, like a machine.",
     "She was always prompt at the workshop; at the Lawyer’s too: and she indeed did laboured, as the usual saying is, like a machine.",
     (("PREDICATE", "was", "punctual"), ("ELLIPTIC_POSSESSOR", "’s", "Doctor"),
      ("SIMILE", "work", "like"), ("METALINGUISTIC_INCISE", "like", "is")),
     (("PREDICATE", "was", "prompt"), ("ELLIPTIC_POSSESSOR", "’s", "Lawyer"),
      ("SIMILE", "labour", "like"), ("METALINGUISTIC_INCISE", "like", "is"))),
    (1000, "structural_perspective_with_coordinated_relatives_and_stranded_gap",
     "Of that he was quite ignorant; to him she was only the woman who made herself welcome nowhere, and who had not thought him pleasant enough to talk with.",
     "Of that he was quite ignorant; to him she was only the woman who made herself welcome nowhere, and who had not thought him pleasant enough to talked with.",
     (("RELATIVE_CLAUSE", "man", "made"), ("RELATIVE_CLAUSE", "man", "thought"),
      ("NEGATION", "thought", "not"), ("STRANDED_COMPLEMENT", "with", "her"),
      ("AGENT", "dance", "man")),
     (("RELATIVE_CLAUSE", "woman", "made"), ("RELATIVE_CLAUSE", "woman", "thought"),
      ("STRANDED_COMPLEMENT", "with", "him"), ("AGENT", "talk", "woman"))),
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
                        paragraph, expected = source if isinstance(source, tuple) else (source, source)
                        extracted, _ = extract(BOOK, paragraph, length_min=1, length_max=45)
                        chosen = [x for x in extracted if x["source_text"] == expected]
                        self.assertEqual(len(chosen), 1, [x["source_text"] for x in extracted])
                        case, = chosen
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
                    if index in (899, 996):
                        negated = [e for e in graph["relations"] if e["relation"] == "NEGATION"]
                        self.assertEqual(len(negated), 2)
                        self.assertEqual(len({tuple(nodes[e["target"]]["span"]) for e in negated}), 2)


if __name__ == "__main__":
    unittest.main()
