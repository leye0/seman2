"""Run the independent multi-resource POC against the exact pinned Novel-1000 v3 corpus.

A third-party UD dependency parser provides syntax. External reference layers
attach typed lexical hypotheses with traceable provenance. This is NOT the
canonical Seman2 Parser and cannot be compared as a Seman2 completed-score.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path

from research.typed_resource_poc.core import (
    TYPES, Word, classify_attestation, grammatical_observations,
    nonwhitespace_coverage, source_sha, validate_dependency_tree,
)
from research.typed_resource_poc.resources import export_inventory, load_wordnet
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input
from scripts import novel_source_reporting_v3 as novel
from scripts import novel_ladder as ladder

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research" / "typed_resource_poc"


def stanza_words(sentence) -> list[Word]:
    return [Word(id=int(w.id), text=w.text, lemma=(w.lemma or w.text).casefold(),
                 upos=w.upos or "X", head=int(w.head), deprel=w.deprel or "dep",
                 features=w.feats or "") for w in sentence.words]


def parse_independent(text: str, nlp, evidence: dict, wordnet) -> dict:
    document = nlp(text)
    erg = evidence["erg"]["lexemes"]
    framenet = evidence["framenet"]["frames"]
    verbnet = evidence["verbnet"]["lemmas"]
    coverage_spans = []
    sentence_rows = []
    observed = []
    totals = Counter()
    lexical = Counter()
    models_used = set()
    for sentence in document.sentences:
        words = stanza_words(sentence)
        valid, reason = validate_dependency_tree(words)
        totals["ud_sentences"] += 1
        totals["valid_ud_trees"] += int(valid)
        if not valid:
            totals["invalid_ud_trees"] += 1
        traces = []
        for w in words:
            lemma = w.lemma.lower()
            ergt = erg.get(lemma, [])
            fpos = {"VERB": "v", "AUX": "v", "ADJ": "a",
                    "ADV": "adv", "NOUN": "n"}.get(w.upos, "")
            fn = framenet.get(f"{lemma}|{fpos}", [])
            vn = verbnet.get(lemma, []) if w.upos in {"VERB", "AUX"} else []
            wn_pos = {"VERB": "v", "AUX": "v", "ADJ": "a", "ADV": "r",
                      "NOUN": "n"}.get(w.upos)
            wn_n = len(wordnet.synsets(lemma, pos=wn_pos)) if wn_pos else 0
            if ergt:
                lexical["tokens_with_erg_class"] += 1
            if fn:
                lexical["tokens_with_framenet_candidates"] += 1
            if vn:
                lexical["tokens_with_verbnet_classes"] += 1
            if wn_n:
                lexical["tokens_with_wordnet_senses"] += 1
            lexical["tokens_total"] += 1
            support = sum(bool(x) for x in (ergt, fn, vn, wn_n))
            lexical["tokens_multi_reference"] += int(support >= 2)
            traces.append({"id": w.id, "text": w.text, "lemma": w.lemma,
                           "upos": w.upos, "head": w.head, "deprel": w.deprel,
                           "feats": w.features,
                           "references": {"erg_lex_types": ergt[:10],
                                          "framenet_frames": fn[:10],
                                          "verbnet_classes": vn[:10],
                                          "wordnet_senses_count": wn_n}})
        for obs in grammatical_observations(words):
            o = dict(obs)
            if obs["kind"] == "adjective_to_pp_candidate":
                o["type_hypothesis"] = "adjective-with-to-pp"
            elif obs["kind"] == "adjective_to_infinitive_candidate":
                o["type_hypothesis"] = "adjective-with-to-infinitive"
            elif obs["kind"] == "adjective_adverb_modification":
                o["type_hypothesis"] = "degree-adverb"  # candidate only, not asserted
            o["grammatical_features"] = TYPES.effective(o["type_hypothesis"])
            o["ud_train_evidence"] = classify_attestation(
                obs["head"], obs["kind"], evidence["ud"])
            o["status"] = "hypothesis"  # PP adjunct/selection remains unresolved
            observed.append(o)
            totals[obs["kind"]] += 1
            if o["ud_train_evidence"]["attestation_count"]:
                totals["hypotheses_with_ud_train_evidence"] += 1
        sentence_rows.append({"valid_tree": valid, "reason": reason,
                              "words": traces})
        for token in sentence.tokens:
            if token.start_char is not None and token.end_char is not None:
                coverage_spans.append((int(token.start_char), int(token.end_char)))
    aligned = nonwhitespace_coverage(text, coverage_spans)
    return {"source_text": text, "source_sha256": source_sha(text),
            "analysis": {"sentences": sentence_rows,
                         "observed_grammatical_relations": observed,
                         "source_nonwhitespace_covered": aligned},
            "counts": {**totals, **lexical, "source_covered": int(aligned)}}


def pinned_novel_sources() -> tuple[str, list[tuple[str, dict]]]:
    manifest, groups, _ = novel.prepare()
    expected = ladder.read_json(novel.DIRECTORY / "source-manifest.json")
    if manifest != expected:
        raise ValueError("Frozen Novel-1000 v3 manifest does not match source extraction")
    cases = [(item["transfer_id"], item) for key, (_, group) in groups.items()
             if key != "witnesses" for item in group]
    if len(cases) != 1000 or len({name for name,_ in cases}) != 1000:
        raise ValueError("Expected 1000 unique untouched Novel-1000 source cases")
    return ladder.digest(manifest), cases


def controls(nlp, evidence: dict, wn) -> list[dict]:
    # Prospective grammatical contrasts, never entries in the induced lexicon.
    examples = (
        "Extremely averse to delay.",
        "Prone to errors.",
        "Happy to help.",
        "Extremely pretty.",
        "They can read the book.",
        "They want to read the book.",
        "He did read the book.",
        "The child who we met arrived.",
        "The extremely happy child arrived.",
    )
    return [{"text": text,
             "observations": parse_independent(text, nlp, evidence, wn)
                 ["analysis"]["observed_grammatical_relations"]}
            for text in examples]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, default=Path("/tmp/seman2-typed-resource-poc"))
    p.add_argument("--limit", type=int, help="Development smoke only; never label partial as Novel-1000")
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dataset_sha, cases = pinned_novel_sources()
    if args.limit is not None:
        if not 1 <= args.limit <= 1000:
            p.error("--limit requires 1..1000")
        cases = cases[:args.limit]

    packaged_vn = ROOT / "research" / "verbnet_lr" / "verbnet34.compiled.json.gz"
    evidence = export_inventory(args.cache_dir, packaged_vn)
    wn = load_wordnet(args.cache_dir)
    print("EXTERNAL_INVENTORY", json.dumps({
        "erg_lexicon_entries": evidence["erg"]["lexicon_entries_detected"],
        "erg_lexemes": evidence["erg"]["lexicon_stems"],
        "erg_samples": evidence["erg"]["lexicon_samples"],
        "erg_types": len(evidence["erg"]["types"]),
        "framenet_lexical_units": evidence["framenet"]["lexical_units"],
        "framenet_keys": evidence["framenet"]["entries"],
        "verbnet_lemmas": evidence["verbnet"]["lemma_count"],
        "verbnet_structure": evidence["verbnet"]["top_level_keys"],
        "ud_patterns": evidence["ud"]["counts"]
    }), flush=True)

    import stanza
    stanza.download("en", processors="tokenize,pos,lemma,depparse",
                    model_dir=str(args.cache_dir / "stanza"), verbose=False)
    pipeline = stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse",
                              dir=str(args.cache_dir / "stanza"), use_gpu=False,
                              verbose=False)
    totals = Counter()
    by_group = {}
    exceptions = []
    outputs = []
    for i, (case_id, case) in enumerate(cases, 1):
        prepared = prepare_corpus_input(case)
        text = prepared.analysis_text
        try:
            observed = parse_independent(text, pipeline, evidence, wn)
        except Exception as exc:
            observed = {"source_text": text, "source_sha256": source_sha(text),
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                        "counts": {"error": 1}}
            exceptions.append({"case": case_id, **observed["error"]})
        group = case_id.split("-")[0]
        totals.update(observed["counts"])
        by_group.setdefault(group, Counter()).update(observed["counts"])
        row = {"case_id": case_id, "source_span": case["structural_core_source_span"],
               "book_id": case["book_id"], "source_sha256": observed["source_sha256"],
               **observed}
        outputs.append(row)
        if i % 100 == 0:
            print("PROGRESS", i, "of", len(cases), "covered", totals["source_covered"],
                  "invalid", totals["invalid_ud_trees"], "errors", totals["error"],
                  flush=True)
    with (args.out_dir / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in outputs:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {
        "schema": "seman2-external-typed-grammar-poc-v1",
        "kind": "independent_multisource_diagnostic_not_Seman2_success_score",
        "corpus": "Novel-1000-v3", "manifest_sha256": dataset_sha,
        "n_cases_expected": 1000, "n_cases_evaluated": len(cases),
        "complete_benchmark": len(cases) == 1000, "stanza_version": stanza.__version__,
        "sources": evidence["sources"], "external_inventory": {
            "erg_entries": evidence["erg"]["lexicon_entries_detected"],
            "erg_lexemes": evidence["erg"]["lexicon_stems"],
            "erg_types": len(evidence["erg"]["types"]),
            "framenet_index_entries": evidence["framenet"]["entries"],
            "verbnet_lemmas": evidence["verbnet"]["lemma_count"],
            "ud_external_attested_patterns": evidence["ud"]["counts"],
        }, "totals": dict(totals),
        "by_group": {k: dict(v) for k,v in sorted(by_group.items())},
        "errors": exceptions, "controls": controls(pipeline, evidence, wn),
        "interpretation": {
            "source_covered": "Only token/source-character alignment; not grammar correctness",
            "valid_ud_trees": "Well-formed dependency structure, not correct attachment",
            "grammatical_hypotheses": "UD child relations plus external type inventory",
            "ud_attested": "UD EWT TRAIN frequency of attachment, not proof of lexical selection",
            "framenet": "Candidate frames per lemma/POS, not WSD or argument binding",
            "erg": "TDL lexical type names, not a full ERG derivation",
            "comparable_to_Seman2_completed": False,
        }
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("POC_SUMMARY", json.dumps({
        "n_cases_evaluated": len(cases),
        "source_covered": totals["source_covered"],
        "valid_ud_trees": totals["valid_ud_trees"],
        "invalid_ud_trees": totals["invalid_ud_trees"],
        "errors": totals["error"],
        "adjective_to_pp_candidates": totals["adjective_to_pp_candidate"],
        "adjective_to_infinitive_candidates": totals["adjective_to_infinitive_candidate"],
        "adjective_adverb_modification": totals["adjective_adverb_modification"],
        "hypotheses_with_ud_train_evidence": totals["hypotheses_with_ud_train_evidence"],
        "tokens_with_erg_class": totals["tokens_with_erg_class"],
        "tokens_with_framenet_candidates": totals["tokens_with_framenet_candidates"],
        "tokens_with_verbnet_classes": totals["tokens_with_verbnet_classes"],
        "tokens_with_wordnet_senses": totals["tokens_with_wordnet_senses"],
    }), flush=True)
    if len(cases) == 1000 and (totals["error"] or totals["source_covered"] < 950):
        raise SystemExit("Unacceptable source processing failures in full Novel-1000 benchmark")


if __name__ == "__main__":
    main()
