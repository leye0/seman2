"""Offline ERG/ACE oracle; never inserted into the production parse path."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any


class ErgOracle:
    def __init__(self, ace: str | Path | None = None, grammar: str | Path | None = None) -> None:
        self.ace = str(ace or os.environ.get("ACE_BIN", "ace"))
        self.grammar = str(grammar or os.environ.get("ERG_DAT", ""))

    def analyze(self, text: str, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
        if not self.grammar:
            raise RuntimeError("ERG_DAT is not configured")
        completed = subprocess.run(
            [self.ace, "-g", self.grammar, "-1T", "-f", "-"],
            input=text + "\n",
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "technology": "ERG+ACE",
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "input": text,
        }
