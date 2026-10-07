from __future__ import annotations

from pathlib import Path
import unittest

from seman2_runtime.contracts import ContractError
from seman2_runtime.corpus import CorpusSamplingService, SamplingPolicy, sampling_request, text_projection
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    build_foundation_runtime,
    ingest_records,
    records_from_sample_set,
)


ROOT = Path(__file__).resolve().parent.parent


class CorpusSamplingTests(unittest.TestCase):
    def test_html_projection_preserves_code_text_without_tags(self):
        self.assertEqual(text_projection("<p>Before</p><code>x &lt; 2</code>"), "Before x < 2")

    def test_unsafe_parallel_policy_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "threads=1"):
            SamplingPolicy(threads=2)

    def test_real_parquet_sample_is_bounded_attributed_and_diverse(self):
        parquet = ROOT / "data/parquet/stackoverflow/schema_version=1/questions"
        if not parquet.is_dir():
            self.skipTest("Parquet canoniques absents")
        result = CorpusSamplingService(ROOT).handle(sampling_request("test:corpus"))
        samples = result.payload["samples"]
        policy = result.payload["sampling_policy"]
        self.assertEqual(len(samples), 3)
        self.assertEqual(len({row["question_id"] for row in samples}), 3)
        self.assertEqual(
            {row["criterion"] for row in samples},
            {"code-and-competing-answers", "temporal-discourse", "negation-or-uncertainty"},
        )
        self.assertTrue(all(row["answers"] for row in samples))
        self.assertTrue(all(row["raw_body_sha256"] for row in samples))
        self.assertTrue(all(row["canonical_file"].endswith(".parquet") for row in samples))
        self.assertEqual(policy["threads"], 1)
        self.assertEqual(policy["memory_limit"], "256MB")
        self.assertEqual(policy["shards_scanned"], 10)
        self.assertFalse(policy["full_dataset_materialized"])
        self.assertLessEqual(policy["question_rows_returned"], 3)
        self.assertLessEqual(policy["answer_rows_returned"], 9)
        self.assertLess(policy["process_max_rss_kib"], 1024 * 1024)

        ingestion_policy = IngestionPolicy(max_records=16, max_text_chars=5_000)
        records = records_from_sample_set(result, policy=ingestion_policy)
        runtime = build_foundation_runtime(ingestion_policy)
        report = ingest_records(
            runtime,
            records,
            policy=ingestion_policy,
            session_id="test:real-parquet-ingestion",
        )
        self.assertEqual(report["records_ingested"], 3 + policy["answer_rows_returned"])
        self.assertEqual(report["observations_created"], len(records))
        self.assertFalse(report["labels_or_votes_in_cognitive_payload"])
        self.assertEqual(runtime.scheduler.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
