"""Source-grounded, negative and independent positive controls for Novel-700."""
from __future__ import annotations

import unittest
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts.novel_ladder import LADDER, load_pinned_fixture_sources, read_ladder
from seman_parser.engine import ParseReport, Parser, ParserResources

WORDNET = Path(__import__('os').environ.get('WORDNET_DICT', ''))
ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_BOOK = Book(999, 'Grammatical contrasts', 'Tests', 'syntax')
TARGETS = {
    603: ('structural_discourse_return_with_infinitive_topic',
          'And to revert to happier matters.', 'And to revert happier matters.',
          [('TOPIC','return','subject')]),
    615: ('structural_negated_modal_with_self_concessive_and_result',
          'She would not guide him on, unguarded and ardent as she then was, to his sorrow and lasting regret.',
          'She would not guide him on, unguarded and ardent as he then was, to his sorrow and lasting regret.',
          [('CONCESSION','lead','was'),('RESULT','lead','result1'),('NEGATION','lead','not')]),
    619: ('structural_temporal_as_with_locative_relative_and_coordination',
          'As dusk fell she found herself at the gate of the garden where Charles, Alice, and her brother waited.',
          'As dusk fell she found himself at the gate of the garden where Charles, Alice, and her brother waited.',
          [('TIME','found','approached'),('LOCATION','found','entry'),('RELATIVE','place','reposed'),
           ('COREFERENCE','myself','subject')]),
    623: ('structural_scalar_passive_but_that_self_engagement',
          'Yet, although sad, she is not so deeply occupied by her own grief but that she engages herself greatly in the affairs of others.',
          'Yet, although sad, she is not so deeply occupied by her own grief but that they engages herself greatly in the affairs of others.',
          [('SCALAR_EXCEPTION','occupied','interests'),('COREFERENCE','self','embedded'),
           ('CAUSE','occupied','misery')]),
    641: ('structural_periodic_perception_with_evidential_as_if',
          'Occasionally, by the rippling of the water, she seemed to stir a little, as if she was attempting to stand.',
          'Occasionally, by the rippling of the water, she seemed to stir a little, as if he was attempting to stand.',
          [('FREQUENCY','appeared','frequency'),('EVIDENCE','appeared','evidence'),
           ('COMPARISON','move','trying'),('COMPLEMENT','trying','rise')]),
    652: ('dialogue_structural_reported_minor_wh_reply',
          '“Who?” asked Clara.', '“Who!” asked Clara.',
          [('REPORTED_CONTENT','verb','what'),('AGENT','verb','name')]),
    654: ('structural_propositional_relative_resumption',
          'Which was clear enough.', 'Which were clear enough.',
          [('THEME','be','which'),('ATTRIBUTE','be','quality'),('DEGREE','quality','degree')]),
    665: ('structural_raising_curiosity_with_counterfactual_comparison',
          'She appeared interested concerning the garden, also, as if it was the first time she had visited it.',
          'She appeared interested concerning the garden, also, as if it was the first time he had visited it.',
          [('TOPIC','curious','object'),('RELATIVE','time','seen'),('COREFERENCE','backref','object')]),
    666: ('structural_semicolon_temporal_passive_coordination',
          'Silence fell over her face; and, for a time, all thoughts were wiped out of her memory.',
          'Silence fell over her face; and, for a time, all thoughts was wiped out of her memory.',
          [('CONJUNCT','comes','participle'),('PASSIVE','participle','be'),('TIME','participle','time')]),
    685: ('dialogue_structural_reported_copular_comment_with_companion',
          '“And that was often the case with her,” he said.',
          '“And that was often the case with her” he said.',
          [('COMPANION','way','person'),('REPORTED_CONTENT','report','be'),('AGENT','report','report_subject')]),
    700: ('structural_fronted_gerund_judgment_with_concessive_affect',
          'Of having another son engaged to Dr. Smith, he thought with similar confidence, and with great, though not comparable, delight.',
          'Of having another son engaged to Dr. Smith, he thinks with similar confidence, and with great, though not comparable, delight.',
          [('TOPIC','thought','having'),('AFFECT','thought','pleasure'),
           ('CONCESSIVE_DEGREE','pleasure','equal2'),('NEGATION','equal2','not')]),
}


class Novel700StructuralAttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORDNET.is_dir():
            raise RuntimeError('WORDNET_DICT must identify WordNet 3.0 dictionary')
        cls.parser = Parser(ParserResources.from_dir(ROOT/'data', wordnet_dict=WORDNET), cache_size=0)
        cls.parser.parse('John opened the box.')
        cohorts, _, _ = read_ladder(LADDER, load_pinned_fixture_sources())
        cls.cases = {c['ladder_index']: c for _, rows in cohorts for c in rows}

    def parse(self, case):
        prepared, lattice, result = parse_corpus_case(
            self.parser, case, max_items=50_000, kbest_work_limit=500_000,
        )
        self.assertEqual(prepared.analysis_text, case['source_text'])
        self.assertEqual(lattice.text, case['source_text'])
        return lattice, result

    def test_selected_source_and_independent_contrasts(self):
        for index, (rule, positive, negative, links) in TARGETS.items():
            with self.subTest(index=index):
                source = self.cases[index]
                self.assertFalse(source['synthetic_prefix'] or source['synthetic_suffix'])
                for text, must_match in ((source['source_text'], True), (positive, True), (negative, False)):
                    with self.subTest(index=index, text=text[:30]):
                        if text == source['source_text']:
                            case = source
                        else:
                            extracted, _ = extract(SYNTHETIC_BOOK, text, length_min=1, length_max=50)
                            self.assertEqual(len(extracted), 1)
                            case = extracted[0]
                        lattice, result = self.parse(case)
                        root = result.best()
                        if not must_match:
                            self.assertTrue(root is None or root.rule_id != rule)
                            continue
                        self.assertTrue(result.completed)
                        self.assertIsNotNone(root)
                        self.assertEqual(root.rule_id, rule)
                        self.assertEqual((root.start, root.end), (0, len(text)))
                        self.assertFalse(result.stats.get('budget_exceeded'))
                        self.assertFalse(result.stats.get('kbest_budget_exceeded'))
                        package = ParseReport(result, self.parser._quoted_sentence_resources, lattice).best_semantic_graph()
                        handles = package['handles']
                        edges = {(e['relation'], e['source'], e['target'])
                                 for e in package['graph']['relations']}
                        for relation, left, right in links:
                            self.assertIn((relation, handles[left], handles[right]), edges)
                        nodes = {n['id']: n for n in package['graph']['nodes']}
                        for n in nodes.values():
                            if n.get('span') is None:
                                continue
                            a,b = n['span']
                            self.assertEqual(n.get('surface'), text[a:b])


if __name__ == '__main__':
    unittest.main()
