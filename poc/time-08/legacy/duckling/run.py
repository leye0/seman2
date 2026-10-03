#!/usr/bin/env python3
"""Run TIME-02 against the repository-local Duckling HTTP service."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parent
ROOT = POC_DIR.parent.parent
DUCKLING = ROOT / ".local" / "opt" / "duckling" / "bin" / "duckling-example-exe"
OUTPUT = POC_DIR / "output"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def epoch_milliseconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request(port: int, fixture: dict[str, Any]) -> list[dict[str, Any]]:
    payload = urllib.parse.urlencode(
        {
            "locale": fixture["locale"],
            "text": fixture["text"],
            "reftime": str(epoch_milliseconds(fixture["reftime"])),
            "latent": "true",
        }
    ).encode("utf-8")
    response = urllib.request.urlopen(
        urllib.request.Request(f"http://127.0.0.1:{port}/parse", data=payload),
        timeout=10,
    )
    return json.loads(response.read().decode("utf-8"))


def normalize(entity: dict[str, Any], source: str) -> dict[str, Any]:
    value = entity.get("value") or {}
    start, end = entity["start"], entity["end"]
    if source[start:end] != entity["body"]:
        raise RuntimeError(f"Duckling span mismatch: {source[start:end]!r} != {entity['body']!r}")
    interval = None
    if value.get("type") == "interval" or "from" in value or "to" in value:
        interval = {"from": value.get("from"), "to": value.get("to")}
    alternatives = value.get("values", [])
    return {
        "dimension": entity["dim"],
        "span": [start, end],
        "text": entity["body"],
        "value": value.get("value"),
        "value_type": value.get("type"),
        "unit": value.get("unit"),
        "grain": value.get("grain"),
        "interval": interval,
        "latent": bool(entity.get("latent", False)),
        "alternatives": alternatives,
        "producer": "Duckling",
        "raw_value": value,
    }


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    port = free_port()
    command = [
        str(DUCKLING), "--address=127.0.0.1", f"--port={port}",
        "--no-access-log", "--no-error-log", "--quiet", "--no-compression",
    ]
    server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
    try:
        for _ in range(80):
            if server.poll() is not None:
                raise RuntimeError(f"Duckling exited during startup with {server.returncode}")
            try:
                request(port, {"locale": "en_US", "text": "one", "reftime": "2026-09-26T12:00:00Z"})
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Duckling did not become ready")

        results = []
        for fixture in fixtures:
            raw = request(port, fixture)
            annotations = [normalize(entity, fixture["text"]) for entity in raw]
            results.append({
                "fixture": fixture,
                "status": "annotations_found" if annotations else "no_annotation",
                "annotations": annotations,
                "raw_response": raw,
            })
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    dimensions = Counter(a["dimension"] for r in results for a in r["annotations"])
    matrix: dict[str, dict[str, Any]] = {}
    languages = sorted({f["language"] for f in fixtures})
    all_dimensions = sorted(dimensions)
    for dimension in all_dimensions:
        for language in languages:
            selected = [a for r in results if r["fixture"]["language"] == language for a in r["annotations"] if a["dimension"] == dimension]
            matrix[f"{dimension}:{language}"] = {
                "annotation_count": len(selected),
                "fixture_ids": sorted({r["fixture"]["id"] for r in results if r["fixture"]["language"] == language and any(a["dimension"] == dimension for a in r["annotations"])}),
                "latent_count": sum(a["latent"] for a in selected),
                "with_alternatives": sum(bool(a["alternatives"]) for a in selected),
            }

    assert all(r["fixture"]["text"][a["span"][0]:a["span"][1]] == a["text"] for r in results for a in r["annotations"])
    # Duckling's internal Numeral dimension is serialized by its HTTP API as
    # ``number`` (Duckling.Dimensions.Types.toName).
    required = {"time", "number", "ordinal", "quantity", "amount-of-money", "distance", "duration"}
    assert required.issubset(dimensions), required - set(dimensions)
    assert all(any(r["annotations"] for r in results if r["fixture"]["language"] == language) for language in languages)

    summary = {
        "fixture_count": len(results),
        "annotation_count": sum(len(r["annotations"]) for r in results),
        "dimensions": dict(sorted(dimensions.items())),
        "fixtures_without_annotation": [r["fixture"]["id"] for r in results if not r["annotations"]],
        "latent_annotation_count": sum(a["latent"] for r in results for a in r["annotations"]),
        "annotations_with_alternatives": sum(bool(a["alternatives"]) for r in results for a in r["annotations"]),
        "verdict": "GO_WITH_LOCALE_SPECIFIC_COVERAGE",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "duckling": {
            "package_version": "0.2.0.1",
            "source_commit": subprocess.run(
                ["git", "-C", str(ROOT / ".local" / "src" / "duckling"), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip(),
            "executable_sha256": sha256(DUCKLING),
        },
        "parameters": {"latent": True, "reference_time_unit": "milliseconds_since_epoch", "offsets": "validated against Python Unicode code-point slices", "http_port": "ephemeral"},
    }
    public_results = [{k: v for k, v in r.items() if k != "raw_response"} for r in results]
    raw = [{"fixture_id": r["fixture"]["id"], "response": r["raw_response"]} for r in results]
    write_json(OUTPUT / "results.json", public_results)
    write_json(OUTPUT / "dimension-locale-matrix.json", matrix)
    write_json(OUTPUT / "raw" / "responses.json", raw)
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "versions-and-parameters.json", versions)
    print(f"TIME-02: {summary['annotation_count']} entities over {len(results)} fixtures; {dict(dimensions)}")


if __name__ == "__main__":
    main()
