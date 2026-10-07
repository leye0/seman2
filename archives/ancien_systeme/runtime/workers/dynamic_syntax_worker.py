#!/usr/bin/env python3
from __future__ import annotations

import json
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
import dynamicsyntax

text = request["text"].casefold().replace("?", "").replace('"', "")
try:
    result = dynamicsyntax.parse(text, "ttr", trace=True)
    response = {
        "status": "parsed" if result.ok else "failure",
        "semantics": str(result.semantics) if result.semantics else None,
        "action_count": len(result.action_steps),
        "actions": [
            {"word": action.word, "action": action.action_name}
            for action in result.action_steps
        ],
    }
except Exception as exc:
    response = {
        "status": "failure",
        "semantics": None,
        "action_count": 0,
        "actions": [],
        "error": f"{type(exc).__name__}: {exc}",
    }
json.dump(response, sys.stdout, ensure_ascii=False)
sys.stdout.write("\n")
