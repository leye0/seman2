#!/usr/bin/env python3
"""Run TIME-01 against the repository-local HeidelTime and TreeTagger."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parent
ROOT = POC_DIR.parent.parent
HEIDEL_DIR = ROOT / ".local" / "opt" / "heideltime"
JAR = HEIDEL_DIR / "de.unihd.dbs.heideltime.standalone.jar"
CONFIG = HEIDEL_DIR / "config.props"
TREETAGGER = ROOT / ".local" / "opt" / "treetagger"
OUTPUT = POC_DIR / "output"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_timeml(raw: str, source: str) -> tuple[str, list[dict[str, Any]]]:
    root = ET.fromstring(raw)
    text_node = next(
        (node for node in root.iter() if local_name(node.tag) == "TEXT"), root
    )
    chunks: list[str] = []
    annotations: list[dict[str, Any]] = []
    length = 0

    def append(value: str | None) -> None:
        nonlocal length
        if value:
            chunks.append(value)
            length += len(value)

    def walk(node: ET.Element) -> None:
        start = length
        append(node.text)
        for child in node:
            walk(child)
            append(child.tail)
        end = length
        if local_name(node.tag) == "TIMEX3":
            annotations.append(
                {
                    "timex_id": node.attrib.get("tid"),
                    "type": node.attrib.get("type"),
                    "value": node.attrib.get("value"),
                    "modifier": node.attrib.get("mod"),
                    "quantifier": node.attrib.get("quant"),
                    "frequency": node.attrib.get("freq"),
                    "begin_point": node.attrib.get("beginPoint"),
                    "end_point": node.attrib.get("endPoint"),
                    "span": [start, end],
                    "text": "".join(chunks)[start:end],
                    "producer": "HeidelTime",
                }
            )

    walk(text_node)
    rendered = "".join(chunks)
    source_start = rendered.find(source)
    if source_start < 0 or rendered.find(source, source_start + 1) >= 0:
        raise RuntimeError(f"TimeML text does not contain the source exactly once: {rendered!r}")
    reconstructed = rendered[source_start : source_start + len(source)]
    for annotation in annotations:
        annotation["span"] = [
            annotation["span"][0] - source_start,
            annotation["span"][1] - source_start,
        ]
    annotations.sort(key=lambda item: (item["span"], item["timex_id"] or ""))
    return reconstructed, annotations


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8") as stream:
        stream.write(fixture["text"])
        stream.flush()
        command = [
            "java", "-jar", str(JAR), stream.name,
            "-l", fixture["language"], "-t", "news", "-dct", fixture["dct"],
            "-o", "timeml", "-e", "UTF-8", "-c", str(CONFIG), "-it",
        ]
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
    reconstructed, annotations = parse_timeml(completed.stdout, fixture["text"])
    return {
        "fixture": fixture,
        "status": "annotations_found" if annotations else "no_annotation",
        "source_reconstructed": reconstructed == fixture["text"],
        "annotations": annotations,
        "raw": {"timeml": completed.stdout, "stderr": completed.stderr},
    }


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = [run_fixture(fixture) for fixture in fixtures]

    matrix: dict[str, dict[str, Any]] = {}
    for locale in sorted({item["locale"] for item in fixtures}):
        for category in sorted({item["category"] for item in fixtures}):
            selected = [r for r in results if r["fixture"]["locale"] == locale and r["fixture"]["category"] == category]
            matrix[f"{locale}:{category}"] = {
                "fixture_count": len(selected),
                "fixtures_with_annotation": sum(bool(r["annotations"]) for r in selected),
                "annotation_count": sum(len(r["annotations"]) for r in selected),
                "types": sorted({a["type"] for r in selected for a in r["annotations"]}),
            }

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        if group := result["fixture"].get("dct_group"):
            groups[group].append(result)
    dct_tests = []
    for group, members in sorted(groups.items()):
        values = [[a["value"] for a in member["annotations"]] for member in members]
        dct_tests.append({
            "group": group,
            "dcts": [member["fixture"]["dct"] for member in members],
            "normalized_values": values,
            "normalization_changes_with_dct": len({json.dumps(v) for v in values}) > 1,
        })

    types = Counter(a["type"] for r in results for a in r["annotations"])
    assert all(result["source_reconstructed"] for result in results)
    assert all(test["normalization_changes_with_dct"] for test in dct_tests)
    assert {"DATE", "TIME", "DURATION", "SET"}.issubset(types)
    assert all(any(r["annotations"] for r in results if r["fixture"]["locale"] == locale) for locale in ("en", "fr"))

    public_results = [{k: v for k, v in result.items() if k != "raw"} for result in results]
    raw = [{"fixture_id": r["fixture"]["id"], **r["raw"]} for r in results]
    summary = {
        "fixture_count": len(results),
        "annotation_count": sum(len(r["annotations"]) for r in results),
        "types": dict(sorted(types.items())),
        "fixtures_without_annotation": [r["fixture"]["id"] for r in results if not r["annotations"]],
        "dct_dependency_demonstrated": all(t["normalization_changes_with_dct"] for t in dct_tests),
        "source_reconstruction_passed": True,
        "verdict": "GO_WITH_EXPLICIT_COVERAGE_GAPS",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "java": subprocess.run(
            ["java", "-version"], text=True, capture_output=True, check=True
        ).stderr.splitlines()[0],
        "heideltime": {"distribution": "2.2.1", "jar_sha256": sha256(JAR)},
        "treetagger": {"binary": str(TREETAGGER / "bin" / "tree-tagger"), "english_model_sha256": sha256(TREETAGGER / "lib" / "english.par"), "french_model_sha256": sha256(TREETAGGER / "lib" / "french.par")},
        "parameters": {"document_type": "news", "output": "timeml", "interval_tagger": True, "offsets": "Unicode code points, zero-based, end-exclusive"},
    }
    write_json(OUTPUT / "results.json", public_results)
    write_json(OUTPUT / "coverage-matrix.json", matrix)
    write_json(OUTPUT / "dct-dependency.json", dct_tests)
    write_json(OUTPUT / "raw" / "timeml.json", raw)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", versions)
    print(f"TIME-01: {summary['annotation_count']} TIMEX3 over {len(results)} fixtures; {dict(types)}")


if __name__ == "__main__":
    main()
