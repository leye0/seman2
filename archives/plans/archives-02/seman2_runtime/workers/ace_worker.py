"""Processus isolé ACE/ERG : requête JSON sur stdin, résultat natif sur stdout."""

from __future__ import annotations

import json
from pathlib import Path
import resource
import subprocess
import sys
import time


def main() -> int:
    started = time.perf_counter()
    request = json.load(sys.stdin)
    memory_mib = int(request["memory_limit_mib"])
    memory_bytes = memory_mib * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    from delphin import ace

    executable = Path(request["ace_executable"])
    grammar = Path(request["erg_grammar"])
    version = subprocess.run(
        [str(executable), "-V"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=5,
        check=False,
    ).stdout.splitlines()[0]
    with ace.ACEParser(
        str(grammar),
        executable=str(executable),
        cmdargs=["-n", str(int(request["max_candidates"]))],
    ) as parser:
        rows = parser.interact(str(request["text"])).results()

    own_usage = resource.getrusage(resource.RUSAGE_SELF)
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)

    json.dump(
        {
            "status": "parsed" if rows else "no-parse",
            "analyzer": "ACE+ERG",
            "analyzer_version": version,
            "candidate_count": len(rows),
            "worker_wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
            "worker_peak_rss_kib": int(own_usage.ru_maxrss),
            "ace_peak_rss_kib": int(child_usage.ru_maxrss),
            "candidates": [
                {
                    "result_id": row.get("result-id"),
                    "mrs": row.get("mrs"),
                    "tree": row.get("tree"),
                    "derivation": row.get("derivation"),
                    "flags": row.get("flags"),
                }
                for row in rows
            ],
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
