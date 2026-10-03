from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("evaluate_poc", ROOT / "scripts/evaluate_poc.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class EvaluationTests(unittest.TestCase):
    def test_json_pointer_and_exact_checks(self):
        document = {"a": [{"b": [1, 2, 3]}]}
        self.assertEqual(MODULE.pointer_get(document, "/a/0/b/1"), 2)
        check = MODULE.deterministic_check(document, {
            "id": "length", "pointer": "/a/0/b", "operator": "length_equals", "expected": 3,
        })
        self.assertTrue(check["passed"])

    def test_missing_pointer_is_a_failed_check_not_a_crash(self):
        check = MODULE.deterministic_check({}, {
            "id": "missing", "pointer": "/x", "operator": "equals", "expected": 1,
        })
        self.assertFalse(check["passed"])
        self.assertIn("error", check)

    def test_phase3_manifest_passes_deterministically(self):
        artifact = ROOT / "output/phase3/proto-service-plan.json"
        if not artifact.is_file():
            self.skipTest("artefact phase3 absent")
        report = MODULE.evaluate(
            ROOT / "evaluations/manifests/phase3-corpus-plan.json", False, 1
        )
        self.assertTrue(report["deterministic"]["passed"])
        self.assertEqual(len(report["deterministic"]["checks"]), 10)
        self.assertEqual(report["verdict"], "PASS-DETERMINISTIC; SEMANTIC-NOT-RUN")
        self.assertEqual(report["semantic"]["status"], "not-requested")

    def test_semantic_projection_is_compact_and_source_grounded(self):
        artifact = ROOT / "output/phase3/proto-service-plan.json"
        if not artifact.is_file():
            self.skipTest("artefact phase3 absent")
        import json
        evidence = MODULE.phase3_corpus_evidence(json.loads(artifact.read_text()))
        self.assertEqual(len(evidence["cases"]), 3)
        self.assertTrue(all(len(row["mrs_candidates"]) == 3 for row in evidence["cases"]))
        self.assertTrue(all(row["title"] for row in evidence["cases"]))
        self.assertFalse(evidence["global"]["absolute_coordinate_invented"])
        self.assertEqual(evidence["global"]["temporal_unresolved_count"], 6)


if __name__ == "__main__":
    unittest.main()
