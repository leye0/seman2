#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ContractError
from .runtime_bootstrap import execute_epoch


def main() -> int:
    parser = argparse.ArgumentParser(description="Exécute une époque réelle jusqu'à Soar")
    parser.add_argument("--database", type=Path, default=Path("output/runtime/runtime.sqlite"))
    parser.add_argument("--report", type=Path, default=Path("output/runtime/epoch-0.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        result = execute_epoch(root, args.database)
    except ContractError as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    if not all(result["validations"].values()):
        print(json.dumps({"status": "NO-GO", "validations": result["validations"]}, ensure_ascii=False))
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "status": result["status"],
        "questions": result["source_questions"],
        "decisions": len(result["soar_decisions"]),
        "artifacts": result["runtime_metrics"]["artifacts"],
        "events": result["runtime_metrics"]["events"],
        "validations": result["validations"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
