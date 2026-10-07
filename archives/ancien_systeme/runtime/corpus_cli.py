#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ContractError
from .corpus import sample_to_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Échantillonne les vrais Parquet avec une mémoire bornée")
    parser.add_argument("--output", type=Path, default=Path("output/phase3"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        value = sample_to_json(root, args.output)
    except ContractError as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    samples = value["envelope"]["payload"]["samples"]
    policy = value["envelope"]["payload"]["sampling_policy"]
    print(json.dumps({
        "status": "GO",
        "samples": [{"sample_id": row["sample_id"], "title": row["title"], "answers": len(row["answers"])} for row in samples],
        "resource_policy": policy,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
