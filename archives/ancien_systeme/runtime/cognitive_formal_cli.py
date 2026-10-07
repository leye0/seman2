from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .cognitive_formal_analysis import FormalAnalysisPolicy, build_formal_runtime
from .cognitive_ingestion import IngestionPolicy, IngestionRecord, ingest_records
from .contracts import ContractError


DEFAULT_SENTENCE = "Maya carried a blue notebook home."


def main() -> int:
    parser = argparse.ArgumentParser(description="Exécute le premier fan-out formel cognitif")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/the_map_of_everything_nlp_novel.txt"),
    )
    parser.add_argument("--sentence", default=DEFAULT_SENTENCE)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        found = False
        source_line = 0
        with args.input.open("r", encoding="utf-8") as handle:
            for source_line, line in enumerate(handle, start=1):
                if args.sentence in line:
                    found = True
                    break
        if not found:
            raise ContractError("analyse formelle: phrase absente du document source")
        ingestion_policy = IngestionPolicy(max_records=1, max_text_chars=500)
        runtime = build_formal_runtime(
            root,
            ingestion_policy=ingestion_policy,
            formal_policy=FormalAnalysisPolicy(max_units_per_observation=1),
        )
        record = IngestionRecord(
            record_id="formal-demo:" + hashlib.sha256(args.sentence.encode()).hexdigest()[:24],
            discourse_id=f"text:{args.input.stem}",
            turn_index=0,
            speaker_role="narrator",
            text=args.sentence,
            canonical_file=str(args.input),
            source_position=source_line,
            source_record_id=f"line:{source_line}",
            raw_body_sha256=hashlib.sha256(args.sentence.encode()).hexdigest(),
            channel="narrative-text",
            source_kind="sentence",
            native_structure={"selected_from_real_document": True},
        )
        ingest_records(runtime, (record,), policy=ingestion_policy, session_id="formal-demo")
    except (ContractError, OSError) as exc:
        print(json.dumps({"status": "NO-GO", "error": str(exc)}, ensure_ascii=False))
        return 1
    mrs = runtime.arena.query(artifact_type="mrs-analysis")[0]
    dynamic = runtime.arena.query(artifact_type="dynamic-syntax-analysis")[0]
    linkages = runtime.arena.query(artifact_type="linkage-analysis")[0]
    lexical = runtime.arena.query(artifact_type="lexical-analysis")[0]
    form_phonology = runtime.arena.query(artifact_type="form-phonology-analysis")[0]
    cross_representation = runtime.arena.query(
        artifact_type="cross-representation-hypothesis"
    )
    ledger = runtime.arena.query(artifact_type="native-analysis-ledger-entry")
    fragments = runtime.arena.query(artifact_type="graph-fragment")
    semantics = runtime.arena.query(artifact_type="semantic-structure")
    temporal = runtime.arena.query(artifact_type="temporal-constraint-network")
    constraints = runtime.arena.query(artifact_type="constraint-solution")
    hypotheses = runtime.arena.query(artifact_type="hypothesis-candidate")
    families = runtime.arena.query(artifact_type="hypothesis-family")
    dialogue_states = runtime.arena.query(artifact_type="dialogue-state-candidate")
    situations = runtime.arena.query(artifact_type="situation-branch-set")
    episodes = runtime.arena.query(artifact_type="episode-candidate")
    indexes = runtime.arena.query(artifact_type="retrieval-index-entry")
    statistics = runtime.arena.query(artifact_type="statistics-snapshot")
    inductions = runtime.arena.query(artifact_type="induction-state")
    cultures = runtime.arena.query(artifact_type="cultural-learning-state")
    learned_concepts = runtime.arena.query(
        artifact_type="learned-concept-candidate"
    )
    transformations = runtime.arena.query(
        artifact_type="state-transformation-candidate"
    )
    transformation_decisions = runtime.arena.query(
        artifact_type="soar-transformation-decision"
    )
    consolidations = runtime.arena.query(
        artifact_type="memory-consolidation-state"
    )
    soar_states = runtime.arena.query(artifact_type="soar-control-state")
    print(
        json.dumps(
            {
                "status": "GO-BOTTOM-UP-SEMANTIC-SLICE",
                "sentence": args.sentence,
                "source_line": source_line,
                "erg": {
                    "status": mrs.payload_native["status"],
                    "candidate_count": mrs.payload_native["candidate_count"],
                },
                "dynamic_syntax": {
                    "status": dynamic.payload_native["status"],
                    "action_count": dynamic.payload_native["action_count"],
                },
                "link_grammar": {
                    "status": linkages.payload_native["status"],
                    "linkage_count": linkages.payload_native["linkage_count"],
                },
                "lexical_resources": {
                    "status": lexical.payload_native["status"],
                    "occurrence_count": lexical.payload_native.get("occurrence_count", 0),
                    "providers": dict(lexical.payload_native.get("providers", {})),
                },
                "form_phonology": {
                    "status": form_phonology.payload_native["status"],
                    "occurrence_count": form_phonology.payload_native.get(
                        "occurrence_count", 0
                    ),
                    "error_count": len(form_phonology.payload_native.get("errors", ())),
                },
                "fusion_performed": False,
                "ledger_entries": len(ledger),
                "cross_representation_hypotheses": len(cross_representation),
                "cross_representation_alignments": sum(
                    len(row.payload_native["alignments"])
                    for row in cross_representation
                ),
                "graph_fragments": len(fragments),
                "semantic_candidates": len(semantics),
                "temporal_networks": len(temporal),
                "constraint_solutions": len(constraints),
                "constraint_statuses": [
                    row.payload_native["status"] for row in constraints
                ],
                "factorized_hypotheses": len(hypotheses),
                "hypothesis_families": len(families),
                "dialogue_state_candidates": len(dialogue_states),
                "situation_branch_sets": len(situations),
                "episode_candidates": len(episodes),
                "retrieval_index_entries": len(indexes),
                "statistics_snapshots": len(statistics),
                "induction_states": len(inductions),
                "cultural_learning_states": len(cultures),
                "learned_concept_candidates": len(learned_concepts),
                "state_transformation_candidates": len(transformations),
                "soar_transformation_decisions": len(transformation_decisions),
                "memory_consolidation_states": len(consolidations),
                "soar_control_states": len(soar_states),
                "soar_native_control_verified": all(
                    row.payload_native.get("working_memory_verified", False)
                    for row in soar_states
                ),
                "world_commit_performed": False,
                "candidate_selection_performed": False,
                "artifact_count": len(runtime.arena),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
