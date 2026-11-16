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

    def assert_family(self, rule, attested, positive, negative, links):
        for source, shared in ((attested, True), (positive, True), (negative, False)):
            with self.subTest(source=source):
                cases, _ = extract(PROBE, source, length_min=1, length_max=120)
                if not shared and len(cases) != 1:
                    continue
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

