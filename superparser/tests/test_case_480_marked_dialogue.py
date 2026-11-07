"""Pinned case 480: split reported dialogue and two independently located dialectal verbs.

Strict grammar must not relabel plural subjects or singular verbs to force
agreement.  Marked dialogue is an opt-in, fully parsed alternative with overt
provenance.  The final coordinated list is a contextual nominal continuation,
not a fabricated independent finite clause.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources

DATA = Path(__file__).resolve().parents[1] / "data"
MARKED_INVERTED = "dialogue_speech_tag_inverted_marked_plural_subject_singular_verb"
MARKED_POST = "dialogue_speech_tag_post_marked_plural_subject_singular_verb"


def walk(root):
    yield root
    for child in root.children:
        yield from walk(child)


def only(root, rule_id):
    matching = [node for node in walk(root) if node.rule_id == rule_id]
    assert len(matching) == 1, (rule_id, len(matching))
    return matching[0]


class Case480MarkedDialogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser(ParserResources.from_dir(DATA), cache_size=0)

    def test_480_exact_attachments_and_two_attested_agreement_conflicts(self):
        case = select_cases(500)[0][480]
        prepared, original_lattice, strict = parse_corpus_case(self.parser, case)
        self.assertFalse(strict.completed, strict.stats)
        self.assertEqual(strict.usage_deviations(), ())

        prepared, lattice, marked = parse_corpus_case(
            self.parser, case, allow_marked_deviations=True,
        )
        self.assertTrue(marked.completed, marked.stats)
        self.assertEqual(marked.text, prepared.analysis_text)
        self.assertEqual(prepared.source_text, case["source_text"])
        self.assertEqual(marked.as_dict()["grammatical_status"], "nonstandard_attested")
        self.assertEqual(marked.stats["marked_mode"], True)
        def lexical_signature(candidate):
            return (candidate.span_start, candidate.span_end, candidate.surface,
                    candidate.category, candidate.features.as_dict(),
                    candidate.sense_ids, candidate.score)

        self.assertEqual([lexical_signature(c) for c in lattice.candidates],
                         [lexical_signature(c) for c in original_lattice.candidates],
                         "Marked mode must not replace original lexical hypotheses")

        root = marked.best()
        self.assertEqual(root.rule_id, "dialogue_unattributed")
        wrapper = only(root, "dialogue_quote_clause")
        self.assertEqual([child.category for child in wrapper.children],
                         ["OPEN-QUOTE", "CLAUSE", "CLOSE-QUOTE"])
        self.assertIsNone(prepared.reference_span(0, 1),
                          "Transferred opening double quote is not source text")
        self.assertIsNone(prepared.reference_span(99, 100),
                          "Transferred closing double quote is not source text")

        two_tags = only(root, "dialogue_append_reporting_tag_and_nominal_continuation")
        self.assertEqual([child.category for child in two_tags.children],
                         ["QUOTED-TOPIC-REPORT", "SPEECH-TAG", "COMMA", "QUOTED-NOMINAL-CONTINUATION"])
        first_tag = only(root, "dialogue_topic_vocative_interrupted_by_reporting_tag")
        self.assertIs(two_tags.children[0], first_tag)
        self.assertEqual([child.category for child in first_tag.children],
                         ["QUOTED-TOPIC-VOCATIVE", "SPEECH-TAG", "COMMA", "DIRECT-SPEECH"])
        topic_vocative = only(root, "dialogue_quote_topic_vocative_comma")
        self.assertIs(first_tag.children[0], topic_vocative)
        self.assertEqual([child.category for child in topic_vocative.children],
                         ["OPEN-QUOTE-DISCOURSE-TOPIC", "DISCOURSE-TOPIC", "COMMA", "NP", "COMMA", "CLOSE-QUOTE"])
        topic = only(root, "dialogue_topic_as_for_np")
        self.assertEqual(marked.text[topic.start:topic.end], "As for you")
        self.assertEqual(marked.text[topic_vocative.children[3].start:
                                     topic_vocative.children[3].end], "Benjamin Gunn")

        presentation = only(root, "dialogue_presentative_here_copular_np")
        self.assertEqual([child.category for child in presentation.children],
                         ["PRESENTATIVE", "COPULA", "NP"])
        self.assertEqual(marked.text[presentation.children[0].start:
                                     presentation.children[0].end], "here")
        self.assertEqual(marked.text[presentation.children[2].start:
                                     presentation.children[2].end], "a musket")
        continuation = only(root, "dialogue_quote_coordinated_nominal_continuation_stop")
        self.assertIs(two_tags.children[3], continuation)
        self.assertEqual([child.category for child in continuation.children],
                         ["OPEN-QUOTE-NOMINAL-CONTINUATION", "COORD", "NP", "SPEECH-STOP", "CLOSE-QUOTE"])
        items = continuation.children[2]
        self.assertEqual(items.rule_id, "np_list_last")
        self.assertEqual([child.category for child in items.children],
                         ["NP", "COMMA", "COORD", "NP"])
        self.assertEqual(marked.text[items.start:items.end], "a spade, and pick-axe")
        self.assertEqual(marked.text[items.children[3].start:items.children[3].end],
                         "pick-axe")

        deviations = marked.usage_deviations()
        self.assertEqual(len(deviations), 2)
        self.assertEqual([d.rule_id for d in deviations], [MARKED_INVERTED, MARKED_POST])
        for deviation, subject_span, predicate_span, source_subject, source_verb in (
            (deviations[0], (35, 39), (30, 34), (34, 38), (29, 33)),
            (deviations[1], (60, 64), (65, 69), (59, 63), (64, 68)),
        ):
            with self.subTest(rule=deviation.rule_id):
                self.assertEqual(deviation.kind, "subject_verb_number_agreement")
                self.assertEqual(deviation.relation, "speaker_to_reporting_verb")
                self.assertEqual(deviation.subject_surface, "they")
                self.assertEqual(deviation.predicate_surface, "says")
                self.assertEqual(deviation.subject_span, subject_span)
                self.assertEqual(deviation.predicate_span, predicate_span)
                self.assertEqual(prepared.reference_span(*subject_span), source_subject)
                self.assertEqual(prepared.reference_span(*predicate_span), source_verb)
                self.assertEqual(deviation.subject_features["number"], "plural")
                self.assertEqual(deviation.predicate_features["number"], "singular")
                self.assertEqual(deviation.expected, "plural")
                self.assertEqual(deviation.observed, "singular")
                self.assertEqual(deviation.intent, "unknown")

        self.assertTrue(any(candidate.surface == "As for" and
                            candidate.category == "TOPIC-MARKER" for candidate in lattice.candidates))
        self.assertTrue(any(candidate.surface == "As" and
                            candidate.category == "PREP" for candidate in lattice.candidates))
        self.assertTrue(any(candidate.surface == "for" and
                            candidate.category == "PREP" for candidate in lattice.candidates))
        self.assertTrue(any(candidate.surface == "here" and
                            candidate.category == "ADV" for candidate in lattice.candidates))
        self.assertTrue(any(candidate.surface == "here" and
                            candidate.category == "PRESENTATIVE" for candidate in lattice.candidates))

    def test_independent_dialogue_positive_and_missing_structure_negatives(self):
        independent = (
            '"\'As for you, Captain Flint,\' he said, \'here is a lantern,\' '
            'he added, \'and a rope, and a compass.\'"'
        )
        result = self.parser.parse(independent).result
        self.assertTrue(result.completed, result.stats)
        self.assertEqual(result.usage_deviations(), ())
        for rule in (
            "dialogue_topic_vocative_interrupted_by_reporting_tag",
            "dialogue_presentative_here_copular_np",
            "dialogue_append_reporting_tag_and_nominal_continuation",
            "dialogue_quote_coordinated_nominal_continuation_stop",
        ):
            only(result.best(), rule)

        for text in (
            '"\'As for you Captain Flint,\' he said, \'here is a lantern,\' '
            'he added, \'and a rope, and a compass.\'"',
            '"\'As for you, Captain Flint,\' he said, \'here is a lantern,\' '
            'he added, \'a rope, and a compass.\'"',
            '"\'As for you, Captain Flint,\' he said, \'here is a lantern,\' '
            'he added, \'and a rope, and a compass\'"',
        ):
            with self.subTest(text=text):
                parsed = self.parser.parse(text).result
                if parsed.best() is not None:
                    self.assertNotIn(
                        "dialogue_append_reporting_tag_and_nominal_continuation",
                        {node.rule_id for node in walk(parsed.best())},
                    )

        wrong_presentative = self.parser.parse('"Here are a lantern."').result
        if wrong_presentative.best() is not None:
            self.assertNotIn("dialogue_presentative_here_copular_np",
                             {node.rule_id for node in walk(wrong_presentative.best())})

    def test_standard_and_marked_reporting_tags_are_distinct(self):
        normal = (
            ('"I am here," he says.', "dialogue_speech_tag_post"),
            ('"I am here," says he.', "dialogue_speech_tag_inverted"),
            ('"I am here," they say.', "dialogue_speech_tag_post"),
            ('"I am here," they said.', "dialogue_speech_tag_post"),
        )
        for text, speech_tag in normal:
            with self.subTest(text=text):
                result = self.parser.parse(text).result
                self.assertTrue(result.completed, result.stats)
                only(result.best(), speech_tag)
                self.assertEqual(result.usage_deviations(), ())

        for text, marked_tag in (
            ('"I am here," says they.', MARKED_INVERTED),
            ('"I am here," they says.', MARKED_POST),
        ):
            with self.subTest(text=text):
                strict = self.parser.parse(text).result
                self.assertEqual(strict.usage_deviations(), ())
                if strict.best() is not None:
                    self.assertNotIn(marked_tag,
                                     {node.rule_id for node in walk(strict.best())})
                marked = self.parser.parse(text, allow_marked_deviations=True).result
                self.assertTrue(marked.completed, marked.stats)
                only(marked.best(), marked_tag)
                self.assertEqual(len(marked.usage_deviations()), 1)

        for text in ('They says.', '"They said."', '"They say."'):
            with self.subTest(text=text):
                marked = self.parser.parse(text, allow_marked_deviations=True).result
                self.assertEqual(marked.usage_deviations(), ())


if __name__ == "__main__":
    unittest.main()
