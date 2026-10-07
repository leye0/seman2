from __future__ import annotations

from pathlib import Path
import unittest

from seman2_runtime.corpus_planning import run_corpus_planning


ROOT = Path(__file__).resolve().parent.parent


class CorpusPlanningTests(unittest.TestCase):
    def test_real_sample_reaches_live_analysis_and_honest_plan(self):
        required = [
            ROOT / "data/parquet/stackoverflow/schema_version=1/questions",
            ROOT / ".venv-dialogue/bin/python",
            ROOT / ".local/bin/ace",
        ]
        if not all(path.exists() for path in required):
            self.skipTest("corpus ou analyseurs locaux absents")
        plan, trace = run_corpus_planning(ROOT)
        self.assertEqual([row.kind for row in trace], [
            "sampling-request", "corpus-sample-set", "observation-batch",
            "analyzed-corpus-batch", "analysis-ledger", "semantic-fragment-batch",
            "semantic-feature-batch", "corpus-hypothesis-ledger", "proto-service-plan",
        ])
        readiness = plan.payload["readiness"]
        self.assertEqual(len(readiness), 3)
        self.assertTrue(all(row["erg_status"] == "parsed" for row in readiness))
        self.assertTrue(all(row["erg_candidates"] == 3 for row in readiness))
        self.assertTrue(all(row["mrs_fragments"] == 3 for row in readiness))
        self.assertEqual(sum(row["formal_temporal_candidates"] for row in readiness), 3)
        self.assertEqual(sum(row["temporally_underspecified_candidates"] for row in readiness), 6)
        self.assertTrue(all(row["dynamic_syntax_status"] == "failure" for row in readiness))
        self.assertTrue(all(not row["can_enter_existing_narrow_semantic_projection"] for row in readiness))
        self.assertEqual(plan.payload["status"], "GO-INGESTION-ERG-MRS-HYPOTHESES; NO-GO-DYNAMIC-SYNTAX-COVERAGE")
        fragments = next(row for row in trace if row.kind == "semantic-fragment-batch")
        self.assertEqual(len(fragments.payload["fragments"]), 9)
        self.assertEqual(len(fragments.payload["unresolved"]), 3)
        self.assertFalse(fragments.payload["candidate_selection_performed"])
        self.assertTrue(fragments.payload["native_values_preserved"])
        self.assertTrue(all(row["relations"] for row in fragments.payload["fragments"]))
        features = next(row for row in trace if row.kind == "semantic-feature-batch")
        self.assertEqual(len(features.payload["temporal_unresolved"]), 6)
        self.assertFalse(features.payload["absolute_coordinate_invented"])
        self.assertTrue(all(
            row["temporal_candidate"]["formalism"] == "Reichenbach E/R/S"
            for row in features.payload["fragments"]
        ))
        hypotheses = next(row for row in trace if row.kind == "corpus-hypothesis-ledger")
        self.assertEqual(hypotheses.payload["persistent_count"], 9)
        self.assertEqual(len(hypotheses.payload["families"]), 3)
        self.assertEqual(hypotheses.payload["theoretical_cross_observation_product"], 27)
        self.assertEqual(hypotheses.payload["materialized_joint_interpretations"], 0)
        self.assertFalse(hypotheses.payload["cross_observation_product_materialized"])
        self.assertEqual(hypotheses.payload["selection_events"], [])
        self.assertEqual(
            plan.payload["decision"]["next_implementation_boundary"],
            "question-answer observation sequence and interrogative dialogue-state candidates",
        )


if __name__ == "__main__":
    unittest.main()
