#!/usr/bin/env python3
"""Compare un artefact réel à un manifeste d'attentes explicites."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import urllib.error
import urllib.request
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class EvaluationError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def pointer_get(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise EvaluationError(f"pointeur JSON invalide: {pointer}")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise EvaluationError(f"pointeur introuvable: {pointer}") from exc
    return current


def deterministic_check(document: Any, expectation: dict) -> dict:
    try:
        actual = pointer_get(document, expectation["pointer"])
        operator = expectation["operator"]
        expected = expectation.get("expected")
        if operator == "equals":
            passed = actual == expected
            observed = actual
        elif operator == "length_equals":
            observed = len(actual)
            passed = observed == expected
        elif operator == "exists":
            observed = actual is not None
            passed = observed is bool(expected)
        else:
            raise EvaluationError(f"opérateur inconnu: {operator}")
        return {
            "expectation_id": expectation["id"],
            "pointer": expectation["pointer"],
            "operator": operator,
            "expected": expected,
            "observed": observed,
            "passed": passed,
        }
    except EvaluationError as exc:
        return {
            "expectation_id": expectation["id"],
            "pointer": expectation["pointer"],
            "operator": expectation["operator"],
            "expected": expectation.get("expected"),
            "observed": None,
            "passed": False,
            "error": str(exc),
        }


def trace_by_kind(document: dict, kind: str) -> dict:
    matches = [row for row in document["trace"] if row["kind"] == kind]
    if len(matches) != 1:
        raise EvaluationError(f"attendu exactement un message {kind}, trouvé {len(matches)}")
    return matches[0]


def phase3_corpus_evidence(document: dict) -> dict:
    samples = trace_by_kind(document, "corpus-sample-set")["payload"]["samples"]
    features = trace_by_kind(document, "semantic-feature-batch")["payload"]
    analyzed = trace_by_kind(document, "analyzed-corpus-batch")["payload"]["rows"]
    sample_by_question = {row["question_id"]: row for row in samples}
    analyses_by_observation = {row["observation_id"]: row for row in analyzed}
    cases = []
    for observation_id in sorted(analyses_by_observation):
        question_id = observation_id.split(":")[2]
        sample = sample_by_question[question_id]
        fragment_rows = [row for row in features["fragments"] if row["observation_id"] == observation_id]
        dynamic = next(
            row for row in analyses_by_observation[observation_id]["analyses"]
            if row["producer"] == "dynamicsyntax-python"
        )
        cases.append({
            "case_id": observation_id,
            "criterion": sample["criterion"],
            "title": sample["title"],
            "top_answer_excerpt": sample["answers"][0]["text_projection"][:600],
            "dynamic_syntax": {
                "status": dynamic["status"],
                "action_count": dynamic["action_count"],
                "semantics": dynamic["semantics"],
            },
            "mrs_candidates": [
                {
                    "candidate_id": row["candidate_id"],
                    "sentence_force": row["external_grammatical_features"]["sentence_force"],
                    "tense": row["external_grammatical_features"]["tense"],
                    "predicates": [relation["predicate"] for relation in row["relations"]],
                    "temporal_status": row["temporal_candidate"]["status"],
                    "temporal_constraints": row["temporal_candidate"]["constraints"],
                }
                for row in fragment_rows
            ],
        })
    return {
        "cases": cases,
        "global": {
            "absolute_coordinate_invented": features["absolute_coordinate_invented"],
            "temporal_unresolved_count": len(features["temporal_unresolved"]),
            "candidate_selection_performed": features["candidate_selection_performed"],
        },
    }


PROJECTORS = {"phase3-corpus-plan": phase3_corpus_evidence}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, raw_value = stripped.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "a").isalnum():
            continue
        parsed = shlex.split(raw_value, comments=True)
        values[name] = parsed[0] if parsed else ""
    return values


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
                    "expected": {"type": "string"},
                    "observed": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["criterion_id", "verdict", "expected", "observed", "rationale", "evidence_refs"],
                "additionalProperties": False,
            },
        },
        "overall": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["criteria", "overall", "limitations"],
    "additionalProperties": False,
}


def openrouter_judge(manifest: dict, evidence: dict, timeout: int) -> dict:
    env = {**load_env(ROOT / ".env"), **os.environ}
    api_key = env.get("OPENROUTER_API_KEY")
    model = env.get("OPENROUTER_TEXT_MODEL")
    if not api_key or not model:
        raise EvaluationError("OPENROUTER_API_KEY ou OPENROUTER_TEXT_MODEL absent")
    expectations = manifest.get("semantic_expectations", [])
    prompt = {
        "task": "Compare the observed evidence with every expectation. Do not infer missing evidence. Mark uncertain when evidence is insufficient. A parser alternative need only preserve a plausible reading; do not demand that all alternatives be correct. Return one criterion result per supplied criterion_id.",
        "claim": manifest["claim"],
        "expectations": expectations,
        "observed_evidence": evidence,
    }
    request_body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an independent semantic evaluator. Judge only from supplied evidence. Never upgrade deterministic failures. Use uncertain instead of guessing.",
            },
            {"role": "user", "content": canonical(prompt)},
        ],
        "temperature": 0,
        "max_tokens": 2200,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "poc_semantic_evaluation", "strict": True, "schema": JUDGE_SCHEMA},
        },
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(request_body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/seman2-local-evaluation",
            "X-Title": "seman2 POC evaluation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_response = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[-2000:]
        raise EvaluationError(f"OpenRouter HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"OpenRouter indisponible: {exc}") from exc
    try:
        content = raw_response["choices"][0]["message"]["content"]
        judgment = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise EvaluationError("réponse OpenRouter structurée invalide") from exc
    expected_ids = {row["id"] for row in expectations}
    received_ids = {row["criterion_id"] for row in judgment.get("criteria", [])}
    if received_ids != expected_ids:
        raise EvaluationError(
            f"critères OpenRouter incomplets: attendus={sorted(expected_ids)}, reçus={sorted(received_ids)}"
        )
    return {
        "status": "completed",
        "model": raw_response.get("model", model),
        "response_id": raw_response.get("id"),
        "usage": raw_response.get("usage", {}),
        "prompt_sha256": sha256(prompt),
        "evidence": evidence,
        "judgment": judgment,
    }


def evaluate(manifest_path: Path, semantic: bool, timeout: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    subject_path = ROOT / manifest["subject"]
    if not subject_path.is_file():
        raise EvaluationError(f"artefact absent: {subject_path}; reconstruire la POC d'abord")
    subject = json.loads(subject_path.read_text())
    checks = [deterministic_check(subject, row) for row in manifest["deterministic_expectations"]]
    deterministic_pass = all(row["passed"] for row in checks)
    semantic_result: dict = {"status": "not-requested"}
    if semantic:
        projector_name = manifest.get("semantic_projection")
        if projector_name not in PROJECTORS:
            raise EvaluationError(f"projection sémantique inconnue: {projector_name}")
        semantic_result = openrouter_judge(manifest, PROJECTORS[projector_name](subject), timeout)
    semantic_verdict = semantic_result.get("judgment", {}).get("overall")
    if not deterministic_pass:
        verdict = "FAIL-DETERMINISTIC"
    elif not semantic:
        verdict = "PASS-DETERMINISTIC; SEMANTIC-NOT-RUN"
    elif semantic_verdict == "pass":
        verdict = "PASS-DETERMINISTIC-AND-SEMANTIC"
    elif semantic_verdict == "fail":
        verdict = "FAIL-SEMANTIC"
    else:
        verdict = "REVIEW-SEMANTIC-UNCERTAIN"
    return {
        "evaluation_id": manifest["evaluation_id"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "subject": manifest["subject"],
        "subject_sha256": hashlib.sha256(subject_path.read_bytes()).hexdigest(),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "claim": manifest["claim"],
        "deterministic": {"passed": deterministic_pass, "checks": checks},
        "semantic": semantic_result,
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--semantic", action="store_true", help="appeler le juge OpenRouter")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    try:
        report = evaluate(manifest_path, args.semantic, args.timeout)
    except (EvaluationError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    output = args.output or ROOT / "output/evaluations" / f"{report['evaluation_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "evaluation_id": report["evaluation_id"],
        "verdict": report["verdict"],
        "deterministic_checks": len(report["deterministic"]["checks"]),
        "semantic_status": report["semantic"]["status"],
        "report": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
    }, ensure_ascii=False))
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
