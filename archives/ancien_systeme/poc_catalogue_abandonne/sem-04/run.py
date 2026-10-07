#!/usr/bin/env python3
"""SEM-04: scored n-best Phonetisaurus G2P with decode alignments/lattices."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import time

import phonetisaurus
import pynini

from seman2_runtime.cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    thaw_json,
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
CMUDICT = ROOT / ".local/share/nltk_data/corpora/cmudict/cmudict"
BUILD = "sem-04-integrated-phonetisaurus"


def load_training_lexicon(limit: int, held_out: set[str]) -> dict[str, list[list[str]]]:
    lexicon: defaultdict[str, list[list[str]]] = defaultdict(list)
    for line in CMUDICT.read_text(encoding="latin-1").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        word = parts[0].lower()
        if word.isalpha() and word not in held_out:
            lexicon[word].append(parts[2:])
        if len(lexicon) >= limit:
            break
    return dict(lexicon)


def decode_candidates(
    word: str,
    *,
    model: Path,
    nbest: int,
    lattice_directory: Path,
) -> tuple[list[dict], dict]:
    binary_root = Path(phonetisaurus.__file__).parent / "bin/x86_64"
    executable = binary_root / "phonetisaurus-g2pfst"
    environment = phonetisaurus.guess_environment()
    completed = subprocess.run(
        [
            str(executable),
            f"--model={model.resolve()}",
            f"--word={word}",
            f"--nbest={nbest}",
            "--print_scores=true",
            "--write_fsts=true",
        ],
        cwd=lattice_directory,
        text=True,
        capture_output=True,
        timeout=30,
        env=environment,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    lattice_path = lattice_directory / f"{word}.lat.fst"
    decoded_path = lattice_directory / f"{word}.fst"
    if not lattice_path.is_file() or not decoded_path.is_file():
        raise AssertionError(f"decode lattice absent for {word}")
    lattice = pynini.Fst.read(str(lattice_path))
    input_symbols = lattice.input_symbols()
    output_symbols = lattice.output_symbols()
    assert input_symbols is not None and output_symbols is not None
    lattice_paths = list(
        lattice.paths(
            input_token_type=input_symbols,
            output_token_type=output_symbols,
        ).items()
    )

    candidates = []
    for rank, line in enumerate(completed.stdout.splitlines(), start=1):
        fields = line.strip().split("\t")
        if not fields:
            continue
        assert len(fields) == 3 and fields[0] == word, line
        score = float(fields[1])
        phones = fields[2].split()
        aligned = [
            row
            for row in lattice_paths
            if [
                phone
                for group in row[1].split()
                for phone in group.split("|")
                if phone != "_"
            ]
            == phones
        ]
        assert aligned, (word, phones)
        grapheme_alignment, phone_alignment, lattice_score = min(
            aligned, key=lambda row: float(str(row[2]))
        )
        lattice_score_value = float(str(lattice_score))
        assert math.isclose(score, lattice_score_value, abs_tol=1e-3)
        grapheme_groups = grapheme_alignment.split()
        phone_groups = phone_alignment.split()
        assert len(grapheme_groups) == len(phone_groups)
        reconstructed = "".join(grapheme_groups).replace("|", "").replace("_", "")
        assert reconstructed == word
        flattened_phones = [
            phone
            for group in phone_groups
            for phone in group.split("|")
            if phone != "_"
        ]
        assert flattened_phones == phones
        candidates.append(
            {
                "rank": rank,
                "phonemes": phones,
                "score": score,
                "score_kind": "tropical_negative_log_lower_is_better",
                "alignment": [
                    {"graphemes": graphemes, "phonemes": aligned_phones}
                    for graphemes, aligned_phones in zip(
                        grapheme_groups, phone_groups, strict=True
                    )
                ],
                "producer": "phonetisaurus-g2pfst",
            }
        )
    assert len(candidates) >= 2
    assert all(
        left["score"] <= right["score"]
        for left, right in zip(candidates, candidates[1:])
    )
    lattice_metadata = {
        "path": str(lattice_path.relative_to(ROOT)),
        "sha256": hashlib.sha256(lattice_path.read_bytes()).hexdigest(),
        "bytes": lattice_path.stat().st_size,
        "state_count": lattice.num_states(),
        "path_count": len(lattice_paths),
        "input_symbol_checksum_hex": input_symbols.labeled_checksum().hex(),
        "output_symbol_checksum_hex": output_symbols.labeled_checksum().hex(),
        "decoded_fst_path": str(decoded_path.relative_to(ROOT)),
        "stderr": completed.stderr.strip(),
    }
    return candidates, lattice_metadata


def build_runtime(predictions: dict[str, dict], digest: str) -> CognitiveRuntime:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.register(
        ArtifactTypeSpec(
            artifact_type="g2p-candidate-analysis",
            schema_id="seman2/g2p-candidate-analysis",
            layer=2,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({"phonetisaurus-g2p-analyzer"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {"source_text", "source_sha256", "candidates", "decode_lattice"}
            ),
            required_projection_fields=frozenset(
                {"source_rewritten", "pronunciation_selected", "candidate_count"}
            ),
        )
    )
    registry.freeze()

    def analyze(trigger, context):
        word = str(trigger.payload_native["text"])
        prediction = predictions[word]
        yield ArtifactProposal(
            artifact_type="g2p-candidate-analysis",
            producer_id="phonetisaurus-g2p-analyzer",
            producer_build=BUILD,
            configuration_digest=digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=trigger.observation_refs,
            source_anchors=trigger.source_anchors,
            payload_native={
                "source_text": word,
                "source_sha256": hashlib.sha256(word.encode()).hexdigest(),
                "candidates": prediction["candidates"],
                "decode_lattice": prediction["decode_lattice"],
            },
            payload_projection={
                "candidate_count": len(prediction["candidates"]),
                "source_rewritten": False,
                "pronunciation_selected": False,
            },
            justification_ids=(trigger.artifact_id,),
            idempotency_key=f"phonetisaurus-g2p:{trigger.artifact_id}",
        )

    policy = IngestionPolicy(max_records=32, max_text_chars=1_000)
    return CognitiveRuntime(
        registry=registry,
        modules=(
            *build_foundation_modules(policy),
            ModuleSpec(
                module_id="phonetisaurus-g2p-analyzer",
                layer=2,
                modes=frozenset({"ingestion"}),
                consumes=frozenset({"observation"}),
                produces=frozenset({"g2p-candidate-analysis"}),
                producer_build=BUILD,
                configuration_digest=digest,
                handler=analyze,
            ),
        ),
    )


def main() -> None:
    configuration = json.loads((POC / "fixtures.json").read_text(encoding="utf-8"))
    held_out = set(configuration["held_out_words"])
    lexicon = load_training_lexicon(configuration["training_entry_limit"], held_out)
    assert held_out.isdisjoint(lexicon)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = OUTPUT / "phonetisaurus-model.fst"
    corpus = OUTPUT / "phonetisaurus-model.corpus"
    lattice_directory = OUTPUT / "lattices"
    if lattice_directory.exists():
        shutil.rmtree(lattice_directory)
    lattice_directory.mkdir()

    started = time.perf_counter()
    phonetisaurus.train(lexicon, model, corpus)
    training_seconds = time.perf_counter() - started
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)

    predictions: dict[str, dict] = {}
    started = time.perf_counter()
    for word in configuration["held_out_words"]:
        candidates, lattice = decode_candidates(
            word,
            model=model,
            nbest=configuration["nbest"],
            lattice_directory=lattice_directory,
        )
        predictions[word] = {
            "word": word,
            "candidates": candidates,
            "decode_lattice": lattice,
        }
    prediction_seconds = time.perf_counter() - started

    configuration_digest = hashlib.sha256(
        canonical_json(
            {
                "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                "nbest": configuration["nbest"],
                "held_out_words": configuration["held_out_words"],
            }
        ).encode()
    ).hexdigest()
    runtime = build_runtime(predictions, configuration_digest)
    records = tuple(
        IngestionRecord(
            record_id=f"sem-04:{word}",
            discourse_id="sem-04:held-out-g2p",
            turn_index=index,
            speaker_role="fixture-source",
            text=word,
            canonical_file=str((POC / "fixtures.json").relative_to(ROOT)),
            source_position=index,
            source_record_id=f"held-out:{word}",
            raw_body_sha256=hashlib.sha256(word.encode()).hexdigest(),
            channel="controlled-written-form",
            source_kind="written-form",
            native_structure={"fixture_id": f"sem-04-{index}"},
        )
        for index, word in enumerate(configuration["held_out_words"])
    )
    report = ingest_records(
        runtime,
        records,
        policy=IngestionPolicy(max_records=32, max_text_chars=1_000),
        session_id="sem-04:integration",
    )
    analyses = runtime.arena.query(artifact_type="g2p-candidate-analysis")
    assert len(analyses) == len(records)
    assert report["pending_tasks"] == 0

    results = []
    for word, analysis in zip(configuration["held_out_words"], analyses, strict=True):
        ancestry = runtime.arena.ancestry(analysis.artifact_id)
        assert {row.artifact_type for row in ancestry} == {
            "source-record",
            "observation",
            "g2p-candidate-analysis",
        }
        assert analysis.payload_native["source_text"] == word
        assert len(analysis.payload_native["candidates"]) >= 2
        assert all(row["score"] is not None for row in analysis.payload_native["candidates"])
        assert all(row["alignment"] for row in analysis.payload_native["candidates"])
        assert not analysis.payload_projection["source_rewritten"]
        assert not analysis.payload_projection["pronunciation_selected"]
        results.append(
            {
                "word": word,
                "in_training_lexicon": word in lexicon,
                "candidates": thaw_json(analysis.payload_native["candidates"]),
                "candidate_count": len(analysis.payload_native["candidates"]),
                "n_best_available": True,
                "scores_exposed": True,
                "candidate_alignments_exposed": True,
                "decode_lattice": thaw_json(analysis.payload_native["decode_lattice"]),
                "runtime_artifact_id": analysis.artifact_id,
                "causal_ancestry_types": [row.artifact_type for row in ancestry],
                "source_reconstructed": True,
            }
        )

    sem01 = ROOT / "poc/sem-01/output/results.json"
    sem03 = ROOT / "poc/sem-03/output/results.json"
    assert sem01.is_file() and sem03.is_file()
    comparison = {
        "epitran": "attributed deterministic transliteration without learned n-best costs",
        "pynini_sem_03": "explicit authored form relations with composable rule weights",
        "phonetisaurus": "trained G2P with scored n-best candidates, alignments, and decode lattice",
        "sem_01_sha256": hashlib.sha256(sem01.read_bytes()).hexdigest(),
        "sem_03_sha256": hashlib.sha256(sem03.read_bytes()).hexdigest(),
        "automatic_semantic_identity": False,
    }
    summary = {
        "training_lexeme_count": len(lexicon),
        "held_out_count": len(results),
        "all_held_out": all(not row["in_training_lexicon"] for row in results),
        "all_have_multiple_candidates": all(row["n_best_available"] for row in results),
        "all_have_scores": all(row["scores_exposed"] for row in results),
        "all_have_candidate_alignments": all(
            row["candidate_alignments_exposed"] for row in results
        ),
        "all_have_decode_lattices": all(
            Path(ROOT / row["decode_lattice"]["path"]).is_file() for row in results
        ),
        "runtime_source_observation_chain_passed": True,
        "training_seconds": training_seconds,
        "prediction_seconds": prediction_seconds,
        "child_max_rss_kib": child_usage.ru_maxrss,
        "model_bytes": model.stat().st_size,
        "verdict": "GO_SCORED_ALIGNED_NBEST_G2P_WITH_DECODE_LATTICES",
    }
    assert all(
        summary[field]
        for field in (
            "all_held_out",
            "all_have_multiple_candidates",
            "all_have_scores",
            "all_have_candidate_alignments",
            "all_have_decode_lattices",
            "runtime_source_observation_chain_passed",
        )
    )
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "phonetisaurus": importlib.metadata.version("phonetisaurus"),
        "pynini": importlib.metadata.version("pynini"),
        "cmudict_sha256": hashlib.sha256(CMUDICT.read_bytes()).hexdigest(),
        "training_selection": "first alphabetic CMUdict lexemes excluding held-out words",
        "nbest": configuration["nbest"],
        "model_format": "OpenFst WFST",
        "decoder": "phonetisaurus-g2pfst --write_fsts",
        "artifact_contract": "seman2/g2p-candidate-analysis",
    }
    for name, value in (
        ("results.json", {"analyses": results, "comparison": comparison}),
        ("summary.json", summary),
        ("versions-and-parameters.json", versions),
        ("training-lexicon.json", lexicon),
    ):
        (OUTPUT / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"SEM-04: {len(lexicon)} training lexemes; {len(results)} held out; "
        "scored n-best + alignments + lattices + runtime ancestry; GO"
    )


if __name__ == "__main__":
    main()
