"""Selected source trees, lexical contrasts and semantic edges for Novel-600."""
import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import ParseReport, Parser
from seman_parser import scoped_novel_ladder as plans
from seman_parser import scoped_ladder_review as review

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
                ("POLITENESS", "evaluation", "courtesy"),
                ("AGENT", "courtesy", "addressee"),
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
                ("ASPECT", "action", "aspect"),
                ("CIRCUMSTANCE", "action", "circumstance"),
                ("AGENT", "report", "speaker"),
                ("SUPPLEMENT", "report", "gesture"),
                ("REPORTED_CONTENT", "report", "content"),
                ("APPARENT_PURPOSE", "gesture", "apparent_purpose"),
            ],
            attested_spans=[
                ('aspect', 20, 24, 'have'),
                ('circumstance', 31, 44, 'in my fatuity'),
                ('speaker', 52, 65, 'Mr. Wickfield'),
            ],
        )

    def test_factive_gesture_retains_both_circumstance_attachments(self):
        trailing = (
            "‘I don’t know all I have done, in my fatuity,’ said Mr. Wickfield, "
            "putting out his hands, as if to deprecate my condemnation."
        )
        fronted = (
            "“In my confusion, I don’t remember all I have said,” said Mrs. Brown, "
            "holding out her arms, as if to prevent my departure."
        )

        def read(source):
            case, = extract(PROBE, source, length_min=1, length_max=120)[0]
            _, lattice, result = parse_corpus_case(
                self.parser, case, diagnostic_k=64,
                max_items=50_000, kbest_work_limit=500_000,
            )
            self.assertEqual(result.best().rule_id, plans.FACTIVE_GESTURE)
            return result, ParseReport(result, self.parser._quoted_sentence_resources, lattice)

        def has_scope(package, link_source):
            return any(
                e["relation"] == "CIRCUMSTANCE" and e["source"] == package["handles"][link_source]
                and e["target"] == package["handles"]["circumstance"]
                for e in package["graph"]["relations"]
            )

        result, report = read(trailing)
        best = report.best_semantic_graph()
        self.assertTrue(has_scope(best, "action"))
        self.assertFalse(has_scope(best, "content"))
        self.assertTrue(any(
            has_scope(report.interpret(candidate).as_dict(), "content")
            for candidate in result.alternatives(limit=16)
        ))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))

        _, report = read(fronted)
        best = report.best_semantic_graph()
        self.assertTrue(has_scope(best, "content"))
        self.assertFalse(has_scope(best, "action"))

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
                ("ASPECT", "received", "auxiliary"),
                ("EXPERIENCER", "resent", "subject"),
                ("THEME", "received", "offense"),
                ("INTERLOCUTOR", "rebuke", "interlocutor"),
                ("CAUSE", "rebuke", "reason"),
                ("AGENT", "reason", "interlocutor"),
            ],
            attested_spans=[("subject", 0, 12, "Miss Bingley"), ("auxiliary", 46, 49, "had")],
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

    # Selected-tree review for the frozen additive cohort.
    def test_novel_547_embedded_feeling_comparison(self):
        self.assert_family(
            review.EMBEDDED_FEELING_COMPARISON,
            "You may imagine how I felt when I heard this abominable old rogue addressing another in the very same words of flattery as he had used to myself.",
            "You can imagine how she felt when she saw the familiar old sailor greeting him in the very same terms of affection as he had used to her.",
            "You can imagine how she felt when she saw the familiar old sailor greeted him in the very same terms of affection as he had used to her.",
            [
                ("CONTENT", "imagine", "feeling"),
                ("TIME", "feeling", "hearing"),
                ("THEME", "hearing", "perceived"),
                ("AGENT", "addressing", "perceived"),
                ("MANNER", "addressing", "wording"),
                ("COMPARISON", "words", "prior_use"),
                ("ASPECT", "prior_use", "word_aspect"),
            ],
            attested_spans=[
                ("perceived", 60, 65, "rogue"),
                ("wording", 85, 144, "in the very same words of flattery as he had used to myself"),
                ("word_aspect", 126, 129, "had"),
            ],
        )

    def test_novel_575_causative_evidential_purpose(self):
        self.assert_family(
            review.CAUSATIVE_EVIDENTIAL_PURPOSE,
            "The red fox made him say all this, I knew, to exhibit him to me in the light he had indicated on the night when he poisoned my rest.",
            "The old nurse made her read all that, I suspected, to present her to us in the manner she had described on the evening when she calmed her friend.",
            "The old nurse made her to read all that, I suspected, to present her to us in the manner she had described on the evening when she calmed her friend.",
            [
                ("CAUSER", "causation", "causer"),
                ("CAUSEE", "causation", "causee"),
                ("AGENT", "saying", "causee"),
                ("EPISTEMIC_STANCE", "causation", "knowing"),
                ("PURPOSE", "causation", "exhibition"),
                ("AGENT", "exhibition", "causer"),
                ("RELATIVE", "night", "night_action"),
                ("TIME", "indication", "night"),
                ("THEME", "indication", "light"),
                ("ASPECT", "indication", "indicated_aspect"),
            ],
            attested_spans=[
                ("causer", 8, 11, "fox"),
                ("knowing", 37, 41, "knew"),
                ("exhibition", 46, 53, "exhibit"),
                ("night", 101, 106, "night"),
            ],
        )

    def test_novel_592_passive_knowledge_exception(self):
        self.assert_family(
            review.PASSIVE_KNOWLEDGE_EXCEPTION,
            "Of his former way of life nothing had been known in Hertfordshire but what he told himself.",
            "Of her early career nothing had been recorded in London except what she said herself.",
            "Of her early career nothing had been recorded in London except what she said himself.",
            [
                ("THEME", "knowledge", "nothing"),
                ("ASPECT", "knowledge", "perfect"),
                ("PASSIVE", "knowledge", "passive"),
                ("DOMAIN", "knowledge", "domain"),
                ("LOCATION", "knowledge", "place"),
                ("EXCEPTION", "knowledge", "what"),
                ("CONTENT", "telling", "what"),
                ("EMPHASIS", "teller", "self"),
            ],
            attested_spans=[
                ("domain", 0, 25, "Of his former way of life"),
                ("passive", 38, 42, "been"),
                ("place", 52, 65, "Hertfordshire"),
                ("self", 83, 90, "himself"),
            ],
        )

    def test_passive_knowledge_exception_preserves_reflexive_recipient_alternative(self):
        source = "Of his former way of life nothing had been known in Hertfordshire but what he told himself."
        case, = extract(PROBE, source, length_min=1, length_max=120)[0]
        _, lattice, result = parse_corpus_case(
            self.parser, case, diagnostic_k=64, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(result.best().rule_id, review.PASSIVE_KNOWLEDGE_EXCEPTION)
        report = ParseReport(result, self.parser._quoted_sentence_resources, lattice)

        def self_roles(package):
            target = package["handles"]["self"]
            return {e["relation"] for e in package["graph"]["relations"] if e["target"] == target}

        self.assertEqual(self_roles(report.best_semantic_graph()), {"EMPHASIS"})
        self.assertTrue(any(
            "RECIPIENT" in self_roles(report.interpret(candidate).as_dict())
            for candidate in result.alternatives(limit=16)
        ))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))

    def test_novel_596_split_reported_pleasure(self):
        self.assert_family(
            review.SPLIT_REPORTED_PLEASURE,
            "“In nursing your sister I am sure you have pleasure,” said Bingley; “and I hope it will be soon increased by seeing her quite well.”",
            "“In helping your brother I am certain you have satisfaction,” said Edward; “and I hope it will be gradually restored by finding him completely well.”",
            "“In helping your brother I am certain you have satisfaction,” said Edward; “and I hope it will be gradually restored by find him completely well.”",
            [
                ("CONTENT", "sure", "possession"),
                ("DOMAIN", "pleasure", "nursing"),
                ("AGENT", "nursing", "pleased"),
                ("AGENT", "report", "reporter"),
                ("REPORTED_CONTENT", "report", "being_sure"),
                ("REPORTED_CONTENT", "report", "hoping"),
                ("CONTENT", "hoping", "increase"),
                ("MODALITY", "increase", "modal"),
                ("PASSIVE", "increase", "passive"),
                ("MEANS", "increase", "seeing"),
                ("DEPICTIVE", "seeing", "well"),
                ("THEME", "well", "patient"),
                ("COREFERENCE", "it", "pleasure"),
            ],
            attested_spans=[
                ("nursing", 4, 11, "nursing"),
                ("reporter", 59, 66, "Bingley"),
                ("hoping", 75, 79, "hope"),
                ("well", 126, 130, "well"),
            ],
        )

    def test_review_510_ridden_means(self):
        self.assert_family(
            review.RIDDEN_MEANS,
            "I performed the first part of my journey on horseback.",
            "We covered the first stage of our trip on horseback.",
            "We pushed on toward the pass.",
            [
                ("AGENT", "performance", "subject"),
                ("THEME", "performance", "object"),
                ("MANNER", "performance", "manner"),
            ],
            attested_spans=[
                ("manner", 41, 53, "on horseback"),
                ("mount", 44, 53, "horseback"),
            ],
        )

    def test_review_514_timed_decision(self):
        self.assert_family(
            review.TIMED_DECISION,
            "We accordingly determined to commence our journey towards the north at the expiration of another month.",
            "They therefore decided to begin their voyage at dawn.",
            "They therefore decided to began their voyage at dawn.",
            [
                ("COMPLEMENT", "decision", "action"),
                ("AGENT", "action", "subject"),
                ("TIME", "action", "time"),
            ],
            attested_spans=[
                ("decision", 15, 25, "determined"),
                ("action", 29, 37, "commence"),
                ("time", 75, 85, "expiration"),
            ],
        )

    def test_review_517_shared_gaze(self):
        self.assert_family(
            review.SHARED_GAZE,
            "The being finished speaking and fixed his looks upon me in the expectation of a reply.",
            "She stopped talking and turned her eyes toward him in the hope of an answer.",
            "She stopped talking and turned her eyes toward him to answer.",
            [
                ("AGENT", "ended", "subject"),
                ("AGENT", "gaze", "subject"),
                ("AGENT", "speaking", "subject"),
                ("CIRCUMSTANCE", "gaze", "expectation"),
            ],
            attested_spans=[
                ("expectation", 63, 74, "expectation"),
                ("direction", 53, 55, "me"),
            ],
        )

    def test_review_518_alarm_inversion(self):
        self.assert_family(
            review.ALARM_INVERSION,
            "My haggard and wild appearance awoke intense alarm, but I answered no question, scarcely did I speak.",
            "Her pale and anxious expression aroused deep fear, but she answered no questions, hardly did she speak.",
            "Her pale and anxious expression aroused deep fear, but she answered no questions, hardly did she spoke.",
            [
                ("CAUSE", "caused", "stimulus"),
                ("THEME", "caused", "response"),
                ("THEME", "answered", "question"),
                ("AGENT", "spoke", "suppressed"),
            ],
            attested_spans=[
                ("stimulus", 20, 30, "appearance"),
                ("caused", 31, 36, "awoke"),
                ("response", 45, 50, "alarm"),
            ],
        )

    def test_review_519_timed_report(self):
        self.assert_family(
            review.TIMED_REPORT,
            "He then told me that he would commence his narrative the next day when I should be at leisure.",
            "She later told us that she would finish her work the following week when we would be free.",
            "She later told us that she would finished her work the following week when we would be free.",
            [
                ("RECIPIENT", "telling", "recipient"),
                ("CONTENT", "telling", "action"),
                ("TIME", "action", "day"),
                ("RELATIVE", "day", "availability"),
                ("TIME", "telling", "then"),
            ],
            attested_spans=[
                ("recipient", 13, 15, "me"),
                ("day", 62, 65, "day"),
                ("availability", 80, 82, "be"),
            ],
        )

    def test_review_521_topic_relative(self):
        self.assert_family(
            review.TOPIC_RELATIVE,
            "He talked of Geneva, which I should soon visit, of Elizabeth and Ernest; but these words only drew deep groans from me.",
            "She spoke of London, which she would soon see, of Alice and Charles; but these remarks only drew loud sighs from him.",
            "She spoke of London, which she would soon saw, of Alice and Charles; but these remarks only drew loud sighs from him.",
            [
                ("TOPIC", "talked", "place"),
                ("THEME", "visit", "place"),
                ("TOPIC", "talked", "name1"),
                ("TOPIC", "talked", "name2"),
                ("CONTRAST", "talked", "elicitation"),
                ("SOURCE", "elicitation", "source"),
            ],
            attested_spans=[
                ("place", 13, 19, "Geneva"),
                ("name1", 51, 60, "Elizabeth"),
                ("name2", 65, 71, "Ernest"),
            ],
        )

    def test_review_524_reaction_time(self):
        self.assert_family(
            review.REACTION_TIME,
            "I shuddered when I thought of the possible consequences of my consent, but I felt that there was some justice in his argument.",
            "She trembled when she thought about the likely effects of her choice, but she believed that there was some merit in his proposal.",
            "She trembled if she thought about the likely effects of her choice, but she believed that there was some merit in his proposal.",
            [
                ("TIME", "reaction", "trigger"),
                ("CONTENT", "felt", "content"),
                ("CONTRAST", "reaction", "felt"),
            ],
            attested_spans=[
                ("trigger", 19, 26, "thought"),
                ("reaction", 2, 11, "shuddered"),
                ("felt", 77, 81, "felt"),
            ],
        )

    def test_review_525_coordinated_sight(self):
        self.assert_family(
            review.COORDINATED_SIGHT,
            "The starry sky, the sea, and every sight afforded by these wonderful regions seem still to have the power of elevating his soul from earth.",
            "The quiet shore, the hills, and every view provided by these wooded valleys appear still to have the capacity of lifting their spirits from grief.",
            "The quiet shore, the hills, and every view provided by these wooded valleys appears still to have the capacity of lifting their spirits from grief.",
            [
                ("COMPLEMENT", "seem", "possession"),
                ("ASPECT", "possession", "still"),
                ("POSSESSOR", "possession", "sight"),
                ("CONJUNCT", "first", "sight"),
            ],
            attested_spans=[
                ("sight", 35, 40, "sight"),
                ("seem", 77, 81, "seem"),
                ("raising", 109, 118, "elevating"),
            ],
        )

    def test_review_528_nautical_call(self):
        self.assert_family(
            review.NAUTICAL_CALL,
            "\"Avast, there!\" cried Silver.",
            "“Avast, now!” shouted Jim.",
            "“Avast there!” shouted Jim.",
            [
                ("REPORTED_CONTENT", "report", "call"),
                ("ADJUNCT", "call", "particle"),
                ("AGENT", "report", "speaker"),
            ],
            attested_spans=[
                ("call", 1, 6, "Avast"),
                ("particle", 8, 13, "there"),
            ],
        )

    def test_review_529_certain_negation(self):
        self.assert_family(
            review.CERTAIN_NEGATION,
            "Certainly I did not know her way.",
            "Surely she did not read the letter.",
            "Surely she did not read from the letter.",
            [
                ("EPISTEMIC_STANCE", "event", "stance"),
                ("NEGATION", "event", "negation"),
                ("AUXILIARY", "event", "do"),
            ],
            attested_spans=[
                ("stance", 0, 9, "Certainly"),
                ("negation", 16, 19, "not"),
            ],
        )

    def test_review_531_reaction_degree(self):
        self.assert_family(
            review.REACTION_DEGREE,
            "At Silver's polite salute he somewhat flushed.",
            "At Anne's sharp question she slightly blushed.",
            "At Anne's sharp question she slightly blushes.",
            [
                ("TIME", "event", "trigger"),
                ("DEGREE", "event", "degree"),
                ("AGENT", "trigger", "owner"),
            ],
            attested_spans=[
                ("trigger", 19, 25, "salute"),
                ("degree", 29, 37, "somewhat"),
            ],
        )

    def test_review_532_stirred_attitude(self):
        self.assert_family(
            review.STIRRED_ATTITUDE,
            "But at my last words he perked up into a kind of startled slyness.",
            "But at his first remarks she perked up into a sort of nervous animation.",
            "But at his first remarks she perked into a sort of nervous animation.",
            [
                ("PARTICLE", "event", "particle"),
                ("RESULT", "event", "state"),
                ("CLASSIFICATION", "state", "kind"),
                ("TIME", "event", "trigger"),
            ],
            attested_spans=[
                ("kind", 41, 45, "kind"),
                ("state", 58, 65, "slyness"),
            ],
        )

    def test_review_533_excepted_sound(self):
        self.assert_family(
            review.EXCEPTED_SOUND,
            "There was not a soul stirring nor a sound beside the noises of the breeze.",
            "There was not a person moving nor a noise except the rustle of the leaves.",
            "There was not a person moving nor a noise near the rustle of the leaves.",
            [
                ("NEGATION", "exists", "negative"),
                ("THEME", "exists", "person"),
                ("THEME", "exists", "sound"),
                ("EXCEPTION", "sound", "exception"),
            ],
            attested_spans=[
                ("person", 16, 20, "soul"),
                ("sound", 36, 41, "sound"),
                ("exception", 53, 59, "noises"),
            ],
        )

    def test_review_535_comparative_extraposition(self):
        self.assert_family(
            review.COMPARATIVE_EXTRAPOSITION,
            "It was as good as the play to see them.",
            "It was as pleasant as the concert to hear her.",
            "The concert was as pleasant as the play to hear her.",
            [
                ("COMPARISON", "attribute", "benchmark"),
                ("EXTRAPOSED_SUBJECT", "be", "action"),
                ("THEME", "action", "object"),
            ],
            attested_spans=[
                ("benchmark", 22, 26, "play"),
                ("action", 30, 33, "see"),
                ("object", 34, 38, "them"),
            ],
        )

    def test_review_536_oath_report(self):
        self.assert_family(
            review.OATH_REPORT,
            "\"Then here goes!\" said Morgan with an oath.",
            "“Well here goes!” cried Susan with a curse.",
            "“Well here goes with a curse!” cried Susan.",
            [
                ("REPORTED_CONTENT", "report", "goes"),
                ("MANNER", "report", "oath"),
                ("AGENT", "report", "speaker"),
            ],
            attested_spans=[
                ("goes", 11, 15, "goes"),
                ("oath", 38, 42, "oath"),
                ("speaker", 23, 29, "Morgan"),
            ],
        )

    def test_review_537_focused_cleft(self):
        self.assert_family(
            review.FOCUSED_CLEFT,
            "And it was not only we of the cabin party who perceived the danger.",
            "And it was not only they of the village council who noticed the damage.",
            "And it was not only they of the village council whom noticed the damage.",
            [
                ("FOCUS", "be", "focus"),
                ("AGENT", "event", "focus"),
                ("THEME", "event", "object"),
                ("NEGATION", "only", "negative"),
            ],
            attested_spans=[
                ("focus", 20, 22, "we"),
                ("negative", 11, 14, "not"),
                ("group", 36, 41, "party"),
                ("event", 46, 55, "perceived"),
            ],
        )

    def test_review_538_two_minor_acts(self):
        self.assert_family(
            review.TWO_MINOR_ACTS,
            "\"To be sure, boy; quite right,\" said he.",
            "“To be sure, sir; entirely correct,” replied Nora.",
            "“To be sure, sir, entirely correct,” replied Nora.",
            [
                ("REPORTED_CONTENT", "report", "assurance"),
                ("REPORTED_CONTENT", "report", "evaluation"),
                ("VOCATIVE", "assurance", "address"),
                ("DEGREE", "evaluation", "degree"),
            ],
            attested_spans=[
                ("address", 13, 16, "boy"),
                ("evaluation", 24, 29, "right"),
            ],
        )

    def test_review_539_event_relative(self):
        self.assert_family(
            review.EVENT_RELATIVE,
            "But as things fell out, my poor father died quite suddenly that evening, which put all other matters on one side.",
            "But as events turned out, my old friend collapsed quite suddenly that morning, which put all other work on one side.",
            "But as events turned out, my old friend collapsed quite suddenly that morning, who put all other work on one side.",
            [
                ("TIME", "event", "time"),
                ("CAUSE", "put", "event"),
                ("RESULT", "put", "side"),
                ("RELATIVE", "event", "put"),
            ],
            attested_spans=[
                ("event", 39, 43, "died"),
                ("time", 64, 71, "evening"),
                ("side", 108, 112, "side"),
            ],
        )

    def test_review_540_quoted_condition_then_action(self):
        self.assert_family(
            review.QUOTED_CONDITION_THEN_ACTION,
            "\"Now, then, if Jim is agreeable, we'll open the packet\"; and he laid it before him on the table.",
            "\"Now, then, if Alice is willing, we'll read the letter\"; and she placed it before me on the desk.",
            "\"Now, then, if Alice is willing, we'll read the letter; and she placed it before me on the desk.\"",
            [
                ("CONDITION", "open", "condition"),
                ("NARRATIVE_FOLLOWS", "open", "laid"),
                ("THEME", "laid", "theme"),
                ("RESULT_LOCATION", "laid", "surface"),
                ("ORIENTATION", "laid", "anchor"),
            ],
            attested_spans=[
                ("will", 35, 38, "'ll"),
                ("condition", 19, 21, "is"),
                ("laid", 64, 68, "laid"),
                ("surface", 90, 95, "table"),
            ],
        )

    def test_review_542_reported_coordinate_negation(self):
        self.assert_family(
            review.REPORTED_COORDINATE_NEGATION,
            "\"I'm not strong enough, and I don't like the job; and there he lies, for me,\" said I.",
            "\"I'm not brave enough, and I don't want the money; and there she sits, for us,\" said Henry.",
            "\"I'm not brave enough, and I don't want the money; and there she sit, for us,\" said Henry.",
            [
                ("NEGATION", "be", "not1"),
                ("NEGATION", "attitude", "not2"),
                ("LOCATION", "state3", "there"),
                ("CIRCUMSTANCE", "state3", "object3"),
                ("REPORTED_CONTENT", "report", "be"),
            ],
            attested_spans=[
                ("be", 2, 4, "'m"),
                ("not2", 32, 35, "n't"),
                ("there", 54, 59, "there"),
                ("state3", 63, 67, "lies"),
            ],
        )

    def test_review_544_triple_passive(self):
        self.assert_family(
            review.TRIPLE_PASSIVE,
            "The sign was newly painted; the windows had neat red curtains; the floor was cleanly sanded.",
            "The door was freshly varnished; the halls had bright blue rugs; the desk was carefully polished.",
            "The doors was freshly varnished; the halls had bright blue rugs; the desk was carefully polished.",
            [
                ("THEME", "first", "first_theme"),
                ("MANNER", "first", "first_manner"),
                ("THEME", "third", "third_theme"),
                ("MANNER", "third", "third_manner"),
                ("THEME", "middle", "held"),
            ],
            attested_spans=[
                ("first", 19, 26, "painted"),
                ("third", 85, 91, "sanded"),
                ("held", 53, 61, "curtains"),
            ],
        )

    def test_review_545_shared_start_control(self):
        self.assert_family(
            review.SHARED_START_CONTROL,
            "Instantly I began to extricate myself and crawl back again, with what speed and silence I could manage, to the more open portion of the wood.",
            "Immediately she started to free herself and creep back again, with what care and caution she could muster, toward the more sheltered part of the garden.",
            "Immediately she started to free himself and creep back again, with what care and caution she could muster, toward the more sheltered part of the garden.",
            [
                ("COMPLEMENT", "start", "first"),
                ("COMPLEMENT", "start", "second"),
                ("AGENT", "second", "actor"),
                ("MANNER", "second", "manner"),
                ("DIRECTION", "second", "part"),
            ],
            attested_spans=[
                ("actor", 10, 11, "I"),
                ("second", 42, 47, "crawl"),
                ("manner", 60, 102, "with what speed and silence I could manage"),
            ],
        )

    def test_review_546_existential_and_remainder(self):
        self.assert_family(
            review.EXISTENTIAL_AND_REMAINDER,
            "But there were all our stores at the bottom, and to make things worse, only two guns out of five remained in a state for service.",
            "But there were all their supplies at the entrance, and to make matters worse, only three tools out of six remained in a condition for use.",
            "But there were all their supplies at the entrance, and to make matters worse, only three tool out of six remained in a condition for use.",
            [
                ("THEME", "exist", "pivot"),
                ("DISCOURSE", "remain", "make"),
                ("FOCUS", "only", "count"),
                ("PARTITIVE_TOTAL", "count", "total"),
                ("ATTRIBUTE", "remain", "state"),
            ],
            attested_spans=[
                ("count", 76, 79, "two"),
                ("total", 92, 96, "five"),
                ("state", 111, 116, "state"),
            ],
        )

    def test_review_549_concessive_negative_observation(self):
        self.assert_family(
            review.CONCESSIVE_NEGATIVE_OBSERVATION,
            "They had never so much as looked at their fallen comrade, though he was not dead, and I could see him trying to crawl away.",
            "We had never so much as glanced towards our wounded companion, although she was not unconscious, and I could see her attempting to walk away.",
            "We had never so much as glanced towards our wounded companion, although she was not unconscious, and I could see her attempting to walked away.",
            [
                ("ASPECT", "looked", "had"),
                ("NEGATION", "looked", "never"),
                ("EMPHASIS", "looked", "minimum"),
                ("CONCESSION", "looked", "was"),
                ("COMPLEMENT", "see", "trying"),
                ("AGENT", "crawl", "object"),
            ],
            attested_spans=[
                ("minimum", 15, 25, "so much as"),
                ("trying", 102, 108, "trying"),
                ("crawl", 112, 117, "crawl"),
            ],
        )

    def test_review_550_reaction_result(self):
        self.assert_family(
            review.REACTION_RESULT,
            "I was so much startled that I struggled to withdraw, but the blind man pulled me close up to him with a single action of his arm.",
            "She was so much alarmed that she tried to escape, but the tall woman dragged her close up to her with a sudden movement of her arm.",
            "She was so much alarmed that she tried to escaped, but the tall woman dragged her close up to her with a sudden movement of her arm.",
            [
                ("PASSIVE", "startled", "was"),
                ("RESULT", "startled", "struggled"),
                ("AGENT", "withdraw", "actor"),
                ("RESULT_LOCATION", "pulled", "proximity"),
                ("MANNER", "pulled", "action"),
            ],
            attested_spans=[
                ("proximity", 81, 96, "close up to him"),
                ("withdraw", 43, 51, "withdraw"),
                ("body", 125, 128, "arm"),
            ],
        )

    def test_review_554_reported_negative_vocative(self):
        self.assert_family(
            review.REPORTED_NEGATIVE_VOCATIVE,
            "‘No, father,’ Minnie interposed.",
            "“No, sir,” Alice interposed.",
            "“No, sir,” Alice interposed a hand.",
            [
                ("VOCATIVE", "no", "address"),
                ("AGENT", "report", "speaker"),
                ("REPORTED_CONTENT", "report", "no"),
            ],
            attested_spans=[
                ("speaker", 14, 20, "Minnie"),
                ("no", 1, 3, "No"),
                ("address", 5, 11, "father"),
            ],
        )

    def test_review_555_adjectival_echo(self):
        self.assert_family(
            review.ADJECTIVAL_ECHO,
            "‘Cross, my love?’",
            "“Angry, my friend?”",
            "“Cross, my love!”",
            [
                ("VOCATIVE", "predicate", "address"),
                ("QUESTION", "predicate", "predicate"),
            ],
            attested_spans=[
                ("predicate", 1, 6, "Cross"),
                ("address", 11, 15, "love"),
            ],
        )

    def test_review_556_named_court(self):
        self.assert_family(
            review.NAMED_COURT,
            "What was the Arches?",
            "What was the Consistory?",
            "What were the arches?",
            [
                ("THEME", "copula", "court"),
                ("QUESTION", "copula", "what"),
            ],
            attested_spans=[
                ("court", 13, 19, "Arches"),
            ],
        )

    def test_review_557_reported_sure(self):
        self.assert_family(
            review.REPORTED_SURE,
            "‘I am sure of it,’ said Agnes.",
            "“We are certain of that,” replied Clara.",
            "“We is certain of that,” replied Clara.",
            [
                ("COMPLEMENT", "attribute", "object"),
                ("EXPERIENCER", "attribute", "subject"),
                ("REPORTED_CONTENT", "report", "copula"),
            ],
            attested_spans=[
                ("attribute", 6, 10, "sure"),
                ("object", 14, 16, "it"),
            ],
        )

    def test_review_560_named_vocative(self):
        self.assert_family(
            review.NAMED_VOCATIVE,
            "‘He is a partaker of glory at present, Master Copperfield,’ said Uriah Heep.",
            "“She was a witness of history at first, Captain Wentworth,” said Clara Finch.",
            "“She was a witness of history at first, Captain Wentworth,” said the captain.",
            [
                ("AGENT", "report", "speaker"),
                ("VOCATIVE", "copula", "address"),
                ("ADDRESSEE", "report", "address"),
                ("TIME", "copula", "time"),
            ],
            attested_spans=[
                ("speaker", 65, 75, "Uriah Heep"),
                ("address", 39, 57, "Master Copperfield"),
                ("time", 27, 37, "at present"),
            ],
        )

    def test_review_561_belief_vocative(self):
        self.assert_family(
            review.BELIEF_VOCATIVE,
            "‘I believe you, my pet,’ replied Miss Mowcher.",
            "“We trust him, my friend,” said Doctor Smith.",
            "“We trust him and my friend,” said Doctor Smith.",
            [
                ("THEME", "belief", "object"),
                ("VOCATIVE", "belief", "address"),
                ("AGENT", "report", "speaker"),
                ("REPORTED_CONTENT", "report", "belief"),
            ],
            attested_spans=[
                ("belief", 3, 10, "believe"),
                ("object", 11, 14, "you"),
                ("speaker", 33, 45, "Miss Mowcher"),
            ],
        )

    def test_review_562_shared_contact(self):
        self.assert_family(
            review.SHARED_CONTACT,
            "Then she kissed me more and more, and clasped me round the neck.",
            "Then he hugged her more and more, and grasped her around the wrist.",
            "Then he hugged her more and more, and she grasped him around the wrist.",
            [
                ("AGENT", "first", "subject"),
                ("AGENT", "second", "subject"),
                ("DEGREE", "first", "degree"),
                ("BODY_SITE", "second", "site"),
            ],
            attested_spans=[
                ("first", 9, 15, "kissed"),
                ("second", 38, 45, "clasped"),
                ("site", 59, 63, "neck"),
            ],
        )

    def test_review_563_perception_and_reply(self):
        self.assert_family(
            review.PERCEPTION_AND_REPLY,
            "I thought him looking as villainous as ever, and I replied that I saw no change in him.",
            "She thought him looking as weary as ever, and she replied that she noticed no difference in him.",
            "She thought him look as weary as ever, and she replied that she noticed no difference in him.",
            [
                ("THEME", "looked", "object"),
                ("COMPARISON", "attribute", "ever"),
                ("COMPLEMENT", "thought", "looked"),
                ("CONTENT", "replied", "saw"),
                ("DOMAIN", "change", "affected"),
            ],
            attested_spans=[
                ("looked", 14, 21, "looking"),
                ("replied", 51, 58, "replied"),
                ("saw", 66, 69, "saw"),
            ],
        )

    def test_review_564_negated_misgiving(self):
        self.assert_family(
            review.NEGATED_MISGIVING,
            "I was troubled with no misgiving that it was young in me to respond to her emotions.",
            "She was troubled with no fear that it was unwise in her to reply to his objections.",
            "She was troubled with no fear that it was unwise in her to replied to his objections.",
            [
                ("QUANTIFIER", "misgiving", "no"),
                ("CONTENT", "misgiving", "be"),
                ("EXTRAPOSED_SUBJECT", "be", "action"),
                ("AGENT", "action", "judge"),
                ("TARGET", "action", "target"),
            ],
            attested_spans=[
                ("judge", 54, 56, "me"),
                ("action", 60, 67, "respond"),
                ("target", 75, 83, "emotions"),
            ],
        )

    def test_review_565_reported_nominal_series(self):
        self.assert_family(
            review.REPORTED_NOMINAL_SERIES,
            "I said he was my dearest friend, the protector of my boyhood, and the companion of my prime.",
            "She said he was his dearest friend, the guardian of his childhood, and the partner of his adulthood.",
            "She said they was her closest friend, the guardian of her childhood, and the partner of her adulthood.",
            [
                ("CONTENT", "said", "be"),
                ("THEME", "be", "person"),
                ("ATTRIBUTE", "be", "first"),
                ("ATTRIBUTE", "be", "role1"),
                ("ATTRIBUTE", "be", "role2"),
                ("TIME", "role2", "time2"),
            ],
            attested_spans=[
                ("role1", 37, 46, "protector"),
                ("role2", 70, 79, "companion"),
                ("time2", 86, 91, "prime"),
            ],
        )

    def test_review_567_scene_location(self):
        self.assert_family(
            review.SCENE_LOCATION,
            "It is a summer evening, down in a green hollow, at the corner of a wall.",
            "It was a winter morning, up in a lonely valley, at the edge of a forest.",
            "It was a winter morning, up in a lonely valley, and the edge of a forest.",
            [
                ("TIME", "scene", "time"),
                ("LOCATION", "scene", "place"),
                ("LOCATION", "scene", "spot"),
                ("LANDMARK", "spot", "landmark"),
            ],
            attested_spans=[
                ("time", 15, 22, "evening"),
                ("place", 40, 46, "hollow"),
                ("spot", 55, 61, "corner"),
                ("landmark", 67, 71, "wall"),
            ],
        )

    def test_review_568_existential_relative_focus(self):
        self.assert_family(
            review.EXISTENTIAL_RELATIVE_FOCUS,
            "There was no other question that I knew of in the world, and only Dora could give the answer to it.",
            "There was no other problem that she knew of in the town, and only Clara could find the solution to it.",
            "There was no other problem that she knew in the town, and only Clara could find the solution to it.",
            [
                ("RELATIVE", "thing", "knew"),
                ("CONTENT", "knew", "thing"),
                ("FOCUS", "only", "actor"),
                ("COMPLEMENT", "answer", "object"),
                ("THEME", "give", "answer"),
            ],
            attested_spans=[
                ("thing", 19, 27, "question"),
                ("actor", 66, 70, "Dora"),
                ("answer", 86, 92, "answer"),
            ],
        )

    def test_review_569_fronted_perception(self):
        self.assert_family(
            review.FRONTED_PERCEPTION,
            "The expression of her face, as they both looked towards me, I felt to be very touching.",
            "The sound of her voice, as they both turned towards us, I found to be rather familiar.",
            "The sound of her voice, as they both turned towards us, I found to been rather familiar.",
            [
                ("THEME", "felt", "focus"),
                ("THEME", "be", "focus"),
                ("TIME", "felt", "look"),
                ("AGENT", "look", "their"),
            ],
            attested_spans=[
                ("look", 41, 47, "looked"),
                ("felt", 62, 66, "felt"),
                ("focus", 4, 14, "expression"),
            ],
        )

    def test_review_581_ended_state(self):
        self.assert_family(
            review.ENDED_STATE,
            "It was over at last, however.",
            "The wait was finished at last, though.",
            "The wait was under the table, though.",
            [
                ("ATTRIBUTE", "event", "state"),
                ("TIME", "event", "time"),
                ("DISCOURSE", "event", "stance"),
            ],
            attested_spans=[
                ("state", 7, 11, "over"),
                ("time", 12, 19, "at last"),
            ],
        )

    def test_review_582_modal_restoration(self):
        self.assert_family(
            review.MODAL_RESTORATION,
            "“A little sea-bathing would set me up forever.”",
            "“Some fresh air could set her up for the day.”",
            "“Some fresh air could set up her room for the day.”",
            [
                ("MODALITY", "event", "modal"),
                ("PARTICLE", "event", "particle"),
                ("DURATION", "event", "duration"),
                ("THEME", "event", "affected"),
            ],
            attested_spans=[
                ("particle", 35, 37, "up"),
                ("duration", 38, 45, "forever"),
            ],
        )

    def test_review_584_conditional_hope(self):
        self.assert_family(
            review.CONDITIONAL_HOPE,
            "“If my children are silly, I must hope to be always sensible of it.”",
            "“If our friends are wrong, we should hope to be always aware of that.”",
            "“If our friends are wrong, we should hope to been always aware of that.”",
            [
                ("CONDITION", "hope", "be1"),
                ("COMPLEMENT", "hope", "be2"),
                ("THEME", "be2", "subject2"),
                ("COMPLEMENT", "attribute2", "object"),
                ("FREQUENCY", "be2", "frequency"),
            ],
            attested_spans=[
                ("hope", 34, 38, "hope"),
                ("attribute2", 52, 60, "sensible"),
                ("frequency", 45, 51, "always"),
            ],
        )

    def test_review_585_possibility_question(self):
        self.assert_family(
            review.POSSIBILITY_QUESTION,
            "“Can it be possible that he will marry her?”",
            "“Could it be likely that she would visit them?”",
            "“Could it be likely and she would visit them?”",
            [
                ("ATTRIBUTE", "copula", "possible"),
                ("MODALITY", "copula", "modal"),
                ("EXTRAPOSITION", "possible", "content"),
                ("QUESTION", "copula", "possible"),
            ],
            attested_spans=[
                ("possible", 11, 19, "possible"),
                ("content", 33, 38, "marry"),
            ],
        )

    def test_review_586_conditional_evaluation(self):
        self.assert_family(
            review.CONDITIONAL_EVALUATION,
            "“She is a great fool for going away, if she liked him.”",
            "“He is a real coward for turning away, if he trusted her.”",
            "“He is a real coward for turn away, if he trusted her.”",
            [
                ("AGENT", "action", "subject"),
                ("GROUND", "characterization", "action"),
                ("CONDITION", "be", "liked"),
                ("THEME", "liked", "object"),
            ],
            attested_spans=[
                ("action", 25, 30, "going"),
                ("away", 31, 35, "away"),
                ("liked", 44, 49, "liked"),
            ],
        )

    def test_review_587_inverted_effect(self):
        self.assert_family(
            review.INVERTED_EFFECT,
            "Widely different was the effect of a second perusal.",
            "Markedly different was the result of the trial.",
            "Markedly different were the result of the trial.",
            [
                ("PREDICATE", "effect", "predicate"),
                ("ATTRIBUTE", "event", "predicate"),
                ("THEME", "event", "effect"),
            ],
            attested_spans=[
                ("effect", 25, 31, "effect"),
                ("predicate", 7, 16, "different"),
            ],
        )

    def test_review_590_two_questions_passive(self):
        self.assert_family(
            review.TWO_QUESTIONS_PASSIVE,
            "“Then, who taught you? who attended to you? Without a governess, you must have been neglected.”",
            "“Well, who helped her? who listened to her? Without a tutor, she might have been forgotten.”",
            "“Well, who helped her? who listened to her? Without a tutor, she might had been forgotten.”",
            [
                ("AGENT", "taught", "who1"),
                ("AGENT", "attended", "who2"),
                ("MODALITY", "neglected", "must"),
                ("ASPECT", "neglected", "have"),
                ("PASSIVE", "neglected", "been"),
            ],
            attested_spans=[
                ("taught", 11, 17, "taught"),
                ("attended", 27, 35, "attended"),
                ("neglected", 84, 93, "neglected"),
            ],
        )

    def test_review_591_partitive_passage(self):
        self.assert_family(
            review.PARTITIVE_PASSAGE,
            "The park paling was still the boundary on one side, and she soon passed one of the gates into the ground.",
            "The garden wall was still the border on one side, and he quickly crossed one of the doors into the yard.",
            "The garden wall was still the border on one side, and he quickly crossed one of the door into the yard.",
            [
                ("THEME", "be", "fence"),
                ("ASPECT", "be", "still"),
                ("PARTITIVE", "one", "gates"),
                ("THEME", "passed", "one"),
                ("DIRECTION", "passed", "direction"),
            ],
            attested_spans=[
                ("gates", 83, 88, "gates"),
                ("direction", 98, 104, "ground"),
                ("one", 72, 75, "one"),
            ],
        )

    def test_review_593_resumed_exclamative(self):
        self.assert_family(
            review.RESUMED_EXCLAMATIVE,
            "The mischief of neglect and mistaken indulgence towards such a girl--oh! how acutely did she now feel it!",
            "The harm of silence and blind approval towards such a child—oh! how deeply did he now feel it!",
            "The harm of silence and blind approval towards such a child—oh! how deeply did he now feel it?",
            [
                ("DISLOCATED_TOPIC", "feel", "topic"),
                ("THEME", "feel", "it"),
                ("COREFERENCE", "it", "topic"),
                ("DEGREE", "feel", "degree"),
                ("TIME", "feel", "now"),
            ],
            attested_spans=[
                ("topic", 0, 67, "The mischief of neglect and mistaken indulgence towards such a girl"),
                ("it", 102, 104, "it"),
                ("now", 93, 96, "now"),
            ],
        )

    def test_review_594_reported_three_acts(self):
        self.assert_family(
            review.REPORTED_THREE_ACTS,
            "“This account then is what he has received from Mr. Darcy. I am satisfied. But what does he say of the living?”",
            "“This letter then is what she has received from Mr. Smith. I am convinced. But what did she say about the contract?”",
            "“This letter then is what she has receive from Mr. Smith. I am convinced. But what did she say about the contract?”",
            [
                ("THEME", "received", "what"),
                ("SOURCE", "received", "source"),
                ("ASPECT", "received", "has"),
                ("ATTRIBUTE", "am", "attribute"),
                ("TOPIC", "say", "topic"),
            ],
            attested_spans=[
                ("source", 48, 57, "Mr. Darcy"),
                ("topic", 103, 109, "living"),
                ("attribute", 64, 73, "satisfied"),
            ],
        )

if __name__ == "__main__":
    unittest.main()
