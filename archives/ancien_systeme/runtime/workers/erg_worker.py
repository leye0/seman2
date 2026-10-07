#!/usr/bin/env python3
from __future__ import annotations

import json
import resource
import sys
from pathlib import Path


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
from delphin import ace

root = Path(request["root"])
with ace.ACEParser(
    str(root / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
    executable=str(root / ".local/bin/ace"),
    cmdargs=["-n", str(request["max_candidates"])],
) as parser:
    results = parser.interact(request["text"]).results()
json.dump(
    {
        "status": "parsed" if results else "failure",
        "candidate_count": len(results),
        "candidates": [
            {
                "result_id": row.get("result-id"),
                "mrs": row.get("mrs"),
                "tree": row.get("tree"),
            }
            for row in results
        ],
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
