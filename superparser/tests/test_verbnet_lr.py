"""Fast isolated tests with a small XML fixture modeling VerbNet 3.4 hierarchy."""
from pathlib import Path
import tempfile
import unittest

from research.verbnet_lr import compile_directory, read_index, write_index, PrefixIndex

XML = '''<!DOCTYPE VNCLASS SYSTEM "vn_class-3.dtd">
<VNCLASS ID="give-13.1"><MEMBERS>
<MEMBER name="lend" wn="lend%2:40:00" /></MEMBERS>
<FRAMES><FRAME><SYNTAX><NP value="Agent"/><VERB/><NP value="Theme"/>
<PREP value="to"/><NP value="Recipient"/></SYNTAX></FRAME></FRAMES>
<SUBCLASSES><VNSUBCLASS ID="give-13.1-1"><MEMBERS>
<MEMBER name="give" wn="give%2:40:00" /></MEMBERS>
<FRAMES><FRAME><SYNTAX><NP value="Agent"/><VERB/><NP value="Recipient"/>
<NP value="Theme"/></SYNTAX></FRAME></FRAMES><SUBCLASSES/></VNSUBCLASS></SUBCLASSES></VNCLASS>'''

HELP = '''<VNCLASS ID="help-72"><MEMBERS><MEMBER name="help"/></MEMBERS>
<FRAMES><FRAME><SYNTAX><NP value="Agent"/><VERB/><NP value="Beneficiary"/>
<PREP value="with | for"/><NP value="Theme"/></SYNTAX></FRAME>
<FRAME><SYNTAX><NP value="Agent"/><VERB/><NP value="Beneficiary"/>
<NP value="Theme"><SYNRESTRS><SYNRESTR Value="+" type="oc_to_inf"/></SYNRESTRS></NP>
</SYNTAX></FRAME><FRAME><SYNTAX><NP/><VERB/><MYSTERY/><NP/></SYNTAX></FRAME>
</FRAMES><SUBCLASSES/></VNCLASS>'''


class TestVerbNetLR(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)
        (path / "give.xml").write_text(XML, encoding="utf-8")
        (path / "help.xml").write_text(HELP, encoding="utf-8")
        self.senses = path / "index.sense"
        self.senses.write_text("give%2:40:00:: 01234567 1 0\nlend%2:40:00:: 02345678 1 0\n", encoding="utf-8")
        self.frames, self.stats = compile_directory(path, self.senses)
        self.assertGreaterEqual(self.stats["members_exact"], 2)
        self.index = PrefixIndex(self.frames)

    def test_inherited_frames_do_not_flow_downwards(self):
        self.assertEqual(len([f for f in self.frames if f.lemma == "lend"]), 1)
        self.assertEqual(len([f for f in self.frames if f.lemma == "give"]), 2)
        self.assertEqual(self.stats["frames_unsupported"], 1)

    def test_exact_wordnet_join_and_prefix(self):
        p = self.index.predict("give", ("NP",), synset_offset=1234567)
        self.assertEqual(p.status, "PREFIX")
        self.assertEqual(set(p.next_events), {"NP", "PREP:to"})
        self.assertEqual(self.index.predict("give", ("NP", "NP"), synset_offset=1234567).status, "ATTESTED")
        self.assertEqual(self.index.predict("give", ("NP", "PREP:to", "NP"), synset_offset=1234567).status, "ATTESTED")
        self.assertEqual(self.index.predict("give", ("NP",), synset_offset=999).status, "UNKNOWN")

    def test_no_incorrect_subclass_export(self):
        self.assertEqual(self.index.predict("lend", ("NP", "NP")).status, "UNKNOWN")
        self.assertEqual(self.index.predict("lend", ("NP", "PREP:to", "NP")).status, "ATTESTED")

    def test_preposition_alternatives_and_infinitive(self):
        p = self.index.predict("help", ("NP",))
        self.assertEqual(set(p.next_events), {"PREP:with", "PREP:for", "TO_INF"})
        self.assertEqual(self.index.predict("help", ("NP", "TO_INF")).status, "ATTESTED")
        self.assertEqual(self.index.predict("help", ("NP", "PREP:for", "NP")).status, "ATTESTED")
        self.assertEqual(self.index.predict("help", ("NP", "PREP:to")).status, "UNKNOWN")

    def test_unknown_is_not_rejection(self):
        self.assertEqual(self.index.predict("give", ("NP", "PREP:purple")).status, "UNKNOWN")
        self.assertEqual(self.index.predict("nonexistent", ()).status, "UNKNOWN")

    def test_round_trip(self):
        output = Path(self.temp.name) / "compiled.json"
        write_index(output, self.frames, self.stats)
        again = read_index(output)
        self.assertEqual(again.predict("give", ("NP", "NP")).status, "ATTESTED")


if __name__ == "__main__":
    unittest.main()

class TestLexicalAdapter(unittest.TestCase):
    def test_morphology_preserved_and_sense_filtered(self):
        from types import SimpleNamespace
        from research.verbnet_lr.adapter import predict_candidate
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "give.xml").write_text(XML)
            sense_index = path / "index.sense"
            sense_index.write_text("give%2:40:00:: 01234567 1 0\nlend%2:40:00:: 02345678 1 0\n")
            frames, _ = compile_directory(path, sense_index)
            index = PrefixIndex(frames)
            c = SimpleNamespace(category="V", lemma="give", surface="gave",
                                sense_ids=("wn-1234567-v-finite", "wn-2222222-v-ed"))
            before = dict(vars(c))
            answer = predict_candidate(index, c, ("NP", "NP"))
            self.assertEqual(answer.status, "ATTESTED")
            self.assertEqual(answer.confidence, "sense_verified")
            self.assertEqual(vars(c), before)
            nonverb = SimpleNamespace(category="N", lemma="give", sense_ids=())
            self.assertEqual(predict_candidate(index, nonverb).status, "UNKNOWN")
