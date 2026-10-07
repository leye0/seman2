#!/usr/bin/env python3
"""Run LEX-06: inspect WordNet 3.0 to SUMO mappings and SUO-KIF axioms."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import nltk
from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parent.parent
SUMO_ROOT = REPO_ROOT / ".local" / "share" / "sumo"
MAPPING_DIR = SUMO_ROOT / "WordNetMappings"
ADAPTER_VERSION = "1"
SCHEMA_VERSION = "seman2.lexical-wordnet-sumo-poc.v1"

MAPPING_FILES = {
    "n": "WordNetMappings30-noun.txt",
    "v": "WordNetMappings30-verb.txt",
    "a": "WordNetMappings30-adj.txt",
    "r": "WordNetMappings30-adv.txt",
}
MAPPING_OPERATOR_SEMANTICS = {
    "=": {
        "relation_type": "equivalent_to",
        "description": "the WordNet synset is equivalent in meaning to the SUMO concept",
        "negative": False,
    },
    "+": {
        "relation_type": "subsumed_by",
        "description": "the WordNet synset is subsumed by the SUMO concept",
        "negative": False,
    },
    "@": {
        "relation_type": "instance_of",
        "description": "the WordNet synset denotes an instance of the SUMO concept",
        "negative": False,
    },
    ":": {
        "relation_type": "not_equivalent_to",
        "description": "complement of the equivalence mapping",
        "negative": True,
    },
    "[": {
        "relation_type": "not_subsumed_by",
        "description": "complement of the subsumption mapping",
        "negative": True,
    },
    "]": {
        "relation_type": "not_instance_of",
        "description": "complement of the instance mapping",
        "negative": True,
    },
}
MAPPING_PATTERN = re.compile(r"&%([^\s&]+?)([=+@:\[\]])(?=\s|$)")
RECORD_PATTERN = re.compile(r"^(\d{8})\s")
LOGICAL_OPERATORS = {"=>", "<=>", "forall", "exists", "and", "or", "not"}


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def canonical_pos(pos: str) -> str:
    return "a" if pos == "s" else pos


def mapping_key(pos: str, offset: int) -> tuple[str, int]:
    return canonical_pos(pos), offset


def parse_mapping_files() -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any]]:
    records: dict[tuple[str, int], dict[str, Any]] = {}
    raw_record_count = 0
    duplicate_record_count = 0
    raw_operator_counts: Counter[str] = Counter()
    unique_edges: set[tuple[str, int, str, str]] = set()
    file_stats: dict[str, dict[str, Any]] = {}
    for pos, filename in MAPPING_FILES.items():
        path = MAPPING_DIR / filename
        file_raw_count = 0
        file_keys: set[tuple[str, int]] = set()
        file_unmapped_keys: set[tuple[str, int]] = set()
        for line_number, line in enumerate(path.open(encoding="utf-8", errors="replace"), 1):
            match = RECORD_PATTERN.match(line)
            if match is None:
                continue
            raw_record_count += 1
            file_raw_count += 1
            offset = int(match.group(1))
            key = (pos, offset)
            file_keys.add(key)
            payload = line.split("|", 1)[1] if "|" in line else ""
            mappings = MAPPING_PATTERN.findall(payload)
            if not mappings:
                file_unmapped_keys.add(key)
            raw_operator_counts.update(operator for _concept, operator in mappings)
            unique_edges.update(
                (pos, offset, concept, operator)
                for concept, operator in mappings
            )
            if key in records:
                duplicate_record_count += 1
                records[key]["source_occurrences"].append(
                    {"line_number": line_number, "raw_line": line.rstrip("\n")}
                )
                existing = {
                    (item["concept"], item["operator"])
                    for item in records[key]["mappings"]
                }
                for concept, operator in mappings:
                    if (concept, operator) not in existing:
                        records[key]["mappings"].append(
                            mapping_record(pos, offset, concept, operator)
                        )
                continue
            try:
                synset = wn.synset_from_pos_and_offset(pos, offset)
                synset_name = synset.name()
                wordnet_resolved = True
                resolution_error = None
            except (KeyError, ValueError, WordNetError) as error:
                synset_name = None
                wordnet_resolved = False
                resolution_error = f"{type(error).__name__}: {error}"
            records[key] = {
                "wordnet_key": f"{pos}:{offset:08d}",
                "part_of_speech": pos,
                "offset": offset,
                "synset": synset_name,
                "wordnet_resolved": wordnet_resolved,
                "wordnet_resolution_error": resolution_error,
                "mapping_file": filename,
                "source_occurrences": [
                    {"line_number": line_number, "raw_line": line.rstrip("\n")}
                ],
                "mappings": [
                    mapping_record(pos, offset, concept, operator)
                    for concept, operator in mappings
                ],
            }
        file_stats[filename] = {
            "raw_record_count": file_raw_count,
            "distinct_synset_key_count": len(file_keys),
            "unmapped_synset_key_count": len(file_unmapped_keys),
        }
    unique_operator_counts = Counter(edge[3] for edge in unique_edges)
    mapped_keys = {
        key for key, record in records.items() if record["mappings"]
    }
    inventory = {
        "raw_record_count": raw_record_count,
        "distinct_synset_key_count": len(records),
        "duplicate_record_count": duplicate_record_count,
        "mapped_synset_key_count": len(mapped_keys),
        "unmapped_synset_key_count": len(records) - len(mapped_keys),
        "unique_mapping_edge_count": len(unique_edges),
        "raw_mapping_operator_counts": dict(sorted(raw_operator_counts.items())),
        "unique_mapping_operator_counts": dict(
            sorted(unique_operator_counts.items())
        ),
        "files": file_stats,
    }
    return records, inventory


def mapping_record(pos: str, offset: int, concept: str, operator: str) -> dict[str, Any]:
    semantics = MAPPING_OPERATOR_SEMANTICS[operator]
    return {
        "mapping_id": stable_id(
            "wordnet-sumo-mapping:",
            {
                "wordnet_version": "3.0",
                "pos": pos,
                "offset": offset,
                "sumo_concept": concept,
                "operator": operator,
            },
        ),
        "concept": concept,
        "operator": operator,
        **semantics,
    }


def iter_kif_forms(path: Path) -> Iterator[tuple[int, str]]:
    """Yield balanced top-level SUO-KIF forms, excluding line comments."""
    text = path.read_text(encoding="utf-8", errors="replace")
    depth = 0
    line_number = 1
    start_line = 0
    buffer: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character == "\n":
                in_comment = False
                line_number += 1
            continue
        if in_string:
            if depth:
                buffer.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            if character == "\n":
                line_number += 1
            continue
        if character == ";":
            in_comment = True
            continue
        if character == '"':
            in_string = True
            if depth:
                buffer.append(character)
            continue
        if character == "(":
            if depth == 0:
                buffer = []
                start_line = line_number
            depth += 1
            buffer.append(character)
        elif character == ")" and depth:
            buffer.append(character)
            depth -= 1
            if depth == 0:
                yield start_line, "".join(buffer)
        elif depth:
            buffer.append(character)
        if character == "\n":
            line_number += 1
    if depth != 0:
        raise RuntimeError(f"Unbalanced SUO-KIF form in {path}")


def kif_atoms(form: str) -> list[str]:
    """Return atoms outside quoted strings in a SUO-KIF form."""
    atoms: list[str] = []
    token: list[str] = []
    in_string = False
    escaped = False
    for character in form:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            if token:
                atoms.append("".join(token))
                token = []
            in_string = True
        elif character.isspace() or character in "()":
            if token:
                atoms.append("".join(token))
                token = []
        else:
            token.append(character)
    if token:
        atoms.append("".join(token))
    return atoms


def classify_formula(predicate: str, atoms: list[str], concept: str) -> str:
    if predicate in LOGICAL_OPERATORS:
        return "rule_or_logical_axiom"
    if predicate == "documentation":
        return "documentation"
    if predicate == "termFormat":
        return "term_format"
    if len(atoms) > 1 and atoms[1] == concept:
        return "direct_relation_from_concept"
    return "direct_or_nested_relation_to_concept"


def build_kif_index(
    kif_paths: list[Path], selected_concepts: set[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any], set[str]]:
    selected_formulas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_symbols: set[str] = set()
    formula_count = 0
    predicate_counts: Counter[str] = Counter()
    for path in kif_paths:
        for line_number, formula in iter_kif_forms(path):
            atoms = kif_atoms(formula)
            if not atoms:
                continue
            formula_count += 1
            predicate = atoms[0]
            predicate_counts[predicate] += 1
            all_symbols.update(atom for atom in atoms if not atom.startswith("?"))
            for concept in selected_concepts.intersection(atoms):
                selected_formulas[concept].append(
                    {
                        "axiom_id": stable_id(
                            "sumo-kif-axiom:",
                            {
                                "file": path.name,
                                "line": line_number,
                                "formula": formula,
                            },
                        ),
                        "source_file": path.name,
                        "start_line": line_number,
                        "predicate": predicate,
                        "formula_kind": classify_formula(predicate, atoms, concept),
                        "concept_atom_positions": [
                            index for index, atom in enumerate(atoms) if atom == concept
                        ],
                        "formula": formula,
                    }
                )
    inventory = {
        "production_kif_file_count": len(kif_paths),
        "top_level_formula_count": formula_count,
        "distinct_unquoted_symbol_count": len(all_symbols),
        "top_level_predicate_counts": dict(sorted(predicate_counts.items())),
        "scope": (
            "top-level *.kif files; development/, tests/, translations, and generated "
            "artifacts excluded"
        ),
    }
    return selected_formulas, inventory, all_symbols


def serialize_synset(synset: Any) -> dict[str, Any]:
    return {
        "synset": synset.name(),
        "wordnet_key": f"{canonical_pos(synset.pos())}:{synset.offset():08d}",
        "offset": synset.offset(),
        "part_of_speech": synset.pos(),
        "lemmas": [lemma.name() for lemma in synset.lemmas()],
        "definition": synset.definition(),
        "examples": synset.examples(),
        "hypernyms": [item.name() for item in synset.hypernyms()],
        "hyponyms": [item.name() for item in synset.hyponyms()],
    }


def concept_record(
    mapping: dict[str, Any],
    formulas: dict[str, list[dict[str, Any]]],
    all_symbols: set[str],
) -> dict[str, Any]:
    concept = mapping["concept"]
    concept_formulas = formulas.get(concept, [])
    predicate_counts = Counter(item["predicate"] for item in concept_formulas)
    kind_counts = Counter(item["formula_kind"] for item in concept_formulas)
    return {
        **mapping,
        "concept_occurs_in_production_kif": concept in all_symbols,
        "accessible_formula_count": len(concept_formulas),
        "predicate_counts": dict(sorted(predicate_counts.items())),
        "formula_kind_counts": dict(sorted(kind_counts.items())),
        "formulas": concept_formulas,
        "inference_performed": False,
    }


def validate(fixtures: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    if len(fixtures) != len(results):
        raise RuntimeError("LEX-06 fixture coverage is incomplete")
    for fixture, result in zip(fixtures, results, strict=True):
        if result["mapping_record_present"] != fixture["expected_mapping_record"]:
            raise RuntimeError(f"Wrong record status: {fixture['id']}")
        actual_mappings = {
            (item["concept"], item["operator"])
            for item in result["sumo_concepts"]
        }
        expected_mappings = {
            (item["concept"], item["operator"])
            for item in fixture["expected_mappings"]
        }
        if actual_mappings != expected_mappings:
            raise RuntimeError(f"Wrong mappings: {fixture['id']}")
        concept_present = any(
            item["concept_occurs_in_production_kif"]
            for item in result["sumo_concepts"]
        )
        if concept_present != fixture["expected_concept_in_kif"]:
            raise RuntimeError(f"Wrong KIF concept status: {fixture['id']}")
        predicates = {
            formula["predicate"]
            for concept in result["sumo_concepts"]
            for formula in concept["formulas"]
        }
        if not set(fixture.get("expected_predicates", [])).issubset(predicates):
            raise RuntimeError(f"Missing expected predicates: {fixture['id']}")
        if not result["wordnet_synset"]["synset"] == fixture["synset"]:
            raise RuntimeError(f"Wrong WordNet synset: {fixture['id']}")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    mapping_paths = [MAPPING_DIR / filename for filename in MAPPING_FILES.values()]
    for path in mapping_paths:
        if not path.is_file():
            raise RuntimeError(f"Missing WordNet-SUMO mapping file: {path}")
    kif_paths = sorted(SUMO_ROOT.glob("*.kif"))
    if not kif_paths:
        raise RuntimeError("No production SUMO KIF files found")

    mapping_records, mapping_inventory = parse_mapping_files()
    fixture_synsets = [wn.synset(fixture["synset"]) for fixture in fixtures]
    selected_concepts = {
        mapping["concept"]
        for synset in fixture_synsets
        for mapping in mapping_records.get(
            mapping_key(synset.pos(), synset.offset()), {}
        ).get("mappings", [])
    }
    formulas, kif_inventory, all_symbols = build_kif_index(
        kif_paths, selected_concepts
    )

    results = []
    raw_mapping_lines = []
    raw_axioms: dict[str, list[dict[str, Any]]] = {}
    for fixture, synset in zip(fixtures, fixture_synsets, strict=True):
        key = mapping_key(synset.pos(), synset.offset())
        mapping_source = mapping_records.get(key)
        mappings = mapping_source["mappings"] if mapping_source else []
        concepts = [
            concept_record(mapping, formulas, all_symbols) for mapping in mappings
        ]
        if mapping_source:
            raw_mapping_lines.append(
                {
                    "fixture": fixture["id"],
                    "mapping_file": mapping_source["mapping_file"],
                    "occurrences": mapping_source["source_occurrences"],
                }
            )
        raw_axioms[fixture["id"]] = [
            formula
            for concept in concepts
            for formula in concept["formulas"]
        ]
        results.append(
            {
                **fixture,
                "analysis_id": stable_id(
                    "wordnet-sumo-analysis:",
                    {
                        "wordnet_version": wn.get_version(),
                        "synset": synset.name(),
                    },
                ),
                "wordnet_synset": serialize_synset(synset),
                "mapping_record_present": mapping_source is not None,
                "mapping_record_status": (
                    "mapped"
                    if mappings
                    else "present_without_sumo_mapping"
                    if mapping_source
                    else "absent_from_mapping_files"
                ),
                "mapping_source": (
                    {
                        "file": mapping_source["mapping_file"],
                        "line_numbers": [
                            item["line_number"]
                            for item in mapping_source["source_occurrences"]
                        ],
                    }
                    if mapping_source
                    else None
                ),
                "sumo_concepts": concepts,
                "mapping_selects_word_sense_for_new_occurrence": False,
                "sumo_is_internal_cognitive_ontology": False,
            }
        )

    validate(fixtures, results)

    all_wordnet_keys = {
        mapping_key(synset.pos(), synset.offset())
        for pos in ("n", "v", "a", "r")
        for synset in wn.all_synsets(pos)
    }
    mapping_keys = set(mapping_records)
    mapped_keys = {
        key for key, record in mapping_records.items() if record["mappings"]
    }
    mapping_concepts = {
        mapping["concept"]
        for record in mapping_records.values()
        for mapping in record["mappings"]
    }
    concept_edge_count = sum(
        1
        for record in mapping_records.values()
        for mapping in record["mappings"]
        if mapping["concept"] in all_symbols
    )
    unique_edge_count = mapping_inventory["unique_mapping_edge_count"]
    summary = {
        "fixture_count": len(fixtures),
        "wordnet_version": wn.get_version(),
        "wordnet_synset_count": len(all_wordnet_keys),
        "mapping_distinct_synset_key_count": len(mapping_keys),
        "mapping_synset_key_coverage": {
            "resolved": len(all_wordnet_keys.intersection(mapping_keys)),
            "applicable": len(all_wordnet_keys),
            "rate": ratio(
                len(all_wordnet_keys.intersection(mapping_keys)),
                len(all_wordnet_keys),
            ),
        },
        "synsets_with_positive_or_negative_sumo_mapping": len(mapped_keys),
        "mapped_synset_coverage": {
            "resolved": len(all_wordnet_keys.intersection(mapped_keys)),
            "applicable": len(all_wordnet_keys),
            "rate": ratio(
                len(all_wordnet_keys.intersection(mapped_keys)),
                len(all_wordnet_keys),
            ),
        },
        "distinct_sumo_concept_count_in_mappings": len(mapping_concepts),
        "mapping_edge_to_production_kif_symbol_resolution": {
            "resolved": concept_edge_count,
            "applicable": unique_edge_count,
            "rate": ratio(concept_edge_count, unique_edge_count),
        },
        "production_kif_file_count": len(kif_paths),
        "production_kif_formula_count": kif_inventory["top_level_formula_count"],
        "automatic_word_sense_disambiguation_performed": False,
        "logical_inference_performed": False,
        "verdict": "ADAPTER_REQUIRED_RESOURCE_AND_DIRECT_AXIOM_LOOKUP_VALIDATED",
    }
    inventory = {
        "mapping_files": mapping_inventory,
        "mapping_operator_semantics": MAPPING_OPERATOR_SEMANTICS,
        "kif": kif_inventory,
        "wordnet_keys_missing_from_mapping_files": [
            {
                "wordnet_key": f"{pos}:{offset:08d}",
                "synset": wn.synset_from_pos_and_offset(pos, offset).name(),
            }
            for pos, offset in sorted(all_wordnet_keys - mapping_keys)
        ],
        "mapping_keys_absent_from_installed_wordnet": [
            f"{pos}:{offset:08d}" for pos, offset in sorted(mapping_keys - all_wordnet_keys)
        ],
        "mapping_concepts_absent_from_production_kif_symbols": sorted(
            mapping_concepts - all_symbols
        ),
    }
    resource_boundary = {
        "wordnet_lookup": {
            "input": "already selected WordNet 3.0 synset",
            "output": "zero or more typed SUMO mapping edges",
            "performs_word_sense_disambiguation": False,
        },
        "sumo_lookup": {
            "input": "SUMO concept named by a mapping edge",
            "output": (
                "direct top-level SUO-KIF formulas mentioning the exact unquoted symbol"
            ),
            "performs_logical_inference": False,
            "transitive_relations_materialized": False,
        },
        "ontology_status": {
            "sumo_is_external_resource": True,
            "sumo_becomes_internal_cognitive_ontology": False,
            "mapping_edge_is_identity": False,
        },
        "adapter_status": {
            "required": True,
            "missing_external_tool": False,
            "implemented_in_poc": (
                "mapping reader, exact KIF symbol index, provenance, and typed output"
            ),
            "not_implemented": (
                "complete SUO-KIF parser, theorem proving, ontology editing, and SigmaKEE UI"
            ),
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("summary.json", summary),
        ("corpus-inventory.json", inventory),
        ("resource-vs-inference.json", resource_boundary),
        ("raw/selected-mapping-lines.json", raw_mapping_lines),
        ("raw/selected-kif-axioms.json", raw_axioms),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    commit = subprocess.run(
        ["git", "-C", str(SUMO_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "adapter_version": ADAPTER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "nltk_version": nltk.__version__,
        "wordnet_version": wn.get_version(),
        "sumo_git_commit": commit,
        "mapping_files": {
            path.name: {"path": str(path), "sha256": sha256_file(path)}
            for path in mapping_paths
        },
        "production_kif_files": {
            path.name: {"path": str(path), "sha256": sha256_file(path)}
            for path in kif_paths
        },
        "parameters": {
            "wordnet_key": "part of speech plus zero-padded 8-digit synset offset",
            "adjective_satellite_normalization": "s -> a",
            "kif_scope": "top-level *.kif files only",
            "kif_lookup": "exact unquoted symbol match in balanced top-level forms",
            "logical_inference": False,
            "automatic_word_sense_disambiguation": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"LEX-06: {len(results)} fixtures validated")
    print(
        f"WordNet keys: {len(all_wordnet_keys)}; mapping keys: {len(mapping_keys)}; "
        f"SUMO KIF formulas: {kif_inventory['top_level_formula_count']}"
    )
    print("inference: not performed (direct mapping and exact KIF lookup only)")


if __name__ == "__main__":
    main()
