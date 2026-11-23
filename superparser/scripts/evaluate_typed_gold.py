"""Independent syntactic validity on gold UD-EWT TEST, not the Novel corpus.

Stanza receives only the gold token boundaries. It does NOT receive gold POS,
gold dependency labels or heads. The resulting UAS/LAS are accuracy estimates
against *annotated dependency truth*, not mere tree-validity percentages.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from research.typed_resource_poc.core import Word
from research.typed_resource_poc.evaluation import compare_to_gold, read_conllu
from research.typed_resource_poc.composition import compose_adjective_projections
from research.typed_resource_poc.alternatives import (
    evaluate_alternatives, propose_alternative_attachments
)
from research.typed_resource_poc.resources import UD_COMMIT, download, load_erg
from research.typed_resource_poc.core import induce_evidence


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache-dir", type=Path, default=Path("/tmp/seman2-typed-resource-poc"))
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--limit", type=int, help="Development smoke, never full gold evaluation")
    args = cli.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{UD_COMMIT}/"
    raw = download(prefix + "en_ewt-ud-test.conllu",
                   args.cache_dir / "ud-ewt-test.conllu").decode("utf-8")
    gold = read_conllu(raw)
    expected_count = len(gold)
    if args.limit is not None:
        gold = gold[:args.limit]
    elif expected_count < 1800:
        raise ValueError("Unexpectedly small UD-EWT TEST, refuse misleading score")
    training = download(prefix + "en_ewt-ud-train.conllu",
                        args.cache_dir / "ud-ewt-train.conllu").decode("utf-8")
    train_evidence = induce_evidence(training)
    erg = load_erg(args.cache_dir)
    import stanza
    stanza.download("en", processors="tokenize,pos,lemma,depparse",
                    model_dir=str(args.cache_dir / "stanza"), verbose=False)
    parser = stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse",
                             dir=str(args.cache_dir / "stanza"), use_gpu=False,
                             tokenize_pretokenized=True, verbose=False)
    predictions = []
    composition_counts = Counter()
    alternatives_totals = Counter()
    alternatives_witnesses = []
    unexpected = []
    case_examples = []
    for i, expected in enumerate(gold, 1):
        gold_tokens = [w.text for w in expected.tokens]
        try:
            doc = parser([gold_tokens])
            if len(doc.sentences) != 1:
                raise ValueError(f"Expected one sentence, got {len(doc.sentences)}")
            words = tuple(Word(id=int(w.id), text=w.text,
                               lemma=(w.lemma or w.text).lower(),
                               upos=w.upos or "X", head=int(w.head),
                               deprel=w.deprel or "dep", features=w.feats or "")
                          for w in doc.sentences[0].words)
        except Exception as exc:
            words = ()
            unexpected.append({"sent_id":expected.sent_id,"error":str(exc)[:320]})
        predictions.append(words)
        if len(words) == len(gold_tokens) and all(
            (g.id, g.text) == (p.id, p.text)
            for g,p in zip(expected.tokens, words)
        ):
            independent_alternatives = propose_alternative_attachments(
                words, train_evidence, erg["lexemes"])
            edge_score = evaluate_alternatives(
                expected.tokens, words, independent_alternatives)
            for key in ("gold","original_correct","original_predicted","proposed",
                        "proposed_correct","new_correct","new_false",
                        "supported_new_correct","supported_new_false",
                        "gold_missing_in_all_candidates"):
                alternatives_totals[key] += edge_score[key]
            alternatives_totals["sentences_with_new_proposals"] += (
                edge_score["new_correct"] + edge_score["new_false"] > 0)
            if len(alternatives_witnesses) < 40 and (
                edge_score["new_correct"] or edge_score["supported_new_false"]):
                alternatives_witnesses.append({
                    "sent_id": expected.sent_id, "text": expected.text,
                    "score": edge_score,
                    "candidates": [a.as_dict() for a in independent_alternatives],
                })
            projections = compose_adjective_projections(
                words, train_evidence, erg["lexemes"])
            composition_counts["sentences_with_composition"] += bool(projections)
            composition_counts["projections"] += len(projections)
            for p in projections:
                composition_counts["head_modifier_operations"] += sum(
                    op.kind == "head_modifier" for op in p.operations)
                composition_counts["candidate_pp_attachment_operations"] += sum(
                    op.kind == "head_pp_attachment_candidate" for op in p.operations)
                composition_counts["candidate_infinitival_attachment_operations"] += sum(
                    op.kind == "head_infinitival_attachment_candidate" for op in p.operations)
                composition_counts["modification_and_attachment_in_same_projection"] += (
                    any(op.kind == "head_modifier" for op in p.operations)
                    and any(op.kind != "head_modifier" for op in p.operations))
                composition_counts["lexical_head_preserved"] += (
                    p.features["HEAD"]["pos"] == "ADJ"
                    and p.lexical_head_id in {w.id for w in words if w.upos == "ADJ"})
                for h in p.lexical_hypotheses:
                    composition_counts["valence_not_yet_proven"] += (
                        not h["selected_complement_proven"])
                    composition_counts["candidate_with_train_evidence"] += (
                        h["ud_train_attestation"]["attestation_count"] > 0)
            if len(case_examples) < 12 and any(
                len(p.operations) >= 2 for p in projections):
                case_examples.append({
                    "sent_id": expected.sent_id,
                    "text": expected.text,
                    "typed": [p.as_dict() for p in projections if len(p.operations) >= 2],
                })
        if i % 250 == 0:
            print("GOLD_PROGRESS", i, "of", len(gold), "alignment_errors", len(unexpected), flush=True)
    report = compare_to_gold(gold, predictions)
    # A second held-out measurement deliberately withholds gold tokenization
    # and sentence boundaries, matching deployment on raw Novel prose.
    # Sample is chosen by stable sent_id hash, never by the model outcomes.
    from hashlib import sha256
    indices = sorted(range(len(gold)),
                     key=lambda i: sha256(gold[i].sent_id.encode("utf-8")).hexdigest())
    indices = indices[:min(len(gold), 200 if args.limit is None else 10)]
    raw_gold = [gold[i] for i in indices]
    raw_parser = stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse",
                                dir=str(args.cache_dir / "stanza"), use_gpu=False,
                                tokenize_pretokenized=False, verbose=False)
    raw_predictions = []
    raw_failed = []
    for g in raw_gold:
        try:
            doc = raw_parser(g.text)
            if len(doc.sentences) != 1:
                raise ValueError(f"raw parser split into {len(doc.sentences)} sentences")
            pw = tuple(Word(id=int(w.id), text=w.text,
                            lemma=(w.lemma or w.text).lower(), upos=w.upos or "X",
                            head=int(w.head), deprel=w.deprel or "dep",
                            features=w.feats or "") for w in doc.sentences[0].words)
        except Exception as exc:
            pw = ()
            raw_failed.append({"sent_id":g.sent_id, "error":str(exc)[:250]})
        raw_predictions.append(pw)
    raw_report = compare_to_gold(raw_gold, raw_predictions)
    token_gold_report = compare_to_gold(raw_gold, [predictions[i] for i in indices])
    report["raw_input_evaluation"] = {
        "selection": "200 stable SHA256(sent_id) samples from UD-EWT TEST",
        "n_sentences": len(raw_gold),
        "metrics": raw_report["metrics"],
        "counts": raw_report["counts"],
        "adjectival_relations": raw_report["adjectival_relations"],
        "reference_tokenization_on_same_subset": token_gold_report["metrics"],
        "raw_sample_source_ids_sha256": sha256(
            "\\n".join(g.sent_id for g in raw_gold).encode("utf-8")).hexdigest(),
        "errors": raw_failed[:20],
        "gold_tokens_supplied": False,
        "gold_sentence_boundaries_supplied": False,
        "unmatched_sentences_in_denominator": True,
    }
    print("RAW_INPUT_EVALUATION", json.dumps({
        "n":len(raw_gold), "raw_metrics":raw_report["metrics"],
        "gold_token_metrics_same_cases":token_gold_report["metrics"],
        "unaligned":raw_report["counts"].get("unaligned_sentences",0),
    }), flush=True)
    report["schema"] = "seman2-independent-ud-ewt-heldout-gold-v1"
    report["gold_dataset"] = "UD_English-EWT_test"
    report["gold_revision"] = UD_COMMIT
    report["full_gold_size"] = expected_count
    report["evaluated"] = len(gold)
    report["full_test_evaluated"] = len(gold) == expected_count
    report["stanza_version"] = stanza.__version__
    report["typed_composition"] = dict(composition_counts)
    report["independent_attachment_alternatives"] = {
        **dict(alternatives_totals),
        "source": "Typed constituent generation independent of selected Stanza edges",
        "baseline_recall": (
            round(alternatives_totals["original_correct"]/alternatives_totals["gold"],6)
            if alternatives_totals["gold"] else None),
        "oracle_recall_with_candidates": (
            round((alternatives_totals["original_correct"]+
                   alternatives_totals["new_correct"])/alternatives_totals["gold"],6)
            if alternatives_totals["gold"] else None),
        "proposed_precision": (
            round(alternatives_totals["proposed_correct"]/alternatives_totals["proposed"],6)
            if alternatives_totals["proposed"] else None),
        "new_candidate_precision": (
            round(alternatives_totals["new_correct"] / (
                alternatives_totals["new_correct"]+
                alternatives_totals["new_false"]),6)
            if (alternatives_totals["new_correct"]+
                alternatives_totals["new_false"]) else None),
        "supported_new_candidate_precision": (
            round(alternatives_totals["supported_new_correct"] / (
                alternatives_totals["supported_new_correct"]+
                alternatives_totals["supported_new_false"]),6)
            if (alternatives_totals["supported_new_correct"]+
                alternatives_totals["supported_new_false"]) else None),
        "witnesses": alternatives_witnesses,
        "not_a_selected_parse_score": True,
        "unlicensed_candidates_count_as_candidates": True,
        "claims": "UD-head candidates only, not validated lexical selection",
    }
    report["compositional_examples"] = case_examples
    report["exceptions"] = unexpected[:30]
    report["conclusions"] = {
        "meaning_of_uas_las": "Measured against independent UD gold (gold token boundaries provided)",
        "what_erg_means": "Lexical type candidates / head inheritance, not a full ERG parse",
        "not_proven": "Selection vs adjunct, exact lexical sense, semantic roles, correctness on Novel-1000",
        "does_this_improve_stanza_attachment_accuracy": False,
        "does_this_replace_seman2_grammar": False,
    }
    (args.out_dir / "gold-evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GOLD_EVALUATION", json.dumps({
        "size": report["evaluated"],
        "strict_uas": report["metrics"]["strict_uas_all"],
        "strict_las": report["metrics"]["strict_las_all"],
        "strict_upos": report["metrics"]["strict_upos_all"],
        "alignment": report["metrics"]["alignment_rate"],
        "adjective_relations": report["adjectival_relations"],
        "composition": report["typed_composition"],
        "alternative_search": {k:v for k,v in
            report["independent_attachment_alternatives"].items()
            if k not in {"witnesses","claims","source"}},
    }), flush=True)
    if args.limit is None and (
        report["counts"].get("unaligned_sentences", 0) > 50 or
        report["counts"]["gold_sentences"] != expected_count
    ):
        raise SystemExit("Gold evaluation misalignment exceeds accepted diagnostic threshold")


if __name__ == "__main__":
    main()
