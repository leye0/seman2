#!/usr/bin/env python3
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import sys
import unittest

import numpy


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/core-01/output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS = (
    "tests.test_developmental_core",
    "tests.test_cognitive_memory",
    "tests.test_concept_learning",
    "tests.test_formal_core_adapter",
    "tests.test_open_vocabulary",
    "tests.test_attention_controller",
    (
        "tests.test_cognitive_core.CognitiveCoreTests."
        "test_real_novel_sentence_reaches_isolated_formal_analyzers"
    ),
)


def write_json(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    stream = io.StringIO()
    suite = unittest.TestLoader().loadTestsFromNames(TESTS)
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    validations = {
        "expected_test_count": expected,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "all_oracles_executed": result.testsRun == expected,
        "all_oracles_passed": result.wasSuccessful(),
        "real_mrs_path_required": True,
        "real_mrs_path_skipped": any(
            "test_real_novel_sentence" in str(test) for test, _ in result.skipped
        ),
    }
    if validations["real_mrs_path_skipped"]:
        raise RuntimeError("CORE-01 refuse un GO sans le trajet MRS réel")
    verdict = (
        "GO-DEVELOPMENTAL-CORE-AND-REAL-MRS-ADAPTER"
        if all(
            (
                validations["all_oracles_executed"],
                validations["all_oracles_passed"],
                not validations["real_mrs_path_skipped"],
            )
        )
        else "NO-GO-DEVELOPMENTAL-CORE"
    )
    results = {
        "verdict": verdict,
        "validations": validations,
        "test_log": stream.getvalue().splitlines(),
    }
    write_json("results.json", results)
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "vector_dimensions_tested": [512, 2048],
            "real_input_records": 1,
            "maximum_workers": 4,
            "rst_model_loaded": False,
        },
    )
    write_json(
        "summary.json",
        {
            "verdict": verdict,
            "tests_run": result.testsRun,
            "all_oracles_passed": result.wasSuccessful(),
            "real_mrs_path_executed": not validations["real_mrs_path_skipped"],
        },
    )
    print(json.dumps(results, ensure_ascii=False))
    if verdict.startswith("NO-GO"):
        raise AssertionError(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
