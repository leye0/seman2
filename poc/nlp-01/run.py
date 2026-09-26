#!/usr/bin/env python3
"""Run NLP-01 against the repository-local ACE and ERG installation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delphin import ace


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_ACE = REPO_ROOT / ".local/bin/ace"
DEFAULT_GRAMMAR = REPO_ROOT / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
TOKEN_RE = re.compile(
    r'\((?P<id>\d+),\s*(?P<start_vertex>\d+),\s*(?P<end_vertex>\d+),\s*'
    r'<(?P<from>\d+):(?P<to>\d+)>,\s*\d+,\s*"(?P<form>(?:[^"\\]|\\.)*)"'
    r',\s*\d+,\s*"[^"]*",\s*"(?P<pos>[^"]+)"\s+(?P<probability>[0-9.]+)\)'
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def initial_tokens(raw: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for match in TOKEN_RE.finditer(raw):
        item = match.groupdict()
        tokens.append(
            {
                "id": int(item["id"]),
                "start_vertex": int(item["start_vertex"]),
                "end_vertex": int(item["end_vertex"]),
                "charspan": [int(item["from"]), int(item["to"])],
                "form": json.loads(f'"{item["form"]}"'),
                "pos": item["pos"],
                "pos_probability": float(item["probability"]),
            }
        )
    return tokens


def ace_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-V"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def run_raw(
    executable: Path,
    grammar: Path,
    sentences: list[str],
    max_results: int,
    raw_dir: Path,
) -> None:
    command = [
        str(executable),
        "-g",
        str(grammar),
        "-n",
        str(max_results),
        "--tsdb-notes",
        "--tsdb-stdout",
        "--report-labels",
    ]
    completed = subprocess.run(
        command,
        input="\n".join(sentences) + "\n",
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "ace-tsdb.stdout").write_text(completed.stdout, encoding="utf-8")
    (raw_dir / "ace-tsdb.stderr").write_text(completed.stderr, encoding="utf-8")


def serialize_response(fixture: dict[str, str], response: Any) -> dict[str, Any]:
    analyses = []
    for rank, result in enumerate(response.results(), start=1):
        mrs = result.mrs()
        flags = dict(result.get("flags", []))
        analyses.append(
            {
                "rank": rank,
                "result_id": result.get("result-id"),
                "score": flags.get(":ascore"),
                "probability": flags.get(":probability"),
                "derivation_raw": result.get("derivation"),
                "derivation": result.derivation().to_dict(),
                "syntax_tree_raw": result.get("tree"),
                "syntax_tree": result.tree(),
                "mrs_raw": result.get("mrs"),
                "morphosyntactic_features": mrs.variables,
            }
        )

    token_lattice = response.get("tokens", {})
    declared_readings = int(response.get("readings", 0))
    return {
        **fixture,
        "status": "parsed" if declared_readings else "parse_failure",
        "failure": None
        if declared_readings
        else {
            "type": "no_analysis",
            "message": "ACE/ERG returned zero readings.",
        },
        "analysis_count": declared_readings,
        "returned_analysis_count": len(analyses),
        "limit_reached": False,  # Set by main(), which knows the configured cap.
        "tokens": initial_tokens(token_lattice.get("initial", "")),
        "token_lattice_raw": token_lattice,
        "chart": {
            "passive_edges": response.get("pedges"),
            "active_edges": response.get("aedges"),
        },
        "notes": response.get("NOTES", []),
        "warnings": response.get("WARNINGS", []),
        "errors": response.get("ERRORS", []),
        "analyses": analyses,
    }


def validate(fixtures: list[dict[str, str]], results: list[dict[str, Any]]) -> None:
    required = {
        "declarative",
        "interrogative",
        "imperative",
        "negation",
        "coordination",
        "relative clause",
        "subject control",
        "passive",
        "fragment",
        "ungrammatical",
    }
    observed = {fixture["construction"] for fixture in fixtures}
    if observed != required:
        raise RuntimeError("The fixture set no longer covers all ten NLP-01 cases.")
    if not any(result["status"] == "parse_failure" for result in results):
        raise RuntimeError("NLP-01 requires at least one explicit parse failure.")
    for result in results:
        if result["status"] == "parsed":
            if not result["tokens"] or not result["analyses"]:
                raise RuntimeError(f"Incomplete parsed result: {result['id']}")
            for analysis in result["analyses"]:
                required_fields = {
                    "derivation",
                    "syntax_tree",
                    "morphosyntactic_features",
                    "rank",
                    "score",
                }
                if not required_fields.issubset(analysis):
                    raise RuntimeError(f"Incomplete analysis: {result['id']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ace", type=Path, default=DEFAULT_ACE)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    if args.max_results < 1:
        parser.error("--max-results must be positive")
    if not args.ace.is_file() or not args.grammar.is_file():
        parser.error("ACE or the ERG image is missing; run ./scripts/seman2 install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    sentences = [fixture["sentence"] for fixture in fixtures]
    output_dir = POC_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_raw(args.ace, args.grammar, sentences, args.max_results, output_dir / "raw")

    command_args = ["-n", str(args.max_results)]
    results = []
    with ace.ACEParser(
        str(args.grammar), executable=str(args.ace), cmdargs=list(command_args)
    ) as process:
        for fixture in fixtures:
            result = serialize_response(fixture, process.interact(fixture["sentence"]))
            result["limit_reached"] = (
                result["returned_analysis_count"] == args.max_results
            )
            results.append(result)

    validate(fixtures, results)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "ace": ace_version(args.ace),
        "erg": {
            "image": os.path.relpath(args.grammar, REPO_ROOT),
            "sha256": sha256(args.grammar),
            "label_reported_by_ace": "ERG (2018)",
        },
        "pydelphin": importlib.metadata.version("pydelphin"),
        "parameters": {
            "max_results": args.max_results,
            "ace_arguments": command_args
            + ["--tsdb-notes", "--tsdb-stdout", "--report-labels"],
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"NLP-01: {len(results)} fixtures validated")
    for result in results:
        print(
            f"{result['id']:16} {result['status']:13} "
            f"{result['analysis_count']} reading(s)"
        )


if __name__ == "__main__":
    main()
