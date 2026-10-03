"""Orchestration vérifiable de la chaîne d'intégration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .contracts import ContractError, Envelope
from .services import (
    AnalysisService,
    DecisionService,
    DialogueStateService,
    HypothesisService,
    ObservationService,
    PlanningService,
    RetrievalService,
    SemanticProjectionService,
    Service,
    SimpleNLGService,
    TemporalContextService,
)


@dataclass
class PipelineResult:
    final: Envelope
    trace: tuple[Envelope, ...]

    def as_dict(self) -> dict:
        by_kind = {message.kind: message for message in self.trace}
        return {
            "status": "GO",
            "final": self.final.as_dict(),
            "trace": [message.as_dict() for message in self.trace],
            "checks": {
                "correlation_preserved": len({x.correlation_id for x in self.trace}) == 1,
                "causal_chain_complete": all(
                    previous.message_id in current.parent_ids
                    for previous, current in zip(self.trace, self.trace[1:])
                ),
                "all_boundaries_attributed": all(x.producer for x in self.trace),
                "all_messages_integrity_tagged": all(len(x.sha256) == 64 for x in self.trace),
                "native_analyses_not_fused": by_kind["analysis-bundle"].payload["semantic_fusion"] is False,
                "temporal_relations_are_formal": all(
                    row["formalism"] == "Reichenbach E/R/S"
                    for row in by_kind["temporally-qualified-candidates"].payload["constraints"]
                ),
                "no_absolute_time_invented": by_kind["temporally-qualified-candidates"].payload["absolute_coordinate_invented"] is False,
                "persistent_alternatives_retained": len(by_kind["active-beam"].payload["persistent"]) == 3,
                "active_beam_bounded": len(by_kind["active-beam"].payload["active"]) <= by_kind["active-beam"].payload["bound"],
                "surface_content_linked": self.final.payload["content_id"]
                    == by_kind["communicative-plan"].payload["ordered_content"][0]["content_id"],
                "surface_added_no_content": self.final.payload["added_content"] == [],
            },
        }


class IntegrationPipeline:
    def __init__(self, services: Iterable[Service]) -> None:
        self.services = tuple(services)
        if not self.services:
            raise ContractError("pipeline vide")
        self._validate_topology()

    def _validate_topology(self) -> None:
        names: set[str] = set()
        current_kind = "request"
        for service in self.services:
            spec = service.spec
            if spec.name in names:
                raise ContractError(f"service dupliqué: {spec.name}")
            missing = set(spec.dependencies) - names
            if missing:
                raise ContractError(f"{spec.name}: dépendances non satisfaites: {sorted(missing)}")
            if spec.input_kind != current_kind:
                raise ContractError(
                    f"frontière incompatible vers {spec.name}: {current_kind} -> {spec.input_kind}"
                )
            names.add(spec.name)
            current_kind = spec.output_kind

    def manifest(self) -> dict:
        return {
            "entry_kind": "request",
            "exit_kind": self.services[-1].spec.output_kind,
            "services": [
                {
                    "name": service.spec.name,
                    "input_kind": service.spec.input_kind,
                    "output_kind": service.spec.output_kind,
                    "dependencies": list(service.spec.dependencies),
                }
                for service in self.services
            ],
        }

    def run(self, text: str, *, speaker: str = "user", correlation_id: str | None = None) -> PipelineResult:
        correlation_id = correlation_id or uuid4().hex
        message = Envelope(
            kind="request",
            message_id=f"request:{correlation_id}",
            correlation_id=correlation_id,
            producer="integration-client",
            parent_ids=(),
            payload={"text": text, "speaker": speaker},
        )
        trace = [message]
        for service in self.services:
            message = service.handle(message)
            trace.append(message)
        result = PipelineResult(message, tuple(trace))
        failed = [name for name, passed in result.as_dict()["checks"].items() if not passed]
        if failed:
            raise ContractError(f"invariants de chaîne violés: {', '.join(failed)}")
        return result


def build_pipeline(root: Path) -> IntegrationPipeline:
    return IntegrationPipeline([
        ObservationService(),
        AnalysisService(root / "poc/dlg-03/output/results.json"),
        SemanticProjectionService(),
        TemporalContextService(),
        DialogueStateService(),
        HypothesisService(),
        RetrievalService(bound=2),
        DecisionService(),
        PlanningService(),
        SimpleNLGService(root / ".local/opt/simplenlg/SimpleNLG-4.5.0.jar"),
    ])


def write_result(result: PipelineResult, output: Path, manifest: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    (output / "result.json").write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n"
    )
    (output / "trace.jsonl").write_text(
        "".join(json.dumps(row.as_dict(), ensure_ascii=False) + "\n" for row in result.trace)
    )
