"""Entrée L0, orchestration bornée et ledger L1 du système actif."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any, Iterable

from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    thaw_json,
)
from .contracts import ContractError, canonical_json


GATEWAY_BUILD = "active-experience-gateway"
ORCHESTRATOR_BUILD = "active-analysis-orchestrator"
ACE_WORKER_BUILD = "active-ace-erg-worker"
_SENTENCE_END = re.compile(r"[.!?]+(?:[\"'’”])?(?=\s|$)")
_NONTERMINAL_ABBREVIATIONS = frozenset(
    {
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "sr.",
        "jr.",
        "st.",
        "vs.",
        "e.g.",
        "i.e.",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LowLevelPolicy:
    max_sentence_chars: int = 400
    max_line_chars: int = 16_384
    max_candidates: int = 3
    worker_timeout_seconds: float = 30.0
    worker_memory_mib: int = 1_024
    max_observations_per_wave: int = 32

    def __post_init__(self) -> None:
        if not 1 <= self.max_sentence_chars <= 2_000:
            raise ContractError("SYS-01: max_sentence_chars invalide")
        if self.max_line_chars < self.max_sentence_chars:
            raise ContractError("SYS-01: max_line_chars trop petit")
        if not 1 <= self.max_candidates <= 10:
            raise ContractError("SYS-01: max_candidates invalide")
        if not 0.001 <= self.worker_timeout_seconds <= 120:
            raise ContractError("SYS-01: timeout worker invalide")
        if not 512 <= self.worker_memory_mib <= 4_096:
            raise ContractError("SYS-01: budget mémoire worker invalide")
        if not 1 <= self.max_observations_per_wave <= 1_024:
            raise ContractError("SYS-01: budget d'observations invalide")

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.__dict__).encode()).hexdigest()


def register_low_level_types(registry: ArtifactTypeRegistry) -> None:
    registry.register(
        ArtifactTypeSpec(
            "experience-occurrence",
            "seman2/active/L0/experience-occurrence",
            0,
            root_allowed=True,
            allowed_producers=frozenset({"experience-gateway"}),
            required_native_fields=frozenset(
                {
                    "experience_ref",
                    "source_ref",
                    "source_kind",
                    "sequence_index",
                    "source_sha256",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "observation",
            "seman2/active/L0/observation",
            0,
            allowed_producers=frozenset({"observation-register"}),
            parent_types=frozenset({"experience-occurrence"}),
            required_native_fields=frozenset(
                {
                    "experience_ref",
                    "surface",
                    "span_start",
                    "span_end",
                    "span_unit",
                    "surface_sha256",
                }
            ),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "analysis-contribution",
            "seman2/active/L1/analysis-contribution",
            1,
            allowed_producers=frozenset({"ace-erg-worker"}),
            parent_types=frozenset({"observation"}),
            required_native_fields=frozenset(
                {"formalism", "candidate_index", "worker_status", "native_result"}
            ),
            required_projection_fields=frozenset(
                {"truth_committed", "world_update_performed"}
            ),
        )
    )


def build_low_level_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    register_low_level_types(registry)
    registry.freeze()
    return registry


@dataclass(frozen=True)
class SourceSpan:
    surface: str
    line: int
    character_start: int
    character_end: int
    byte_start: int
    byte_end: int


class ExperienceGateway:
    """Transforme un flux UTF-8 en expériences ordonnées sans connaître le texte."""

    def __init__(
        self,
        arena: ArtifactArena,
        *,
        session_id: str,
        policy: LowLevelPolicy | None = None,
        source_root: str | Path | None = None,
        mode: str = "ingestion",
    ) -> None:
        if mode not in {"ingestion", "chatbot"}:
            raise ContractError(f"gateway: mode invalide {mode!r}")
        self.arena = arena
        self.session_id = session_id
        self.policy = policy or LowLevelPolicy()
        self.source_root = Path(source_root or Path.cwd()).resolve()
        self.mode = mode

    def ingest_file(
        self,
        path: str | Path,
        *,
        experience_prefix: str,
        sequence_start: int = 0,
        source_kind: str = "curriculum-text",
        start_line: int = 1,
        max_observations: int | None = None,
    ) -> tuple[tuple[CognitiveArtifact, CognitiveArtifact], ...]:
        """Segmente un fichier ligne par ligne et publie un échantillon borné."""
        if start_line < 1 or sequence_start < 0:
            raise ContractError("SYS-01: position d'ingestion invalide")
        limit = max_observations or self.policy.max_observations_per_wave
        if not 1 <= limit <= self.policy.max_observations_per_wave:
            raise ContractError("SYS-01: nombre d'observations hors budget")
        source = Path(path)
        source_digest = sha256_file(source)
        source_size = source.stat().st_size
        rows: list[tuple[CognitiveArtifact, CognitiveArtifact]] = []
        byte_cursor = 0
        with source.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if len(raw_line) > self.policy.max_line_chars * 4:
                    raise ContractError(f"SYS-01: ligne {line_number} hors budget")
                if line_number < start_line:
                    byte_cursor += len(raw_line)
                    continue
                text_with_break = raw_line.decode("utf-8", errors="strict")
                text = text_with_break.rstrip("\r\n")
                for span in self._sentence_spans(text, line_number, byte_cursor):
                    if len(span.surface) > self.policy.max_sentence_chars:
                        raise ContractError(
                            f"SYS-01: observation hors budget ligne {line_number}"
                        )
                    sequence = sequence_start + len(rows)
                    ref = (
                        f"{experience_prefix}:{source_digest[:12]}:"
                        f"{span.byte_start}-{span.byte_end}"
                    )
                    rows.append(
                        self._publish_span(
                            source,
                            source_size,
                            source_digest,
                            span,
                            experience_ref=ref,
                            sequence_index=sequence,
                            source_kind=source_kind,
                        )
                    )
                    if len(rows) == limit:
                        return tuple(rows)
                byte_cursor += len(raw_line)
        if not rows:
            raise ContractError("SYS-01: aucune observation dans la fenêtre demandée")
        return tuple(rows)

    def ingest_sentence_from_file(
        self,
        path: str | Path,
        sentence: str,
        *,
        experience_ref: str,
        sequence_index: int,
        source_kind: str = "curriculum-text",
    ) -> tuple[CognitiveArtifact, CognitiveArtifact]:
        """Compatibilité ciblée; SYS-01 utilise désormais ``ingest_file``."""
        if not sentence or len(sentence) > self.policy.max_sentence_chars:
            raise ContractError("SYS-01: phrase vide ou hors budget")
        source = Path(path)
        raw = source.read_bytes()
        needle = sentence.encode("utf-8")
        first = raw.find(needle)
        if first < 0 or raw.find(needle, first + 1) >= 0:
            raise ContractError("SYS-01: phrase source absente ou non unique")
        prefix = raw[:first]
        line = prefix.count(b"\n") + 1
        line_start = prefix.rfind(b"\n") + 1
        character_start = len(raw[line_start:first].decode("utf-8"))
        span = SourceSpan(
            sentence,
            line,
            character_start,
            character_start + len(sentence),
            first,
            first + len(needle),
        )
        return self._publish_span(
            source,
            len(raw),
            hashlib.sha256(raw).hexdigest(),
            span,
            experience_ref=experience_ref,
            sequence_index=sequence_index,
            source_kind=source_kind,
        )

    def ingest_dialogue_tsv(
        self,
        path: str | Path,
        *,
        dialogue_ref: str,
        experience_prefix: str,
        sequence_start: int = 0,
        max_turns: int | None = None,
    ) -> tuple[tuple[CognitiveArtifact, CognitiveArtifact], ...]:
        """Ingest ``speaker<TAB>surface`` turns without mixing metadata into text."""
        if not dialogue_ref.strip() or sequence_start < 0:
            raise ContractError("dialogue L0: référence ou position invalide")
        limit = max_turns or self.policy.max_observations_per_wave
        if not 1 <= limit <= self.policy.max_observations_per_wave:
            raise ContractError("dialogue L0: nombre de tours hors budget")
        source = Path(path)
        source_digest = sha256_file(source)
        source_size = source.stat().st_size
        rows: list[tuple[CognitiveArtifact, CognitiveArtifact]] = []
        byte_cursor = 0
        with source.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if len(raw_line) > self.policy.max_line_chars * 4:
                    raise ContractError(f"dialogue L0: ligne {line_number} hors budget")
                raw_content = raw_line.rstrip(b"\r\n")
                if not raw_content:
                    byte_cursor += len(raw_line)
                    continue
                if b"\t" not in raw_content:
                    raise ContractError(f"dialogue L0: séparateur absent ligne {line_number}")
                raw_speaker, raw_surface = raw_content.split(b"\t", 1)
                try:
                    speaker = raw_speaker.decode("utf-8", errors="strict").strip()
                    surface = raw_surface.decode("utf-8", errors="strict").strip()
                except UnicodeDecodeError as exc:
                    raise ContractError(f"dialogue L0: UTF-8 invalide ligne {line_number}") from exc
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", speaker):
                    raise ContractError(f"dialogue L0: locuteur invalide ligne {line_number}")
                if not surface or len(surface) > self.policy.max_sentence_chars:
                    raise ContractError(f"dialogue L0: surface hors budget ligne {line_number}")
                leading = len(raw_surface) - len(raw_surface.lstrip())
                surface_bytes = surface.encode("utf-8")
                relative_start = len(raw_speaker) + 1 + leading
                span = SourceSpan(
                    surface=surface,
                    line=line_number,
                    character_start=len(raw_content[:relative_start].decode("utf-8")),
                    character_end=len(raw_content[:relative_start].decode("utf-8")) + len(surface),
                    byte_start=byte_cursor + relative_start,
                    byte_end=byte_cursor + relative_start + len(surface_bytes),
                )
                sequence = sequence_start + len(rows)
                experience_ref = (
                    f"{experience_prefix}:{source_digest[:12]}:"
                    f"{span.byte_start}-{span.byte_end}"
                )
                rows.append(
                    self._publish_span(
                        source,
                        source_size,
                        source_digest,
                        span,
                        experience_ref=experience_ref,
                        sequence_index=sequence,
                        source_kind="dialogue-turn-tsv",
                        experience_metadata={
                            "channel": "dialogue",
                            "dialogue_ref": dialogue_ref,
                            "turn_index": len(rows),
                            "speaker_ref": f"speaker:{speaker}",
                            "participant_refs": [f"speaker:{speaker}"],
                        },
                    )
                )
                if len(rows) == limit:
                    return tuple(rows)
                byte_cursor += len(raw_line)
        if not rows:
            raise ContractError("dialogue L0: aucun tour")
        return tuple(rows)

    @staticmethod
    def _sentence_spans(
        text: str, line: int, line_byte_start: int
    ) -> tuple[SourceSpan, ...]:
        rows: list[SourceSpan] = []
        cursor = 0
        ends = [
            match.end()
            for match in _SENTENCE_END.finditer(text)
            if not ExperienceGateway._is_nonterminal_abbreviation(text, match.start())
        ]
        if text[cursor:].strip() and (not ends or text[ends[-1] :].strip()):
            ends.append(len(text))
        for original_end in ends:
            end = original_end
            start = cursor
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                byte_start = line_byte_start + len(text[:start].encode("utf-8"))
                byte_end = line_byte_start + len(text[:end].encode("utf-8"))
                rows.append(
                    SourceSpan(text[start:end], line, start, end, byte_start, byte_end)
                )
            cursor = original_end
        return tuple(rows)

    @staticmethod
    def _is_nonterminal_abbreviation(text: str, period_index: int) -> bool:
        if text[period_index] != ".":
            return False
        prefix = text[: period_index + 1]
        match = re.search(r"(?:[A-Za-z]\.){1,3}$|[A-Za-z]+\.$", prefix)
        if not match:
            return False
        token = match.group(0)
        return token.lower() in _NONTERMINAL_ABBREVIATIONS or bool(
            re.fullmatch(r"[A-Z]\.", token)
        )

    def _logical_path(self, source: Path) -> str:
        resolved = source.resolve()
        try:
            return resolved.relative_to(self.source_root).as_posix()
        except ValueError as exc:
            raise ContractError("SYS-01: source hors de la racine autorisée") from exc

    def _publish_span(
        self,
        source: Path,
        source_size: int,
        source_digest: str,
        span: SourceSpan,
        *,
        experience_ref: str,
        sequence_index: int,
        source_kind: str,
        experience_metadata: dict[str, Any] | None = None,
    ) -> tuple[CognitiveArtifact, CognitiveArtifact]:
        if sequence_index < 0:
            raise ContractError("SYS-01: sequence_index négatif")
        surface_bytes = span.surface.encode("utf-8")
        with source.open("rb") as handle:
            handle.seek(span.byte_start)
            source_slice = handle.read(span.byte_end - span.byte_start)
        if source_slice != surface_bytes:
            raise ContractError("SYS-01: la surface ne correspond pas aux octets source")
        logical_path = self._logical_path(source)
        surface_digest = hashlib.sha256(surface_bytes).hexdigest()
        source_ref = f"source:sha256:{source_digest}"
        anchor = {
            "source_path": logical_path,
            "source_sha256": source_digest,
            "line": span.line,
            "character_start": span.character_start,
            "character_end": span.character_end,
            "byte_start": span.byte_start,
            "byte_end": span.byte_end,
            "surface_sha256": surface_digest,
        }
        base_cost = {
            "source_bytes": source_size,
            "surface_bytes": len(surface_bytes),
        }
        experience = self.arena.publish(
            ArtifactProposal(
                artifact_type="experience-occurrence",
                producer_id="experience-gateway",
                producer_build=GATEWAY_BUILD,
                configuration_digest=self.policy.digest,
                mode=self.mode,
                session_id=self.session_id,
                wave=0,
                parent_ids=(),
                source_anchors=(anchor,),
                resource_cost=base_cost,
                payload_native={
                    "experience_ref": experience_ref,
                    "source_ref": source_ref,
                    "source_kind": source_kind,
                    "sequence_index": sequence_index,
                    "source_sha256": source_digest,
                    **(experience_metadata or {}),
                },
                payload_projection={"content_interpreted": False},
                idempotency_key=f"experience:{experience_ref}",
            )
        )
        observation = self.arena.publish(
            ArtifactProposal(
                artifact_type="observation",
                producer_id="observation-register",
                producer_build=GATEWAY_BUILD,
                configuration_digest=self.policy.digest,
                mode=self.mode,
                session_id=self.session_id,
                wave=0,
                parent_ids=(experience.artifact_id,),
                observation_refs=(experience_ref,),
                source_anchors=(anchor,),
                resource_cost={"surface_bytes": len(surface_bytes)},
                payload_native={
                    "experience_ref": experience_ref,
                    "surface": span.surface,
                    "span_start": span.byte_start,
                    "span_end": span.byte_end,
                    "span_unit": "utf8-byte-in-source",
                    "surface_sha256": surface_digest,
                },
                payload_projection={"surface_preserved": True},
                idempotency_key=f"observation:{experience_ref}",
            )
        )
        return experience, observation


@dataclass(frozen=True)
class ClosedAnalysisLedger:
    wave: int
    contribution_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    route_decisions: tuple[dict[str, Any], ...]
    closed: bool
    ledger_digest: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "wave": self.wave,
            "observations": list(self.observation_ids),
            "contributions": list(self.contribution_ids),
            "routes": list(self.route_decisions),
            "closed": self.closed,
        }

    def recompute_digest(self) -> str:
        return hashlib.sha256(
            canonical_json(self.integrity_payload()).encode()
        ).hexdigest()

    def validate_integrity(self) -> None:
        if not self.closed:
            raise ContractError("SYS-01: ledger L1 non fermé")
        if self.wave < 1:
            raise ContractError("SYS-01: vague de ledger invalide")
        if not self.observation_ids or not self.contribution_ids:
            raise ContractError("SYS-01: ledger L1 vide")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ContractError("SYS-01: observation dupliquée dans le ledger")
        if len(set(self.contribution_ids)) != len(self.contribution_ids):
            raise ContractError("SYS-01: contribution dupliquée dans le ledger")
        if len(self.route_decisions) != len(self.observation_ids):
            raise ContractError("SYS-01: couverture de routage incomplète")

        routed_observations: list[str] = []
        routed_contributions: list[str] = []
        for route in self.route_decisions:
            if not isinstance(route, dict):
                raise ContractError("SYS-01: décision de routage invalide")
            observation_ref = route.get("observation_ref")
            contribution_refs = route.get("contribution_refs")
            if not isinstance(observation_ref, str) or not isinstance(
                contribution_refs, list
            ):
                raise ContractError("SYS-01: décision de routage incomplète")
            if not contribution_refs or any(
                not isinstance(ref, str) for ref in contribution_refs
            ):
                raise ContractError("SYS-01: route sans contribution explicite")
            routed_observations.append(observation_ref)
            routed_contributions.extend(contribution_refs)

        if tuple(routed_observations) != self.observation_ids:
            raise ContractError("SYS-01: ordre de routage incohérent")
        if tuple(routed_contributions) != self.contribution_ids:
            raise ContractError("SYS-01: contributions de routage incohérentes")
        if self.recompute_digest() != self.ledger_digest:
            raise ContractError("SYS-01: digest du ledger L1 invalide")

    def as_dict(self) -> dict[str, Any]:
        return {
            "wave": self.wave,
            "contribution_ids": list(self.contribution_ids),
            "observation_ids": list(self.observation_ids),
            "route_decisions": list(self.route_decisions),
            "closed": self.closed,
            "ledger_digest": self.ledger_digest,
        }


class AnalysisOrchestrator:
    """Route chaque observation, conserve les échecs puis ferme la vague."""

    def __init__(self, *, policy: LowLevelPolicy | None = None) -> None:
        self.policy = policy or LowLevelPolicy()

    def execute(
        self,
        observations: Iterable[CognitiveArtifact],
        analyzer: "AceErgAnalyzer",
        *,
        wave: int = 1,
    ) -> tuple[ClosedAnalysisLedger, tuple[CognitiveArtifact, ...]]:
        rows = tuple(observations)
        if not rows or len(rows) > self.policy.max_observations_per_wave:
            raise ContractError("SYS-01: vague vide ou hors budget")
        if any(row.artifact_type != "observation" for row in rows):
            raise ContractError("SYS-01: l'orchestrateur exige des observations L0")
        contributions: list[CognitiveArtifact] = []
        routes: list[dict[str, Any]] = []
        for observation in rows:
            produced = analyzer.analyze(observation)
            if not produced:
                raise ContractError("SYS-01: worker sans contribution explicite")
            contributions.extend(produced)
            routes.append(
                {
                    "observation_ref": observation.artifact_id,
                    "analyzer": "ACE+ERG",
                    "applicable": True,
                    "contribution_refs": [row.artifact_id for row in produced],
                    "reason_if_ignored": None,
                }
            )
        payload = {
            "wave": wave,
            "observations": [row.artifact_id for row in rows],
            "contributions": [row.artifact_id for row in contributions],
            "routes": routes,
            "closed": True,
        }
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        ledger = ClosedAnalysisLedger(
            wave,
            tuple(row.artifact_id for row in contributions),
            tuple(row.artifact_id for row in rows),
            tuple(routes),
            True,
            digest,
        )
        ledger.validate_integrity()
        return ledger, tuple(contributions)


class AceErgAnalyzer:
    def __init__(
        self,
        arena: ArtifactArena,
        *,
        project_root: str | Path,
        policy: LowLevelPolicy | None = None,
        ace_executable: str | Path | None = None,
        erg_grammar: str | Path | None = None,
    ) -> None:
        self.arena = arena
        self.root = Path(project_root)
        self.policy = policy or LowLevelPolicy()
        self.ace_executable = Path(ace_executable or self.root / ".local/bin/ace")
        self.erg_grammar = Path(
            erg_grammar
            or self.root / ".local/share/erg/erg-2018-x86-64-0.9.34.dat"
        )
        tool_identity = {
            "policy": self.policy.__dict__,
            "ace_sha256": sha256_file(self.ace_executable)
            if self.ace_executable.is_file()
            else "missing",
            "erg_sha256": sha256_file(self.erg_grammar)
            if self.erg_grammar.is_file()
            else "missing",
        }
        self.configuration_digest = hashlib.sha256(
            canonical_json(tool_identity).encode()
        ).hexdigest()

    def analyze(self, observation: CognitiveArtifact) -> tuple[CognitiveArtifact, ...]:
        if observation.artifact_type != "observation":
            raise ContractError("SYS-01: ACE exige une observation L0")
        native = thaw_json(observation.payload_native)
        request = {
            "text": native["surface"],
            "max_candidates": self.policy.max_candidates,
            "memory_limit_mib": self.policy.worker_memory_mib,
            "ace_executable": str(self.ace_executable),
            "erg_grammar": str(self.erg_grammar),
        }
        command = [sys.executable, "-m", "seman2_runtime.workers.ace_worker"]
        started = time.perf_counter()
        process = subprocess.Popen(
            command,
            cwd=self.root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(
                json.dumps(request, ensure_ascii=False),
                timeout=self.policy.worker_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            return (
                self._publish_failure(
                    observation,
                    "timeout",
                    "worker exceeded configured deadline",
                    resource_cost={
                        "wall_time_ms": elapsed_ms,
                        "timeout_seconds": self.policy.worker_timeout_seconds,
                        "memory_limit_mib": self.policy.worker_memory_mib,
                        "process_group_killed": True,
                    },
                ),
            )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if process.returncode:
            return (
                self._publish_failure(
                    observation,
                    "process-failure",
                    "worker exited non-zero; diagnostic retained outside cognitive stock",
                    resource_cost={
                        "wall_time_ms": elapsed_ms,
                        "memory_limit_mib": self.policy.worker_memory_mib,
                        "exit_code": process.returncode,
                    },
                ),
            )
        try:
            response: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return (
                self._publish_failure(
                    observation,
                    "invalid-worker-json",
                    str(exc),
                    resource_cost={"wall_time_ms": elapsed_ms},
                ),
            )
        cost = {
            "wall_time_ms": elapsed_ms,
            "worker_wall_time_ms": response.get("worker_wall_time_ms"),
            "worker_peak_rss_kib": response.get("worker_peak_rss_kib"),
            "ace_peak_rss_kib": response.get("ace_peak_rss_kib"),
            "memory_limit_mib": self.policy.worker_memory_mib,
            "candidate_limit": self.policy.max_candidates,
        }
        candidates = response.get("candidates", [])
        if not candidates:
            return (
                self._publish_failure(
                    observation,
                    str(response.get("status", "no-parse")),
                    "ACE/ERG returned no analysis",
                    worker_response=response,
                    resource_cost=cost,
                ),
            )
        rows = []
        for index, candidate in enumerate(candidates):
            rows.append(
                self.arena.publish(
                    ArtifactProposal(
                        artifact_type="analysis-contribution",
                        producer_id="ace-erg-worker",
                        producer_build=str(
                            response.get("analyzer_version", ACE_WORKER_BUILD)
                        ),
                        configuration_digest=self.configuration_digest,
                        mode=observation.mode,
                        session_id=observation.session_id,
                        wave=1,
                        parent_ids=(observation.artifact_id,),
                        observation_refs=observation.observation_refs,
                        source_anchors=tuple(
                            thaw_json(row) for row in observation.source_anchors
                        ),
                        resource_cost=cost,
                        payload_native={
                            "formalism": "ERG-MRS",
                            "candidate_index": index,
                            "worker_status": response["status"],
                            "native_result": candidate,
                        },
                        payload_projection={
                            "truth_committed": False,
                            "world_update_performed": False,
                        },
                        status=ArtifactStatus.SUCCESS,
                        idempotency_key=(
                            f"{observation.artifact_id}:ace:"
                            f"{self.configuration_digest}:{index}"
                        ),
                    )
                )
            )
        return tuple(rows)

    def _publish_failure(
        self,
        observation: CognitiveArtifact,
        status: str,
        detail: str,
        *,
        worker_response: dict[str, Any] | None = None,
        resource_cost: dict[str, Any] | None = None,
    ) -> CognitiveArtifact:
        response = dict(worker_response or {})
        response.pop("candidates", None)
        response.pop("worker_wall_time_ms", None)
        response.pop("worker_peak_rss_kib", None)
        response.pop("ace_peak_rss_kib", None)
        return self.arena.publish(
            ArtifactProposal(
                artifact_type="analysis-contribution",
                producer_id="ace-erg-worker",
                producer_build=str(response.get("analyzer_version", ACE_WORKER_BUILD)),
                configuration_digest=self.configuration_digest,
                mode=observation.mode,
                session_id=observation.session_id,
                wave=1,
                parent_ids=(observation.artifact_id,),
                observation_refs=observation.observation_refs,
                source_anchors=tuple(
                    thaw_json(row) for row in observation.source_anchors
                ),
                resource_cost=resource_cost or {},
                payload_native={
                    "formalism": "ERG-MRS",
                    "candidate_index": None,
                    "worker_status": status,
                    "native_result": response,
                    "failure_detail": detail,
                },
                payload_projection={
                    "truth_committed": False,
                    "world_update_performed": False,
                },
                status=ArtifactStatus.FAILURE,
                losses=("no-grammatical-analysis",),
                idempotency_key=(
                    f"{observation.artifact_id}:ace:"
                    f"{self.configuration_digest}:failure"
                ),
            )
        )


def lineage_manifest(
    arena: ArtifactArena,
    *,
    real_source_refs: list[str],
    causal_effects: list[dict[str, Any]],
) -> dict[str, Any]:
    level_by_type = {
        "experience-occurrence": "L0",
        "observation": "L0",
        "analysis-contribution": "L1",
        "composed-candidate": "L2",
        "situation-branch-set": "L3",
        "episode-memory": "L4",
        "transformation-episode": "L4",
        "memory-admission": "L4",
        "learned-transformation": "L5",
        "learned-transformation-contribution": "L2",
        "transformation-expectation-set": "L3",
        "temporal-analysis": "L3",
        "temporal-branch-set": "L3",
        "temporal-memory": "L4",
        "identity-mention-candidate": "L2",
        "identity-beam": "L3",
        "discourse-memory": "L4",
        "control-goal": "L4",
        "retrieval-result": "L4",
        "soar-control-decision": "L6",
        "concept-application-goal": "L5",
        "concept-match-retrieval": "L5",
        "soar-concept-decision": "L6",
        "learned-concept-contribution": "L2",
        "concept-expectation-set": "L3",
        "concept-feedback-episode": "L4",
        "recursive-learned-concept": "L5",
        "dialogue-turn-content": "L3",
        "dialogue-control-goal": "L4",
        "soar-dialogue-decision": "L6",
        "dialogue-state": "L4",
        "internal-memory-retrieval": "L5",
        "response-control-goal": "L6",
        "soar-response-decision": "L6",
        "communicative-plan": "L6",
        "realized-turn": "L7",
        "reingested-experience": "L0",
        "reingested-observation": "L0",
    }
    artifacts = arena.query()
    return {
        "architecture": "plans/architecture_cognitive_developpementale.md",
        "artifact_levels": sorted(
            {level_by_type[row.artifact_type] for row in artifacts}
        ),
        "real_source_refs": real_source_refs,
        "causal_effects": causal_effects,
        "artifacts": [
            {
                "artifact_id": row.artifact_id,
                "artifact_type": row.artifact_type,
                "producer_id": row.producer_id,
                "producer_revision": row.producer_build,
                "content_digest": row.content_sha256,
                "parent_artifact_refs": list(row.parent_ids),
                "observation_refs": list(row.observation_refs),
                "context_refs": list(row.context_refs),
                "status": row.status.value,
                "wave": row.wave,
                "resource_cost": thaw_json(row.resource_cost),
                "source_anchors": [
                    thaw_json(anchor) for anchor in row.source_anchors
                ],
            }
            for row in artifacts
        ],
    }
