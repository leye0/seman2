"""Audit hyphenated English spellings attested in the pinned cleaned novels.

This is a REVIEW QUEUE, not an uncontrolled generator of lexical senses.
The supplemental lexicon is curated with POS and surface provenance. Never
rewrite the source corpus or an immutable evaluation cohort to improve coverage.

Run from repository root with PYTHONPATH=superparser:
    python -m scripts.audit_literary_lexicon --top 30
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import Book

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LITERARY_LEXICON = DATA_DIR / "literary_lexicon.jsonl"

# SINGLE hyphens only. A Gutenberg "--" is an em dash, NEVER a compound.
# Avoid partial match in "side--effect" or "blood-stained--but".
COMPOUND_RE = re.compile(r"(?<![A-Za-z-])[A-Za-z]+(?:-[A-Za-z]+)+(?![A-Za-z-])")


def scan_hyphenated(text: str) -> Counter[str]:
    """Count written compound spellings, preserving source text elsewhere."""
    return Counter(match.group().casefold() for match in COMPOUND_RE.finditer(text))


def attested_catalog(path: Path = LITERARY_LEXICON) -> dict[str, list[dict]]:
    """Map each explicitly documented surface to its lexical entries."""
    inventory: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            row = json.loads(line)
            if row.get("provenance", {}).get("source") != "attested-literary-supplement":
                raise ValueError(f"Unproven attestation {path}:{line_number}")
            if not row.get("senses"):
                raise ValueError(f"No category for {path}:{line_number}")
            for surface in row.get("surfaces", [row["lemma"]]):
                inventory.setdefault(surface.casefold(), []).append(row)
    return inventory


def audit_corpora(*, top: int = 50) -> dict:
    """Corpus-wide inventory with a reproducible unlexicalized review queue."""
    if top < 0:
        raise ValueError("top must be nonnegative")
    inventory = attested_catalog()
    counts: Counter[str] = Counter()
    by_book = []
    evidence: dict[str, set[int]] = {}
    manifest = read_manifest()
    for record in manifest["books"]:
        ebook_id = int(record["ebook_id"])
        text, _ = load_cleaned(Book(ebook_id, record["title"],
                                    record["author"], "train"))
        items = scan_hyphenated(text)
        counts.update(items)
        by_book.append({
            "ebook_id": ebook_id,
            "book": record["title"],
            "compound_occurrences": sum(items.values()),
            "compound_types": len(items),
            "listed_types": sum(s in inventory for s in items),
        })
        for surface in items:
            evidence.setdefault(surface, set()).add(ebook_id)
    unknown = counts.keys() - inventory.keys()
    return {
        "total_compound_occurrences": sum(counts.values()),
        "total_compound_types": len(counts),
        "explicitly_listed_compound_types": sum(s in inventory for s in counts),
        "unlisted_compound_types": len(unknown),
        "unlisted_review_queue": [
            {
                "surface": surface,
                "occurrences": count,
                "books": sorted(evidence[surface]),
            }
            for surface, count in counts.most_common()
            if surface in unknown
        ][:top],
        "by_book": by_book,
        "policy": "Review and attest morphology/POS before adding any lexeme. Keep WordNet and productive hyphen fallback. NEVER treat -- as a hyphenated word.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(audit_corpora(top=args.top), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
