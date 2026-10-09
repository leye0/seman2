"""Capability boundary for the local OpenCog Miner."""

from __future__ import annotations

import ctypes.util
from pathlib import Path
from typing import Any, Mapping, Sequence


class MinerAdapter:
    """Expose Miner availability and preserve every invocation as derivation data.

    Actual mining is performed by the installed Atomese module.  The Python
    runtime does not silently replace it with a semantic rules engine.
    """

    def __init__(self, prefix: str | Path | None = None) -> None:
        self.prefix = Path(prefix) if prefix is not None else None
        library = ctypes.util.find_library("miner") or ctypes.util.find_library("Miner")
        if library is None and self.prefix is not None:
            candidates = tuple(self.prefix.rglob("*miner*.so")) if self.prefix.exists() else ()
            library = str(candidates[0]) if candidates else None
        self.library = library

    @property
    def available(self) -> bool:
        return self.library is not None

    @property
    def status(self) -> dict[str, Any]:
        return {"available": self.available, "library": self.library}

    def invocation(
        self,
        *,
        database_ids: Sequence[str],
        minimum_support: int,
        maximum_variables: int,
        initial_pattern: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("local OpenCog Miner unavailable")
        return {
            "technology": "OpenCog Miner",
            "library": self.library,
            "database_ids": list(database_ids),
            "minimum_support": minimum_support,
            "maximum_variables": maximum_variables,
            "initial_pattern": dict(initial_pattern or {}),
        }
