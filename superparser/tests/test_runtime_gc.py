"""Low-level GC policy regression tests; no timing or benchmarks."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from seman_parser import runtime_gc


class WordNetGcPolicyTests(unittest.TestCase):
    def setUp(self):
        self._original_frozen = runtime_gc._frozen
        runtime_gc._frozen = False
        self.addCleanup(setattr, runtime_gc, "_frozen", self._original_frozen)

    @staticmethod
    def lexicon(*, loaded=True, positions=("n", "v", "a", "r")):
        return SimpleNamespace(
            _wordnet=SimpleNamespace(_loaded_index=loaded, _loaded_data=set(positions))
        )

    def test_freeze_only_after_complete_wordnet_load(self):
        with patch.dict("os.environ", {"SEMAN2_DISABLE_GC_FREEZE": ""}), \
             patch.object(runtime_gc.gc, "isenabled", return_value=True), \
             patch.object(runtime_gc.gc, "collect", return_value=0) as collect, \
             patch.object(runtime_gc.gc, "freeze") as freeze:
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(SimpleNamespace(_wordnet=None)))
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(self.lexicon(loaded=False)))
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(self.lexicon(positions=("n",))))
            self.assertFalse(runtime_gc._frozen)
            collect.assert_not_called()
            freeze.assert_not_called()
            self.assertTrue(runtime_gc.freeze_loaded_wordnet_once(self.lexicon()))
            collect.assert_called_once_with(2)
            freeze.assert_called_once_with()
            self.assertTrue(runtime_gc._frozen)
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(self.lexicon()))
            freeze.assert_called_once_with()

    def test_public_parser_freezes_after_real_wordnet_load(self):
        # Regression: the policy must run on the actual public parse path,
        # not only when invoked manually with a fake lexical backend.
        import os
        from pathlib import Path

        from seman_parser.engine import Parser, ParserResources

        wordnet_dir = os.environ.get("WORDNET_DICT")
        if not wordnet_dir:
            self.skipTest("Requires WORDNET_DICT to validate the real WordNet load")
        resources = ParserResources.from_dir(
            Path(__file__).resolve().parents[1] / "data", wordnet_dict=wordnet_dir)
        parser = Parser(resources, cache_size=0)
        with patch.dict("os.environ", {"SEMAN2_DISABLE_GC_FREEZE": ""}), \
             patch.object(runtime_gc.gc, "isenabled", return_value=True), \
             patch.object(runtime_gc.gc, "collect", return_value=0), \
             patch.object(runtime_gc.gc, "freeze") as freeze:
            report = parser.parse("John opened the box.")
            self.assertTrue(report.result.completed)
            self.assertTrue(runtime_gc._frozen)
            freeze.assert_called_once_with()

    def test_respects_disabled_automatic_gc(self):
        with patch.dict("os.environ", {"SEMAN2_DISABLE_GC_FREEZE": ""}), \
             patch.object(runtime_gc.gc, "isenabled", return_value=False), \
             patch.object(runtime_gc.gc, "freeze") as freeze:
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(self.lexicon()))
            freeze.assert_not_called()

    def test_explicit_runtime_opt_out(self):
        with patch.dict("os.environ", {"SEMAN2_DISABLE_GC_FREEZE": "1"}), \
             patch.object(runtime_gc.gc, "isenabled", return_value=True), \
             patch.object(runtime_gc.gc, "freeze") as freeze:
            self.assertFalse(runtime_gc.freeze_loaded_wordnet_once(self.lexicon()))
            freeze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
