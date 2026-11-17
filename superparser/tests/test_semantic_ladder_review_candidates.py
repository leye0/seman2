"""Source-grounded rank-one semantic checks for previously unreviewed cases.

Do NOT mark an individual verified solely because a test method passed:
the exact original source, an independent grammatical positive, an invalid
near-miss, a correct selected rule and overt semantic relations must all pass.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from scripts import novel_ladder as ladder
from seman_parser.engine import Parser, ParserResources, ParseReport

ROOT=Path(__file__).resolve().parents[1]
BOOK=Book(91991, "Semantic audit independent controls", "Audit", "syntax")

class SemanticReviewCandidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wordnet=Path(os.environ["WORDNET_DICT"])
        if not wordnet.is_dir():
            raise RuntimeError("WordNet 3.0 is required")
        cls.parser=Parser(ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet),
                          cache_size=0,max_items=50000)
        sources=ladder.load_sources()
        cohort=ladder.read_json(ladder.LADDER/"novel-700-cohort.json")
        cls.cases={r["ladder_index"]:r for r in ladder.resolve(cohort,601,sources)}
        candidate=ladder.read_json(ROOT/"research/novel_800_exploration/novel-800-candidate-cohort.json")
        cls.cases.update({r["ladder_index"]:r for r in ladder.resolve(candidate,701,sources)})
        cls.parser.parse("John opened the box.")

    def parse(self,source):
        if isinstance(source,int):
            case=self.cases[source]
        else:
            extracted,_=extract(BOOK,source,length_min=1,length_max=45)
            self.assertEqual(len(extracted),1,f"Unusable independent control: {source!r}")
            case=extracted[0]
        prepared,lattice,result=parse_corpus_case(self.parser,case,max_items=50000,kbest_work_limit=500000)
        self.assertEqual(prepared.analysis_text,case["source_text"])
        return prepared,lattice,result

    def check(self,index,positive,negative,links,expected_root,source_links=None):
        for source,is_positive in ((index,True),(positive,True),(negative,False)):
            with self.subTest(index=index,source=str(source)[:55]):
                prepared,lattice,result=self.parse(source)
                tree=result.best()
                if not is_positive:
                    self.assertFalse(tree and tree.rule_id==expected_root,
                                     "An unsuitable near-miss selected the allegedly verified source construction")
                    continue
                self.assertTrue(result.completed)
                self.assertIsNotNone(tree)
                self.assertEqual(tree.rule_id,expected_root)
                self.assertEqual(tree.start,0)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                resources=(self.parser._quoted_sentence_resources or self.parser.resources
                           if result.stats.get("structural_composition") else
                           self.parser._dialogue_resources or self.parser.resources
                           if result.stats.get("dialogue_scoped") else self.parser.resources)
                package=ParseReport(result,resources,lattice).best_semantic_graph()
                self.assertIsNotNone(package)
                n={node["id"]:node for node in package["graph"]["nodes"]}
                observed={(e["relation"],n[e["source"]].get("surface"),
                                     n[e["target"]].get("surface"))
                          for e in package["graph"]["relations"]}
                expected=source_links if isinstance(source,int) and source_links is not None else links
                for wanted in expected:
                    self.assertIn(wanted,observed)
                for node in n.values():
                    span=node.get("span")
                    if span is not None and node.get("surface") is not None:
                        a,b=span
                        self.assertEqual(node["surface"],prepared.analysis_text[a:b])
                self.assertTrue(any(node.get("surface") == word for node in n.values()
                                    for word in (links[0][1],links[0][2])))


    def selected(self, source):
        prepared, lattice, result = self.parse(source)
        tree = result.best()
        if not result.completed or tree is None:
            return prepared.analysis_text, None, {}, []
        self.assertFalse(result.stats.get("budget_exceeded"))
        self.assertFalse(result.stats.get("kbest_budget_exceeded"))
        resources = ((self.parser._quoted_sentence_resources or self.parser.resources)
                     if result.stats.get("structural_composition") else
                     (self.parser._dialogue_resources or self.parser.resources)
                     if result.stats.get("dialogue_scoped") else self.parser.resources)
        graph = ParseReport(result, resources, lattice).best_semantic_graph()["graph"]
        nodes = {n["id"]: n for n in graph["nodes"]}
        edges = [(e["relation"], nodes[e["source"]], nodes[e["target"]])
                 for e in graph["relations"]]
        for node in nodes.values():
            if node["span"] is not None and node["surface"] is not None:
                a, b = node["span"]
                self.assertEqual(prepared.analysis_text[a:b], node["surface"])
        return prepared.analysis_text, tree, nodes, edges

    def test_n601_modal_negation_binds_selected_predicate(self):
        for source, verb, modal, subject in (
            (601, "answer", "could", "I"), ("We could not stay.", "stay", "could", "We"),
        ):
            with self.subTest(source=source):
                text, tree, _, edges = self.selected(source)
                self.assertEqual(tree.rule_id, "clause_np_vp")
                vp = tree.children[1]
                self.assertEqual(vp.rule_id, "vp_modal_bare")
                negated = vp.children[1]
                self.assertEqual(negated.rule_id, "vp_neg_bare")
                neg, predicate = negated.children
                self.assertEqual((neg.category, text[neg.start:neg.end]), ("NEG", "not"))
                self.assertEqual(text[predicate.start:predicate.end], verb)
                roles = {(r, a["surface"], b["surface"]) for r, a, b in edges}
                self.assertEqual(roles, {("MODALITY", verb, modal), ("NEGATION", verb, "not"),
                                         ("AGENT", verb, subject)})
        _, tree, _, edges = self.selected("We could stay.")
        self.assertEqual(tree.rule_id, "clause_np_vp")
        self.assertFalse(any(r == "NEGATION" for r, _, _ in edges))

    def test_do_support_attaches_negation_to_its_own_predicate(self):
        for source, verb in ((692, "follow"), ("I did not answer.", "answer"),
                             ("Do not touch it.", "touch")):
            with self.subTest(source=source):
                _, tree, _, edges = self.selected(source)
                self.assertIsNotNone(tree)
                self.assertEqual([(a["surface"], b["surface"]) for r, a, b in edges
                                  if r == "NEGATION"], [(verb, "not")])
        _, tree, _, edges = self.selected("I did answer.")
        self.assertIsNotNone(tree)
        self.assertFalse(any(r == "NEGATION" for r, _, _ in edges))

    def test_n660_reprise_and_vocative_scope(self):
        from seman_parser.scoped_novel_700 import N660_GERUND_QUESTION
        for source, focus, name in (
            (660, "I", "Daisy"),
            ("‘Not we! my dear Clara--will you mind my calling you Clara?’", "we", "Clara"),
        ):
            with self.subTest(source=source):
                text, tree, nodes, edges = self.selected(source)
                self.assertEqual(tree.rule_id, N660_GERUND_QUESTION)
                _, reprise, vocative, _, question, _ = tree.children
                self.assertEqual(reprise.rule_id, "structural_negative_subject_reprise")
                self.assertEqual(text[reprise.start:reprise.end], f"Not {focus}!")
                self.assertEqual(vocative.rule_id, "structural_affectionate_epithet_vocative")
                self.assertEqual([child.category for child in vocative.children],
                                 ["POSS", "ADJ", "PROPER-NOUN"])
                self.assertEqual(text[vocative.start:vocative.end], f"my dear {name}")
                self.assertTrue(text[question.start:question.end].endswith("?"))
                roles = {(r, a["surface"] or a["type"], b["surface"] or b["type"])
                         for r, a, b in edges}
                self.assertEqual(roles, {
                    ("NEGATION", "NEGATIVE_REPRISE", "Not"),
                    ("FOCUS", "NEGATIVE_REPRISE", focus),
                    ("DISCOURSE_SEQUENCE", "NEGATIVE_REPRISE", "mind"),
                    ("MODIFIER", name, "dear"), ("VOCATIVE", "mind", name),
                    ("MODALITY", "mind", "will"), ("EXPERIENCER", "mind", "you"),
                    ("CONTENT", "mind", "calling"), ("AGENT", "calling", "my"),
                    ("THEME", "calling", "you"), ("PREDICATE_NOMINAL", "you", name),
                })
                address, = (b for r, _, b in edges if r == "VOCATIVE")
                self.assertEqual(address["span"], [vocative.children[-1].start, vocative.end])
                negated, = (a for r, a, _ in edges if r == "NEGATION")
                self.assertEqual(negated["span"], [reprise.start, reprise.end])
                self.assertFalse(any(n["surface"] == "dear" and n["type"] == "PERSON"
                                     for n in nodes.values()))
        for source in (
            "‘Now we! my dear Clara--will you mind my calling you Clara?’",
            "‘Not we! my dear Clara--will you mind my calling you Clara!’",
        ):
            _, tree, _, _ = self.selected(source)
            self.assertFalse(tree and tree.rule_id == N660_GERUND_QUESTION)

    def test_n680_negative_proform_is_attitude_content(self):
        from seman_parser.scoped_novel_ladder import STANDALONE_NEGATIVE_PROFORM
        for source, attitude, experiencer in (
            (680, "hope", "I"), ("“We expect not.”", "expect", "We"),
        ):
            with self.subTest(source=source):
                text, tree, _, edges = self.selected(source)
                self.assertEqual(tree.rule_id, STANDALONE_NEGATIVE_PROFORM)
                attitude_clause = tree.children[1]
                self.assertEqual(attitude_clause.rule_id, "structural_ladder_belief_with_negative_proform")
                proform = attitude_clause.children[-1]
                self.assertEqual((proform.category, text[proform.start:proform.end]), ("NEG", "not"))
                roles = {(r, a["surface"], b["surface"]) for r, a, b in edges}
                self.assertEqual(roles, {("EXPERIENCER", attitude, experiencer),
                                         ("CONTENT_PROFORM", attitude, "not")})
                content, = (b for r, _, b in edges if r == "CONTENT_PROFORM")
                self.assertEqual(content["type"], "NEGATION")
        for source in ("“We do not expect it.”", "“We expect not to go.”"):
            _, tree, _, edges = self.selected(source)
            self.assertFalse(tree and tree.rule_id == STANDALONE_NEGATIVE_PROFORM)
            self.assertFalse(any(r == "CONTENT_PROFORM" for r, _, _ in edges))

    def test_n663_reported_copular_content_and_vocative(self):
        positive="‘I hope Mrs. Micawber and your family are well, sir,’ said his aunt."
        negative="‘I hope Mrs. Micawber and your family are well, sir,’ said his."
        self.check(663,positive,negative,
            [("COMPLEMENT","hope","are"),("REPORTED_CONTENT","said","hope"),
             ("ATTRIBUTE","are","well"),("ADDRESSEE","said","sir")],
            "dialogue_structural_postposed_finite_clause_vocative")

    def test_n681_selected_passive_patient(self):
        self.check(681,"Mary was distressed.","Mary were distressed.",
            [("THEME","distressed","Mary")],"clause_passive",
            source_links=[("THEME","distressed","Elizabeth")])

    def test_n706_modalized_future_event(self):
        self.check(706,"But victory SHALL crown my efforts.",
            "But victory SHALL crowns my efforts.",
            [("MODALITY","crown","SHALL"),("AGENT","crown","victory"),
             ("AFFECTED","crown","efforts")],"coord_clause",
            source_links=[("MODALITY","crown","SHALL"),
                          ("AGENT","crown","success"),
                          ("AFFECTED","crown","endeavours")])

if __name__=="__main__":
    unittest.main()
