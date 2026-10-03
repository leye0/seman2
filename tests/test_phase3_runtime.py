from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from seman2_runtime.contracts import ContractError, Envelope, ServiceSpec
from seman2_runtime.pipeline import IntegrationPipeline, build_pipeline, write_result
from seman2_runtime.services import ObservationService, RetrievalService, TemporalContextService


ROOT = Path(__file__).resolve().parent.parent


class ContractTests(unittest.TestCase):
    def request(self, text="John likes Mary.") -> Envelope:
        return Envelope("request", "req:1", "corr:1", "test", (), {"text": text, "speaker": "u"})

    def test_empty_observation_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "non vide"):
            ObservationService().handle(self.request("  "))

    def test_wrong_input_kind_is_rejected(self):
        wrong = Envelope("observation", "obs:1", "corr:1", "test", (), {"text": "x"})
        with self.assertRaisesRegex(ContractError, "attend request"):
            ObservationService().handle(wrong)

    def test_duplicate_parents_are_rejected(self):
        with self.assertRaisesRegex(ContractError, "doublon"):
            Envelope("x", "x:1", "c", "test", ("a", "a"), {})

    def test_unsatisfied_dependency_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "dépendances non satisfaites"):
            IntegrationPipeline([RetrievalService()])

    def test_manifest_has_explicit_boundaries(self):
        pipeline = build_pipeline(ROOT)
        manifest = pipeline.manifest()
        self.assertEqual(manifest["entry_kind"], "request")
        self.assertEqual(manifest["exit_kind"], "realization")
        self.assertEqual(len(manifest["services"]), 10)
        previous = "request"
        for service in manifest["services"]:
            self.assertEqual(service["input_kind"], previous)
            previous = service["output_kind"]

    def test_temporal_service_builds_formal_past_constraints(self):
        source = Envelope(
            "semantic-candidates", "sem:1", "corr:1", "test", ("analysis:1",),
            {"candidates": [{"content_id": "prop:work:paul", "tense": "past"}],
             "source_analyses_preserved": True},
        )
        result = TemporalContextService().handle(source)
        constraints = result.payload["constraints"]
        self.assertEqual([row["operator"] for row in constraints], ["=", "<"])
        self.assertTrue(all(row["formalism"] == "Reichenbach E/R/S" for row in constraints))
        self.assertFalse(result.payload["absolute_coordinate_invented"])

    def test_temporal_service_rejects_unsupported_tense(self):
        source = Envelope(
            "semantic-candidates", "sem:1", "corr:1", "test", ("analysis:1",),
            {"candidates": [{"content_id": "prop:x", "tense": "timeless-ish"}],
             "source_analyses_preserved": True},
        )
        with self.assertRaisesRegex(ContractError, "non pris en charge"):
            TemporalContextService().handle(source)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = [
            ROOT / "poc/dlg-03/output/results.json",
            ROOT / ".local/opt/simplenlg/SimpleNLG-4.5.0.jar",
        ]
        absent = [str(path) for path in required if not path.is_file()]
        if absent:
            raise unittest.SkipTest("dépendances locales absentes: " + ", ".join(absent))

    def test_real_pipeline_preserves_contracts_and_content(self):
        pipeline = build_pipeline(ROOT)
        result = pipeline.run("John likes Mary.", correlation_id="test:e2e")
        serialized = result.as_dict()
        self.assertEqual(serialized["status"], "GO")
        self.assertTrue(all(serialized["checks"].values()))
        self.assertEqual(result.final.payload["text"], "John likes Mary.")
        self.assertEqual(len(result.trace), 11)
        self.assertEqual(
            {row["producer"] for row in result.trace[2].payload["alternatives"]},
            {"ACE_ERG", "dynamicsyntax-python"},
        )
        projection = next(row for row in result.trace if row.kind == "semantic-candidates")
        self.assertEqual(projection.payload["cross_representation"]["status"], "partial-correspondence")
        self.assertFalse(projection.payload["cross_representation"]["asserted_identity"])
        self.assertEqual(projection.losses, ("Dynamic Syntax object binding unresolved",))
        temporal = next(row for row in result.trace if row.kind == "temporally-qualified-candidates")
        self.assertEqual([row["operator"] for row in temporal.payload["constraints"]], ["=", "="])
        self.assertFalse(temporal.payload["absolute_coordinate_invented"])
        beam = next(row for row in result.trace if row.kind == "active-beam")
        self.assertEqual(len(beam.payload["persistent"]), 3)
        self.assertEqual(len(beam.payload["active"]), 2)
        self.assertEqual(beam.losses, ("working-set-pruned; persistent hypotheses retained",))

    def test_unknown_analysis_is_no_go(self):
        pipeline = build_pipeline(ROOT)
        with self.assertRaisesRegex(ContractError, "exactement un bundle"):
            pipeline.run("This fixture does not exist.", correlation_id="test:no-go")

    def test_written_trace_roundtrips_and_is_causally_chained(self):
        pipeline = build_pipeline(ROOT)
        result = pipeline.run("John likes Mary.", correlation_id="test:trace")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            write_result(result, target, pipeline.manifest())
            rows = [json.loads(line) for line in (target / "trace.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 11)
            self.assertTrue(all(len(row["sha256"]) == 64 for row in rows))
            self.assertTrue(all(
                previous["message_id"] in current["parent_ids"]
                for previous, current in zip(rows, rows[1:])
            ))


if __name__ == "__main__":
    unittest.main()
