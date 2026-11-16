"""Selected source trees, lexical contrasts and semantic edges for Novel-600."""
import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import ParseReport, Parser
from seman_parser import scoped_novel_ladder as plans

DATA = Path(__file__).resolve().parents[1] / "data"
PROBE = Book(999, "Syntax contrast", "Test", "tests")


class NovelLadderAttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser.from_dir(DATA, cache_size=0)

    def assert_family(self, rule, attested, positive, negative, links, *, attested_spans=()):
        for source, shared in ((attested, True), (positive, True), (negative, False)):
            with self.subTest(source=source):
                cases, _ = extract(PROBE, source, length_min=1, length_max=120)
                case, = cases
                prepared, lattice, result = parse_corpus_case(
                    self.parser, case, max_items=50_000, kbest_work_limit=500_000,
                )
                self.assertEqual((prepared.analysis_text, lattice.text, result.text), (source, source, source))
                root = result.best()
                self.assertEqual(shared, root is not None and root.rule_id == rule)
                if not shared:
                    continue
                self.assertEqual((root.start, root.end), (0, len(source)))
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                graph = ParseReport(
                    result, self.parser._quoted_sentence_resources, lattice,
                ).best_semantic_graph()
                handles = graph["handles"]
                actual = {(e["relation"], e["source"], e["target"])
                          for e in graph["graph"]["relations"]}
                for relation, before, after in links:
                    self.assertIn((relation, handles[before], handles[after]), actual)
                if source == attested:
                    nodes = {n["id"]: n for n in graph["graph"]["nodes"]}
                    for handle, start, end, surface in attested_spans:
                        self.assertEqual(nodes[handles[handle]]["span"], [start, end])
                        self.assertEqual(source[start:end], surface)

    def test_novel_502_fronted_precipitation(self):
        self.assert_family(
            plans.FRONTED_PRECIPITATION,
            "Suddenly a heavy storm of rain descended.",
            "Abruptly the thick shower of hail fell.",
            "Abruptly the final portion of hail fell.",
            [
                ("TIME", "event", "onset"),
                ("THEME", "event", "weather"),
                ("MODIFIER", "weather", "intensity"),
                ("MATERIAL", "weather", "precipitation"),
            ],
            attested_spans=[
                ("onset", 0, 8, "Suddenly"),
                ("intensity", 11, 16, "heavy"),
                ("weather", 17, 22, "storm"),
                ("precipitation", 26, 30, "rain"),
                ("event", 31, 40, "descended"),
            ],
        )

    def test_novel_506_postpos_quality(self):
        self.assert_family(
            plans.POSTPOS_QUALITY,
            "It is a scene terrifically desolate.",
            "It was a vista remarkably bleak.",
            "They is a vista remarkably bleak.",
            [
                ("MODIFIER", "classification", "quality"),
                ("DEGREE", "quality", "degree"),
                ("PREDICATE", "subject", "classification"),
            ],
        )

    def test_novel_508_framed_result(self):
        self.assert_family(
            plans.FRAMED_RESULT,
            "In the mean time I worked on, and my labour was already considerably advanced.",
            "In the meantime she walked on, and her legs were already very tired.",
            "In the mean time she walked on, and her body were already very tired.",
            [
                ("PARTICLE", "continuing", "continuation"),
                ("DEGREE", "state", "degree"),
                ("PREDICATE", "affected", "state"),
                ("TIME", "state", "aspect"),
                ("CONJUNCT", "continuing", "result"),
            ],
        )

    def test_novel_509_purpose_then(self):
        self.assert_family(
            plans.PURPOSE_THEN,
            "I paused to collect myself and then entered the chamber.",
            "We paused to steady ourselves and then entered the corridor.",
            "I paused to steady himself and then approached the table.",
            [
                ("PURPOSE", "first", "purpose"),
                ("AGENT", "purpose", "subject"),
                ("COREFERENCE", "self", "subject"),
                ("AGENT", "second", "subject"),
                ("PRECEDES", "first", "second"),
                ("TIME", "second", "then"),
            ],
        )

    def test_novel_512_recall_progressive(self):
        self.assert_family(
            plans.RECALL_PROGRESSIVE,
            "Remember, I am not recording the vision of a madman.",
            "Remember, she was not describing the dream of a child.",
            "Remember, she were not describing the dream of a child.",
            [
                ("CONTENT", "remember", "content"),
                ("AGENT", "recording", "recorder"),
                ("ASPECT", "recording", "progressive"),
                ("NEGATION", "recording", "negation"),
            ],
        )

    def test_novel_513_temporal_shared_modal(self):
        self.assert_family(
            plans.TEMPORAL_SHARED_MODAL,
            "When reason returned, she would remonstrate and endeavour to inspire me with resignation.",
            "When courage returned, she would protest and try to inspire him with confidence.",
            "When courage returned, she would protest and tried to inspire him with confidence.",
            [
                ("TIME", "first", "when"),
                ("TIME", "second", "when"),
                ("MODALITY", "first", "modal"),
                ("MODALITY", "second", "modal"),
                ("AGENT", "action", "subject"),
                ("CONJUNCT", "first", "second"),
            ],
        )

    def test_novel_515_negative_equative(self):
        self.assert_family(
            plans.NEGATIVE_EQUATIVE,
            "Never did I behold a vision so horrible as his face, of such loathsome yet appalling hideousness.",
            "Never did she see a picture so beautiful as his portrait, of such subtle yet brilliant artistry.",
            "Never did she saw a picture so beautiful as his portrait, of such subtle yet brilliant artistry.",
            [
                ("NEGATION", "event", "negation"),
                ("MODIFIER", "object", "quality"),
                ("COMPARISON", "quality", "standard"),
                ("MODIFIER", "standard", "supplement"),
                ("CONTRAST", "quality1", "quality2"),
            ],
        )

    def test_novel_516_interposed_manner(self):
        self.assert_family(
            plans.INTERPOSED_MANNER,
            "While my companion contemplated with a serious and satisfied spirit the magnificent appearances of things, I delighted in investigating their causes.",
            "While my brother contemplated with a serious and satisfied spirit the magnificent appearances of history, I delighted in investigating their origins.",
            "While my brother contemplated with a serious and satisfied spirit the magnificent appearances of history, I delighted in investigate their origins.",
            [
                ("MANNER", "temporal", "manner"),
                ("THEME", "temporal", "observed"),
                ("TIME", "matrix", "temporal"),
                ("AGENT", "activity", "subject"),
                ("THEME", "activity", "goal"),
            ],
        )

    def test_novel_520_vocative_comparison(self):
        self.assert_family(
            plans.VOCATIVE_COMPARISON,
            "My beloved sister, the sickening failing of your heart-felt expectations is, in prospect, more terrible to me than my own death.",
            "My dear brother, the troubling loss of our hopes was, in retrospect, more painful to us than his own illness.",
            "My dear brother, the troubling loss of our hopes were, in retrospect, more painful to us than his own illness.",
            [
                ("VOCATIVE", "event", "vocative"),
                ("EXPERIENCER", "quality", "experiencer"),
                ("COMPARISON", "quality", "standard"),
                ("CIRCUMSTANCE", "quality", "parenthesis"),
            ],
        )

    def test_novel_523_bare_passive_recipient(self):
        self.assert_family(
            plans.BARE_PASSIVE_RECIPIENT,
            "I feared the vengeance of the disappointed fiend, yet I was unable to overcome my repugnance to the task which was enjoined me.",
            "She dreaded the anger of her father, yet she was unable to conquer her aversion to the duty which was assigned her.",
            "She dreaded the anger of her father, yet she was unable to conquer her aversion to the duty which were assigned her.",
            [
                ("THEME", "relative_event", "task"),
                ("RECIPIENT", "relative_event", "recipient"),
                ("MODIFIER", "task", "relative_event"),
                ("AGENT", "action", "controller"),
            ],
        )

    def test_novel_534_motion_speech(self):
        self.assert_family(
            plans.MOTION_SPEECH,
            "I ran to him at once, calling to my mother.",
            "She hurried to the door immediately, shouting to her brother.",
            "She hurried to the door immediately, shouted to her brother.",
            [
                ("DESTINATION", "motion", "destination"),
                ("ADDRESSEE", "speech", "addressee"),
                ("SUPPLEMENT", "motion", "speech"),
                ("AGENT", "speech", "subject"),
            ],
        )

    def test_novel_541_parallel_groups(self):
        self.assert_family(
            plans.PARALLEL_GROUPS,
            "The doctor and Gray and I for one; the squire, Hunter, and Joyce upon the other.",
            "The captain and Mary and I for one; the cook, Peter, and Edward upon the other.",
            "The captain and Mary and I for one, the cook, Peter, and Edward upon the other.",
            [
                ("PARALLEL", "first_group", "other_group"),
                ("MEMBER", "first_group", "second_member"),
                ("MEMBER", "other_group", "fifth_member"),
            ],
        )

    def test_novel_548_experiential_existential(self):
        self.assert_family(
            plans.EXPERIENTIAL_EXISTENTIAL,
            "For me, at least, there was no secret about the matter, for I was, in a way, a sharer in his alarms.",
            "For her, at least, there was no mystery about the affair, for she was, in a sense, a participant in his troubles.",
            "For her, at least, there was no mystery about the affair, for she were, in a sense, a participant in his troubles.",
            [
                ("CAUSE", "left", "right"),
                ("NEGATION", "entity", "negation"),
                ("QUALIFICATION", "classification", "qualification"),
                ("COMPLEMENT", "classification", "shared_state"),
            ],
        )

    def test_novel_551_minor_negative(self):
        self.assert_family(
            plans.MINOR_NEGATIVE,
            "Not at all.",
            "Not in the least.",
            "Not all are ready.",
            [
                ("DEGREE", "negation", "degree"),
            ],
        )

    def test_novel_553_topical_possession(self):
        self.assert_family(
            plans.TOPICAL_POSSESSION,
            "That thought I never had.",
            "This objection she never had.",
            "That feeling they never has.",
            [
                ("TOPIC", "event", "topic"),
                ("THEME", "event", "topic"),
                ("NEGATION", "event", "negation"),
            ],
        )

    def test_novel_558_numeric_vocative(self):
        self.assert_family(
            plans.NUMERIC_VOCATIVE,
            "‘Well, Twenty Seven,’ said Mr. Creakle, mournfully admiring him.",
            "“Well, Thirty Two,” said Mrs. Jones, silently watching her.",
            "“Well, Thirty,” said Mrs. Jones, silently watching her.",
            [
                ("VOCATIVE", "report", "address"),
                ("AGENT", "report", "speaker"),
                ("MANNER", "gesture", "manner"),
                ("EXPERIENCER", "gesture", "speaker"),
            ],
        )

    def test_novel_559_perfect_located_motion(self):
        self.assert_family(
            plans.PERFECT_LOCATED_MOTION,
            "Peggotty had hastened to the chair before the fire.",
            "Edward had hurried to the bench beside the window.",
            "Edward had hurry to the bench beside the window.",
            [
                ("ASPECT", "motion", "perfect"),
                ("DESTINATION", "motion", "destination"),
                ("LOCATION", "destination", "location"),
            ],
        )

    def test_novel_570_amount_restart(self):
        self.assert_family(
            plans.AMOUNT_RESTART,
            "‘What should you--what should I--how much ought I to--what would it be right to pay the waiter, if you please?’",
            "“What could he—what should we—how much ought we to—what might it be fair to pay the driver, if you please?”",
            "“What could he—what should I—how much ought we to—what might it be fair to pay the driver, if you please?”",
            [
                ("REPAIR", "first", "second"),
                ("REPAIR", "second", "third"),
                ("REPAIR", "third", "question"),
                ("RECIPIENT", "payment", "payee"),
                ("THEME", "payment", "amount"),
                ("EXTRAPOSED_SUBJECT", "evaluation", "payment"),
            ],
        )

    def test_novel_571_anticipatory_means(self):
        self.assert_family(
            plans.ANTICIPATORY_MEANS,
            "So, the close of every week was a delicious time for me; and I got through the rest of the week by looking forward to it.",
            "Thus, the end of each month was a welcome time for her; and she got through the rest of the month by looking forward to it.",
            "Thus, the end of each month was a welcome time for her; and she got through the rest of the month by looked forward to it.",
            [
                ("THEME", "left", "period"),
                ("PATH", "traversal", "interval"),
                ("MEANS", "traversal", "means"),
                ("EXPERIENCER", "means", "traveler"),
            ],
        )

    def test_novel_572_apprehensive_gaze(self):
        self.assert_family(
            plans.APPREHENSIVE_GAZE,
            "I felt apprehensive that I was personally interested in this dialogue, and sought Mr. Murdstone’s eye as it lighted on mine.",
            "She felt uneasy that she was directly involved in this affair, and sought Mary’s gaze as it settled on hers.",
            "She felt uneasy that she were directly involved in this affair, and sought Mary’s gaze as it settled on hers.",
            [
                ("CONTENT", "apprehensive", "content"),
                ("TIME", "seeking", "gaze"),
                ("ANAPHOR", "gaze_subject", "sought"),
                ("POSSESSOR", "gaze_target", "gaze_possessor"),
                ("ELLIPSIS_ANTECEDENT", "gaze_target", "sought"),
            ],
        )

    def test_novel_573_factive_gesture(self):
        self.assert_family(
            plans.FACTIVE_GESTURE,
            "‘I don’t know all I have done, in my fatuity,’ said Mr. Wickfield, putting out his hands, as if to deprecate my condemnation.",
            "“I don’t remember all I have said, in my confusion,” said Mrs. Brown, holding out her arms, as if to prevent my departure.",
            "“I don’t remember all I have say, in my confusion,” said Mrs. Brown, holding out her arms, as if to prevent my departure.",
            [
                ("RELATIVE", "totality", "action"),
                ("THEME", "action", "totality"),
                ("REPORTED_CONTENT", "report", "content"),
                ("APPARENT_PURPOSE", "gesture", "apparent_purpose"),
            ],
        )

    def test_novel_574_clock_status(self):
        self.assert_family(
            plans.CLOCK_STATUS,
            "So, at six o’clock that evening, which was one of the early office evenings, I announced myself as ready, to Uriah.",
            "Thus, at seven o’clock that morning, which was one of the late market mornings, she declared herself as available, to Mary.",
            "Thus, at seven o’clock that morning, which was one of the late market mornings, she declared myself as available, to Mary.",
            [
                ("TIME", "report", "period"),
                ("MODIFIER", "period", "relative"),
                ("COREFERENCE", "self", "subject"),
                ("CONTENT", "report", "status"),
                ("ADDRESSEE", "report", "addressee"),
            ],
        )

    def test_novel_583_genitive_where(self):
        self.assert_family(
            plans.GENITIVE_WHERE,
            "It was at Sir William Lucas's, where a large party were assembled.",
            "It was at Sir Edward Martin's, where a small crowd was gathered.",
            "It was at Sir Edward Martin, where a small crowd was gathered.",
            [
                ("LOCATION", "event", "place"),
                ("POSSESSOR", "place", "surname"),
                ("LOCATION", "relative", "place"),
                ("MODIFIER", "place", "relative"),
            ],
        )

    def test_novel_589_emotive_rebuke(self):
        self.assert_family(
            plans.EMOTIVE_REBUKE,
            "Miss Bingley warmly resented the indignity he had received, in an expostulation with her brother for talking such nonsense.",
            "Miss Morgan bitterly resented the insult she had suffered, in an argument with her sister for talking such rubbish.",
            "Miss Morgan bitterly resented the insult she had suffer, in an argument with her sister for talking such rubbish.",
            [
                ("RELATIVE", "offense", "received"),
                ("THEME", "received", "offense"),
                ("INTERLOCUTOR", "rebuke", "interlocutor"),
                ("CAUSE", "rebuke", "reason"),
                ("AGENT", "reason", "interlocutor"),
            ],
        )

    def test_novel_595_modal_gerund_contrast(self):
        self.assert_family(
            plans.MODAL_GERUND_CONTRAST,
            "Elizabeth could hardly help laughing at so convenient a proposal; yet was really vexed that her mother should be always giving him such an epithet.",
            "Mary could hardly help laughing at so foolish a remark; yet was deeply annoyed that her brother should be continually giving him such an excuse.",
            "Mary could hardly help laughing at so foolish a remark; yet was deeply annoyed that her brother should be continually give him such an excuse.",
            [
                ("AGENT", "reaction", "subject"),
                ("PREDICATE", "subject", "vexed_attribute"),
                ("CONTRAST", "left", "right"),
                ("CONTENT", "vexed_attribute", "content"),
                ("AGENT", "giving", "relative_agent"),
                ("RECIPIENT", "giving", "recipient"),
            ],
        )

    def test_novel_597_dispatch_purposes(self):
        self.assert_family(
            plans.DISPATCH_PURPOSES,
            "Elizabeth most thankfully consented, and a servant was dispatched to Longbourn to acquaint the family with her stay and bring back a supply of clothes.",
            "Mary very politely consented, and a messenger was sent to London to acquaint the family with their plans and bring back a bundle of letters.",
            "Mary very politely consented, and a messenger was sent to London to acquaint the family with their plans and brought back a bundle of letters.",
            [
                ("DESTINATION", "dispatch", "destination"),
                ("PURPOSE", "dispatch", "purpose1"),
                ("PURPOSE", "dispatch", "purpose2"),
                ("AGENT", "purpose1", "messenger"),
                ("AGENT", "purpose2", "messenger"),
                ("PARTICLE", "purpose2", "particle"),
            ],
        )

    def test_novel_598_document_relative(self):
        self.assert_family(
            plans.DOCUMENT_RELATIVE,
            "When she came to that part of the letter in which her family were mentioned in terms of such mortifying, yet merited reproach, her sense of shame was severe.",
            "When he came to this passage of the report in which his household was described in terms of such harsh, yet justified criticism, his sense of guilt was acute.",
            "When he came to this passage of the report in which his household was describe in terms of such harsh, yet justified criticism, his sense of guilt was acute.",
            [
                ("TIME", "event", "when"),
                ("MODIFIER", "part", "mention"),
                ("LOCATION", "mention", "part"),
                ("MANNER", "mention", "terms"),
                ("PREDICATE", "affect", "attribute"),
            ],
        )

    def test_novel_600_concessive_affect(self):
        self.assert_family(
            plans.CONCESSIVE_AFFECT,
            "Mrs. Bennet, all amazement, though flattered by having a guest of such high importance, received her with the utmost politeness.",
            "Mrs. Brown, all astonishment, though pleased by having a visitor of such great importance, welcomed him with the greatest courtesy.",
            "Mrs. Brown, all astonishment, though pleased by have a visitor of such great importance, welcomed him with the greatest courtesy.",
            [
                ("PREDICATE", "subject", "affect"),
                ("CONCESSION", "reception", "flatter"),
                ("CAUSE", "flatter", "cause"),
                ("AGENT", "having", "subject"),
                ("MANNER", "reception", "manner"),
            ],
        )


    def test_novel_522_distinguishes_comparison_and_outer_relative(self):
        self.assert_family(
            plans.COPULAR_COMPARED_RELATIVE,
            "It was, in fact, a sledge, like that we had seen before, which had drifted towards us in the night on a large fragment of ice.",
            "It was, indeed, a boat, like that we had found earlier, which had floated towards the shore during the storm on a rising tide.",
            "It was, indeed, a boat, like that we had find earlier, which had floated towards the shore during the storm on a rising tide.",
            [
                ("ATTRIBUTE", "event", "vehicle"), ("DISCOURSE", "event", "stance"),
                ("COMPARISON", "vehicle", "standard"), ("RELATIVE", "standard", "observation"),
                ("THEME", "observation", "standard"), ("AGENT", "observation", "observer"),
                ("RELATIVE", "vehicle", "motion"), ("THEME", "motion", "vehicle"),
                ("COREFERENCE", "relative_marker", "vehicle"), ("TIME", "motion", "time"),
                ("DIRECTION", "motion", "direction"), ("CIRCUMSTANCE", "motion", "support"),
            ],
        )

    def test_novel_543_concession_is_modal_perfect_and_capacity_controls_infinitive(self):
        self.assert_family(
            plans.MODAL_PERFECT_CONCESSION,
            "Sharp as must have been his annoyance, Silver had the strength of mind to hide it.",
            "Great as might have been her fear, Clara had the strength of character to face it.",
            "Great as might have be her fear, Clara had the strength of character to face it.",
            [
                ("CONCESSION", "possession", "state"), ("THEME", "state", "state_bearer"),
                ("ATTRIBUTE", "state", "degree_state"), ("MODALITY", "state", "modal"),
                ("ASPECT", "state", "aspect"), ("THEME", "possession", "capacity"),
                ("COMPLEMENT", "capacity", "action"), ("AGENT", "action", "subject"),
                ("THEME", "action", "anaphor"),
            ],
        )

    def test_novel_566_preserves_the_full_existential_content(self):
        self.assert_family(
            plans.INCISED_EXISTENTIAL_CONTENT,
            "My impression is, after many years of consideration, that there never can have been anybody in the world who played worse.",
            "Her conclusion was, after several months of observation, that there never could have been anybody in the village who sang better.",
            "Her conclusion was, after several months of observation, that there never could has been anybody in the village who sang better.",
            [
                ("TIME", "event", "consideration_time"), ("CONTENT", "subject", "content"),
                ("EXISTENT", "content", "pivot"), ("DOMAIN", "pivot", "domain"),
                ("MODALITY", "content", "modal"), ("ASPECT", "content", "aspect"),
                ("NEGATION", "modal", "negation"), ("RELATIVE", "pivot", "relative_action"),
                ("AGENT", "relative_action", "pivot"), ("MANNER", "relative_action", "relative_manner"),
            ],
        )

    def test_novel_588_frequency_has_scope_and_charlotte_stays_subject(self):
        self.assert_family(
            plans.FREQUENCY_CONTRAST,
            "Once or twice she could discern a faint blush; but in general Charlotte wisely did not hear.",
            "Once or twice he could notice a slight movement; but in general Clara prudently did not speak.",
            "Once or twice he could noticed a slight movement; but in general Clara prudently did not speak.",
            [
                ("ALTERNATIVE", "first_frequency", "second_frequency"),
                ("FREQUENCY", "perception", "first_frequency"), ("EXPERIENCER", "perception", "observer"),
                ("THEME", "perception", "perceived"), ("FREQUENCY", "hearing", "generalization"),
                ("EXPERIENCER", "hearing", "hearer"), ("MANNER", "hearing", "manner"),
                ("NEGATION", "hearing", "negation"), ("CONTRAST", "perception", "hearing"),
            ],
        )

    def test_novel_599_shared_subject_depictive_and_finite_purpose(self):
        self.assert_family(
            plans.DEPICTIVE_FINITE_PURPOSE,
            "Elizabeth received her congratulations amongst the rest, and then, sick of this folly, took refuge in her own room, that she might think with freedom.",
            "Clara accepted her apologies among the guests, and then, tired of the commotion, took shelter in her room, that she might rest with ease.",
            "Clara accepted her apologies among the guests, and then, tired of the commotion, took shelter in her room, that she might rested with ease.",
            [
                ("THEME", "event", "item"), ("CIRCUMSTANCE", "event", "group"),
                ("AGENT", "event", "subject"), ("AGENT", "second", "subject"),
                ("CONJUNCT", "event", "second"), ("TIME", "second", "then"),
                ("DEPICTIVE", "second", "state"), ("THEME", "state", "subject"),
                ("LOCATION", "second", "location"), ("PURPOSE", "second", "purpose"),
                ("AGENT", "purpose", "purpose_subject"), ("MANNER", "purpose", "purpose_manner"),
            ],
        )

    def test_novel_503_relative_object_gap_refers_to_the_matrix_object(self):
        self.assert_family(
            plans.EMPHATIC_OBJECT_RELATIVE,
            "She indeed gained the resignation she desired.",
            "He indeed bought the book he wanted.",
            "He indeed bought the book him wanted.",
            [("THEME", "event", "object"), ("THEME", "relative_event", "object"),
             ("AGENT", "relative_event", "relative_subject"), ("RELATIVE", "object", "relative_event")],
        )

    def test_novel_507_interjection_and_addressee_are_not_two_names(self):
        self.assert_family(
            plans.REPORTED_EXCLAMATION_VOCATIVE,
            '"Oh, Justine!" said she.',
            '“Ah, Margaret!” exclaimed he.',
            '“Oh, Margaret!” he broke the chair.',
            [("VOCATIVE", "outcry", "addressee"), ("AGENT", "event", "speaker"),
             ("REPORTED_CONTENT", "event", "outcry"), ("ADDRESSEE", "event", "addressee")],
        )

    def test_novel_511_fever_is_antecedent_and_months_are_duration(self):
        self.assert_family(
            plans.EMBEDDED_DURATION_RELATIVE,
            "This was the commencement of a nervous fever which confined me for several months.",
            "This was the onset of a severe illness which detained her for several weeks.",
            "This was the onset of a severe illness which detain her for several weeks.",
            [("ATTRIBUTE", "event", "classification"), ("COMPLEMENT", "classification", "antecedent"),
             ("RELATIVE", "antecedent", "relative_event"), ("AGENT", "relative_event", "antecedent"),
             ("THEME", "relative_event", "affected"), ("DURATION", "relative_event", "duration")],
        )

    def test_novel_530_reports_a_negative_modal_question(self):
        self.assert_family(
            plans.REPORTED_MODAL_CONFIRMATION,
            '\"You won\'t forget?\" he inquired anxiously.',
            '\"She wouldn\'t listen?\" he asked softly.',
            '\"You won forget?\" he inquired anxiously.',
            [("AGENT", "question_event", "question_subject"), ("MODALITY", "question_event", "modal"),
             ("NEGATION", "modal", "negation"), ("AGENT", "event", "speaker"),
             ("MANNER", "event", "manner"), ("REPORTED_CONTENT", "event", "question_event")],
        )

    def test_novel_576_quoted_reprise_is_a_response_not_an_apposition(self):
        self.assert_family(
            plans.QUOTED_NEGATIVE_REPRISE,
            '“No, not at all.”',
            '“No, not in the least.”',
            '“No, not a word.”',
            [("DEGREE", "negation", "degree"), ("REINFORCEMENT", "response", "negation")],
        )

    def test_novel_577_reporting_manner_stays_outside_the_elliptical_answer(self):
        self.assert_family(
            plans.REPORT_COPULAR_ELLIPSIS,
            "Elizabeth replied very concisely that she was.",
            "Clara answered very calmly that he was.",
            "Clara answered very calmly that he were.",
            [("AGENT", "event", "subject"), ("MANNER", "event", "manner"),
             ("DEGREE", "manner", "degree"), ("REPORTED_CONTENT", "event", "content"),
             ("THEME", "content", "embedded_subject")],
        )

    def test_novel_578_maam_is_a_vocative_not_a_contraction_of_be(self):
        self.assert_family(
            plans.AFFIRMATIVE_TOTALITY,
            "“Yes, ma'am, all.”",
            '“Yes, sir, all.”',
            '“Yes, sir, all agreed.”',
            [("VOCATIVE", "answer", "addressee"), ("ANSWER_VALUE", "answer", "totality")],
        )

    def test_novel_579_not_stands_for_negative_content_not_manner(self):
        self.assert_family(
            plans.NEGATIVE_PROPOSITIONAL_REPLY,
            '“No, I believe not.”',
            '“No, we think not.”',
            '“No, we walk not.”',
            [("EXPERIENCER", "belief", "thinker"), ("CONTENT_PROFORM", "belief", "negative_proform"),
             ("QUALIFICATION", "answer", "belief")],
        )

    def test_novel_501_reports_an_interjection_not_a_stranded_adverb(self):
        self.assert_family(
            plans.REPORTED_INTERJECTION,
            '"Alas!" said she.', '“Ah!” exclaimed he.', '“Quickly!” exclaimed he.',
            [("AGENT", "event", "speaker"), ("REPORTED_CONTENT", "event", "outcry")],
        )

    def test_novel_504_keeps_cause_on_the_passive_event(self):
        self.assert_family(
            plans.PHONATION_PASSIVE_CAUSE,
            "Her voice was suffocated with sobs.", "Her voice was choked with emotion.",
            "Her voice was choked with a scarf.",
            [("THEME", "event", "voice"), ("AUXILIARY", "event", "auxiliary"),
             ("CAUSE", "event", "cause"), ("POSSESSOR", "voice", "possessor")],
        )

    def test_novel_505_response_and_scoped_copular_negation(self):
        self.assert_family(
            plans.NEGATED_GRADED_RESPONSE,
            "No; I am not so selfish.", "No; we were not so careless.", "No; we was not so careless.",
            [("RESPONSE_ELABORATION", "response", "event"), ("THEME", "event", "subject"),
             ("ATTRIBUTE", "event", "attribute"), ("NEGATION", "event", "negation"),
             ("DEGREE", "attribute", "degree")],
        )
