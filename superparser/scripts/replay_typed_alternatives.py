"""Fast, reproducible evaluation without running Stanza again.

Input is the frozen held-out gold/prediction pair artifact from
scripts.evaluate_typed_gold. Only **external train** dependencies and ERG types
can supply lexical evidence. The gold labels are consulted for scoring,
never as features in the alternative generator.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from research.typed_resource_poc.alternatives import (
    evaluate_alternatives, propose_alternative_attachments
)
from research.typed_resource_poc.core import Word, induce_evidence
from research.typed_resource_poc.resources import UD_COMMIT, download, load_erg


def replay(pairs: Path, cache: Path) -> dict:
    prefix = f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{UD_COMMIT}/"
    train = download(prefix + "en_ewt-ud-train.conllu",
                     cache / "ud-ewt-train.conllu").decode("utf-8")
    evidence = induce_evidence(train)
    erg = load_erg(cache)["lexemes"]
    totals: Counter[str] = Counter()
    cases = []
    for line in pairs.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        gold = tuple(Word(**w) for w in row["gold"])
        pred = tuple(Word(**w) for w in row["predicted"])
        # No feature from gold enters this generator.
        candidates = propose_alternative_attachments(pred, evidence, erg)
        score = evaluate_alternatives(gold,pred,candidates)
        for key in ("gold","original_correct","original_predicted","proposed",
                    "proposed_correct","new_correct","new_false",
                    "supported_new_correct","supported_new_false",
                    "admissible_new_correct","admissible_new_false",
                    "gold_missing_in_all_candidates"):
            totals[key] += score[key]
        totals["sentences"] += 1
        if score["admissible_new_correct"] or score["admissible_new_false"]:
            cases.append({"sent_id":row["sent_id"], "text":row["text"],
                          "score":score,
                          "accepted_alternatives":[c.as_dict() for c in candidates
                            if c.status == "cross_resource_admissible_candidate"]})
    accepted_den = totals["admissible_new_correct"]+totals["admissible_new_false"]
    return {"schema":"seman2-frozen-typed-alternative-replay-v1",
            "source":"UD English EWT heldout gold / frozen Stanza predictions",
            "n_sentences":totals["sentences"], "counts":dict(totals),
            "admissible_precision":(round(totals["admissible_new_correct"]/accepted_den,6)
                                    if accepted_den else None),
            "admissible_oracle_recall":(
                round((totals["original_correct"]+totals["admissible_new_correct"])/
                      totals["gold"],6) if totals["gold"] else None),
            "novel_correction_not_established": True,
            "candidates_are_not_automatically_selected":True,
            "admissible_witnesses":cases}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--cache-dir",type=Path,default=Path("/tmp/seman2-typed-resource-poc"))
    p.add_argument("--expected-gold-report",type=Path)
    args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    report=replay(args.pairs,args.cache_dir)
    if args.expected_gold_report:
        previous=json.loads(args.expected_gold_report.read_text(encoding="utf-8"))
        baseline=previous["independent_attachment_alternatives"]
        for key,val in report["counts"].items():
            if key=="sentences":continue
            if val!=baseline[key]:
                raise ValueError(f"Frozen replay diverged on {key}: {val} != {baseline[key]}")
    (args.out_dir/"fast-alternative-replay.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("FROZEN_ALTERNATIVE_REPLAY",json.dumps({
        "n":report["n_sentences"],"counts":report["counts"],
        "admissible_precision":report["admissible_precision"],
        "admissible_oracle_recall":report["admissible_oracle_recall"],
    }),flush=True)


if __name__=="__main__":
    main()
