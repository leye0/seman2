"""Inspection en lecture seule d'un checkpoint de session cognitive vérifié."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .cognitive_ingestion_session import SESSION_FORMAT
from .contracts import ContractError, canonical_json


def load_verified_session_checkpoint(path: Path) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"checkpoint session illisible: {exc}") from exc
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or payload.get("format") != SESSION_FORMAT:
        raise ContractError("checkpoint session: format incompatible")
    digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    if envelope.get("sha256") != digest:
        raise ContractError("checkpoint session: empreinte invalide")
    return payload


def artifact_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload["runtime"]["arena"]["artifacts"]
    return {row["artifact_id"]: row for row in rows}


def artifacts_of_type(
    payload: Mapping[str, Any], artifact_type: str
) -> list[dict[str, Any]]:
    return [
        row
        for row in payload["runtime"]["arena"]["artifacts"]
        if row["artifact_type"] == artifact_type
    ]


def ancestry(
    artifacts: Mapping[str, dict[str, Any]], artifact_id: str
) -> list[dict[str, Any]]:
    pending = [artifact_id]
    seen: set[str] = set()
    rows = []
    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            row = artifacts[current]
        except KeyError as exc:
            raise ContractError(f"checkpoint: parent absent {current}") from exc
        rows.append(row)
        pending.extend(row["parent_ids"])
    return rows
