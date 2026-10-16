"""Regression tests for full VerbNet L-R prefix reporting (stdlib only)."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from research.verbnet_lr import PrefixIndex, compile_directory, read_index, write_index
from research.verbnet_lr.adapter import predict_candidate

XML = """<VNCLASS ID="branch-1">
<MEMBERS><MEMBER name="branch" wn="branch%2:35:00"/></MEMBERS>
<FRAMES>
<FRAME><SYNTAX><NP value="Agent"/><VERB/><PREP value="to"/><NP value="Theme"/></SYNTAX></FRAME>
<FRAME><SYNTAX><NP value="Agent"/><VERB/><PREP value=""/><NP value="Theme"/><NP value="Recipient"/></SYNTAX></FRAME>
<FRAME><SYNTAX><NP value="Agent"/><VERB/><MYSTERY/><NP/></SYNTAX></FRAME>
</FRAMES><SUBCLASSES/></VNCLASS>"""


class TestCorpusInterface(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "test.xml").write_text(XML, encoding="utf-8")
        (root / "index.sense").write_text("branch%2:35:00 08123456 1 0\n", encoding="utf-8")
        self.frames, self.stats = compile_directory(root, root / "index.sense")
        self.index = PrefixIndex(self.frames)

    def test_wildcard_kept_even_with_concrete_preposition(self):
        p = self.index.predict("branch", ("PREP:to", "NP"), synset_offset=8123456)
        self.assertEqual(p.status, "ATTESTED")
        self.assertIn("NP", p.next_events)
        self.assertEqual(len(p.matching_frames), 2)
        # Wildcard is available for other prepositions as weak attestation.
        self.assertEqual(self.index.predict("branch", ("PREP:around", "NP", "NP")).status, "ATTESTED")

    def test_unsupported_skipped(self):
        self.assertEqual(self.stats["frames_unsupported"], 1)
        self.assertEqual(len(self.frames), 2)

    def test_no_fabricated_sense_match(self):
        c = SimpleNamespace(category="V", lemma="branch", sense_ids=("wn-99999-v-base",))
        p = predict_candidate(self.index, c, ("PREP:to",))
        self.assertEqual(p.status, "UNKNOWN")
        self.assertEqual(p.confidence, "none")

    def test_roundtrip_and_stable_prefix(self):
        dest = Path(self.tmp.name) / "index.json"
        write_index(dest, self.frames, self.stats)
        again = read_index(dest)
        self.assertEqual(again.predict("branch", ("PREP:to", "NP")).next_events, ("NP",))
        zipped = Path(self.tmp.name) / "index.json.gz"
        write_index(zipped, self.frames, self.stats)
        self.assertEqual(read_index(zipped).predict("branch", ("PREP:to", "NP")).next_events, ("NP",))


if __name__ == "__main__":
    unittest.main()
