from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "seman2"
FORBIDDEN_IDENTIFIERS = {
    "requesthandler",
    "questionhandler",
    "transferevent",
    "possessionstate",
    "sarcasmdetector",
    "greetingmanager",
    "passivesentence",
}
FORBIDDEN_DISPATCH_VALUES = {
    "request",
    "transfer",
    "dog",
    "question",
    "sarcastic",
    "passive",
    "possession",
}


class ConstitutionTests(unittest.TestCase):
    def test_no_domain_class_function_or_dispatch_branch_is_encoded(self) -> None:
        violations: list[str] = []
        for path in sorted(SOURCE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.lower() in FORBIDDEN_IDENTIFIERS:
                        violations.append(f"{path}:{node.lineno}:{node.name}")
                if isinstance(node, ast.If):
                    for nested in ast.walk(node.test):
                        if (
                            isinstance(nested, ast.Constant)
                            and isinstance(nested.value, str)
                            and nested.value.lower() in FORBIDDEN_DISPATCH_VALUES
                        ):
                            violations.append(
                                f"{path}:{nested.lineno}:dispatch={nested.value}"
                            )
        self.assertEqual(violations, [])

    def test_archived_runtime_is_not_imported(self) -> None:
        imports: list[str] = []
        for path in sorted(SOURCE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        self.assertFalse(any(name.startswith("seman2_runtime") for name in imports))

    def test_active_runtime_contains_no_remote_trips_endpoint(self) -> None:
        active = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SOURCE.rglob("*.py"))
        )
        self.assertNotIn("trips.ihmc.us", active)
        self.assertNotIn("HttpTripsTransport", active)


if __name__ == "__main__":
    unittest.main()
