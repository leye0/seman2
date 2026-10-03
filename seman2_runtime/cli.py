#!/usr/bin/env python3
"""Exécute et audite la chaîne de proto-services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ContractError
from .pipeline import build_pipeline, write_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="John likes Mary.")
    parser.add_argument("--speaker", default="user:john")
    parser.add_argument("--correlation-id", default="phase3:integration:001")
    parser.add_argument("--output", type=Path, default=Path("output/phase3"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    pipeline = build_pipeline(root)
    try:
        result = pipeline.run(
            args.text, speaker=args.speaker, correlation_id=args.correlation_id
        )
    except ContractError as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    write_result(result, args.output, pipeline.manifest())
    print(json.dumps({
        "status": "GO",
        "text": result.final.payload["text"],
        "services": len(pipeline.services),
        "checks": result.as_dict()["checks"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
