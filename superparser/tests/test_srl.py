import unittest
from seman_parser.srl import SRL,project,align

class SRLAdapterTests(unittest.TestCase):
    def test_source_alignment_and_all_frames(self):
        calls=[]
        def native(texts,tasks):
            calls.append((texts,tasks))
            return {"tok":[["Nora","gave","Felix","a","book","."]],
                    "srl":[[[["Nora","ARG0",0,1],["gave","PRED",1,2],
                             ["Felix","ARG2",2,3],["a book","ARG1",3,5]]]]}
        r=SRL(backend=native).inspect("Nora gave Felix a book.")
        self.assertEqual(calls,[ (["Nora gave Felix a book."],["tok","srl"]) ])
        self.assertEqual(r["frames"][0]["predicates"][0]["source_span"],[5,9])
        self.assertEqual([x["source_text"] for x in r["frames"][0]["arguments"]],["Nora","Felix","a book"])
        self.assertEqual(r["alignment"],"exact")

    def test_normalization_never_invents_span(self):
        r=project("‘Hi’",["'","Hi","'"],[[["Hi","PRED",1,2]]])
        self.assertEqual(r["alignment"],"unmapped_native_tokens")
        self.assertIsNone(r["frames"][0]["predicates"][0]["source_span"])
        self.assertEqual(r["native_srl"],[[["Hi","PRED",1,2]]])

    def test_repeated_tokens_and_whitespace(self):
        self.assertEqual(align("go  go",["go","go"]),[[0,2],[4,6]])
        self.assertIsNone(align("go x go",["go","go"]))

    def test_native_bad_offset_fails(self):
        with self.assertRaises(ValueError):
            project("go",["go"],[[["go","PRED",0,2]]])
