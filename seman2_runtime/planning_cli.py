#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ContractError
from .corpus_planning import run_corpus_planning


def main() -> int:
    parser = argparse.ArgumentParser(description="Planifie les proto-services depuis les Parquet réels")
    parser.add_argument("--output", type=Path, default=Path("output/phase3"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        plan, trace = run_corpus_planning(root)
    except ContractError as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    args.output.mkdir(parents=True, exist_ok=True)
    value = {"status": "GO", "plan": plan.as_dict(), "trace": [row.as_dict() for row in trace]}
    (args.output / "proto-service-plan.json").write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps({
        "status": "GO",
        "integration_status": plan.payload["status"],
        "readiness": plan.payload["readiness"],
        "next": plan.payload["decision"]["next_implementation_boundary"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
