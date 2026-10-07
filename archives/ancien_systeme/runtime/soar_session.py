"""Session Soar longue durée et checkpoint coordonné reconstructible."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import Python_sml_ClientInterface as sml

from .contracts import ContractError, canonical_json


RULES = r"""
sp {runtime*select-question
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^observation-id <obs> ^role question-title ^hypotheses <hs>)
    (<hs> ^hypothesis <h>)
    (<h> ^rank 1 ^external-id <id>)
    -->
    (<o> ^runtime-decision <d>)
    (<d> ^observation-id <obs> ^selected-hypothesis <id> ^next-action request-internal-memory)
}

sp {runtime*select-answer
    (state <s> ^io <io>)
    (<io> ^input-link <i> ^output-link <o>)
    (<i> ^active-context <c>)
    (<c> ^observation-id <obs> ^role answer ^hypotheses <hs>)
    (<hs> ^hypothesis <h>)
    (<h> ^rank 1 ^external-id <id>)
    -->
    (<o> ^runtime-decision <d>)
    (<d> ^observation-id <obs> ^selected-hypothesis <id> ^next-action evaluate-dialogue-update)
}

sp {runtime*propose-transformation
    (state <s> ^io.input-link.active-context <c>)
    (<c> ^role state-transformation ^observation-id <obs> ^transformations <ts>)
    (<ts> ^transformation <t>)
    (<t> ^eligible yes ^external-id <id> ^kind <kind>
         ^direct-source-link <linked> ^parsed-content <parsed>)
    -->
    (<s> ^operator <o> +)
    (<o> ^name select-state-transformation ^observation-id <obs>
         ^external-id <id> ^kind <kind> ^direct-source-link <linked>
         ^parsed-content <parsed>)
}

sp {runtime*prefer-attributed-answer-candidate
    (state <s> ^operator <preferred> + ^operator <other> +)
    (<preferred> ^name select-state-transformation
                 ^kind attach-answer-candidate
                 ^direct-source-link yes ^parsed-content yes)
    (<other> ^name select-state-transformation
             ^kind { <> attach-answer-candidate })
    -->
    (<s> ^operator <preferred> > <other>)
}

sp {runtime*apply-transformation
    (state <s> ^io.output-link <out> ^operator <o>)
    (<o> ^name select-state-transformation ^observation-id <obs>
         ^external-id <id> ^kind <kind>)
    -->
    (<out> ^runtime-transformation-decision <d>)
    (<d> ^observation-id <obs> ^selected-transformation <id>
         ^transformation-kind <kind> ^next-action apply-state-transformation)
}
"""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class SoarRuntimeSession:
    def __init__(self, *, agent_file: Path | None = None) -> None:
        self.kernel = sml.Kernel.CreateKernelInNewThread()
        if self.kernel.HadError():
            raise ContractError(f"Soar kernel: {self.kernel.GetLastErrorDescription()}")
        self.agent = self.kernel.CreateAgent("seman2-runtime")
        if not self.agent or self.agent.HadError():
            self.kernel.Shutdown()
            raise ContractError("Soar: création de la session impossible")
        self.input_link = self.agent.GetInputLink()
        self.beams: list[dict[str, Any]] = []
        self.agent.ExecuteCommandLine("smem --set learning on")
        self.agent.ExecuteCommandLine("epmem --set learning on")
        self.agent.ExecuteCommandLine("epmem --set trigger dc")
        loaded = ""
        if agent_file is not None:
            loaded = self.agent.ExecuteCommandLine(f"load file {agent_file}")
        # Les productions de contrôle livrées avec le runtime font partie du
        # code exécutable courant. Les recharger après un checkpoint remplace
        # proprement leurs définitions nommées tout en gardant les productions
        # apprises et autres éléments sauvegardés dans l'agent.
        sourced = self.agent.ExecuteCommandLine(RULES)
        if "Error" in loaded or "Error" in sourced:
            self.close()
            raise ContractError(
                f"Soar: chargement des productions échoué: checkpoint={loaded}; runtime={sourced}"
            )

    def close(self) -> None:
        if getattr(self, "agent", None) is not None:
            self.kernel.DestroyAgent(self.agent)
            self.agent = None
        if getattr(self, "kernel", None) is not None:
            self.kernel.Shutdown()
            self.kernel = None

    def __enter__(self) -> "SoarRuntimeSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def inject(self, beams: list[dict[str, Any]]) -> None:
        if self.beams:
            raise ContractError("Soar: le contexte actif est déjà injecté")
        for beam in beams:
            context = self.input_link.CreateIdWME("active-context")
            context.CreateStringWME("observation-id", beam["observation_id"])
            context.CreateStringWME("role", beam.get("role", "question-title"))
            if beam.get("role") == "state-transformation":
                transformations = context.CreateIdWME("transformations")
                for candidate in beam["transformations"]:
                    transformation = transformations.CreateIdWME("transformation")
                    transformation.CreateStringWME("external-id", candidate["transformation_id"])
                    transformation.CreateStringWME("kind", candidate["kind"])
                    transformation.CreateStringWME(
                        "eligible", "yes" if candidate["eligible"] else "no"
                    )
                    transformation.CreateStringWME(
                        "direct-source-link",
                        "yes" if candidate["evidence"]["direct_source_link"] else "no",
                    )
                    transformation.CreateStringWME(
                        "parsed-content",
                        "yes" if candidate["evidence"]["parsed_content"] else "no",
                    )
            else:
                hypotheses = context.CreateIdWME("hypotheses")
                for rank, hypothesis_id in enumerate(beam["hypothesis_ids"], 1):
                    hypothesis = hypotheses.CreateIdWME("hypothesis")
                    hypothesis.CreateIntWME("rank", rank)
                    hypothesis.CreateStringWME("external-id", hypothesis_id)
        self.agent.Commit()
        self.beams = json.loads(json.dumps(beams))

    def decide(self) -> list[dict[str, Any]]:
        if not self.beams:
            raise ContractError("Soar: aucun contexte actif")
        transformation_mode = all(
            beam.get("role") == "state-transformation" for beam in self.beams
        )
        if transformation_mode and len(self.beams) != 1:
            raise ContractError(
                "Soar: les opérateurs de conversations indépendantes doivent être décidés séparément"
            )
        if not transformation_mode and any(
            beam.get("role") == "state-transformation" for beam in self.beams
        ):
            raise ContractError("Soar: lot mixte hypothèses/transformations interdit")
        run = self.agent.ExecuteCommandLine("run 2" if transformation_mode else "run 1")
        top = self.agent.ExecuteCommandLine("print S1 --depth 20")
        if "rules fired" not in run and "rule fired" not in run:
            raise ContractError(f"Soar: aucune production déclenchée: {run}")
        decisions = []
        for beam in self.beams:
            observation = re.escape(beam["observation_id"])
            if transformation_mode:
                pattern = re.compile(
                    rf"\([^\s()]+\s+\^next-action\s+apply-state-transformation\s+"
                    rf"\^observation-id\s+{observation}\s+"
                    rf"\^selected-transformation\s+([^\s()]+)\s+"
                    rf"\^transformation-kind\s+([^\s()]+)\)"
                )
                match = pattern.search(top)
                if not match:
                    raise ContractError(
                        f"Soar: décision de transformation absente pour {beam['observation_id']}"
                    )
                decisions.append({
                    "observation_id": beam["observation_id"],
                    "selected_transformation_id": match.group(1),
                    "transformation_kind": match.group(2),
                    "next_action": "apply-state-transformation",
                    "run_result": run,
                    "input_transformation_count": len(beam["transformations"]),
                    "operator_semantics": "Soar acceptable and better preferences",
                })
                continue
            pattern = re.compile(
                rf"\([^\s()]+\s+\^next-action\s+([^\s()]+)\s+"
                rf"\^observation-id\s+{observation}\s+"
                rf"\^selected-hypothesis\s+([^\s()]+)\)"
            )
            match = pattern.search(top)
            if not match:
                raise ContractError(f"Soar: décision absente pour {beam['observation_id']}")
            decisions.append({
                "observation_id": beam["observation_id"],
                "selected_hypothesis_id": match.group(2),
                "next_action": match.group(1),
                "run_result": run,
                "input_hypothesis_count": len(beam["hypothesis_ids"]),
            })
        return decisions

    def checkpoint(self, directory: Path, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        directory.mkdir(parents=True, exist_ok=True)
        agent_file = directory / "agent.soar"
        semantic_file = directory / "semantic-memory.sqlite"
        episodic_file = directory / "episodic-memory.sqlite"
        context_file = directory / "active-context.json"
        input_file = directory / "working-memory-input.txt"
        output_file = directory / "working-memory-output.txt"
        manifest_file = directory / "soar-checkpoint.json"

        for path in (agent_file, semantic_file, episodic_file, context_file, input_file, output_file):
            if path.exists():
                path.unlink()
        # The in-memory episodic database is opened lazily by Soar. Querying
        # its statistics forces that connection before the backup command.
        episodic_stats = self.agent.ExecuteCommandLine("epmem --stats")
        save_episodic = self.agent.ExecuteCommandLine(f"epmem --backup {episodic_file}")
        save_semantic = self.agent.ExecuteCommandLine(f"smem --backup {semantic_file}")
        # save agent can close/reconfigure native memories while serializing
        # settings, so their live databases must be copied first.
        save_agent = self.agent.ExecuteCommandLine(f"save agent {agent_file}")
        context_file.write_text(json.dumps(self.beams, ensure_ascii=False, indent=2) + "\n")
        input_file.write_text(self.agent.ExecuteCommandLine(
            f"print {self.input_link.GetIdentifierName()} --depth 20"
        ) + "\n")
        top = self.agent.ExecuteCommandLine("print S1 --depth 2")
        output_link = re.search(r"\^output-link ([A-Z]\d+)", top)
        if not output_link:
            raise ContractError("Soar checkpoint: output-link introuvable")
        output_file.write_text(
            self.agent.ExecuteCommandLine(f"print {output_link.group(1)} --depth 20") + "\n"
        )
        required = [agent_file, semantic_file, episodic_file, context_file, input_file, output_file]
        absent = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
        if absent:
            raise ContractError(
                f"Soar checkpoint incomplet: {absent}; "
                f"save_agent={save_agent!r}; smem={save_semantic!r}; epmem={save_episodic!r}"
            )
        manifest = {
            "kind": "soar-coordinated-reconstruction-checkpoint",
            "active_context_sha256": hashlib.sha256(canonical_json(self.beams).encode()).hexdigest(),
            "decisions_before_stop": decisions,
            "commands": {
                "save_agent": save_agent,
                "backup_semantic": save_semantic,
                "backup_episodic": save_episodic,
                "episodic_stats_before_backup": episodic_stats,
            },
            "files": {
                path.name: {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
                for path in required
            },
            "working_memory_restore_mode": "reconstruct-from-active-context",
            "native_whole-working-memory_restore_claimed": False,
        }
        temporary = manifest_file.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, manifest_file)
        return manifest


def checkpoint_and_verify(
    beams: list[dict[str, Any]],
    directory: Path,
    *,
    agent_file: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with SoarRuntimeSession(agent_file=agent_file) as session:
        session.inject(beams)
        before = session.decide()
        checkpoint = session.checkpoint(directory, before)

    agent_file = directory / "agent.soar"
    restored_beams = json.loads((directory / "active-context.json").read_text())
    if hashlib.sha256(canonical_json(restored_beams).encode()).hexdigest() != checkpoint["active_context_sha256"]:
        raise ContractError("Soar restore: active context digest mismatch")
    with SoarRuntimeSession(agent_file=agent_file) as restored:
        restored.inject(restored_beams)
        after = restored.decide()
    if before != after:
        raise ContractError("Soar restore: decisions differ after reconstruction")
    return before, {
        **checkpoint,
        "decisions_after_restore": after,
        "decision_equivalence": True,
    }
