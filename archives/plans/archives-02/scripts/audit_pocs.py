#!/usr/bin/env python3
"""Audit only the active SYS-* vertical integration POCs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "plans" / "required_poc.md"
POC_ROOT = ROOT / "poc"
STATE = ROOT / ".local" / "state" / "poc-audit"
HEADING = re.compile(r"^###\s+(SYS-\d+)\s+—\s+(.+)$", re.MULTILINE)


def planned() -> list[tuple[str, str]]:
    rows = HEADING.findall(PLAN.read_text(encoding="utf-8"))
    if len(rows) != len({identifier for identifier, _ in rows}):
        raise SystemExit("duplicate SYS POC identifier")
    return rows


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def static_errors(identifier: str) -> list[str]:
    directory = POC_ROOT / identifier.lower()
    errors: list[str] = []
    for name in ("README.md", "run.py", "run.sh"):
        path = directory / name
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"missing {path.relative_to(ROOT)}")
    if errors:
        return errors
    runner = (directory / "run.py").read_text(encoding="utf-8")
    readme = (directory / "README.md").read_text(encoding="utf-8")
    if "tests." in runner or "unittest" in runner:
        errors.append("runner invokes unit tests instead of production components")
    for phrase in ("Entrée réelle", "Stock consommé", "Stock produit", "Lignée"):
        if phrase not in readme:
            errors.append(f"README missing contract section: {phrase}")
    if not re.search(r"data/|source réelle|source reelle", readme, re.IGNORECASE):
        errors.append("README does not name a real source")
    return errors


def output_errors(identifier: str) -> list[str]:
    output = POC_ROOT / identifier.lower() / "output"
    errors: list[str] = []
    required = ("results.json", "summary.json", "lineage.json")
    payloads: dict[str, object] = {}
    for name in required:
        path = output / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        try:
            payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid {path.relative_to(ROOT)}: {exc}")
    results = payloads.get("results.json")
    if isinstance(results, dict) and results.get("verdict") != "GO":
        errors.append("results verdict is not GO")
    if isinstance(results, dict):
        checks = results.get("checks")
        if not isinstance(checks, dict) or not checks:
            errors.append("results has no executable checks")
        elif any(value is not True for value in checks.values()):
            errors.append("one or more executable checks did not pass")
    lineage = payloads.get("lineage.json")
    if isinstance(lineage, dict):
        artifacts = lineage.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append("lineage has no artifacts")
        else:
            ids = {row.get("artifact_id") for row in artifacts if isinstance(row, dict)}
            for row in artifacts:
                if not isinstance(row, dict):
                    errors.append("lineage artifact is not an object")
                    continue
                for field in (
                    "artifact_id",
                    "artifact_type",
                    "producer_id",
                    "producer_revision",
                    "content_digest",
                    "parent_artifact_refs",
                    "context_refs",
                    "resource_cost",
                ):
                    if field not in row:
                        errors.append(f"lineage artifact missing {field}")
                for parent in row.get("parent_artifact_refs", []):
                    if parent not in ids:
                        errors.append(f"lineage references missing parent {parent}")
                for anchor in row.get("source_anchors", []):
                    if Path(anchor.get("source_path", "/")).is_absolute():
                        errors.append("lineage contains an absolute source path")
        if not lineage.get("real_source_refs"):
            errors.append("lineage has no real_source_refs")
        effects = lineage.get("causal_effects")
        if not effects:
            errors.append("lineage has no causal_effects")
        elif isinstance(effects, list):
            required_effect_fields = {
                "consumer_artifact_ref",
                "input_factor_ref",
                "producer_artifact_ref",
                "operation",
                "effect_on_output",
                "activation_or_weight_change",
                "context_ref",
                "reason_if_ignored",
            }
            for effect in effects:
                if not isinstance(effect, dict):
                    errors.append("causal effect is not an object")
                    continue
                missing = sorted(required_effect_fields - set(effect))
                if missing:
                    errors.append(f"causal effect missing fields {missing}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="validate the active plan without requiring implementation")
    parser.add_argument("--only", action="append", default=[], help="SYS identifier to audit")
    parser.add_argument("--timeout", type=int, default=180, help="runner timeout in seconds")
    args = parser.parse_args()

    rows = planned()
    selected = {value.upper() for value in args.only}
    known = {identifier for identifier, _ in rows}
    if selected - known:
        parser.error(f"unknown POC: {', '.join(sorted(selected - known))}")
    if selected:
        # Une demande ciblée inclut toujours tous ses prérequis. Cela empêche
        # d'auditer artificiellement SYS-03 tout en contournant SYS-01.
        highest = max(
            index for index, row in enumerate(rows) if row[0] in selected
        )
        rows = rows[: highest + 1]

    active_directories = {
        path.name
        for path in POC_ROOT.iterdir()
        if path.is_dir() and re.fullmatch(r"sys-\d+", path.name)
    }
    undeclared = active_directories - {identifier.lower() for identifier, _ in planned()}
    report = {"planned": len(planned()), "implemented": 0, "go": 0, "blocked": 0, "not_implemented": 0, "failed": 0, "pocs": []}
    if undeclared:
        report["failed"] += len(undeclared)
        report["undeclared_directories"] = sorted(undeclared)

    first_blocker: str | None = None
    for identifier, title in rows:
        directory = POC_ROOT / identifier.lower()
        item = {"id": identifier, "title": title}
        if first_blocker is not None:
            item["status"] = "BLOCKED_BY_PREREQUISITE"
            item["blocked_by"] = first_blocker
            report["blocked"] += 1
            report["pocs"].append(item)
            continue
        if not directory.is_dir():
            item["status"] = "NOT_IMPLEMENTED"
            report["not_implemented"] += 1
            report["pocs"].append(item)
            first_blocker = identifier
            continue
        report["implemented"] += 1
        errors = static_errors(identifier)
        if not errors and not args.plan:
            shutil.rmtree(directory / "output", ignore_errors=True)
            completed = subprocess.run(
                [str(directory / "run.sh")],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=args.timeout,
                check=False,
            )
            STATE.mkdir(parents=True, exist_ok=True)
            log = STATE / f"{identifier.lower()}.log"
            log.write_text(completed.stdout, encoding="utf-8")
            item["runner_sha256"] = file_digest(directory / "run.py")
            item["log"] = str(log.relative_to(ROOT))
            if completed.returncode:
                errors.append(f"runner exited {completed.returncode}")
            errors.extend(output_errors(identifier))
        if errors:
            declared_verdict = None
            result_path = directory / "output" / "results.json"
            if result_path.is_file():
                try:
                    declared_verdict = json.loads(
                        result_path.read_text(encoding="utf-8")
                    ).get("verdict")
                except (json.JSONDecodeError, OSError, AttributeError):
                    pass
            status = "INCOMPLETE" if declared_verdict == "INCOMPLETE" else "FAIL"
            item.update(status=status, errors=errors)
            report["failed"] += 1
            first_blocker = identifier
        else:
            item["status"] = "STRUCTURALLY_READY" if args.plan else "GO"
            if not args.plan:
                report["go"] += 1
        report["pocs"].append(item)

    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["failed"]:
        return 1
    if not args.plan and report["not_implemented"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
