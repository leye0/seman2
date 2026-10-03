from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

try:
    import Python_sml_ClientInterface  # noqa: F401
except ImportError:
    Python_sml_ClientInterface = None

from seman2_runtime.soar_session import checkpoint_and_verify
from seman2_runtime.contracts import ContractError
from seman2_runtime.soar_session import SoarRuntimeSession


class SoarSessionTests(unittest.TestCase):
    @unittest.skipIf(Python_sml_ClientInterface is None, "bindings Soar absents")
    def test_active_context_reconstruction_preserves_decision(self):
        beams = [{
            "observation_id": "observation:test:one",
            "role": "question-title",
            "hypothesis_ids": ["hypothesis:test:one", "hypothesis:test:two"],
        }]
        with tempfile.TemporaryDirectory() as directory:
            decisions, checkpoint = checkpoint_and_verify(beams, Path(directory))
            self.assertTrue(checkpoint["decision_equivalence"])
            self.assertEqual(decisions[0]["selected_hypothesis_id"], "hypothesis:test:one")
            self.assertEqual(checkpoint["working_memory_restore_mode"], "reconstruct-from-active-context")
            self.assertFalse(checkpoint["native_whole-working-memory_restore_claimed"])
            self.assertIn("agent.soar", checkpoint["files"])
            self.assertIn("episodic-memory.sqlite", checkpoint["files"])
            self.assertIn("semantic-memory.sqlite", checkpoint["files"])

    @unittest.skipIf(Python_sml_ClientInterface is None, "bindings Soar absents")
    def test_answer_context_selects_assessment_action(self):
        beams = [{
            "observation_id": "observation:test:answer",
            "role": "answer",
            "hypothesis_ids": ["hypothesis:test:answer"],
        }]
        with tempfile.TemporaryDirectory() as directory:
            decisions, checkpoint = checkpoint_and_verify(beams, Path(directory))
            self.assertEqual(decisions[0]["next_action"], "assess-answer")
            self.assertTrue(checkpoint["decision_equivalence"])

    @unittest.skipIf(Python_sml_ClientInterface is None, "bindings Soar absents")
    def test_transformation_uses_real_operator_preference(self):
        candidates = [
            {
                "transformation_id": "TRANSFORM:ATTACH",
                "kind": "attach-answer-candidate",
                "eligible": True,
                "evidence": {"direct_source_link": True, "parsed_content": True},
            },
            {
                "transformation_id": "TRANSFORM:KEEP",
                "kind": "keep-qud-open",
                "eligible": True,
                "evidence": {"direct_source_link": True, "parsed_content": True},
            },
            {
                "transformation_id": "TRANSFORM:REJECT",
                "kind": "reject-answer",
                "eligible": True,
                "evidence": {"direct_source_link": True, "parsed_content": True},
            },
        ]
        context = [{
            "observation_id": "observation:test:operator",
            "role": "state-transformation",
            "transformations": candidates,
        }]
        with tempfile.TemporaryDirectory() as directory:
            decisions, checkpoint = checkpoint_and_verify(context, Path(directory))
        self.assertEqual(decisions[0]["selected_transformation_id"], "TRANSFORM:ATTACH")
        self.assertEqual(decisions[0]["operator_semantics"], "Soar acceptable and better preferences")
        self.assertTrue(checkpoint["decision_equivalence"])

    @unittest.skipIf(Python_sml_ClientInterface is None, "bindings Soar absents")
    def test_transformation_without_attributed_support_reaches_impasse(self):
        candidates = [
            {
                "transformation_id": "TRANSFORM:ATTACH",
                "kind": "attach-answer-candidate",
                "eligible": True,
                "evidence": {"direct_source_link": False, "parsed_content": True},
            },
            {
                "transformation_id": "TRANSFORM:KEEP",
                "kind": "keep-qud-open",
                "eligible": True,
                "evidence": {"direct_source_link": False, "parsed_content": True},
            },
        ]
        with SoarRuntimeSession() as session:
            session.inject([{
                "observation_id": "observation:test:unsupported",
                "role": "state-transformation",
                "transformations": candidates,
            }])
            with self.assertRaisesRegex(ContractError, "décision de transformation absente"):
                session.decide()


if __name__ == "__main__":
    unittest.main()
