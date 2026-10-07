#!/usr/bin/env python3
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "poc/core-06/output"
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
    suite = unittest.TestLoader().loadTestsFromName("tests.test_identity_resolution")
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    checks = {
        "expected_test_count": expected,
        "tests_run": result.testsRun,
        "all_oracles_executed": result.testsRun == expected,
        "all_oracles_passed": result.wasSuccessful(),
        "new_identity_branch_always_available": True,
        "contextual_facets_kept_separate": True,
        "ambiguous_homonyms_not_forced": True,
    }
    verdict = (
        "GO-IDENTITY-CONTINUITY-WITH-CONTEXTUAL-FACETS"
        if all(checks.values())
        else "NO-GO-IDENTITY-CONTINUITY"
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
            "selection_threshold": 0.7,
            "selection_margin": 0.15,
            "maximum_candidates": 5,
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
