import unittest
from scripts.audit_erg_dialogue_components import stratum, compare_component, anchors

MRS='[ TOP: h0 INDEX: e2 RELS: < [ _bark_v_1<4:9> LBL: h1 ARG0: e2 ARG1: x3 ] > HCONS: < h0 qeq h1 > ]'

class DialogueAuditTests(unittest.TestCase):
    def test_strata(self):
        clear={"quality_flags":[]}
        flagged={"quality_flags":["quoted"]}
        self.assertEqual(stratum({"results":[]}),"no_result")
        self.assertEqual(stratum({"results":[flagged]}),"all_flagged")
        self.assertEqual(stratum({"results":[flagged,clear]}),"first_flagged_alternative_clear")
        self.assertEqual(stratum({"results":[clear,flagged]}),"first_clear")

    def test_exact_span_and_union_comparison(self):
        result={"mrs":MRS,"quality_flags":[]}
        text='"Dog barks."'
        part={"start":1,"end":11}
        a={"source_text":text[1:11],"results":[result]}
        prior={(5,10,"_bark_v_1")}
        c=compare_component(set(),prior,text,part,a)
        self.assertEqual(c["new_vs_whole_first"],[(5,10,"_bark_v_1")])
        self.assertEqual(c["new_vs_any_whole"],[])
        with self.assertRaises(ValueError):
            compare_component(set(),set(),text,part,{**a,"source_text":"rewritten"})
