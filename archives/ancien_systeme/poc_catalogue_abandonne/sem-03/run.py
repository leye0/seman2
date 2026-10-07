#!/usr/bin/env python3
"""SEM-03: attributed WFST form relations in the cognitive artifact flow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path

import pynini
from pynini.lib import pynutil

from seman2_runtime.cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    IngestionRecord,
    build_foundation_modules,
    ingest_records,
    register_foundation_types,
)
from seman2_runtime.cognitive_runtime import CognitiveRuntime
from seman2_runtime.cognitive_scheduler import ModuleSpec
from seman2_runtime.contracts import canonical_json


POC = Path(__file__).resolve().parent
ROOT = POC.parent.parent
OUTPUT = POC / "output"
BUILD = "sem-03-integrated-wfst"


def weighted(rule: dict) -> pynini.Fst:
    return pynutil.add_weight(
        pynini.cross(rule["input"], rule["output"]), rule["weight"]
    )


def enumerate_paths(fst: pynini.Fst) -> list[dict]:
    return [
        {"input": input_value, "output": output_value, "weight": float(str(weight))}
        for input_value, output_value, weight in fst.paths(
            input_token_type="byte", output_token_type="byte"
        ).items()
    ]


def analyze_text(text: str, machine: pynini.Fst, rules: list[dict]) -> list[dict]:
    found = enumerate_paths(pynini.compose(pynini.accep(text), machine))
    for path in found:
        matches = [
            rule
            for rule in rules
            if rule["input"] == text
            and rule["output"] == path["output"]
            and math.isclose(rule["weight"], path["weight"], abs_tol=1e-5)
        ]
        assert len(matches) == 1, (text, path, matches)
        rule = matches[0]
        path.update(
            {
                "rule_id": rule["id"],
                "transformation_type": rule["type"],
                "source_span": [0, len(text)],
                "semantic_identity_inferred": False,
                "canonical_correction_proposed": False,
                "source_rewritten": False,
            }
        )
    return sorted(found, key=lambda row: (row["weight"], row["output"]))


def byte_symbol_table(rules: list[dict]):
    labels = sorted(
        {
            value
            for rule in rules
            for field in ("input", "output")
            for value in rule[field].encode("utf-8")
        }
    )
    table = pynini.SymbolTable()
    table.add_symbol("<eps>", 0)
    rows = [{"symbol": "<eps>", "label": 0, "byte_hex": None}]
    for label in labels:
        symbol = chr(label) if 32 <= label <= 126 else f"byte-0x{label:02x}"
        table.add_symbol(symbol, label)
        rows.append({"symbol": symbol, "label": label, "byte_hex": f"{label:02x}"})
    return table, rows


def build_runtime(machine: pynini.Fst, rules: list[dict], digest: str) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            artifact_type="wfst-form-analysis",
            schema_id="seman2/wfst-form-analysis",
            layer=2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"wfst-form-analyzer"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {"source_text", "source_sha256", "paths", "rule_set_sha256"}
            ),
            required_projection_fields=frozenset(
                {
                    "semantic_identity_inferred",
                    "canonical_correction_proposed",
                    "source_rewritten",
                }
            ),
        )
    )
    registry.freeze()

    def analyze(trigger, context):
        text = str(trigger.payload_native["text"])
        paths = analyze_text(text, machine, rules)
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        yield ArtifactProposal(
            artifact_type="wfst-form-analysis",
            producer_id="wfst-form-analyzer",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "source_text": text,
                "source_sha256": source_hash,
                "paths": paths,
                "rule_set_sha256": digest,
            },
            payload_projection={
                "candidate_count": len(paths),
                "semantic_identity_inferred": False,
                "canonical_correction_proposed": False,
                "source_rewritten": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"wfst-form-analysis:{trigger.artifact_id}",
        )

    policy = IngestionPolicy(max_records=32, max_text_chars=1_000)
    module = ModuleSpec(
        module_id="wfst-form-analyzer",
        layer=2,
        modes=frozenset({"ingestion"}),
        consumes=frozenset({"observation"}),
        produces=frozenset({"wfst-form-analysis"}),
        producer_build=BUILD,
        configuration_digest=digest,
        handler=analyze,
    )
    return CognitiveRuntime(
        registry=registry,
        modules=(*build_foundation_modules(policy), module),
    )


def main() -> None:
    fixture_path = POC / "fixtures.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    rules = data["rules"]
    by_id = {rule["id"]: rule for rule in rules}
    rule_digest = hashlib.sha256(canonical_json(rules).encode()).hexdigest()
    machine = pynini.union(*(weighted(rule) for rule in rules)).optimize()

    runtime = build_runtime(machine, rules, rule_digest)
    records = tuple(
        IngestionRecord(
            record_id=f"sem-03:{index}:{query['input']}",
            discourse_id="sem-03:controlled-form-observations",
            turn_index=index,
            speaker_role="fixture-source",
            text=query["input"],
            canonical_file=str(fixture_path.relative_to(ROOT)),
            source_position=index,
            source_record_id=f"query:{index}",
            raw_body_sha256=hashlib.sha256(query["input"].encode()).hexdigest(),
            channel="controlled-written-form",
            source_kind="written-form",
            native_structure={"fixture_id": f"sem-03-query-{index}"},
        )
        for index, query in enumerate(data["queries"])
    )
    report = ingest_records(
        runtime,
        records,
        policy=IngestionPolicy(max_records=32, max_text_chars=1_000),
        session_id="sem-03:integration",
    )
    analyses = runtime.arena.query(artifact_type="wfst-form-analysis")
    assert len(analyses) == len(data["queries"])
    assert report["pending_tasks"] == 0

    results = []
    for query, analysis in zip(data["queries"], analyses, strict=True):
        paths = [dict(row) for row in analysis.payload_native["paths"]]
        assert query["minimum_paths"] <= len(paths) <= query.get(
            "maximum_paths", 10**9
        )
        assert analysis.payload_native["source_text"] == query["input"]
        assert analysis.payload_native["source_sha256"] == hashlib.sha256(
            query["input"].encode()
        ).hexdigest()
        ancestry = runtime.arena.ancestry(analysis.artifact_id)
        assert {row.artifact_type for row in ancestry} == {
            "source-record",
            "observation",
            "wfst-form-analysis",
        }
        source = next(row for row in ancestry if row.artifact_type == "source-record")
        observation = next(row for row in ancestry if row.artifact_type == "observation")
        assert source.payload_native["text"] == observation.payload_native["text"]
        assert observation.payload_native["text"] == query["input"]
        results.append(
            {
                "query": query,
                "paths": paths,
                "runtime_artifact_id": analysis.artifact_id,
                "parent_observation_id": analysis.parent_ids[0],
                "causal_ancestry_types": [row.artifact_type for row in ancestry],
                "source_reconstructed": True,
            }
        )

    composition = data["composition"]
    first = weighted(by_id[composition["first_rule"]])
    second = weighted(by_id[composition["second_rule"]])
    composed = pynini.compose(first, second).optimize()
    composition_paths = enumerate_paths(
        pynini.compose(pynini.accep(composition["input"]), composed)
    )
    assert len(composition_paths) == 1
    assert composition_paths[0]["output"] == composition["expected_output"]
    assert math.isclose(
        composition_paths[0]["weight"], composition["expected_weight"], abs_tol=1e-5
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    symbols, symbol_rows = byte_symbol_table(rules)
    serialized_machine = machine.copy()
    serialized_machine.set_input_symbols(symbols)
    serialized_machine.set_output_symbols(symbols)
    machine_path = OUTPUT / "form-relations.fst"
    composed_path = OUTPUT / "composed-io-expansion.fst"
    symbol_binary_path = OUTPUT / "byte-symbols.syms"
    symbol_text_path = OUTPUT / "byte-symbols.txt"
    serialized_machine.write(str(machine_path))
    composed.write(str(composed_path))
    symbols.write(str(symbol_binary_path))
    symbols.write_text(str(symbol_text_path))
    reloaded = pynini.Fst.read(str(machine_path))
    assert pynini.equal(serialized_machine, reloaded)
    assert reloaded.input_symbols() is not None
    assert reloaded.output_symbols() is not None
    assert reloaded.input_symbols().labeled_checksum() == symbols.labeled_checksum()

    all_paths = [path for result in results for path in result["paths"]]
    assert all(not path["semantic_identity_inferred"] for path in all_paths)
    assert all(not path["canonical_correction_proposed"] for path in all_paths)
    assert all(not path["source_rewritten"] for path in all_paths)
    assert not results[-1]["paths"]
    result_payload = {
        "rules": rules,
        "queries": results,
        "composition": {
            **composition,
            "paths": composition_paths,
            "component_weights": [
                by_id[composition["first_rule"]]["weight"],
                by_id[composition["second_rule"]]["weight"],
            ],
            "component_rule_ids": [
                composition["first_rule"],
                composition["second_rule"],
            ],
        },
        "symbol_table": symbol_rows,
        "runtime_integration": {
            "session_id": "sem-03:integration",
            "artifact_count": len(runtime.arena),
            "analysis_count": len(analyses),
            "pending_tasks": runtime.scheduler.pending_count,
            "source_observation_analysis_chain_verified": True,
        },
    }
    summary = {
        "rule_count": len(rules),
        "query_count": len(results),
        "path_count": len(all_paths),
        "negative_query_path_count": len(results[-1]["paths"]),
        "composition_passed": True,
        "fst_roundtrip_passed": True,
        "runtime_source_observation_chain_passed": True,
        "semantic_identity_inference_count": 0,
        "canonical_correction_count": 0,
        "source_rewrite_count": 0,
        "verdict": "GO_INTEGRATED_COMPOSABLE_WEIGHTED_FORM_RELATIONS",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "pynini": importlib.metadata.version("pynini"),
        "weight_semiring": "tropical",
        "token_type": "UTF-8 byte labels",
        "rule_set_sha256": rule_digest,
        "fst_sha256": hashlib.sha256(machine_path.read_bytes()).hexdigest(),
        "symbol_table_labeled_checksum_hex": symbols.labeled_checksum().hex(),
        "artifact_contract": "seman2/wfst-form-analysis",
        "ontology_status": "formal relation candidates only",
    }
    for name, value in (
        ("results.json", result_payload),
        ("summary.json", summary),
        ("symbol-table.json", symbol_rows),
        ("versions-and-parameters.json", versions),
    ):
        (OUTPUT / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"SEM-03: {len(rules)} rules; {len(all_paths)} paths; "
        f"{len(analyses)} attributed runtime analyses; FST round-trip; GO"
    )


if __name__ == "__main__":
    main()
