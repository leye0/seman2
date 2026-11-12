"""Contrastive grammar ablation for the batch's new rule families.

Run from the repository root with WORDNET_DICT and PYTHONPATH configured.
Each profile changes only a temporary working-tree copy of grammar.jsonl.
Files are restored on completion; no Git history or benchmark cohort changes.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAMMAR = ROOT / "superparser" / "data" / "grammar.jsonl"

TARGETS = [
    "superparser.tests.test_parser_integration.ResidualLiteraryCoverageTests.test_selected_object_control_and_perfect_in_original_literary_tree",
    "superparser.tests.test_parser_integration.FrontedPossessiveRelativeAndOtherComparisonTests.test_pinned_371_selected_tree_has_exact_antecedent_and_scopes",
]
FAMILIES = {
    "copular_adv": {"vp_copula_predicative_scope_adjective"},
    "greeting": {"clause_time_of_day_valediction_vocative"},
    "passive": {"vp_passive_resultative_predicative_adjp"},
}


def main():
    import json
    original = GRAMMAR.read_text()
    rows = [json.loads(x) for x in original.splitlines() if x]
    baseline = [r for r in rows if r["id"] not in
                {name for group in FAMILIES.values() for name in group}]
    try:
        profiles = [
            ("all_new", rows), ("no_new", baseline),
            *((f"minus_{name}",
               [r for r in rows if r["id"] not in rules])
              for name, rules in FAMILIES.items()),
        ]
        for name, profile in profiles:
            GRAMMAR.write_text("\n".join(json.dumps(x) for x in profile)+"\n")
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "-q", *TARGETS],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "superparser")},
                capture_output=True, text=True, timeout=120,
            )
            print("GRAMMAR_ABLATION", name,
                  "PASS" if proc.returncode == 0 else "FAIL", flush=True)
            if proc.returncode:
                print((proc.stdout + "\n" + proc.stderr)[-1800:], flush=True)
    finally:
        GRAMMAR.write_text(original)


if __name__ == "__main__":
    main()
