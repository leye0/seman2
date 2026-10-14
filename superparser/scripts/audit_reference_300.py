#!/usr/bin/env python3
"""Create the reviewed compact reference and a machine-readable audit trail."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "300_phrases_with_answer.json"
OUTPUT = ROOT / "data" / "seman2_reference_300_compact.json"
AUDIT = ROOT / "data" / "seman2_reference_300_audit.jsonl"

ATTACHMENT_PHENOMENA = {
    "noun_pp_attachment", "verb_pp_attachment", "adverbial_pp",
    "multiple_adjuncts", "pp_adjunct",
}
PARTICIPLE_SURFACES = {"closed", "missing", "broken", "hidden"}


def walk(node):
    yield node
    for child in node.get("children", ()):
        yield from walk(child)


def main() -> None:
    original = json.loads(SOURCE.read_text(encoding="utf-8"))
    reviewed = deepcopy(original)
    reviewed["metadata"].update({
        "format": "seman2-reviewed-reference-constituency-v2",
        "review_status": "systematic_initial_audit",
        "source_file": SOURCE.name,
        "audit_file": AUDIT.name,
        "strict_evaluation_exclusions": ["SEM-GOLD-213"],
        "evaluation_warning": (
            "Development/validation/test share controlled templates; test is useful "
            "for regression but is not an out-of-distribution generalization measure."
        ),
    })
    audit = []

    for row in reviewed["sentences"]:
        notes = []
        phenomena = set(row["phenomena"])

        if {"expletive", "existential"} <= phenomena:
            vp = next(node for node in walk(row["tree"]) if node["category"] == "VP")
            pivot = next(
                child for child in vp["children"]
                if child["category"] == "NP" and child["role"] == "subject"
            )
            old = {"role": pivot["role"], "span": pivot["span"], "text": pivot["text"]}
            pivot["role"] = "pivot"
            new = {"role": pivot["role"], "span": pivot["span"], "text": pivot["text"]}
            audit.append({
                "id": row["id"], "kind": "correction", "path": "tree/VP/NP",
                "original": old, "new": new,
                "justification": (
                    "In an existential there-construction, expletive 'there' is the "
                    "syntactic subject and the postverbal NP is the existential pivot/associate."
                ),
            })
            notes.append({"status": "corrected", "topic": "existential_pivot"})

        if row["id"] == "SEM-GOLD-213":
            note = {
                "status": "excluded_from_strict_evaluation",
                "topic": "verbal_valency",
                "justification": (
                    "Standard English 'greet' is normally transitive. The absolute use in "
                    "'Nora arrived, greeted, and stayed' requires an elliptical understood "
                    "object and must not force a generic intransitive frame into the lexicon."
                ),
            }
            notes.append(note)
            audit.append({"id": row["id"], "kind": "quality_flag", **note})

        ambiguous = sorted(phenomena & ATTACHMENT_PHENOMENA)
        if ambiguous:
            note = {
                "status": "accepted_ambiguity", "topic": "pp_attachment",
                "justification": (
                    "The annotated NP/VP attachment is a preferred reading, but syntax alone "
                    "does not exclude the alternative attachment."
                ),
            }
            notes.append(note)
            audit.append({"id": row["id"], "kind": "ambiguity", **note})

        participles = [
            token["text"].casefold() for token in row["tokens"]
            if token["text"].casefold() in PARTICIPLE_SURFACES
        ]
        if participles:
            note = {
                "status": "accepted_ambiguity", "topic": "adjective_vs_participle",
                "surfaces": participles,
                "justification": (
                    "The reference selects an adjectival/stative reading; a verbal passive or "
                    "progressive analysis may also be grammatical and is not automatically an error."
                ),
            }
            notes.append(note)
            audit.append({"id": row["id"], "kind": "ambiguity", **note})

        if row["text"].startswith("Growing vegetables "):
            note = {
                "status": "accepted_ambiguity", "topic": "gerund_vs_participial_np",
                "justification": (
                    "'Growing vegetables' permits both activity-gerund and vegetables-that-grow "
                    "readings; the reference records only the intended activity reading."
                ),
            }
            notes.append(note)
            audit.append({"id": row["id"], "kind": "ambiguity", **note})

        if notes:
            row["reference_review"] = notes

    OUTPUT.write_text(
        json.dumps(reviewed, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with AUDIT.open("w", encoding="utf-8") as stream:
        for entry in audit:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({
        "sentences": len(reviewed["sentences"]),
        "corrections": sum(entry["kind"] == "correction" for entry in audit),
        "quality_flags": sum(entry["kind"] == "quality_flag" for entry in audit),
        "ambiguities": sum(entry["kind"] == "ambiguity" for entry in audit),
        "output": str(OUTPUT), "audit": str(AUDIT),
    }, indent=2))


if __name__ == "__main__":
    main()
