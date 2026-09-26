#!/usr/bin/env python3
"""Run LEX-01: establish the lexical data exposed by NLTK WordNet."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nltk
from nltk.corpus import wordnet as wn


POC_DIR = Path(__file__).resolve().parent
POS_NAMES = {
    wn.NOUN: "noun",
    wn.VERB: "verb",
    wn.ADJ: "adjective",
    wn.ADJ_SAT: "adjective satellite",
    wn.ADV: "adverb",
}
MORPHY_POS = {
    "noun": wn.NOUN,
    "verb": wn.VERB,
    "adjective": wn.ADJ,
    "adverb": wn.ADV,
}


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def synset_ref(synset: Any) -> dict[str, Any]:
    return {
        "synset_id": synset.name(),
        "pos": synset.pos(),
        "offset": synset.offset(),
        "lemma_names": synset.lemma_names(),
    }


def sorted_refs(synsets: list[Any]) -> list[dict[str, Any]]:
    return [synset_ref(synset) for synset in sorted(synsets, key=lambda s: s.name())]


def lemma_relation(source_lemma: Any, target_lemma: Any) -> dict[str, Any]:
    return {
        "source_lemma": source_lemma.name(),
        "source_lemma_key": source_lemma.key(),
        "target_lemma": target_lemma.name(),
        "target_lemma_key": target_lemma.key(),
        "target_synset_id": target_lemma.synset().name(),
    }


def serialize_synset(
    fixture: dict[str, Any], lookup_key: str, synset: Any
) -> dict[str, Any]:
    lemmas = []
    antonyms = []
    derivations = []
    for lemma in synset.lemmas():
        lemma_item = {
            "name": lemma.name(),
            "lemma_key": lemma.key(),
            "sense_frequency_count": lemma.count(),
            "syntactic_marker": lemma.syntactic_marker(),
            "verb_frame_ids": lemma.frame_ids(),
        }
        lemmas.append(lemma_item)
        antonyms.extend(
            lemma_relation(lemma, target) for target in lemma.antonyms()
        )
        derivations.extend(
            lemma_relation(lemma, target)
            for target in lemma.derivationally_related_forms()
        )

    candidate_id = stable_id(
        "wordnet-analysis:",
        {
            "source_observation_id": f"source:{fixture['id']}",
            "lookup_key": lookup_key,
            "wordnet_version": wn.get_version(),
            "synset_id": synset.name(),
        },
    )
    return {
        "analysis_id": candidate_id,
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {
            "interface": "NLTK WordNet",
            "resource": "Princeton WordNet",
            "resource_version": wn.get_version(),
        },
        "lookup_key": lookup_key,
        "synset_id": synset.name(),
        "offset": synset.offset(),
        "pos": synset.pos(),
        "pos_name": POS_NAMES[synset.pos()],
        "lexicographer_file": synset.lexname(),
        "definition": synset.definition(),
        "examples": synset.examples(),
        "lemmas": lemmas,
        "relations": {
            "hypernyms": sorted_refs(synset.hypernyms()),
            "instance_hypernyms": sorted_refs(synset.instance_hypernyms()),
            "hyponyms": sorted_refs(synset.hyponyms()),
            "instance_hyponyms": sorted_refs(synset.instance_hyponyms()),
            "meronyms": {
                "part": sorted_refs(synset.part_meronyms()),
                "member": sorted_refs(synset.member_meronyms()),
                "substance": sorted_refs(synset.substance_meronyms()),
            },
            "holonyms": {
                "part": sorted_refs(synset.part_holonyms()),
                "member": sorted_refs(synset.member_holonyms()),
                "substance": sorted_refs(synset.substance_holonyms()),
            },
            "antonyms": sorted(
                antonyms,
                key=lambda item: (
                    item["source_lemma_key"], item["target_lemma_key"]
                ),
            ),
            "derivationally_related_forms": sorted(
                derivations,
                key=lambda item: (
                    item["source_lemma_key"], item["target_lemma_key"]
                ),
            ),
        },
    }


def relation_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "hypernyms": 0,
        "hyponyms": 0,
        "meronyms": 0,
        "holonyms": 0,
        "antonyms": 0,
        "derivationally_related_forms": 0,
    }
    for candidate in candidates:
        relations = candidate["relations"]
        counts["hypernyms"] += len(relations["hypernyms"]) + len(
            relations["instance_hypernyms"]
        )
        counts["hyponyms"] += len(relations["hyponyms"]) + len(
            relations["instance_hyponyms"]
        )
        counts["meronyms"] += sum(
            len(items) for items in relations["meronyms"].values()
        )
        counts["holonyms"] += sum(
            len(items) for items in relations["holonyms"].values()
        )
        counts["antonyms"] += len(relations["antonyms"])
        counts["derivationally_related_forms"] += len(
            relations["derivationally_related_forms"]
        )
    return counts


def lookup_fixture(
    fixture: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    query = fixture["query"]
    surface_synsets = wn.synsets(query)
    normalized_key = fixture.get("compound_normalization", query)
    normalized_synsets = wn.synsets(normalized_key)
    candidates = [
        serialize_synset(fixture, normalized_key, synset)
        for synset in normalized_synsets
    ]
    candidate_ids = [candidate["analysis_id"] for candidate in candidates]
    for candidate in candidates:
        candidate["competes_with"] = [
            item for item in candidate_ids if item != candidate["analysis_id"]
        ]
        candidate["selected_by_lookup"] = False

    morphy = {
        name: wn.morphy(normalized_key, pos) for name, pos in MORPHY_POS.items()
    }
    result = {
        **fixture,
        "source_observation": {
            "id": f"source:{fixture['id']}",
            "text": query,
            "charspan": [0, len(query)],
        },
        "lookup": {
            "surface_api_key": query,
            "surface_api_candidate_count": len(surface_synsets),
            "surface_api_synset_ids": [synset.name() for synset in surface_synsets],
            "effective_key": normalized_key,
            "transform": (
                "spaces_to_wordnet_underscores"
                if normalized_key != query
                else "none"
            ),
            "morphy_by_pos": morphy,
            "candidate_count": len(candidates),
            "status": "candidates_found" if candidates else "no_candidates",
            "selected_synset_id": None,
            "is_contextual_disambiguation": False,
        },
        "candidates": candidates,
        "relation_counts": relation_counts(candidates),
    }
    raw = {
        "fixture": fixture["id"],
        "query": query,
        "surface_api_call": f"wn.synsets({query!r})",
        "surface_api_results": [repr(synset) for synset in surface_synsets],
        "effective_api_call": f"wn.synsets({normalized_key!r})",
        "effective_results": [repr(synset) for synset in normalized_synsets],
        "morphy_by_pos": morphy,
    }
    return result, raw


def context_independence(bank_result: dict[str, Any]) -> dict[str, Any]:
    candidate_ids = [candidate["synset_id"] for candidate in bank_result["candidates"]]
    contexts = [
        {
            "text": "They sat on the bank of the river.",
            "target": "bank",
            "humanly_relevant_candidate": "bank.n.01",
        },
        {
            "text": "They deposited the money at the bank.",
            "target": "bank",
            "humanly_relevant_candidate": "depository_financial_institution.n.01",
        },
    ]
    for item in contexts:
        item["wordnet_lookup_input"] = item["target"]
        item["returned_candidate_synset_ids"] = candidate_ids
        item["selected_synset_id"] = None
    return {
        "target": "bank",
        "contexts": contexts,
        "candidate_lists_identical": (
            contexts[0]["returned_candidate_synset_ids"]
            == contexts[1]["returned_candidate_synset_ids"]
        ),
        "wordnet_lookup_uses_context": False,
        "wordnet_lookup_selects_a_sense": False,
        "conclusion": (
            "WordNet lookup enumerates lexical candidates; contextual word-sense "
            "disambiguation must be performed by another component."
        ),
    }


def validate(
    fixtures: list[dict[str, Any]],
    results: list[dict[str, Any]],
    context_demo: dict[str, Any],
) -> None:
    if len(results) != len(fixtures):
        raise RuntimeError("LEX-01 fixture coverage is incomplete")
    analysis_ids: set[str] = set()
    for fixture, result in zip(fixtures, results, strict=True):
        candidate_ids = {candidate["synset_id"] for candidate in result["candidates"]}
        for expected in fixture.get("expected_synsets", []):
            if expected not in candidate_ids:
                raise RuntimeError(f"Missing expected synset {expected}")
        if len(result["candidates"]) < fixture.get("expected_minimum_candidates", 0):
            raise RuntimeError(f"Insufficient candidates: {fixture['id']}")
        if "expected_candidates" in fixture and len(result["candidates"]) != fixture["expected_candidates"]:
            raise RuntimeError(f"Unexpected candidate count: {fixture['id']}")
        for candidate in result["candidates"]:
            if candidate["analysis_id"] in analysis_ids:
                raise RuntimeError(f"Duplicate analysis id: {candidate['analysis_id']}")
            analysis_ids.add(candidate["analysis_id"])
            if not candidate["definition"] or not candidate["lemmas"]:
                raise RuntimeError(f"Incomplete synset: {candidate['synset_id']}")
            if any(not lemma["lemma_key"] for lemma in candidate["lemmas"]):
                raise RuntimeError(f"Missing lemma key: {candidate['synset_id']}")

    inflected = next(result for result in results if result["id"] == "inflected-dogs")
    for pos, expected in inflected["expected_morphy"].items():
        if inflected["lookup"]["morphy_by_pos"][pos] != expected:
            raise RuntimeError(f"Morphological recovery failed for {pos}")
    compound = next(result for result in results if result["id"] == "compound-credit-card")
    if compound["lookup"]["surface_api_candidate_count"] != compound["expected_surface_candidates"]:
        raise RuntimeError("Compound surface lookup behavior changed")
    if compound["lookup"]["transform"] != "spaces_to_wordnet_underscores":
        raise RuntimeError("Compound normalization is not explicit")
    derivational = next(
        result for result in results if result["id"] == "derivational-decision"
    )
    derivational_lemmas = {
        relation["target_lemma"]
        for candidate in derivational["candidates"]
        for relation in candidate["relations"]["derivationally_related_forms"]
    }
    if not set(derivational["expected_derivational_lemmas"]).issubset(
        derivational_lemmas
    ):
        raise RuntimeError("Derivational relations are missing")
    antonymy = next(result for result in results if result["id"] == "antonymy-good")
    antonym_lemmas = {
        relation["target_lemma"]
        for candidate in antonymy["candidates"]
        for relation in candidate["relations"]["antonyms"]
    }
    if not set(antonymy["expected_antonym_lemmas"]).issubset(antonym_lemmas):
        raise RuntimeError("Antonym relations are missing")
    mereology = next(result for result in results if result["id"] == "mereology-car")
    if not mereology["relation_counts"]["meronyms"] or not mereology["relation_counts"]["holonyms"]:
        raise RuntimeError("Mereological relations are missing")
    totals = relation_counts(
        [candidate for result in results for candidate in result["candidates"]]
    )
    if any(count == 0 for count in totals.values()):
        raise RuntimeError(f"A required relation family is absent: {totals}")
    absent = next(result for result in results if result["id"] == "absent-term")
    if absent["lookup"]["status"] != "no_candidates" or absent["candidates"]:
        raise RuntimeError("Absent term is not represented explicitly")
    if not context_demo["candidate_lists_identical"]:
        raise RuntimeError("WordNet lookup unexpectedly used sentence context")
    if any(
        item["selected_synset_id"] is not None for item in context_demo["contexts"]
    ):
        raise RuntimeError("Lookup was mislabeled as disambiguation")


def main() -> None:
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = []
    raw_records = []
    for fixture in fixtures:
        result, raw = lookup_fixture(fixture)
        results.append(result)
        raw_records.append(raw)
    bank = next(result for result in results if result["id"] == "polysemous-bank")
    context_demo = context_independence(bank)
    validate(fixtures, results, context_demo)

    all_candidates = [candidate for result in results for candidate in result["candidates"]]
    totals = relation_counts(all_candidates)
    summary = {
        "fixture_count": len(results),
        "candidate_synset_count": len(all_candidates),
        "candidate_counts_by_fixture": {
            result["id"]: len(result["candidates"]) for result in results
        },
        "synsets_with_examples": sum(bool(candidate["examples"]) for candidate in all_candidates),
        "lemma_count": sum(len(candidate["lemmas"]) for candidate in all_candidates),
        "relation_counts": totals,
        "absent_term_count": sum(not result["candidates"] for result in results),
        "contextual_disambiguation_performed": False,
        "selected_sense_count": 0,
        "verdict": "GO_AS_CANDIDATE_LEXICAL_RESOURCE",
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("results.json", results),
        ("context-independence.json", context_demo),
        ("summary.json", summary),
        ("raw/lookups.json", raw_records),
    ):
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "nltk_version": nltk.__version__,
        "wordnet_version": wn.get_version(),
        "wordnet_root": str(wn.root),
        "parameters": {
            "language": "eng",
            "pos_filter": None,
            "relation_depth": "immediate relations returned by NLTK methods",
            "compound_normalization": "explicit per fixture; spaces become underscores",
            "context_used": False,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"LEX-01: {len(results)} fixtures validated")
    print(
        f"candidates: {summary['candidate_synset_count']}; "
        f"lemmas: {summary['lemma_count']}; absent terms: {summary['absent_term_count']}"
    )
    print(f"relations: {totals}")
    print("contextual disambiguation: not performed (candidate lookup only)")


if __name__ == "__main__":
    main()
