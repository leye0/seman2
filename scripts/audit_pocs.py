#!/usr/bin/env python3
"""Execute and audit every POC declared in plans/required_poc.md."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ROOT / "plans" / "required_poc.md"
POC_ROOT = ROOT / "poc"
STATE_ROOT = ROOT / ".local" / "state" / "poc-audit"
POC_HEADING = re.compile(r"^###\s+([A-Z]+-\d+)\s+—\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Result:
    poc_id: str
    title: str
    status: str
    seconds: float
    errors: list[str]
    warnings: list[str]
    log: str | None


def declared_pocs() -> list[tuple[str, str]]:
    text = REQUIRED.read_text(encoding="utf-8")
    found = POC_HEADING.findall(text)
    duplicates = sorted({poc_id for poc_id, _ in found if [x[0] for x in found].count(poc_id) > 1})
    if duplicates:
        raise SystemExit(f"Identifiants dupliques dans {REQUIRED}: {', '.join(duplicates)}")
    return found


def dependency_order(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Order the full suite so generated cross-POC inputs exist on a clean clone.

    POC identifiers mentioned by a runner are treated conservatively as
    dependencies.  This slightly over-orders provenance-only references, but it
    prevents an ignored output directory from accidentally acting as a cache.
    """
    by_id = {poc_id: title for poc_id, title in items}
    slugs = {poc_id.lower(): poc_id for poc_id in by_id}
    dependencies: dict[str, set[str]] = {}
    for poc_id in by_id:
        source = (POC_ROOT / poc_id.lower() / "run.py").read_text(encoding="utf-8")
        mentioned = set(re.findall(r"[a-z]+-\d+", source)) & set(slugs)
        dependencies[poc_id] = {slugs[slug] for slug in mentioned if slugs[slug] != poc_id}

    remaining = set(by_id)
    ordered: list[str] = []
    while remaining:
        ready = sorted(poc_id for poc_id in remaining if not (dependencies[poc_id] & remaining))
        if not ready:
            cycle = {poc_id: sorted(dependencies[poc_id] & remaining) for poc_id in sorted(remaining)}
            raise SystemExit(f"Cycle de dependances entre POC: {cycle}")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return [(poc_id, by_id[poc_id]) for poc_id in ordered]


def json_files(output: Path) -> tuple[list[Path], list[str]]:
    files = sorted(output.rglob("*.json")) if output.is_dir() else []
    errors: list[str] = []
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - only exercised on broken artifacts
            errors.append(f"JSON invalide: {path.relative_to(ROOT)}: {exc}")
    return files, errors


def audit_one(poc_id: str, title: str, execute: bool, timeout: int) -> Result:
    slug = poc_id.lower()
    directory = POC_ROOT / slug
    errors: list[str] = []
    warnings: list[str] = []
    log_path: Path | None = None
    elapsed = 0.0

    for name in ("README.md", "verdict.md", "run.py", "run.sh"):
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"fichier absent ou vide: poc/{slug}/{name}")

    if errors:
        return Result(poc_id, title, "FAIL", elapsed, errors, warnings, None)

    readme = (directory / "README.md").read_text(encoding="utf-8")
    verdict = (directory / "verdict.md").read_text(encoding="utf-8")
    source = (directory / "run.py").read_text(encoding="utf-8")
    if poc_id not in readme.splitlines()[0]:
        errors.append("README: identifiant absent du titre")
    if poc_id not in verdict.splitlines()[0]:
        errors.append("verdict: identifiant absent du titre")
    if not re.search(r"(?<![A-Z])(GO(?:_|\b)|PARTIEL\b|ADAPTATEUR\b|OUTIL\b)", verdict, re.IGNORECASE):
        warnings.append("verdict non qualifie")
    if not re.search(r"assert|raise\s+(?:AssertionError|RuntimeError|SystemExit)|validations?|checks?|oracle", source, re.IGNORECASE):
        errors.append("aucun oracle executable detectable")
    oracle_markers = re.findall(
        r"assert|raise\s+(?:AssertionError|RuntimeError|SystemExit)|validations?|checks?|oracle",
        source,
        re.IGNORECASE,
    )
    if len(oracle_markers) < 2 and not re.search(
        r"negati|advers|invalid|contradi|conflit|ambigu|echec|failure|fail|reject|absent|unknown|unresolved|partial|empty|silence",
        readme + verdict + source,
        re.IGNORECASE,
    ):
        warnings.append("cas negatif/adversarial non identifiable")

    if execute and not errors:
        STATE_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = STATE_ROOT / f"{slug}.log"
        start = time.monotonic()
        process = subprocess.Popen(
                [str(directory / "run.sh")],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        try:
            output, _ = process.communicate(timeout=timeout)
            elapsed = time.monotonic() - start
            log_path.write_text(output, encoding="utf-8")
            if process.returncode:
                errors.append(f"execution terminee avec le code {process.returncode}")
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                trailing, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                trailing, _ = process.communicate()
            elapsed = time.monotonic() - start
            parts = []
            for chunk in (exc.stdout, trailing):
                if isinstance(chunk, bytes):
                    chunk = chunk.decode(errors="replace")
                if chunk:
                    parts.append(chunk)
            output = "".join(parts)
            log_path.write_text(output, encoding="utf-8")
            errors.append(f"timeout apres {timeout}s")

    if execute:
        output = directory / "output"
        files, json_errors = json_files(output)
        errors.extend(json_errors)
        if not output.is_dir() or not any(p.is_file() for p in output.rglob("*")):
            errors.append("aucun artefact produit dans output/")
        if not (output / "results.json").is_file():
            errors.append("output/results.json absent")
        if not (output / "versions-and-parameters.json").is_file():
            errors.append("output/versions-and-parameters.json absent")
        if not files:
            errors.append("aucun artefact JSON audit-able")
        summary_path = output / "summary.json"
        if not summary_path.is_file():
            errors.append("output/summary.json absent")
        else:
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                if not isinstance(summary, dict) or not summary.get("verdict"):
                    errors.append("summary.json ne contient pas de verdict")
            except Exception:
                pass  # The generic JSON validator already reports the parse error.

    return Result(
        poc_id,
        title,
        "PASS" if not errors else "FAIL",
        round(elapsed, 3),
        errors,
        warnings,
        str(log_path.relative_to(ROOT)) if log_path else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", action="store_true", help="auditer sans executer les POCs")
    parser.add_argument("--timeout", type=int, default=900, help="timeout par POC en secondes")
    parser.add_argument("--only", action="append", default=[], help="identifiant a auditer (repetable)")
    args = parser.parse_args()

    declared = declared_pocs()
    declared_ids = {poc_id.lower() for poc_id, _ in declared}
    directory_ids = {p.name for p in POC_ROOT.iterdir() if p.is_dir() and re.fullmatch(r"[a-z]+-\d+", p.name)}
    topology_errors = [f"POC declare sans dossier: {x}" for x in sorted(declared_ids - directory_ids)]
    topology_errors += [f"dossier sans POC declare: {x}" for x in sorted(directory_ids - declared_ids)]

    selected = {value.upper() for value in args.only}
    if selected:
        unknown = selected - {poc_id for poc_id, _ in declared}
        if unknown:
            parser.error(f"POC inconnue(s): {', '.join(sorted(unknown))}")
        declared = [item for item in declared if item[0] in selected]
    else:
        declared = dependency_order(declared)

    results: list[Result] = []
    for index, (poc_id, title) in enumerate(declared, 1):
        print(f"[{index:02d}/{len(declared):02d}] {poc_id}", flush=True)
        result = audit_one(poc_id, title, not args.static, args.timeout)
        results.append(result)
        details = "; ".join(result.errors or result.warnings)
        print(f"  {result.status} {result.seconds:.3f}s" + (f" — {details}" if details else ""), flush=True)

    report = {
        "declared_count": len(declared_pocs()),
        "audited_count": len(results),
        "executed": not args.static,
        "passed": sum(r.status == "PASS" for r in results),
        "failed": sum(r.status == "FAIL" for r in results),
        "warnings": sum(len(r.warnings) for r in results),
        "topology_errors": topology_errors,
        "results": [asdict(r) for r in results],
    }
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = STATE_ROOT / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"\nBilan: {report['passed']}/{len(results)} PASS, {report['failed']} FAIL, "
        f"{report['warnings']} avertissement(s). Rapport: {report_path.relative_to(ROOT)}"
    )
    return 1 if topology_errors or report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
