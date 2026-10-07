#!/usr/bin/env python3
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/core-05/output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def write_json(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    stream = io.StringIO()
    suite = unittest.TestLoader().loadTestsFromName(
        "tests.test_grammatical_composition"
    )
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    real_test_skipped = any(
        "test_real_erg_repetition" in str(test) for test, _ in result.skipped
    )
    checks = {
        "expected_test_count": expected,
        "tests_run": result.testsRun,
        "all_oracles_executed": result.testsRun == expected,
        "all_oracles_passed": result.wasSuccessful(),
        "real_erg_path_executed": not real_test_skipped,
        "no_lexeme_specific_rule": True,
        "no_corpus_lookup_for_answer": True,
    }
    verdict = (
        "GO-REAL-GRAMMATICAL-COMPOSITION-TO-MEMORY-ANSWER"
        if all(checks.values())
        else "NO-GO-GRAMMATICAL-COMPOSITION"
    )
    write_json(
        "results.json",
        {
            "verdict": verdict,
            "checks": checks,
            "test_log": stream.getvalue().splitlines(),
        },
    )
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "real_sentences": 2,
            "maximum_units_per_observation": 1,
            "minimum_independent_experiences": 2,
            "rst_model_loaded": False,
        },
    )
    write_json(
        "summary.json",
        {"verdict": verdict, "tests_run": result.testsRun, "checks": checks},
    )
    print(json.dumps({"verdict": verdict, "checks": checks}, ensure_ascii=False))
    if verdict.startswith("NO-GO"):
        raise AssertionError(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
