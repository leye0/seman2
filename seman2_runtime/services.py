"""Proto-services concrets de la première chaîne intégrée."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .contracts import ContractError, Envelope, ServiceSpec, output_envelope, require_fields


class Service(Protocol):
    spec: ServiceSpec

    def handle(self, source: Envelope) -> Envelope: ...


class ObservationService:
    spec = ServiceSpec("observation", "request", "observation")

    def handle(self, source: Envelope) -> Envelope:
        if source.kind != self.spec.input_kind:
            raise ContractError(
                f"{self.spec.name} attend {self.spec.input_kind}, reçu {source.kind}"
            )
        require_fields(source, "text", "speaker")
        text = source.payload["text"]
        if not isinstance(text, str) or not text.strip():
            raise ContractError("observation: text doit être une chaîne non vide")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"obs:{source.correlation_id}",
            payload={
                "text": text,
                "speaker": source.payload["speaker"],
                "immutable": True,
                "modality": "text",
            },
        )


class AnalysisService:
    spec = ServiceSpec("analysis", "observation", "analysis-bundle", ("observation",))

    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "text")
        if not self.artifact.is_file():
            raise ContractError(
                f"analysis: artefact absent: {self.artifact}; exécuter poc/dlg-03/run.sh"
            )
        rows = json.loads(self.artifact.read_text())
        matches = [row for row in rows if row.get("fixture", {}).get("text") == source.payload["text"]]
        if len(matches) != 1:
            raise ContractError(
                f"analysis: attendu exactement un bundle pour {source.payload['text']!r}, trouvé {len(matches)}"
            )
        analyses = matches[0].get("analyses", [])
        producers = {item.get("producer") for item in analyses if item.get("status") == "parsed"}
        if producers != {"ACE_ERG", "dynamicsyntax-python"}:
            raise ContractError(f"analysis: producteurs requis absents: {sorted(producers)}")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"analysis:{source.correlation_id}",
            payload={
                "observation_id": source.message_id,
                "alternatives": analyses,
                "semantic_fusion": False,
                "correspondences": [],
            },
            provenance=(str(self.artifact),),
        )


class SemanticProjectionService:
    """Projette un candidat commun sans fusionner les structures sources."""

    spec = ServiceSpec(
        "semantic-projection", "analysis-bundle", "semantic-candidates", ("analysis",)
    )
    _named = re.compile(r'named<[^>]+>[^\]]*CARG: "([^"]+)" ARG0: (x\d+)')
    _verb = re.compile(r'(_[a-z][a-z0-9_-]*_v_[a-z0-9]+)<[^>]+>[^\]]*ARG1: (x\d+) ARG2: (x\d+)')

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "alternatives", "semantic_fusion")
        if source.payload["semantic_fusion"] is not False:
            raise ContractError("semantic-projection: les analyses natives ont déjà été fusionnées")
        by_producer = {row["producer"]: row for row in source.payload["alternatives"]}
        erg = by_producer["ACE_ERG"]
        ds = by_producer["dynamicsyntax-python"]
        if erg.get("candidate_count") != 1 or not erg.get("candidates"):
            raise ContractError("semantic-projection: le cas intégré exige un candidat ERG unique")
        mrs = erg["candidates"][0]["mrs"]
        names = {variable: name for name, variable in self._named.findall(mrs)}
        verb_match = self._verb.search(mrs)
        if not verb_match:
            raise ContractError("semantic-projection: prédicat transitif ERG introuvable")
        predicate, subject_var, object_var = verb_match.groups()
        if subject_var not in names or object_var not in names:
            raise ContractError("semantic-projection: arguments ERG non liés à des entités nommées")
        lemma = predicate.removeprefix("_").rsplit("_v_", 1)[0]
        subject, obj = names[subject_var], names[object_var]
        ds_semantics = ds.get("semantics", "")
        checks = {
            "predicate": f"=={lemma}" in ds_semantics,
            "subject": subject.casefold() in ds_semantics.casefold(),
            "object": obj.casefold() in ds_semantics.casefold(),
        }
        # Dynamic Syntax expose ici le prédicat et le sujet, mais sa sortie
        # finale réutilise la variable x pour l'objet. Cette limite observée ne
        # doit ni être cachée, ni transformer une correspondance partielle en
        # identité sémantique. ERG reste donc l'unique support de la proposition
        # complète; la sortie DS native demeure attachée comme analyse séparée.
        if not checks["predicate"]:
            raise ContractError("semantic-projection: le prédicat ERG est absent de l'analyse DS")
        content_id = f"prop:{lemma}:{subject.casefold()}:{obj.casefold()}"
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"sem:{source.correlation_id}",
            payload={
                "candidates": [{
                    "content_id": content_id,
                    "predicate": lemma,
                    "arguments": [subject, obj],
                    "tense": "present",
                    "polarity": "positive",
                    "supported_by": [erg["analysis_id"]],
                    "source_native_values": {"mrs": mrs, "ttr": ds_semantics},
                }],
                "source_analyses_preserved": True,
                "cross_representation": {
                    "analysis_id": ds["analysis_id"],
                    "checks": checks,
                    "asserted_identity": False,
                    "status": "partial-correspondence" if not all(checks.values()) else "correspondence",
                },
            },
            losses=("Dynamic Syntax object binding unresolved",) if not checks["object"] else (),
        )


class TemporalContextService:
    """Construit des relations E/R/S de Reichenbach, sans date absolue."""

    spec = ServiceSpec(
        "temporal-context",
        "semantic-candidates",
        "temporally-qualified-candidates",
        ("semantic-projection",),
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "candidates", "source_analyses_preserved")
        qualified = []
        all_constraints = []
        for candidate in source.payload["candidates"]:
            tense = candidate.get("tense")
            event = f"event:{candidate['content_id']}"
            reference = f"reference:{source.correlation_id}"
            speech = f"utterance:{source.correlation_id}"
            if tense == "present":
                relations = [(event, "=", reference), (reference, "=", speech)]
            elif tense == "past":
                relations = [(event, "=", reference), (reference, "<", speech)]
            elif tense == "future":
                relations = [(speech, "<", reference), (reference, "=", event)]
            else:
                raise ContractError(f"temporal-context: temps non pris en charge: {tense!r}")
            constraints = [
                {"left": left, "operator": operator, "right": right, "formalism": "Reichenbach E/R/S"}
                for left, operator, right in relations
            ]
            self._validate_consistency(constraints)
            all_constraints.extend(constraints)
            qualified.append({
                **candidate,
                "temporal_context": {
                    "event": event,
                    "reference": reference,
                    "speech": speech,
                    "constraints": constraints,
                    "absolute_coordinate": None,
                },
            })
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"temporal:{source.correlation_id}",
            payload={
                "candidates": qualified,
                "constraints": all_constraints,
                "absolute_coordinate_invented": False,
                "source_analyses_preserved": source.payload["source_analyses_preserved"],
            },
        )

    @staticmethod
    def _validate_consistency(constraints: list[dict]) -> None:
        parent: dict[str, str] = {}

        def find(node: str) -> str:
            parent.setdefault(node, node)
            if parent[node] != node:
                parent[node] = find(parent[node])
            return parent[node]

        def union(left: str, right: str) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for constraint in constraints:
            if constraint["operator"] == "=":
                union(constraint["left"], constraint["right"])
        edges: dict[str, set[str]] = {}
        for constraint in constraints:
            if constraint["operator"] != "<":
                continue
            left, right = find(constraint["left"]), find(constraint["right"])
            if left == right:
                raise ContractError("temporal-context: ordre strict à l'intérieur d'une classe d'égalité")
            edges.setdefault(left, set()).add(right)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ContractError("temporal-context: cycle d'ordre strict")
            if node in visited:
                return
            visiting.add(node)
            for target in edges.get(node, set()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in list(edges):
            visit(node)


class DialogueStateService:
    spec = ServiceSpec(
        "dialogue-state",
        "temporally-qualified-candidates",
        "dialogue-state",
        ("temporal-context",),
    )

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "candidates", "constraints", "source_analyses_preserved")
        candidates = source.payload["candidates"]
        if len(candidates) != 1:
            raise ContractError("dialogue-state: cette chaîne exige un candidat propositionnel unique")
        proposition = candidates[0]
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"state:{source.correlation_id}",
            payload={
                "previous_state_id": "state:initial",
                "facts": [{**proposition, "status": "proposed"}],
                "obligations": [{
                    "kind": "acknowledge",
                    "content_id": proposition["content_id"],
                    "status": "open",
                }],
                "reversible_delta": {
                    "add": [proposition["content_id"]],
                    "remove": [],
                },
                "temporal_constraints": source.payload["constraints"],
            },
        )


class HypothesisService:
    spec = ServiceSpec("hypothesis", "dialogue-state", "hypothesis-set", ("dialogue-state",))

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "facts", "obligations", "reversible_delta")
        proposition = source.payload["facts"][0]
        base = proposition["content_id"]
        hypotheses = [
            {
                "hypothesis_id": f"hyp:{base}:literal",
                "content": proposition,
                "score": 0.93,
                "family": "literal-assertion",
                "contradiction": False,
                "justification_ids": proposition["supported_by"],
            },
            {
                "hypothesis_id": f"hyp:{base}:negated",
                "content": {**proposition, "polarity": "negative"},
                "score": 0.42,
                "family": "negated-reading",
                "contradiction": True,
                "justification_ids": ["constraint:affirmative-source"],
            },
            {
                "hypothesis_id": f"hyp:{base}:figurative",
                "content": {**proposition, "predicate": "affinity"},
                "score": 0.31,
                "family": "figurative-reading",
                "contradiction": False,
                "justification_ids": ["candidate:weak-context"],
            },
        ]
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"hypotheses:{source.correlation_id}",
            payload={"hypotheses": hypotheses, "dialogue_state_id": source.message_id},
        )


class RetrievalService:
    spec = ServiceSpec("retrieval", "hypothesis-set", "active-beam", ("hypothesis",))

    def __init__(self, bound: int = 2) -> None:
        if bound < 1:
            raise ContractError("retrieval: bound doit être positif")
        self.bound = bound

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "hypotheses")
        hypotheses = source.payload["hypotheses"]
        if len({row["hypothesis_id"] for row in hypotheses}) != len(hypotheses):
            raise ContractError("retrieval: identifiants d'hypothèse dupliqués")
        ordered = sorted(hypotheses, key=lambda row: (-row["score"], row["hypothesis_id"]))
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"beam:{source.correlation_id}",
            payload={
                "bound": self.bound,
                "active": ordered[: self.bound],
                "persistent": ordered,
                "pruned_ids": [row["hypothesis_id"] for row in ordered[self.bound :]],
            },
            losses=("working-set-pruned; persistent hypotheses retained",)
            if len(ordered) > self.bound else (),
        )


class DecisionService:
    spec = ServiceSpec("decision", "active-beam", "selection", ("retrieval",))

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "active", "persistent", "bound")
        eligible = [row for row in source.payload["active"] if not row["contradiction"]]
        if not eligible:
            raise ContractError("decision: aucune hypothèse active compatible")
        selected = max(eligible, key=lambda row: (row["score"], row["hypothesis_id"]))
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"selection:{source.correlation_id}",
            payload={
                "selected": selected,
                "operation": "acknowledge-with-content",
                "policy": "highest-score-non-contradictory",
                "considered_ids": [row["hypothesis_id"] for row in source.payload["active"]],
                "persistent_count": len(source.payload["persistent"]),
            },
        )


class PlanningService:
    spec = ServiceSpec("planning", "selection", "communicative-plan", ("decision",))

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "selected", "operation", "considered_ids")
        selected = source.payload["selected"]
        content = selected["content"]
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"plan:{source.correlation_id}",
            payload={
                "goal": "ground-presented-proposition",
                "operation": source.payload["operation"],
                "ordered_content": [content],
                "omitted_hypothesis_ids": [
                    item for item in source.payload["considered_ids"]
                    if item != selected["hypothesis_id"]
                ],
                "added_content": [],
            },
        )


class SimpleNLGService:
    spec = ServiceSpec("realization", "communicative-plan", "realization", ("planning",))

    def __init__(self, jar: Path) -> None:
        self.jar = jar

    def handle(self, source: Envelope) -> Envelope:
        require_fields(source, "ordered_content", "added_content")
        if source.payload["added_content"]:
            raise ContractError("realization: le plan contient du contenu ajouté")
        content = source.payload["ordered_content"][0]
        arguments = content.get("arguments", [])
        if len(arguments) != 2 or not content.get("predicate"):
            raise ContractError("realization: contenu transitif incomplet")
        if not self.jar.is_file():
            raise ContractError(f"realization: SimpleNLG absent: {self.jar}")
        source_code = """
import simplenlg.framework.*;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.SPhraseSpec;
import simplenlg.realiser.english.Realiser;
public class Seman2Realize {
  public static void main(String[] a) {
    if (a.length != 3) throw new IllegalArgumentException("subject verb object required");
    Lexicon l=Lexicon.getDefaultLexicon(); NLGFactory f=new NLGFactory(l);
    SPhraseSpec c=f.createClause(a[0],a[1],a[2]);
    System.out.println(new Realiser(l).realiseSentence(c));
  }
}
""".strip()
        with tempfile.TemporaryDirectory(prefix="seman2-realize-") as directory:
            java_file = Path(directory) / "Seman2Realize.java"
            java_file.write_text(source_code + "\n")
            compiled = subprocess.run(
                ["javac", "--release", "17", "-cp", str(self.jar), "-d", directory, str(java_file)],
                text=True, capture_output=True, timeout=30,
            )
            if compiled.returncode:
                raise ContractError(f"realization: javac a échoué: {compiled.stderr.strip()}")
            realized = subprocess.run(
                ["java", "-cp", f"{directory}:{self.jar}", "Seman2Realize", arguments[0], content["predicate"], arguments[1]],
                text=True, capture_output=True, timeout=30,
            )
            if realized.returncode:
                raise ContractError(f"realization: SimpleNLG a échoué: {realized.stderr.strip()}")
        text = realized.stdout.strip()
        if not text:
            raise ContractError("realization: SimpleNLG a produit une chaîne vide")
        return output_envelope(
            spec=self.spec,
            source=source,
            message_id=f"realization:{source.correlation_id}",
            payload={
                "text": text,
                "content_id": content["content_id"],
                "covered_content_ids": [content["content_id"]],
                "added_content": [],
                "backend": "SimpleNLG",
            },
            provenance=(str(self.jar),),
        )
