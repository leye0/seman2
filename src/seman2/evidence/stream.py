"""Bounded streaming adapters that preserve source bytes and positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Protocol

from .model import EvidenceUnit


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    raw: str
    kind: str
    source: Mapping[str, Any]
    observed_at: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class EvidenceSink(Protocol):
    def ingest(
        self,
        raw: str,
        *,
        stream_id: str,
        kind: str = "text",
        source: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
        context: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        sequence: int | None = None,
    ) -> EvidenceUnit: ...


def text_blocks(
    path: str | Path,
    *,
    mode: str = "paragraph",
    max_units: int | None = None,
    max_unit_bytes: int = 1_000_000,
) -> Iterator[EvidenceRecord]:
    """Yield exact UTF-8 source slices without loading the document as a whole."""
    if mode not in {"paragraph", "line"}:
        raise ValueError("text mode must be 'paragraph' or 'line'")
    if max_units is not None and max_units < 0:
        raise ValueError("max units cannot be negative")
    if max_unit_bytes < 1:
        raise ValueError("max unit bytes must be positive")
    source_path = Path(path).resolve()
    emitted = 0
    byte_cursor = 0
    line_number = 0
    block: list[bytes] = []
    block_size = 0
    block_start_byte = 0
    block_start_line = 0

    def make_record(raw_bytes: bytes, start: int, start_line: int, end_line: int) -> EvidenceRecord:
        if len(raw_bytes) > max_unit_bytes:
            raise ValueError(
                f"source unit at byte {start} exceeds {max_unit_bytes} bytes"
            )
        try:
            raw = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"source is not valid UTF-8 at byte {start}") from exc
        return EvidenceRecord(
            raw=raw,
            kind="text",
            source={
                "type": "file-slice",
                "source_id": str(source_path),
                "byte_start": start,
                "byte_end": start + len(raw_bytes),
                "line_start": start_line,
                "line_end": end_line,
            },
            metadata={"source_mode": mode, "encoding": "utf-8"},
        )

    with source_path.open("rb") as handle:
        for raw_line in handle:
            line_number += 1
            if max_units is not None and emitted >= max_units:
                return
            if mode == "line":
                if raw_line.strip():
                    yield make_record(raw_line, byte_cursor, line_number, line_number)
                    emitted += 1
                byte_cursor += len(raw_line)
                continue

            if raw_line.strip():
                if not block:
                    block_start_byte = byte_cursor
                    block_start_line = line_number
                block.append(raw_line)
                block_size += len(raw_line)
                if block_size > max_unit_bytes:
                    raise ValueError(
                        f"source unit at byte {block_start_byte} exceeds "
                        f"{max_unit_bytes} bytes"
                    )
            elif block:
                # The blank separator is a boundary, not part of the text unit.
                payload = b"".join(block)
                yield make_record(
                    payload, block_start_byte, block_start_line, line_number - 1
                )
                emitted += 1
                block = []
                block_size = 0
            byte_cursor += len(raw_line)
        if block and (max_units is None or emitted < max_units):
            yield make_record(
                b"".join(block), block_start_byte, block_start_line, line_number
            )


def dialogue_tsv(
    path: str | Path,
    *,
    max_units: int | None = None,
    max_line_bytes: int = 1_000_000,
) -> Iterator[EvidenceRecord]:
    """Read speaker<TAB>surface while retaining the complete native row."""
    if max_units is not None and max_units < 0:
        raise ValueError("max units cannot be negative")
    if max_line_bytes < 1:
        raise ValueError("max line bytes must be positive")
    source_path = Path(path).resolve()
    emitted = 0
    byte_cursor = 0
    with source_path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if max_units is not None and emitted >= max_units:
                return
            if len(raw_line) > max_line_bytes:
                raise ValueError(f"dialogue row {line_number} exceeds byte bound")
            if not raw_line.strip():
                byte_cursor += len(raw_line)
                continue
            try:
                native_row = raw_line.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ValueError(f"dialogue row {line_number} is not UTF-8") from exc
            row_without_ending = native_row.rstrip("\r\n")
            if "\t" not in row_without_ending:
                raise ValueError(f"dialogue row {line_number} has no tab separator")
            speaker, surface = row_without_ending.split("\t", 1)
            if not surface:
                raise ValueError(f"dialogue row {line_number} has empty surface")
            yield EvidenceRecord(
                raw=surface,
                kind="text",
                source={
                    "type": "dialogue-row",
                    "source_id": str(source_path),
                    "byte_start": byte_cursor,
                    "byte_end": byte_cursor + len(raw_line),
                    "line": line_number,
                },
                context={"speaker_source_value": speaker},
                metadata={"native_record": native_row, "encoding": "utf-8"},
            )
            emitted += 1
            byte_cursor += len(raw_line)


def ingest_records(
    sink: EvidenceSink,
    records: Iterable[EvidenceRecord],
    *,
    stream_id: str,
) -> tuple[EvidenceUnit, ...]:
    units: list[EvidenceUnit] = []
    for record in records:
        units.append(
            sink.ingest(
                record.raw,
                stream_id=stream_id,
                kind=record.kind,
                source=record.source,
                observed_at=record.observed_at,
                context=record.context,
                metadata=record.metadata,
            )
        )
    return tuple(units)
