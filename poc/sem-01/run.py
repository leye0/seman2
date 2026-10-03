#!/usr/bin/env python3
"""SEM-01: attributed, non-destructive Epitran analyses."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import epitran

POC_DIR = Path(__file__).resolve().parent
ROOT = POC_DIR.parent.parent
OUTPUT = POC_DIR / "output"


def serializable(value):
    if isinstance(value, map):
        return list(value)
    if isinstance(value, tuple):
        return [serializable(item) for item in value]
    if isinstance(value, list):
        return [serializable(item) for item in value]
    return value


def flite_analyze(fixture, executable, source_hash):
    raw = fixture["text"]
    analyzer_input = raw.lower()
    completed = subprocess.run([str(executable), analyzer_input], text=True, capture_output=True, timeout=10)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    def phones(line):
        return line[1:-1].split() if line.startswith("(") and line.endswith(")") else []

    candidates = []
    for rank, (kind, line) in enumerate(zip(("lexicon_or_fallback", "lts_only"), lines), 1):
        candidates.append({"rank": rank, "kind": kind, "phones": phones(line),
                           "raw_native_output": line, "score": None})
    warnings = ["native_output_is_CMU_ARPABET_not_IPA"]
    if analyzer_input != raw:
        warnings.append("producer_input_lowercased_while_source_remains_unchanged")
    if len(candidates) < 2:
        warnings.append("expected_lexicon_and_lts_lines_not_both_returned")
    if len(candidates) == 2 and candidates[0]["phones"] == candidates[1]["phones"]:
        warnings.append("lexicon_or_fallback_and_lts_candidates_identical")
    if any(not candidate["phones"] for candidate in candidates):
        warnings.append("native_candidate_contains_no_phones")
    if any(character.isspace() for character in raw):
        warnings.append("lex_lookup_is_word_oriented_but_input_contains_whitespace")
    return {
        "analysis_id": f"flite:{fixture['id']}", "producer": "Flite lex_lookup",
        "language_script": fixture["language_script"], "input_modality": "written_text",
        "derived_not_observed_audio": True, "source_span": [0, len(raw)], "source_text": raw,
        "source_sha256": source_hash, "native_alphabet": "CMU_ARPABET", "ipa": None,
        "ipa_available": False, "producer_input": analyzer_input, "candidates": candidates, "alignment_kind": None,
        "alignments": [], "status": "complete" if completed.returncode == 0 and candidates and all(c["phones"] for c in candidates) else "partial_or_failed",
        "warnings": warnings + ([f"stderr:{completed.stderr.strip()}"] if completed.stderr.strip() else []),
        "return_code": completed.returncode, "replaces_source_observation": False,
        "canonical_correction": None,
    }


def analyze(fixture, analyzers, lex_lookup):
    raw = fixture["text"]
    source_hash = hashlib.sha256(raw.encode()).hexdigest()
    warnings = []
    try:
        analyzer = analyzers.setdefault(fixture["language_script"], epitran.Epitran(fixture["language_script"]))
        ipa = analyzer.transliterate(raw)
        tuples = serializable(analyzer.word_to_tuples(raw))
        alignments = [
            {"category": item[0], "case": item[1], "orthographic_fragment": item[2], "ipa_fragment": item[3], "segments_and_features": item[4]}
            for item in tuples
        ]
        status = "complete" if ipa else "empty_output"
        if not ipa:
            warnings.append("analyzer_returned_empty_transcription")
        if any(not item["ipa_fragment"] for item in alignments):
            warnings.append("alignment_contains_unpronounced_source_fragment")
    except Exception as error:
        ipa, alignments, status = None, [], "failed"
        warnings.append(f"{type(error).__name__}:{error}")
    analysis = {
        "analysis_id": f"epitran:{fixture['id']}", "producer": "Epitran",
        "language_script": fixture["language_script"], "input_modality": "written_text",
        "derived_not_observed_audio": True, "source_span": [0, len(raw)],
        "source_text": raw, "source_sha256": source_hash, "ipa": ipa,
        "alignment_kind": "Epitran.word_to_tuples_without_claimed_character_offsets",
        "alignments": alignments, "status": status, "warnings": warnings,
        "replaces_source_observation": False, "canonical_correction": None,
    }
    assert analysis["source_text"] == raw and hashlib.sha256(analysis["source_text"].encode()).hexdigest() == source_hash
    assert analysis["source_span"] == [0, len(raw)]
    assert analysis["derived_not_observed_audio"] and not analysis["replaces_source_observation"]
    external_analyses = [analysis]
    if fixture["language_script"] == "eng-Latn":
        external_analyses.append(flite_analyze(fixture, lex_lookup, source_hash))
    assert all(item["source_text"] == raw and item["source_sha256"] == source_hash for item in external_analyses)
    return {"fixture": fixture, "observation": {"raw": raw, "span": [0, len(raw)], "sha256": source_hash},
            "external_analyses": external_analyses,
            "external_analysis": analysis}  # compatibility alias for the original Epitran view


def main():
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    analyzers = {}
    lex_lookup = ROOT / ".local/bin/lex_lookup"
    if not lex_lookup.is_file():
        raise SystemExit(f"Flite lex_lookup missing: {lex_lookup}")
    results = [analyze(fixture, analyzers, lex_lookup) for fixture in fixtures]
    assert any(r["external_analysis"]["status"] != "complete" or r["external_analysis"]["warnings"] for r in results)
    assert all(r["observation"]["raw"] == r["fixture"]["text"] for r in results)
    flite_commit = subprocess.run(["git", "-C", str(ROOT / ".local/src/flite"), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
    analyses = [analysis for result in results for analysis in result["external_analyses"]]
    producer_counts = {producer: sum(a["producer"] == producer for a in analyses)
                       for producer in sorted({a["producer"] for a in analyses})}
    assert producer_counts == {"Epitran": 10, "Flite lex_lookup": 4}
    summary = {
        "fixture_count": len(results), "complete_count": sum(r["external_analysis"]["status"] == "complete" for r in results),
        "empty_or_failed_count": sum(r["external_analysis"]["status"] != "complete" for r in results),
        "epitran_warning_count": sum(len(r["external_analysis"]["warnings"]) for r in results),
        "warning_count": sum(len(a["warnings"]) for a in analyses),
        "external_analysis_count": len(analyses), "producer_counts": producer_counts,
        "external_complete_count": sum(a["status"] == "complete" for a in analyses),
        "external_partial_or_failed_count": sum(a["status"] != "complete" for a in analyses),
        "flite_candidate_count": sum(len(a.get("candidates", [])) for a in analyses if a["producer"] == "Flite lex_lookup"),
        "flite_complete_count": sum(a["status"] == "complete" for a in analyses if a["producer"] == "Flite lex_lookup"),
        "flite_native_alphabet": "CMU_ARPABET", "flite_claimed_ipa_count": 0,
        "languages": sorted({r["fixture"]["language_script"] for r in results}),
        "source_reconstruction_passed": True, "audio_observation_claim_count": 0,
        "source_replacement_count": 0, "verdict": "GO_ATTRIBUTED_NON_DESTRUCTIVE_PHONOLOGY_WITH_COVERAGE_WARNINGS",
    }
    versions = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "epitran": importlib.metadata.version("epitran"),
        "panphon": importlib.metadata.version("panphon"), "flite_commit": flite_commit,
        "lex_lookup": str(lex_lookup), "lex_lookup_available": lex_lookup.exists(),
        "path_contains_lex_lookup": bool(next((p for p in os.environ["PATH"].split(":") if (Path(p) / "lex_lookup").exists()), None)),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("results.json", results), ("summary.json", summary), ("versions-and-parameters.json", versions)):
        (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SEM-01: {len(results)} written forms; {summary['complete_count']} non-empty Epitran IPA; "
          f"{summary['flite_complete_count']} Flite analyses; {summary['warning_count']} explicit warnings")


if __name__ == "__main__":
    main()
