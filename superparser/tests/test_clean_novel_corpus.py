"""Integrity, paratext and reproducibility checks for committed novel prose."""
from __future__ import annotations

import re
import unittest

from research.verbnet_lr.clean_novel_corpus import (
    CORPUS_DIR, clean_source, git_blob_sha, load_cleaned, read_manifest,
)
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS
from seman_parser.sentence_boundaries import split_prose_sentences


class CleanNovelCorpusTests(unittest.TestCase):
    def test_all_files_have_expected_hash_and_paragraphs(self):
        for record in read_manifest()["books"]:
            with self.subTest(title=record["title"]):
                file = CORPUS_DIR / record["path"].split("/")[-1]
                raw = file.read_bytes()
                self.assertEqual(git_blob_sha(raw), record["clean_git_blob_sha"])
                text = raw.decode("utf-8")
                self.assertEqual(text.count("\n\n") + 1, record["paragraphs"])
                self.assertTrue(text.endswith("\n"))
                self.assertNotIn("\r", text)
                self.assertNotIn("\ufeff", text)
                self.assertNotIn("\t", text)
                self.assertNotRegex(text, re.compile(
                    r"Project Gutenberg|(?m:^\s*(?:CONTENTS|PREFACE|CHAPTER \d+|Letter \d+|PART ONE)\b)",
                    re.I,
                ))
                self.assertGreater(len(text), 300_000)

    def test_cleaned_book_loader_keeps_provenance_separate(self):
        books = {b.ebook_id: b for b in TRAIN_BOOKS}
        for record in read_manifest()["books"]:
            with self.subTest(title=record["title"]):
                contents, metadata = load_cleaned(books[record["ebook_id"]])
                self.assertTrue(contents)
                self.assertTrue(metadata["local_cleaned"])
                self.assertEqual(metadata["clean_git_blob_sha"], record["clean_git_blob_sha"])
                self.assertEqual(metadata["source_git_blob_sha"], record["source_git_blob_sha"])
                self.assertEqual(metadata["id"], record["ebook_id"])

    def test_novel_openings_are_real_narrative(self):
        books = {b.ebook_id: b for b in TRAIN_BOOKS}
        expected = {
            766: "Whether I shall turn out to be the hero",
            1342: "It is a truth universally acknowledged",
            84: "You will rejoice to hear",
            120: "SQUIRE TRELAWNEY, Dr. Livesey",
        }
        for ebook_id, first in expected.items():
            self.assertTrue(load_cleaned(books[ebook_id])[0].startswith(first))

    def test_dialogue_quotes_survive_corpus_cleaning(self):
        # Source editions of Dickens and Austen use curly quotes extensively.
        for ebook_id, minimum in ((766, 10000), (1342, 1000)):
            with self.subTest(ebook_id=ebook_id):
                book = next(b for b in TRAIN_BOOKS if b.ebook_id == ebook_id)
                text, _ = load_cleaned(book)
                self.assertGreater(sum(text.count(c) for c in "“”‘’"), minimum)
                if ebook_id == 1342:
                    self.assertIn("“My dear Mr. Bennet,”", text)

    def test_lossless_segmentation_on_all_cleaned_paragraphs(self):
        books = {b.ebook_id: b for b in TRAIN_BOOKS}
        total_paragraphs = 0
        for record in read_manifest()["books"]:
            with self.subTest(book=record["title"]):
                text, _ = load_cleaned(books[record["ebook_id"]])
                for paragraph in text.rstrip("\n").split("\n\n"):
                    sentences = split_prose_sentences(paragraph)
                    self.assertTrue(sentences)
                    self.assertEqual(" ".join(sentences), paragraph)
                    self.assertTrue(all(not re.fullmatch(r"[A-Z]\.", s) for s in sentences))
                    total_paragraphs += 1
        self.assertGreater(total_paragraphs, 11000)


if __name__ == "__main__":
    unittest.main()
