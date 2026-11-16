"""Resolve frozen literary case identities against the current extractor.

The manifest contains source coordinates and hashes, not an alternate
text corpus or alternate sentence splitter. A missing old span must have
the exact documented documentary owner; nothing is silently dropped.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from research.verbnet_lr.gutenberg_novels import analysis_units, extract
from scripts.evaluate_novel_transfer import ROOT, SOURCES, source_body, verify_source

MANIFEST = ROOT / "research" / "verbnet_lr" / "transfer_source_anchors.json"
PINS = {
    "transfer24-v1": "274534a189d50dda836543397351fe1064539ea0aa66330ad3514a1472454f91",
    "replay96-v1": "df60435af9cb56ca02e8fae5efe8030fcd3b768a65113853b50ac407f2ecdeac",
    "extension48-v1": "992335b242d2fd5e711df3c427cd8c468000efeb2c7f6e0e66b7607da4ee20f2",
    "scout24-v1": "cd2bcc7fdf1d7840e2216bd5d74f0b6f93e7db09cdf17875133c75218977afe0",
    "blind42-v1": "64305eb55dd5a5c14ad4f8f12cd6e34c786dc3737902e8419067ae657936151e",
}


def manifest_digest(rows):
    return sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def resolve_anchors(books_dir: Path, *, manifest: Path = MANIFEST):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema") != "seman2-transfer-source-anchors-v1" or set(data.get("cohorts", {})) != set(PINS):
        raise ValueError("Unrecognized literary source anchor manifest")
    for name, entries in data["cohorts"].items():
        if manifest_digest(entries) != PINS[name]:
            raise ValueError(f"Frozen source anchors changed for {name}")
    source_by_book = {}
    eligible = {}
    documentary = {}
    for book, digest, first, _ in SOURCES:
        body = source_body((books_dir / f"pg{book.ebook_id}.txt").read_bytes(),
                           book.ebook_id, digest, first)
        source_by_book[book.ebook_id] = body
        rows, _ = extract(book, body, length_min=4, length_max=32)
        eligible[book.ebook_id] = {tuple(case["structural_core_source_span"]): case for case in rows}
        documentary[book.ebook_id] = tuple(unit for unit in analysis_units(body)
                                          if unit.structural_status == "nonprose_documentary")
    resolved = {}
    for name, entries in data["cohorts"].items():
        rows = []
        for label, book_id, band, start, end, expected in entries:
            body = source_by_book[book_id]
            span = (start, end)
            if not 0 <= start < end <= len(body):
                raise ValueError(f"Invalid frozen source span for {label}")
            original = " ".join(body[start:end].split())
            if sha256(original.encode()).hexdigest() != expected:
                raise ValueError(f"Exact source text changed for {label}")
            case = eligible[book_id].get(span)
            if case is not None:
                row = {**case, "transfer_id": label, "band": band}
                verify_source(row, body)
                rows.append(row)
                continue
            owners = [unit for unit in documentary[book_id]
                      if unit.core_start == start and end <= unit.core_end
                      and unit.discourse_function == "documentary_postscript"
                      and any(c.function == "document_marker"
                              and unit.source_text[c.start:c.end].strip() == original
                              for c in unit.constituents)]
            if len(owners) != 1:
                raise ValueError(f"Frozen source unit no longer resolves: {label}")
            unit, = owners
            rows.append({
                "transfer_id": label, "book_id": book_id, "band": band,
                "source_text": original, "structural_core_source_span": list(span),
                "disposition": "document_marker_not_a_standalone_utterance",
                "documentary_owner_span": [unit.core_start, unit.core_end],
            })
        resolved[name] = rows
    return resolved
