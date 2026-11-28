import unittest
from seman_parser.dialogue_graph import source_view, remap, resumed_views, compose_dialogue
from seman_parser.structural_preanalysis import analyze_paragraph

def empty(text): return {"source_text":text,"status":"no_analysis_returned","results":[]}

class DialogueGraphTests(unittest.TestCase):
    def test_source_map_discontinuous(self):
        v=source_view("abc XX def",[(0,3),(6,10)])
        self.assertEqual(v["text"],"abc def")
        self.assertEqual(remap(v["source_map"],1,6),[[1,3],[6,9]])
        self.assertEqual(remap(v["source_map"],0,99),[])

    def test_exact_resumed_view_and_comma_variants(self):
        text="‘Martha wants,’ she said to Ham, ‘to go to London.’"
        unit,=analyze_paragraph(text)
        ps=[p.to_dict() for p in unit.constituents]
        views=list(resumed_views(text,ps))
        self.assertEqual([v["text"] for v in views],["Martha wants, to go to London.","Martha wants to go to London."])
        for v in views:
            for a,b,c,d in v["source_map"]:
                self.assertEqual(v["text"][a:b],text[c:d])
        self.assertEqual(text[slice(*views[1]["omitted_intercalation_commas"][0])],",")

    def test_resumption_without_semantic_fabrication(self):
        text='"Come here," said John, "and sit down."'
        unit,=analyze_paragraph(text)
        ps=[p.to_dict() for p in unit.constituents]
        g=compose_dialogue(text,ps,empty(text),[],parse=empty)
        self.assertEqual(len(g["attributions"]),2)
        self.assertEqual([a["reporting_clause_id"] for a in g["attributions"]],["r0","r0"])
        self.assertTrue(all(a["status"]=="unresolved" for a in g["attributions"]))
        self.assertEqual(g["readings"],[])
        self.assertEqual(g["native_cross_quote_links"],[])

    def test_no_invented_speaker_for_nested_or_unattributed(self):
        text="‘“When you see this, I shall be far away.”’"
        unit,=analyze_paragraph(text)
        g=compose_dialogue(text,[p.to_dict() for p in unit.constituents],empty(text),[])
        self.assertEqual(g["attributions"],[])
        self.assertEqual(list(resumed_views(text,g["source_nodes"])),[])

    def test_source_terminal_tag_does_not_join_quotes_or_propagate_speaker(self):
        text="‘And now they are partners,’ said I. ‘Confound him!’"
        unit,=analyze_paragraph(text)
        ps=[p.to_dict() for p in unit.constituents]
        self.assertEqual(list(resumed_views(text,ps)),[])
        g=compose_dialogue(text,ps,empty(text),[],parse=empty)
        self.assertEqual([a["quote_id"] for a in g["attributions"]],["q0"])

    def test_semicolon_has_no_comma_deletion_view(self):
        text='"Nay, mate," said he; "marooned."'
        unit,=analyze_paragraph(text)
        views=list(resumed_views(text,[p.to_dict() for p in unit.constituents]))
        self.assertEqual(len(views),1)
        self.assertEqual(views[0]["interruption_boundaries"],["semicolon"])
        self.assertEqual(views[0]["omitted_intercalation_commas"],[])
