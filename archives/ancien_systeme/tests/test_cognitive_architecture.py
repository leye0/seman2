from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent


class CognitiveArchitectureTests(unittest.TestCase):
    def test_dictionary_is_only_a_corpus_input(self):
        consumers = [
            service["id"]
            for service in self.data["service_families"]
            if "dictionary-jsonl" in service["consumes"]
        ]
        self.assertEqual(consumers, ["corpus-ingestion"])
        self.assertEqual(self.data["ingestion_flow"][0], "corpus-ingestion")

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(
            (ROOT / "plans/archives/cognitive_system_architecture.json").read_text()
        )
        cls.services = {row["id"]: row for row in cls.data["service_families"]}

    def test_archived_blueprint_covers_only_legacy_pocs(self):
        required = set(re.findall(
            r"^### ([A-Z]+-\d+) —",
            (ROOT / "plans/required_poc.md").read_text(),
            re.MULTILINE,
        ))
        covered = {
            poc_id
            for service in self.services.values()
            for poc_id in service["poc_coverage"]
        }
        self.assertTrue(covered <= required)
        current = required - covered
        self.assertEqual(current, {poc_id for poc_id in required if poc_id.startswith("CORE-")})
        self.assertTrue(current)

    def test_parquet_and_evaluation_cannot_bypass_low_levels(self):
        forbidden = set(self.data["forbidden_paths"])
        self.assertIn("parquet-to-high-level-system", forbidden)
        self.assertIn("corpus-answer-id-to-soar-retrieval", forbidden)
        self.assertIn("evaluation-label-to-cognitive-memory", forbidden)
        retrieval = self.services["structural-retrieval"]
        self.assertEqual(
            retrieval["produces"],
            ["ranked-internal-memory-reference", "retrieval-explanation"],
        )
        self.assertFalse(any("parquet" in value for value in retrieval["consumes"]))

    def test_ingestion_and_chatbot_share_bottom_up_systems(self):
        for identifier in (
            "source-observation-provenance",
            "formal-analysis-dispatch",
            "representation-adapters",
            "semantic-reference-state",
            "factorized-hypothesis-manager",
            "formal-dialogue-system",
            "situation-episode-system",
            "soar-control",
        ):
            self.assertEqual(
                set(self.services[identifier]["modes"]),
                {"ingestion", "chatbot"},
                identifier,
            )

    def test_live_memories_are_ram_first_and_checkpointable(self):
        domains = {row["id"]: row for row in self.data["memory_domains"]}
        self.assertEqual(self.data["runtime_model"]["primary_live_state"], "ram")
        for identifier in (
            "artifact-arena",
            "hypothesis-memory",
            "situation-memory",
            "dialogue-discourse-memory",
            "episodic-memory",
            "learned-graph-memory",
            "control-state-memory",
            "scheduler-memory",
        ):
            self.assertIn("ram", domains[identifier]["live"])
            self.assertTrue(domains[identifier]["checkpoint"])

    def test_feedback_is_never_visible_in_same_wave(self):
        self.assertTrue(self.data["feedback_paths"])
        self.assertTrue(all(
            row["visible_after_waves"] >= 1 for row in self.data["feedback_paths"]
        ))

    def test_declared_dependencies_never_point_downward(self):
        for service in self.services.values():
            for dependency in service["dependencies"]:
                self.assertLessEqual(
                    self.services[dependency]["layer"],
                    service["layer"],
                    f"{dependency} -> {service['id']}",
                )


if __name__ == "__main__":
    unittest.main()
