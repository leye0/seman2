"""Frontière d'ingestion séquentielle des corpus vers le cœur cognitif.

Les métadonnées de sélection et de qualité du corpus ne franchissent jamais
cette frontière. Questions et réponses deviennent uniquement des expériences
discursives ordonnées, destinées aux analyseurs low level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .cognitive_artifacts import (
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    freeze_json,
)
from .cognitive_runtime import CognitiveRuntime
from .cognitive_scheduler import ModuleSpec
from .contracts import ContractError, Envelope, canonical_json


SOURCE_PRODUCER = "corpus-source-reader"
OBSERVER_MODULE = "observation-normalizer"
BUILD = "cognitive-foundation"


@dataclass(frozen=True)
class IngestionPolicy:
    max_records: int = 16
    max_text_chars: int = 5_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_records <= 1_000:
            raise ContractError("ingestion: max_records hors [1,1000]")
        if not 64 <= self.max_text_chars <= 100_000:
            raise ContractError("ingestion: max_text_chars hors [64,100000]")

    @property
    def configuration_digest(self) -> str:
        return hashlib.sha256(
            canonical_json(
                {
                    "max_records": self.max_records,
                    "max_text_chars": self.max_text_chars,
                    "reader": "bounded-sequential",
                    "projection": "source-adapter-owned",
                    "ordering": "source-order",
                }
            ).encode()
        ).hexdigest()


@dataclass(frozen=True)
class IngestionRecord:
    record_id: str
    discourse_id: str
    turn_index: int
    speaker_role: str
    text: str
    canonical_file: str
    source_position: int
    source_record_id: str
    raw_body_sha256: str
    channel: str = "document"
    source_kind: str = "text-segment"
    native_structure: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "discourse_id",
            "speaker_role",
            "text",
            "canonical_file",
            "source_record_id",
            "raw_body_sha256",
            "channel",
            "source_kind",
        ):
            if not str(getattr(self, name)).strip():
                raise ContractError(f"enregistrement d'ingestion: {name} requis")
        if self.turn_index < 0 or self.source_position < 0:
            raise ContractError("enregistrement d'ingestion: index négatif")
        object.__setattr__(
            self, "native_structure", freeze_json(dict(self.native_structure))
        )


def records_from_text_file(
    path: str | Path,
    *,
    policy: IngestionPolicy | None = None,
) -> tuple[IngestionRecord, ...]:
    """Lit au plus N paragraphes en flux, sans charger le document complet."""
    active_policy = policy or IngestionPolicy()
    source_path = Path(path)
    records: list[IngestionRecord] = []
    paragraph_lines: list[str] = []
    paragraph_chars = 0
    paragraph_start = 0
    current_line = 0

    def append_paragraph(end_line: int) -> None:
        nonlocal paragraph_lines, paragraph_start, paragraph_chars
        text = " ".join(part.strip() for part in paragraph_lines if part.strip())
        paragraph_lines = []
        paragraph_chars = 0
        if not text or len(records) >= active_policy.max_records:
            return
        if len(text) > active_policy.max_text_chars:
            raise ContractError(
                f"ingestion texte: paragraphe ligne {paragraph_start} de "
                f"{len(text)} caractères au-delà de {active_policy.max_text_chars}"
            )
        index = len(records)
        source_key = f"{source_path.resolve()}:{paragraph_start}:{end_line}"
        records.append(
            IngestionRecord(
                record_id=f"text:{hashlib.sha256(source_key.encode()).hexdigest()[:24]}",
                discourse_id=f"text:{source_path.stem}",
                turn_index=index,
                speaker_role="narrator",
                text=text,
                canonical_file=str(source_path),
                source_position=paragraph_start,
                source_record_id=f"lines:{paragraph_start}-{end_line}",
                raw_body_sha256=hashlib.sha256(text.encode()).hexdigest(),
                channel="narrative-text",
                source_kind="paragraph",
                native_structure={
                    "line_start": paragraph_start,
                    "line_end": end_line,
                },
            )
        )

    try:
        with source_path.open("r", encoding="utf-8") as handle:
            for current_line, line in enumerate(handle, start=1):
                if len(records) >= active_policy.max_records:
                    break
                if line.strip():
                    if not paragraph_lines:
                        paragraph_start = current_line
                    paragraph_lines.append(line)
                    paragraph_chars += len(line)
                    if paragraph_chars > active_policy.max_text_chars:
                        raise ContractError(
                            f"ingestion texte: paragraphe ligne {paragraph_start} "
                            f"au-delà de {active_policy.max_text_chars} caractères"
                        )
                elif paragraph_lines:
                    append_paragraph(current_line - 1)
            if paragraph_lines and len(records) < active_policy.max_records:
                append_paragraph(current_line)
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"ingestion texte: lecture impossible: {exc}") from exc
    if not records:
        raise ContractError("ingestion texte: aucune observation non vide")
    return tuple(records)


def records_from_dictionary_file(
    path: str | Path,
    *,
    policy: IngestionPolicy | None = None,
    max_line_chars: int = 16_384,
) -> tuple[IngestionRecord, ...]:
    """Lit des sens JSONL comme expériences, sans lookup ni sens préinjecté."""
    active_policy = policy or IngestionPolicy()
    if max_line_chars < 1_024:
        raise ContractError("ingestion dictionnaire: max_line_chars trop petit")
    source_path = Path(path)
    records: list[IngestionRecord] = []
    try:
        with source_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if len(records) >= active_policy.max_records:
                    break
                if len(line) > max_line_chars:
                    raise ContractError(
                        f"ingestion dictionnaire: ligne {line_number} hors borne"
                    )
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ContractError(
                        f"ingestion dictionnaire: JSON invalide ligne {line_number}"
                    ) from exc
                word = str(row.get("word", "")).strip()
                part_of_speech = str(row.get("pos", "unknown")).strip() or "unknown"
                senses = row.get("senses")
                if not word or not isinstance(senses, list):
                    raise ContractError(
                        f"ingestion dictionnaire: structure invalide ligne {line_number}"
                    )
                raw_digest = hashlib.sha256(line.encode()).hexdigest()
                for sense_index, sense in enumerate(senses):
                    if len(records) >= active_policy.max_records:
                        break
                    if not isinstance(sense, Mapping):
                        raise ContractError(
                            f"ingestion dictionnaire: sens invalide ligne {line_number}"
                        )
                    glosses = [
                        str(value).strip()
                        for value in sense.get("glosses", ())
                        if str(value).strip()
                    ]
                    examples = [
                        str(item.get("text", "")).strip()
                        for item in sense.get("examples", ())
                        if isinstance(item, Mapping) and str(item.get("text", "")).strip()
                    ]
                    if not glosses:
                        continue
                    # Le libellé structurel fait partie de l'expérience publiée,
                    # mais aucune relation sémantique interne n'est créée ici.
                    text = " ".join(
                        [f"{word} ({part_of_speech}).", *glosses, *examples]
                    )
                    if len(text) > active_policy.max_text_chars:
                        raise ContractError(
                            f"ingestion dictionnaire: sens ligne {line_number} "
                            f"au-delà de {active_policy.max_text_chars} caractères"
                        )
                    entry_key = f"{source_path.resolve()}:{line_number}:{sense_index}"
                    records.append(
                        IngestionRecord(
                            record_id=(
                                "dictionary:"
                                + hashlib.sha256(entry_key.encode()).hexdigest()[:24]
                            ),
                            discourse_id=f"dictionary-entry:{line_number}:{word}",
                            turn_index=sense_index,
                            speaker_role="lexicographic-source",
                            text=text,
                            canonical_file=str(source_path),
                            source_position=line_number,
                            source_record_id=f"line:{line_number}:sense:{sense_index}",
                            raw_body_sha256=raw_digest,
                            channel="dictionary-corpus",
                            source_kind="dictionary-sense",
                            native_structure={
                                "word": word,
                                "language": row.get("lang"),
                                "language_code": row.get("lang_code"),
                                "part_of_speech": part_of_speech,
                                "sense_index": sense_index,
                                "sense": dict(sense),
                                "forms": row.get("forms", []),
                                "sounds": row.get("sounds", []),
                            },
                        )
                    )
    except (OSError, UnicodeError) as exc:
        raise ContractError(
            f"ingestion dictionnaire: lecture impossible: {exc}"
        ) from exc
    if not records:
        raise ContractError("ingestion dictionnaire: aucune observation")
    return tuple(records)


def records_from_sample_set(
    sample_set: Envelope,
    *,
    policy: IngestionPolicy | None = None,
) -> tuple[IngestionRecord, ...]:
    """Retire labels/votes et ordonne les observations comme discours vécu."""
    if sample_set.kind != "corpus-sample-set":
        raise ContractError(
            f"ingestion attend corpus-sample-set, reçu {sample_set.kind}"
        )
    active_policy = policy or IngestionPolicy()
    records: list[IngestionRecord] = []
    for sample in sample_set.payload.get("samples", ()):
        if len(records) >= active_policy.max_records:
            raise ContractError("ingestion: borne max_records dépassée")
        discourse_id = f"stackoverflow:{sample['question_id']}"
        question_text = "\n".join(
            part.strip()
            for part in (str(sample["title"]), str(sample["text_projection"]))
            if part.strip()
        )
        records.append(
            _record(
                record_id=f"question:{sample['question_id']}",
                discourse_id=discourse_id,
                turn_index=0,
                speaker_role="initiator",
                text=question_text,
                source=sample,
                policy=active_policy,
            )
        )
        answers = sorted(
            sample.get("answers", ()),
            key=lambda row: (
                str(row.get("source_group", "")),
                int(row.get("source_ordinal", 0)),
                str(row["answer_id"]),
            ),
        )
        for turn_index, answer in enumerate(answers, start=1):
            if len(records) >= active_policy.max_records:
                raise ContractError("ingestion: borne max_records dépassée")
            records.append(
                _record(
                    record_id=f"answer:{answer['answer_id']}",
                    discourse_id=discourse_id,
                    turn_index=turn_index,
                    speaker_role="respondent",
                    text=str(answer["text_projection"]),
                    source=answer,
                    policy=active_policy,
                )
            )
    return tuple(records)


def _record(
    *,
    record_id: str,
    discourse_id: str,
    turn_index: int,
    speaker_role: str,
    text: str,
    source: Mapping[str, Any],
    policy: IngestionPolicy,
) -> IngestionRecord:
    if len(text) > policy.max_text_chars:
        raise ContractError(
            f"ingestion: texte {record_id} de {len(text)} caractères au-delà de "
            f"la borne {policy.max_text_chars}"
        )
    return IngestionRecord(
        record_id=record_id,
        discourse_id=discourse_id,
        turn_index=turn_index,
        speaker_role=speaker_role,
        text=text,
        canonical_file=str(source["canonical_file"]),
        source_position=int(source["source_position"]),
        source_record_id=str(source["source_record_id"]),
        raw_body_sha256=str(source["raw_body_sha256"]),
        channel="stackoverflow-discourse",
        source_kind="question" if speaker_role == "initiator" else "response",
        native_structure={
            "record_id": record_id,
            "native_discourse_relation": "thread-membership",
            "raw_html": str(source.get("body", "")),
            "raw_html_preserved": "body" in source,
        },
    )


def build_foundation_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_foundation_types(registry)
    registry.freeze()
    return registry


def register_foundation_types(registry: ArtifactTypeRegistry) -> None:
    """Ajoute les contrats L0/L1 à un registre encore modifiable."""
    registry.register(
        ArtifactTypeSpec(
            artifact_type="source-record",
            schema_id="seman2/source-record",
            layer=0,
            root_allowed=True,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({SOURCE_PRODUCER}),
            required_native_fields=frozenset(
                {
                    "text",
                    "discourse_id",
                    "turn_index",
                    "speaker_role",
                    "channel",
                    "source_kind",
                    "native_structure",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            artifact_type="observation",
            schema_id="seman2/observation",
            layer=1,
            allowed_modes=frozenset({"ingestion"}),
            allowed_producers=frozenset({OBSERVER_MODULE}),
            parent_types=frozenset({"source-record"}),
            required_native_fields=frozenset(
                {
                    "text",
                    "discourse_id",
                    "turn_index",
                    "speaker_role",
                    "channel",
                    "source_kind",
                    "native_structure",
                }
            ),
        )
    )


def build_foundation_modules(policy: IngestionPolicy) -> tuple[ModuleSpec, ...]:
    configuration_digest = policy.configuration_digest

    def normalize(trigger, context):
        native = trigger.payload_native
        yield ArtifactProposal(
            artifact_type="observation",
            producer_id=OBSERVER_MODULE,
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            mode=trigger.mode,
            session_id=trigger.session_id,
            wave=context.scheduled_wave,
            parent_ids=(trigger.artifact_id,),
            observation_refs=(trigger.artifact_id,),
            source_anchors=trigger.source_anchors,
            payload_native={
                "text": native["text"],
                "discourse_id": native["discourse_id"],
                "turn_index": native["turn_index"],
                "speaker_role": native["speaker_role"],
                "channel": native["channel"],
                "source_kind": native["source_kind"],
                "native_structure": native["native_structure"],
            },
            payload_projection={
                "character_count": len(native["text"]),
                "non_empty": bool(native["text"].strip()),
            },
            idempotency_key=f"observation:{trigger.artifact_id}",
        )

    return (
        ModuleSpec(
            module_id=OBSERVER_MODULE,
            layer=1,
            modes=frozenset({"ingestion"}),
            consumes=frozenset({"source-record"}),
            produces=frozenset({"observation"}),
            producer_build=BUILD,
            configuration_digest=configuration_digest,
            handler=normalize,
        ),
    )


def build_foundation_runtime(
    policy: IngestionPolicy | None = None,
) -> CognitiveRuntime:
    active_policy = policy or IngestionPolicy()
    return CognitiveRuntime(
        registry=build_foundation_registry(),
        modules=build_foundation_modules(active_policy),
    )


def ingest_records(
    runtime: CognitiveRuntime,
    records: Iterable[IngestionRecord],
    *,
    policy: IngestionPolicy | None = None,
    session_id: str = "corpus-ingestion",
    starting_wave: int = 0,
) -> dict[str, Any]:
    """Ingère un tour, stabilise sa vague, puis seulement passe au suivant."""
    active_policy = policy or IngestionPolicy()
    configuration_digest = active_policy.configuration_digest
    count = 0
    for record in records:
        count += 1
        if count > active_policy.max_records:
            raise ContractError("ingestion: borne max_records dépassée")
        runtime.submit(
            ArtifactProposal(
                artifact_type="source-record",
                producer_id=SOURCE_PRODUCER,
                producer_build=BUILD,
                configuration_digest=configuration_digest,
                mode="ingestion",
                session_id=session_id,
                wave=starting_wave + count - 1,
                parent_ids=(),
                observation_refs=(record.record_id,),
                source_anchors=(
                    {
                        "canonical_file": record.canonical_file,
                        "source_position": record.source_position,
                        "source_record_id": record.source_record_id,
                        "raw_body_sha256": record.raw_body_sha256,
                    },
                ),
                payload_native={
                    "text": record.text,
                    "discourse_id": record.discourse_id,
                    "turn_index": record.turn_index,
                    "speaker_role": record.speaker_role,
                    "channel": record.channel,
                    "source_kind": record.source_kind,
                    "native_structure": record.native_structure,
                },
                payload_projection={
                    "record_id": record.record_id,
                    "source_kind": record.source_kind,
                },
                idempotency_key=f"source:{record.record_id}",
            )
        )
        runtime.run()
        runtime.consolidate_active_memory()
    observations = runtime.arena.query(
        artifact_type="observation", session_id=session_id
    )
    return {
        "status": "GO-SOURCE-OBSERVATION",
        "records_ingested": count,
        "observations_created": len(observations),
        "pending_tasks": runtime.scheduler.pending_count,
        "highest_wave": max((row.wave for row in observations), default=-1),
        "labels_or_votes_in_cognitive_payload": any(
            forbidden in canonical_json(row.as_dict())
            for row in observations
            for forbidden in (
                "native_vote_score",
                "sampling_rank",
                '"criterion"',
                "accepted_answer",
            )
        ),
    }
