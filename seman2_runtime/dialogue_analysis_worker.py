#!/usr/bin/env python3
"""Worker isolé : analyses ACE/ERG et Dynamic Syntax d'un petit batch JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import dynamicsyntax
from delphin import ace


def main() -> int:
    request = json.load(sys.stdin)
    root = Path(request["root"])
    observations = request["observations"]
    if not 1 <= len(observations) <= 16:
        raise ValueError("worker batch must contain between 1 and 16 observations")
    rows = []
    with ace.ACEParser(
        str(root / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"),
        executable=str(root / ".local/bin/ace"),
        cmdargs=["-n", "3"],
    ) as parser:
        for observation in observations:
            text = observation["text"]
            erg_response = parser.interact(text)
            erg_results = erg_response.results()
            ds_text = text.casefold().replace("?", "").replace('"', "")
            try:
                ds_result = dynamicsyntax.parse(ds_text, "ttr", trace=True)
                ds = {
                    "producer": "dynamicsyntax-python",
                    "status": "parsed" if ds_result.ok else "failure",
                    "semantics": str(ds_result.semantics) if ds_result.semantics else None,
                    "action_count": len(ds_result.action_steps),
                    "actions": [
                        {"word": action.word, "action": action.action_name}
                        for action in ds_result.action_steps
                    ],
                }
            except Exception as exc:
                ds = {
                    "producer": "dynamicsyntax-python",
                    "status": "failure",
                    "semantics": None,
                    "action_count": 0,
                    "actions": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            rows.append({
                "observation_id": observation["observation_id"],
                "text": text,
                "analyses": [
                    {
                        "producer": "ACE_ERG",
                        "status": "parsed" if erg_results else "failure",
                        "candidate_count": len(erg_results),
                        "candidates": [
                            {
                                "result_id": result.get("result-id"),
                                "mrs": result.get("mrs"),
                                "tree": result.get("tree"),
                            }
                            for result in erg_results
                        ],
                    },
                    ds,
                ],
                "semantic_fusion": False,
            })
    json.dump({"rows": rows}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
