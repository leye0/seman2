import unittest
from unittest.mock import patch
from seman_parser import Parser

class SourceAdapterTests(unittest.TestCase):
    def test_split_speech_is_exposed_without_stitching_or_rewriting(self):
        text='"Come here," said John, "and sit down."'
        calls=[]
        def parse(s):
            calls.append(s)
            return {"source_text":s,"status":"no_analysis_returned","results":[]}
        with patch.object(Parser,"parse",side_effect=parse):
            out=Parser("unused").parse_paragraph(text)
        unit=out["units"][0]
        self.assertEqual(calls[0],text)
        self.assertEqual(unit["whole"]["status"],"no_analysis_returned")
        self.assertTrue(unit["component_analyses"])
        for item in unit["component_analyses"]:
            a,b=item["unit_span"]
            self.assertEqual(text[a:b],item["analysis"]["source_text"])
        self.assertTrue(any(p["function"]=="split_direct_speech_turn" for p in unit["source_constituents"]))

    def test_unclosed_quote_is_exposed_but_not_parsed(self):
        with patch.object(Parser,"parse") as parse:
            out=Parser("unused").parse_paragraph('"Come here.')
        parse.assert_not_called()
        self.assertEqual(out["units"][0]["status"],"requires_source_review")

    def test_whole_only_does_not_parse_components(self):
        with patch.object(Parser,"parse",return_value={"status":"no_analysis_returned"}) as parse:
            out=Parser("unused").parse_paragraph('"Come here," said John.',parse_components=False)
        parse.assert_called_once()
        self.assertEqual(out["units"][0]["component_analyses"],[])
