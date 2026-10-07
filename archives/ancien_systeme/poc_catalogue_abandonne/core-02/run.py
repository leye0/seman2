#!/usr/bin/env python3
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/core-02/output"
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
    suite = unittest.TestLoader().loadTestsFromNames(
        ("tests.test_curriculum", "tests.test_cognitive_query")
    )
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    checks = {
        "expected_test_count": expected,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "all_oracles_executed": result.testsRun == expected,
        "all_oracles_passed": result.wasSuccessful(),
        "external_network_used": False,
        "llm_runtime_write_allowed": False,
        "corpus_answer_lookup_allowed": False,
    }
    verdict = (
        "GO-CURRICULUM-AND-AUTOBIOGRAPHICAL-ANSWER-PLAN"
        if checks["all_oracles_executed"] and checks["all_oracles_passed"]
        else "NO-GO-CURRICULUM-OR-ANSWER-PLAN"
    )
    write_json(
        "results.json",
        {
            "verdict": verdict,
            "validations": checks,
            "test_log": stream.getvalue().splitlines(),
        },
    )
    write_json(
        "versions-and-parameters.json",
        {
            "python": platform.python_version(),
            "test_modules": ["tests.test_curriculum", "tests.test_cognitive_query"],
            "network": "disabled-by-design",
        },
    )
    write_json(
        "summary.json",
        {
            "verdict": verdict,
            "tests_run": result.testsRun,
            "all_oracles_passed": result.wasSuccessful(),
        },
    )
    print(json.dumps({"verdict": verdict, "validations": checks}, ensure_ascii=False))
    if verdict.startswith("NO-GO"):
        raise AssertionError(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
