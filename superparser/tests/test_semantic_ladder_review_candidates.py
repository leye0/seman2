"""Source-grounded rank-one semantic checks for previously unreviewed cases.

Do NOT mark an individual verified solely because a test method passed:
the exact original source, an independent grammatical positive, an invalid
near-miss, a correct selected rule and overt semantic relations must all pass.
"""
from __future__ import annotations

import json
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

    def test_batch_two_selected_source_structures_and_contrasts(self):
        from seman_parser import scoped_quality_repairs as scoped

        # The source-specific assertions exercise the parser's selected tree
        # and graph, not whether some lower-ranked tree contains a link.
        rows = (
            (602, ("vp_prep_ditransitive",),
             "MEDIUM|expressed|answer;THEME|expressed|feelings;AGENT|expressed|I",
             "I expressed my doubts in a letter.", "MEDIUM|expressed|letter",
             "I expressed my thanks to her.", "MEDIUM|expressed|her"),
            (604, ("vp_transitive",),
             "STIMULUS|troubled|speech;EXPERIENCER|troubled|me",
             "That report alarmed her.", "STIMULUS|alarmed|report;EXPERIENCER|alarmed|her",
             "That man greeted her.", "STIMULUS|greeted|man;EXPERIENCER|greeted|her"),
            (605, (scoped.MANNER_QUESTION, "structural_degree_manner_adverb"),
             "DEGREE|roughly|so;MANNER|answer|roughly;INTERROGATIVE_CAUSE|answer|Why;AUXILIARY|answer|do;AGENT|answer|you;AFFECTED|answer|me",
             "“Why did she greet him so warmly?”", "MANNER|greet|warmly;INTERROGATIVE_CAUSE|greet|Why;DEGREE|warmly|so",
             "“Why does you greet him so warmly?”", ""),
            (606, ("vp_cop_adjp", "adjp_coord"),
             "PREDICAND|was|letter;ATTRIBUTE|was|calm;ATTRIBUTE|was|affectionate;CONJUNCT|calm|affectionate",
             "The report was clear and concise.", "PREDICAND|was|report;ATTRIBUTE|was|clear;ATTRIBUTE|was|concise",
             "The report was clear.", "ATTRIBUTE|was|concise"),
            (608, ("clause_yn_modal_with_predicate", "rel_pp_finite_np_vp", "vp_negative_semimodal_bare"),
             "MODALITY|allude|Could;AGENT|allude|he;COMPLEMENT|to|object;OBLIQUE|allude|to;"
             "RELATIVE_MODIFIER|object|think;RELATIVE_REF|whom|object;COMPLEMENT|on|whom;OBLIQUE|think|on;"
             "MODALITY|think|dared;NEGATION|think|not;FOCUS|think|even;EXPERIENCER|think|I",
             "“Will he refer to the woman with whom I dared not talk?”",
             "MODALITY|refer|Will;RELATIVE_REF|whom|woman;NEGATION|talk|not;COMPLEMENT|with|whom",
             "“Will he refer to the woman?”", "RELATIVE_REF;NEGATION"),
            (626, (scoped.MINOR_REPORT, "structural_minor_polite_polarity"),
             "VOCATIVE|No|sir;AGENT|said|I;REPORTED_CONTENT|said|No",
             "“No, madam,” replied Mary.", "VOCATIVE|No|madam;AGENT|replied|Mary;REPORTED_CONTENT|replied|No",
             "“No,” replied Mary.", "VOCATIVE"),
            (628, ("clause_front_pp_nocomma", "vp_perfect_trans", "np_det_n"),
             "ABOUT|heard|Silver;ASPECT|heard|have;CONTENT|heard|more;NEGATIVE_QUANTIFIER|more|no;AGENT|heard|we",
             "Of Mary we have heard no more.", "ABOUT|heard|Mary;NEGATIVE_QUANTIFIER|more|no",
             "Of Mary we have dreamed.", "ABOUT|dreamed|Mary"),
            (629, (scoped.MINIMIZER,),
             "AGENT|moved|doctor;NEGATION|moved|never;EMPHASIS|moved|so much as",
             "The child never so much as blinked.", "AGENT|blinked|child;NEGATION|blinked|never;EMPHASIS|blinked|so much as",
             "The children never so much as blinks.", "EMPHASIS"),
            (651, ("vp_perfect_trans",),
             "POSSESSES|boy|baby;ASPECT|got|has;POSSESSOR|got|boy;POSSESSED|got|baby",
             "The girl has got the key.", "POSSESSES|girl|key;ASPECT|got|has",
             "The girl had got the key.", "POSSESSES|girl|key"),
            (653, (scoped.MODAL_PASSIVE,),
             "MODALITY|improved|Will;PASSIVE|improved|be;THEME|improved|you",
             "“Could the patient be examined?”", "MODALITY|examined|Could;PASSIVE|examined|be;THEME|examined|patient",
             "“Could the patient be happy?”", "PASSIVE"),
            (676, ("vp_cop_adj_adv",),
             "ATTRIBUTE|was|gone;TEMPORAL|was|directly;PREDICAND|was|She",
             "He was silent immediately.", "TEMPORAL|was|immediately;PREDICAND|was|He",
             "“Is the captain on deck?”", "TEMPORAL"),
            (677, (scoped.MANNER_STATEMENT, "structural_intensifier_manner_adverb"),
             "DEGREE|fast|uncommonly;MANNER|write|fast;AGENT|write|You",
             "“You sing remarkably well.”", "DEGREE|well|remarkably;MANNER|sing|well",
             "“You sings remarkably well.”", "DEGREE|well|remarkably"),
            (678, ("pp_degree", "pp_np_coord"),
             "EXAMPLE|Such|vanity;EXAMPLE|Such|pride;CONJUNCT|vanity|pride",
             "“Such as tea and coffee.”", "EXAMPLE|Such|tea;EXAMPLE|Such|coffee",
             "“Near tea and coffee.”", "EXAMPLE"),
            (679, ("vp_transitive", "np_det_n"),
             "NEGATIVE_QUANTIFIER|answer|no;RESULT|made|answer;AGENT|made|Bennet",
             "We made no reply.", "NEGATIVE_QUANTIFIER|reply|no;RESULT|made|reply",
             "We made a reply.", "NEGATIVE_QUANTIFIER"),
            (703, (scoped.APOSTROPHE,),
             "VOCATIVE|O|sleep;MODIFIER|sleep|blessed",
             "O cruel fate!", "VOCATIVE|O|fate;MODIFIER|fate|cruel",
             "O bless them!", "VOCATIVE|O|them"),
            (712, ("vp_prepositional", "advp_vp", "n_adj_n"),
             "AGENT|walked|I;MANNER|walked|pace;SPEED|pace|quick;CONJUNCT|walked|arrived;"
             "GOAL|arrived|college;TEMPORAL|arrived|soon;AGENT|arrived|we;POSSESSOR|college|my",
             "We walked with a brisk pace, and they soon arrived at their school.",
             "MANNER|walked|pace;SPEED|pace|brisk;TEMPORAL|arrived|soon;GOAL|arrived|school",
             "He walked with a stick.", "MANNER|walked|stick;SPEED"),
            (726, ("clause_front_adv_nocomma",),
             "TEMPORAL_SEQUENCE|spoke|Then;AGENT|spoke|he",
             "Then she laughed.", "TEMPORAL_SEQUENCE|laughed|Then",
             "She laughed loudly.", "TEMPORAL_SEQUENCE"),
            (727, (scoped.MINOR_REPORT, "structural_minor_adjective_exclamation"),
             "REPORTED_CONTENT|cried|Ready;AGENT|cried|squire",
             "“Certain!” exclaimed Mary.", "REPORTED_CONTENT|exclaimed|Certain;AGENT|exclaimed|Mary",
             "“John!” exclaimed Mary.", ""),
            (729, ("vp_prepositional",),
             "GOAL|ran|deck;AGENT|ran|We",
             "They went on deck.", "GOAL|went|deck;AGENT|went|They",
             "They stayed on deck.", "GOAL|stayed|deck"),
            (734, (scoped.MINOR_REPORT, "structural_minor_postposed_report_with_instrumental_depictive"),
             "REPORTED_CONTENT|said|Prophetic;AGENT|said|doctor;DEPICTIVE|said|touching;"
             "AGENT|touching|doctor;AFFECTED|touching|picture;INSTRUMENT|touching|finger;POSSESSOR|finger|his",
             "“Wonderful,” said Mary, touching the screen with her palm.",
             "REPORTED_CONTENT|said|Wonderful;DEPICTIVE|said|touching;INSTRUMENT|touching|palm",
             "“Wonderful,” said Mary, touching the screen with her brother.", "INSTRUMENT|touching|brother"),
            (753, ("clause_passive", "vp_passive_interposed_manner_adverb"),
             "PASSIVE|altered|was;DEGREE|altered|greatly;THEME|altered|She",
             "She was deeply affected.", "PASSIVE|affected|was;DEGREE|affected|deeply;THEME|affected|She",
             "She was deeply happy.", "PASSIVE|happy|was"),
            (754, ("vp_transitive", "n_adj_n"),
             "DURATION|pause|short;LIGHT_VERB_COMPLEMENT|made|pause;AGENT|made|He",
             "She made a long pause.", "DURATION|pause|long;LIGHT_VERB_COMPLEMENT|made|pause",
             "She made a wooden box.", "DURATION;LIGHT_VERB_COMPLEMENT"),
            (776, ("np_title_name", "vp_linking_adj"),
             "ATTRIBUTE|seemed|pleased;PREDICAND|seemed|Catherine",
             "She seemed tired.", "ATTRIBUTE|seemed|tired;PREDICAND|seemed|She",
             "She seemed to agree.", "ATTRIBUTE|seemed|agree"),
            (777, (scoped.FREQUENCY_REPLY, "structural_approximated_universal_frequency"),
             "FREQUENCY|Yes|day;QUANTIFIER|day|every;DEGREE|every|almost",
             "“Yes, nearly every week.”", "FREQUENCY|Yes|week;QUANTIFIER|week|every;DEGREE|every|nearly",
             "“Yes, almost every book.”", "FREQUENCY|Yes|book"),
            (778, ("clause_yn_cop_pp", "pp_prep_np"),
             "PREDICAND|Is|father;LOCATION|Is|town;RELATION_MARKER|Is|in;POSSESSOR|father|my",
             "“Is the captain on deck?”", "PREDICAND|Is|captain;LOCATION|Is|deck;RELATION_MARKER|Is|on",
             "“Is the captain a doctor?”", "LOCATION"),
            (779, ("vp_cop_adjp", "adjp_adj_pp"),
             "PREDICAND|were|They;ATTRIBUTE|were|hopeless;CONTENT|hopeless|remedy",
             "They were afraid of illness.", "PREDICAND|were|They;CONTENT|afraid|illness",
             "They were concerned about remedy.", "CONTENT|concerned|remedy"),
            (780, ("vp_copula_adj", "adj_degree"),
             "DEGREE|universal|almost;ATTRIBUTE|was|universal;PREDICAND|was|dejection",
             "The vote was nearly unanimous.", "DEGREE|unanimous|nearly;PREDICAND|was|vote",
             "The vote was universal.", "DEGREE"),
            (786, ("vp_list3", "vp_prep_ditransitive"),
             "AGENT|went|Jane;GOAL|went|him;TEMPORAL|went|instantly;AGENT|kissed|Jane;AFFECTED|kissed|him;"
             "AGENT|thanked|Jane;ADDRESSEE|thanked|him;GROUNDS|thanked|goodness;"
             "CONJUNCT|went|kissed;CONJUNCT|went|thanked",
             "Mary went to him instantly, kissed him, and thanked him for his patience.",
             "AGENT|thanked|Mary;ADDRESSEE|thanked|him;GROUNDS|thanked|patience",
             "She gave it to him.", "GROUNDS;ADDRESSEE"),
        )

        def descendants(tree):
            if tree is not None:
                yield tree
                for child in tree.children:
                    yield from descendants(child)

        def keys(edges):
            return {"|".join((role, a["surface"] or a["type"] or "", b["surface"] or b["type"] or ""))
                    for role, a, b in edges}

        replacement_roots = {scoped.MANNER_QUESTION, scoped.MINIMIZER, scoped.MODAL_PASSIVE,
                             scoped.MANNER_STATEMENT, scoped.APOSTROPHE, scoped.FREQUENCY_REPLY}
        for index, selected_rules, evidence, good, good_evidence, bad, banned in rows:
            with self.subTest(index=index, example="frozen source"):
                text, tree, _, edges = self.selected(index)
                self.assertIsNotNone(tree)
                self.assertTrue(set(selected_rules).issubset({n.rule_id for n in descendants(tree)}))
                self.assertEqual(tree.start, 0)
                self.assertIn(text[tree.end:], ("", ".", "!", "?"))
                self.assertLessEqual(set(evidence.split(";")), keys(edges))
            with self.subTest(index=index, example="independent positive"):
                _, tree, _, edges = self.selected(good)
                self.assertIsNotNone(tree)
                self.assertLessEqual(set(good_evidence.split(";")), keys(edges))
            with self.subTest(index=index, example="contrast"):
                _, tree, _, edges = self.selected(bad)
                if selected_rules[0] in replacement_roots:
                    self.assertFalse(tree and tree.rule_id == selected_rules[0])
                if index == 727:
                    self.assertNotIn("structural_minor_adjective_exclamation",
                                     {n.rule_id for n in descendants(tree)})
                actual = keys(edges)
                for relation in filter(None, banned.split(";")):
                    self.assertFalse(any(edge == relation or edge.startswith(relation + "|")
                                         for edge in actual), (bad, relation, actual))

    def test_batch_three_selected_source_structures_and_contrasts(self):
        from seman_parser import scoped_quality_followup as plan

        rows = (
            (607, plan.BODY_PART, "structural_body_part_of_genitive",
             "POSSESSOR|hand|Elizabeth;GENITIVE_MARKER|hand|of;AFFECTED|took|hand;AGENT|took|I",
             "He grasped the wrist of Mary.", "POSSESSOR|wrist|Mary;AFFECTED|grasped|wrist",
             "He grasped the portrait of Mary.", ""),
            (610, plan.LOCATIVE_CONTROL, "np_det_n_of",
             "LOCATION|find|house;SUBJECT|chanced|I;AGENT|find|I;CONTROL_COMPLEMENT|chanced|find;"
             "AFFECTED|find|volume;PARTITIVE|volume|works;AUTHOR|works|Cornelius",
             "In that room we happened to find a key.", "LOCATION|find|room;CONTROL_COMPLEMENT|happened|find;AGENT|find|we",
             "In that room he happened to finds a key.", ""),
            (613, plan.RECIPROCAL_AND_CONTROL, plan.RECIPROCAL_AND_CONTROL,
             "AGENT|looked|They;COMPLEMENT|at|one another;RECIPROCAL_GROUP|one another|They;CONJUNCT|looked|were;"
             "PREDICAND|were|They;ATTRIBUTE|were|unable;COMPLEMENT|unable|reply;CONTROLLER|reply|They",
             "They glanced at each other and were unable to speak.",
             "RECIPROCAL_GROUP|each other|They;COMPLEMENT|unable|speak;CONTROLLER|speak|They",
             "They glanced at each other and were unable to spoke.", ""),
            (627, None, "vp_adv",
             "LIGHT_VERB_COMPLEMENT|took|step;DIRECTION|took|nearer;AGENT|took|I",
             "We took a step closer.", "LIGHT_VERB_COMPLEMENT|took|step;DIRECTION|took|closer",
             "We took a book from her.", "LIGHT_VERB_COMPLEMENT"),
            (630, plan.MINIMUM_REPORT, "structural_duration_with_minimum",
             "LOWER_BOUND|week|at least;AGENT|said|I;REPORTED_CONTENT|said|week",
             "“An hour at least,” said she.", "LOWER_BOUND|hour|at least;REPORTED_CONTENT|said|hour",
             "“An hour at most,” said she.", "LOWER_BOUND"),
            (631, None, "np_genitive",
             "ATTRIBUTE|was|mystery;POSSESSOR|mystery|ship;PREDICAND|was|That",
             "That was the captain’s secret.", "POSSESSOR|secret|captain;PREDICAND|was|That",
             "That was a mystery.", "POSSESSOR"),
            (637, plan.INVERTED_REPORT, "structural_postposed_plural_motion_subject",
             "AGENT|come|gigs;DEIXIS|come|Here;VOCATIVE|come|sir;AGENT|said|I;REPORTED_CONTENT|said|come",
             "“Here come the boats, madam,” cried James.", "AGENT|come|boats;VOCATIVE|come|madam;REPORTED_CONTENT|cried|come",
             "“Here comes the boats, madam,” cried James.", ""),
            (656, plan.HANDSHAKE, plan.HANDSHAKE,
             "RECIPROCAL_PARTICIPANTS|shook|We;BODY_PART|shook|hands;MANNER|shook|heartily",
             "They shook hands warmly.", "RECIPROCAL_PARTICIPANTS|shook|They;BODY_PART|shook|hands",
             "They shook the chairs firmly.", "BODY_PART;RECIPROCAL_PARTICIPANTS"),
            (659, plan.TITLED_REPORT, "structural_reportable_emphatic_interjection",
             "HONORIFIC|Copperfield|Master;VOCATIVE|Oh|Copperfield;EMPHASIS|Oh|indeed;"
             "AGENT|said|Uriah;REPORTED_CONTENT|said|Oh",
             "“Oh, truly, Doctor Watson,” said Mary.", "HONORIFIC|Watson|Doctor;VOCATIVE|Oh|Watson;EMPHASIS|Oh|truly",
             "“Oh, truly, beautiful Mary,” said James.", ""),
            (662, plan.TITLED_REPORT, "structural_reportable_nominal_exclamation",
             "HONORIFIC|Copperfield|Master;VOCATIVE|lady|Copperfield;MODIFIER|lady|sweet;AGENT|said|Uriah;REPORTED_CONTENT|said|lady",
             "“A kind gentleman, Captain Nemo!” said Mary Jane.",
             "HONORIFIC|Nemo|Captain;VOCATIVE|gentleman|Nemo;MODIFIER|gentleman|kind;REPORTED_CONTENT|said|gentleman",
             "“A kind gentleman!” said Mary Jane.", "VOCATIVE"),
            (682, plan.CONTRAST, plan.CONTRAST,
             "EXCLAMATIVE|contrast|What;FIRST_TERM|contrast|him;SECOND_TERM|contrast|friend;POSSESSOR|friend|his",
             "What a distinction between us and our neighbours!",
             "EXCLAMATIVE|distinction|What;FIRST_TERM|distinction|us;SECOND_TERM|distinction|neighbours",
             "What a distinction between us!", "SECOND_TERM"),
            (683, None, "vp_cop_pp",
             "MODIFIER|terms|intimate;DEGREE|intimate|most;PREDICATIVE_RELATION|were|terms;FREQUENCY|were|always;"
             "PREDICAND|were|they;COUNTERPART|terms|Gardiners",
             "With the neighbours, we were often on the most cordial terms.",
             "FREQUENCY|were|often;COUNTERPART|terms|neighbours;PREDICAND|were|we",
             "With the neighbours, we played outdoors.", "FREQUENCY;PREDICATIVE_RELATION"),
            (701, plan.DEAR_ADDRESS, plan.DEAR_ADDRESS,
             "VOCATIVE|Dear|Elizabeth;EMPHATIC_REPRISE|dear|Dear;MODIFIER|Elizabeth|dear",
             "“Dear, dear Margaret!”", "VOCATIVE|Dear|Margaret;MODIFIER|Margaret|dear",
             "“Dear Margaret!”", "EMPHATIC_REPRISE"),
            (707, None, "clause_negative_modal_ellipsis",
             "SUBJECT|ELLIPTIC_PREDICATE|You;MODALITY|ELLIPTIC_PREDICATE|would;NEGATION|ELLIPTIC_PREDICATE|not;"
             "CONDITION|ELLIPTIC_PREDICATE|saw;AGENT|saw|you;AFFECTED|saw|him",
             "I would not if you asked me.",
             "MODALITY|ELLIPTIC_PREDICATE|would;NEGATION|ELLIPTIC_PREDICATE|not;CONDITION|ELLIPTIC_PREDICATE|asked",
             "I would leave if you asked me.", "SUBJECT|ELLIPTIC_PREDICATE;NEGATION|ELLIPTIC_PREDICATE"),
            (731, None, "vp_cop_np",
             "MODIFIER|sand|clean;ATTRIBUTE|was|sand;PREDICAND|was|bottom",
             "The surface was dry clay.", "MODIFIER|clay|dry;ATTRIBUTE|was|clay;PREDICAND|was|surface",
             "The surface was clay.", "MODIFIER"),
            (733, None, "adjp_adj_pp",
             "ORDINAL|trip|fifth;DEGREE|different|quite;PARTITIVE|any|others;COMPARISON|different|any;"
             "ATTRIBUTE|was|different;PREDICAND|was|trip",
             "This third visit was quite different from any of the others.", "ORDINAL|visit|third;DEGREE|different|quite;PREDICAND|was|visit",
             "This visit was different from any of the others.", "ORDINAL;DEGREE"),
            (736, plan.RESUMED_PERMISSION, plan.RESUMED_PERMISSION,
             "AGENT|said|I;REPORTED_CONTENT|said|Good;REPORTED_CONTENT|said|go;CONTINUED_SPEECH|Good|go;"
             "AGENT|go|I;TEMPORAL|go|now;MODALITY|go|may",
             "“Fine,” said she, “and now may I leave?”", "CONTINUED_SPEECH|Fine|leave;MODALITY|leave|may;REPORTED_CONTENT|said|leave",
             "“Fine,” said she, “and now may I leaves?”", ""),
            (738, None, "clause_wh_copular_nominal_question",
             "SUPERLATIVE|shot|best;INTERROGATIVE_PREDICAND|'s|Who;ATTRIBUTE|'s|shot;REPORTED_CONTENT|asked|'s;AGENT|asked|captain",
             "“Who’s the best swimmer?” asked the teacher.",
             "SUPERLATIVE|swimmer|best;INTERROGATIVE_PREDICAND|’s|Who;ATTRIBUTE|’s|swimmer",
             "“Where is the swimmer?” asked the teacher.", "INTERROGATIVE_PREDICAND"),
            (751, plan.DEGREE_ECHO, plan.DEGREE_ECHO,
             "DEGREE_REPRISE|Very|Very;DISCOURSE_SEQUENCE|Very|Very",
             "‘Extremely! Extremely!’", "DEGREE_REPRISE|Extremely|Extremely",
             "‘Very! No!’", "DEGREE_REPRISE"),
            (752, plan.FUSED_NEGATIVE, plan.FUSED_NEGATIVE,
             "AGENT|answer|He;MODALITY|answer|can;NEGATION|answer|not;OBLIQUE|answer|for;COMPLEMENT|for|others",
             "“We cannot speak for them.”", "MODALITY|speak|can;NEGATION|speak|not;COMPLEMENT|for|them",
             "“We can speak for them.”", "NEGATION"),
            (755, plan.UNIVERSAL_OBJECT, plan.UNIVERSAL_OBJECT,
             "EXPERIENCER|knew|I;CONTENT|knew|all;TEMPORAL|knew|now",
             "We understood all then.", "CONTENT|understood|all;TEMPORAL|understood|then",
             "We understood all the problems.", "CONTENT|understood|all"),
            (756, plan.CONTINUATION, plan.CONTINUATION,
             "DISCOURSE_TRANSITION|went|So;AGENT|went|we;CONTINUATIVE|went|on",
             "So they carried on.", "DISCOURSE_TRANSITION|carried|So;CONTINUATIVE|carried|on",
             "They carried it on their shoulders.", "DISCOURSE_TRANSITION"),
            (761, plan.MINOR_AND_PERFECT, "structural_perfect_declarative_question",
             "MODIFIER|woman|little;POSSESSOR|name|her;ASPECT|forgot|have;EXPERIENCER|forgot|I;"
             "CONTENT|forgot|name;DISCOURSE_SEQUENCE|woman|forgot",
             "“A tall man. I have forgotten his address?”",
             "MODIFIER|man|tall;ASPECT|forgotten|have;DISCOURSE_SEQUENCE|man|forgotten",
             "“A tall man. I has forgotten his address?”", ""),
            (781, None, "np_genitive",
             "AGENT|sparkled|eyes;POSSESSOR|eyes|Bennet",
             "Alice’s fingers trembled.", "AGENT|trembled|fingers;POSSESSOR|fingers|Alice",
             "Alice and her fingers trembled.", "POSSESSOR|fingers|Alice"),
            (783, plan.OBJECT_CONTROL, "structural_prepositional_controlled_infinitive",
             "AGENT|called|aunt;TEMPORAL|called|now;ADDRESSEE|called|her;CONTROL_COMPLEMENT|called|look;"
             "AGENT|look|her;OBLIQUE|look|at;COMPLEMENT|at|picture",
             "The teacher now asked him to speak to the doctor.",
             "CONTROL_COMPLEMENT|asked|speak;AGENT|speak|him;COMPLEMENT|to|doctor",
             "The teacher now asked he to speak to the doctor.", ""),
            (784, plan.MOTION_PERFECT, "np_of",
             "AGENT|walked|Darcy;ASPECT|walked|had;DIRECTION|walked|away;GOAL|walked|part;"
             "PART_OF|part|room;DISTINCT_ALTERNATIVE|part|another",
             "Mary had hurried back to the garden.", "ASPECT|hurried|had;DIRECTION|hurried|back;GOAL|hurried|garden",
             "Mary had hurry back to the garden.", ""),
        )

        def descendants(tree):
            if tree is not None:
                yield tree
                for child in tree.children:
                    yield from descendants(child)

        def keys(edges):
            return {"|".join((role, a["surface"] or a["type"] or "", b["surface"] or b["type"] or ""))
                    for role, a, b in edges}

        for index, root, witness, required, good, good_edges, bad, forbidden in rows:
            with self.subTest(index=index, kind="frozen source"):
                text, tree, nodes, edges = self.selected(index)
                self.assertIsNotNone(tree)
                if root is not None:
                    self.assertEqual(tree.rule_id, root)
                self.assertIn(witness, {n.rule_id for n in descendants(tree)})
                self.assertEqual(tree.start, 0)
                self.assertIn(text[tree.end:], ("", ".", "!", "?"))
                self.assertLessEqual(set(required.split(";")), keys(edges))
                typed = {610: ("volume", "BOOK_VOLUME"), 656: ("hands", "BODY_PART"),
                         738: ("shot", "PERSON")}
                if index in typed:
                    self.assertIn(typed[index], {(n["surface"], n["type"]) for n in nodes.values()})
                if index == 751:
                    second, first = next((a, b) for rel, a, b in edges if rel == "DEGREE_REPRISE")
                    self.assertLess(first["span"][1], second["span"][0])
                    self.assertNotEqual(first["id"], second["id"])
                if index == 752:
                    _, modal = next((a, b) for rel, a, b in edges if rel == "MODALITY")
                    _, negator = next((a, b) for rel, a, b in edges if rel == "NEGATION")
                    self.assertEqual(modal["span"][1], negator["span"][0])
                    self.assertEqual(text[modal["span"][0]:negator["span"][1]], "cannot")
            with self.subTest(index=index, kind="independent positive"):
                _, tree, _, edges = self.selected(good)
                self.assertIsNotNone(tree)
                if root is not None:
                    self.assertEqual(tree.rule_id, root)
                self.assertLessEqual(set(good_edges.split(";")), keys(edges))
            with self.subTest(index=index, kind="contrast"):
                _, tree, _, edges = self.selected(bad)
                if root is not None:
                    self.assertFalse(tree and tree.rule_id == root)
                actual = keys(edges)
                for absent in filter(None, forbidden.split(";")):
                    self.assertFalse(any(edge == absent or edge.startswith(absent + "|")
                                         for edge in actual), (bad, absent, actual))

    def test_batch_four_selected_attachment_domains(self):
        self.check_batch_attachment_domains("semantic_batch4_controls.json")

    def test_batch_five_selected_attachment_domains(self):
        self.check_batch_attachment_domains("semantic_batch5_controls.json")

    def check_batch_attachment_domains(self, fixture):
        controls = json.loads((ROOT / "tests/data" / fixture).read_text())

        def desc(node):
            return node["surface"] or f'<{node["type"]}>'

        def walk(node):
            yield node
            for child in node.children:
                yield from walk(child)

        def triples(values):
            return {tuple(value.split("|", 2)) for value in values}

        for record in controls:
            index = record["index"]
            for source, key in ((index, "source"), (record["positive"], "positive_edges"),
                                (record["negative"], None)):
                with self.subTest(index=index, contrast=key or "negative"):
                    text, tree, _, edges = self.selected(source)
                    if key is None:
                        self.assertFalse(tree and tree.rule_id == record["root"],
                                         "Contrasting syntax selected the source family")
                        continue
                    self.assertIsNotNone(tree)
                    self.assertEqual(tree.rule_id, record["root"])
                    self.assertEqual((tree.start, tree.end), (0, len(text)))
                    have = {(rel, desc(a), desc(b)) for rel, a, b in edges}
                    self.assertFalse(triples(record[key]) - have, triples(record[key]) - have)
                    if key == "source":
                        leaves = {(leaf.category, text[leaf.start:leaf.end]) for leaf in walk(tree)
                                  if leaf.lexical_candidate is not None}
                        self.assertFalse({tuple(x.split("|", 1)) for x in record.get("leaves", ())} - leaves)
                        self.assertFalse(triples(record.get("blocked", ())) & have)
                    self.assertFalse(any(a["id"] == b["id"] for _, a, b in edges))

    def test_batch_four_shared_and_distinct_source_bindings(self):
        for index, relation, first, second in (
            (636, "NEGATION", "wo", "n't"),
            (711, "ASPECT", "lost", "have"),
            (667, "COMPARISON_STANDARD", None, "of yore"),
        ):
            with self.subTest(index=index):
                text, tree, _, edges = self.selected(index)
                self.assertIsNotNone(tree)
                linked = [(a, b) for rel, a, b in edges
                          if rel == relation and (first is None or a["surface"] == first)
                          and b["surface"] == second]
                if index == 636:
                    (modal, negator), = linked
                    self.assertEqual(modal["span"][1], negator["span"][0])
                    self.assertEqual(text[modal["span"][0]:negator["span"][1]], "won't")
                elif index == 711:
                    self.assertEqual(len(linked), 2)
                    (left_verb, left_aux), (right_verb, right_aux) = linked
                    semicolon = text.index(";")
                    self.assertLess(left_aux["span"][1], left_verb["span"][0])
                    self.assertLess(left_verb["span"][1], semicolon)
                    self.assertLess(semicolon, right_aux["span"][0])
                    self.assertLess(right_aux["span"][1], right_verb["span"][0])
                else:
                    self.assertEqual({a["surface"] for a, _ in linked}, {"confused", "genteel"})
                    self.assertEqual(len({b["id"] for _, b in linked}), 1)

        for index, source, expected_type in ((714, "diligences", "PASSENGER_VEHICLE"),
                                              (743, "Benbow", "VENUE"),
                                              (796, "intelligence", "INFORMATION")):
            with self.subTest(index=index):
                _, _, nodes, _ = self.selected(index)
                (target,) = [n for n in nodes.values() if n["surface"] == source]
                self.assertEqual(target["type"], expected_type)

        for index, contrast in (
            (614, "The storm subsided; but the wind still blew, and the valley were shrouded in a dense mist."),
            (711, "We has lost our dreams of peace and fame; they had abandoned their plan."),
            (757, "‘What are he talking about, Clara?’ said Miss Murdstone."),
        ):
            with self.subTest(index=index):
                _, root, _, _ = self.selected(index)
                _, rejected, _, _ = self.selected(contrast)
                self.assertTrue(root)
                self.assertFalse(rejected and rejected.rule_id == root.rule_id)

    def test_n655_documented_nonpast_stem_cannot_fake_singular_inflection(self):
        for source, verb, subject, body in (
            (655, "shook", "She", "head"),
            ("He shakes his head.", "shakes", "He", "head"),
            ("He shook his head.", "shook", "He", "head"),
            ("They shake their heads.", "shake", "They", "heads"),
            ("He cut his hand.", "cut", "He", "hand"),
            ("She can shake her head.", "shake", "She", "head"),
        ):
            with self.subTest(source=source):
                _, tree, _, edges = self.selected(source)
                self.assertIsNotNone(tree)
                observed = {(rel, a["surface"], b["surface"]) for rel, a, b in edges}
                self.assertIn(("AGENT", verb, subject), observed)
                self.assertIn(("AFFECTED", verb, body), observed)
        for source in ("He shake his head.", "She take the box."):
            with self.subTest(negative=source):
                _, lattice, result = self.parse(source)
                self.assertFalse(result.completed)
                self.assertFalse(result.stats.get("budget_exceeded"))
                self.assertFalse(result.stats.get("kbest_budget_exceeded"))
                self.assertTrue(any(c.excludes_third_singular for c in lattice.candidates))

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
