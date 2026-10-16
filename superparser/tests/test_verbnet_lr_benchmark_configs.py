"""Prevent silent configuration drift between positive and negative L->R controls.

The benchmark uses the same named parser variants for positive oracle
assertions and independent negative minimal pairs. These must instantiate
the same grammatical engine; only their test inputs may differ.
"""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.benchmark_verbnet_negatives import MODES, reader_options
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader


ROOT = Path(__file__).resolve().parents[1]
OPTIONS = (
    "checkpoint_budget", "stack_checkpoints", "construction_guard",
    "fast_multiword", "early_construction_guard", "token_only_lattice",
    "infer_unary_promotions", "reduce_checkpoints", "parent_follow_reduce",
    "reduce_follow_only", "reachable_checkpoints_only",
)


def positive_reader_options():
    """Extract the literal options of each positive benchmark constructor.

    Inspect source rather than copy the truth table: future new options in
    either benchmark must not silently change the grammatical comparison.
    """
    source = (ROOT / "scripts" / "benchmark_verbnet_reader.py").read_text()
    syntax = ast.parse(source)
    for node in ast.walk(syntax):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "machines"
            for target in node.targets
        ) and isinstance(node.value, ast.Dict):
            return {
                ast.literal_eval(key): {
                    kw.arg: ast.literal_eval(kw.value)
                    for kw in val.keywords
                    if kw.arg in OPTIONS
                }
                for key, val in zip(node.value.keys, node.value.values)
                if isinstance(key, ast.Constant) and key.value in dict(MODES)
            }
    raise AssertionError("Could not find the positive benchmark mode dictionary")


class BenchmarkConfigurationTests(unittest.TestCase):
    def test_negative_modes_have_same_positive_engine_options(self):
        positive = positive_reader_options()
        self.assertEqual(set(positive), set(dict(MODES)))
        for name, budget in MODES:
            actual = reader_options(name, budget)
            expected = positive[name]
            with self.subTest(mode=name):
                self.assertEqual(
                    {option: actual.get(option, False) for option in OPTIONS},
                    {option: expected.get(option, False) for option in OPTIONS},
                )

    def test_from_dir_passes_through_research_options(self):
        options = {
            "stack_checkpoints": True,
            "checkpoint_budget": 3,
            "construction_guard": True,
            "token_only_lattice": True,
            "infer_unary_promotions": True,
            "reduce_checkpoints": True,
            "reduce_follow_only": True,
            "reachable_checkpoints_only": True,
        }
        with (
            patch("seman_parser.reading_kernel_compiled_adapter.ParserResources.from_dir",
                  return_value=object()) as resource_loader,
            patch.object(SemanCompiledReader, "__init__", return_value=None) as init,
        ):
            SemanCompiledReader.from_dir("placeholder", **options)
            resource_loader.assert_called_once()
            for key, value in options.items():
                self.assertEqual(init.call_args.kwargs[key], value)


if __name__ == "__main__":
    unittest.main()
