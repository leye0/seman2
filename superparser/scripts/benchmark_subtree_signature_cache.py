"""Read-only held-out study: short observed grammatical subtrees in long prose.

IMPORTANT:
 * Train on canonical feature-unified *best trees* from three books only.
 * Test signature lookups on 17-32-token phrases from the fourth book.
 * No held-out tree or time is ever used for training.
 * A cache hit NEVER changes parsing or grammatical acceptance.
 * Measure lookup hit rate + CPU overhead + full-rule-tree witness rate.
 * Four novels were used historically; not a genuinely unseen new-author test.

The program intentionally does not claim parser acceleration from hint lookup.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns, process_time_ns

from research.verbnet_lr.subtree_signature_cache import (
    SubtreeSignatureCache, SignatureScan, witnessed_matches,
)
from research.verbnet_lr.subtree_feature_replay import SubtreeFeatureReplayer
from scripts.benchmark_heavy_sentence_ab import BANDS, choose_cases
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def pct(values,q):
    if not values:
        return None
    values=sorted(values)
    at=(len(values)-1)*q
    k=int(at)
    return round(values[k]+(values[min(k+1,len(values)-1)]-values[k])*(at-k),5)


def aggregate(rows):
    scored=[r for r in rows if r["query_attempted"]]
    complete=[r for r in scored if r["test_completed"]]
    return {
        "sentences":len(rows),
        "queries":len(scored),
        "sentences_with_hint":sum(r["hint_count"]>0 for r in scored),
        "matched_spans":sum(r["span_count"] for r in scored),
        "hint_occurrences":sum(r["hint_count"] for r in scored),
        "transitions":sum(r["signature_transitions"] for r in scored),
        "capped_queries":sum(r["signature_budget_exceeded"] for r in scored),
        "verified_test_trees":len(complete),
        "cache_hints_witnessed_in_best":sum(r["full_shape_witnesses"] for r in complete),
        "total_signature_cpu_ms":round(sum(r["scan_cpu_ms"] for r in scored),4),
        "total_signature_wall_ms":round(sum(r["scan_wall_ms"] for r in scored),4),
        "signature_p50_cpu_ms":pct([r["scan_cpu_ms"] for r in scored],.5),
        "signature_p95_cpu_ms":pct([r["scan_cpu_ms"] for r in scored],.95),
        "canonical_parse_cpu_ms":round(sum(r["parse_cpu_ms"] for r in scored),4),
        "canonical_completion":sum(r["test_completed"] for r in scored),
        "canonical_saturations":sum(r["forest_saturated"] for r in scored),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=12)
    p.add_argument("--train-per-book-per-band",type=int,default=12)
    p.add_argument("--max-signature-tokens",type=int,default=8)
    p.add_argument("--max-templates",type=int,default=20000)
    p.add_argument("--replay-min-tokens",type=int,default=4)
    p.add_argument("--replay-max-hints",type=int,default=30)
    p.add_argument("--replay-work-limit",type=int,default=400)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    raw,sources=choose_cases(args.per_book_per_band)
    training_raw,training_sources=choose_cases(args.train_per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)

    # One parse per training sentence. The stored data are complete
    # grammatical ChartItem tree shapes, not seen text or inferred gold.
    short_training={}
    training_attempts=Counter()
    training_completed=Counter()
    for row in training_raw:
        if row["tokens"]>16 or any(
            q in row["text"] for q in ('"','“','”','‘','’')):
            continue
        book=row["book_id"]
        training_attempts[book]+=1
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        result=parser.parse_grammar_lattice(
            lattice,max_items=20000,kbest_work_limit=100000)
        tree=result.best()
        if tree is None:
            continue
        training_completed[book]+=1
        short_training.setdefault(book,[]).append((lattice,tree))

    holdout_books=sorted(set(row["book_id"] for row in raw))
    index_per_book={}
    training_info={}
    for heldout in holdout_books:
        cache=SubtreeSignatureCache(
            min_tokens=2,max_tokens=args.max_signature_tokens,
            max_templates=args.max_templates)
        for book,examples in short_training.items():
            if book==heldout:
                continue
            for lattice,tree in examples:
                cache.observe(tree,lattice)
        cache.freeze()
        index_per_book[heldout]=cache
        training_info[str(heldout)]={
            "attempted_from_others":sum(
                v for k,v in training_attempts.items() if k!=heldout),
            "completed_from_others":sum(
                v for k,v in training_completed.items() if k!=heldout),
            **cache.summary(),
        }

    replayers={book:SubtreeFeatureReplayer(
        index_per_book[book].templates,parser._vector_grammar.grammar)
        for book in holdout_books}
    rows=[]
    args.out_dir.mkdir(parents=True,exist_ok=True)
    with (args.out_dir/"per_sentence.jsonl").open(
        "w",encoding="utf8",buffering=1) as output:
        for item in raw:
            if item["tokens"]<17 or any(
                q in item["text"] for q in ('"','“','”','‘','’')):
                continue
            heldout=item["book_id"]
            cache=index_per_book[heldout]
            lattice=build_lattice(item["text"],resources.lexicon,multiword_max=1)
            begin=perf_counter_ns()
            cpu_start=process_time_ns()
            scan=cache.scan(lattice,max_transitions=25000,max_matches=2000)
            scan_cpu_ms=(process_time_ns()-cpu_start)/1e6
            scan_wall_ms=(perf_counter_ns()-begin)/1e6
            # Check the longest, most informative hints first. Only a
            # capped selection is replayed; skipped hints stay UNKNOWN,
            # not ungrammatical. No data or decision enters the parser.
            eligible=sorted(
                (hint for hint in scan.matches
                 if hint.end_token-hint.start_token>=args.replay_min_tokens),
                key=lambda h:(-(h.end_token-h.start_token),h.start_token,
                              h.template_id))
            attempted=eligible[:args.replay_max_hints]
            replay_start=process_time_ns()
            prepared=replayers[heldout].prepare(lattice)
            replay=[replayers[heldout].replay(
                hint,lattice,max_steps=args.replay_work_limit,
                prepared_options=prepared)
                for hint in attempted]
            replay_cpu_ms=(process_time_ns()-replay_start)/1e6
            replay_statuses=Counter(result.status for result in replay)
            parse_start=process_time_ns()
            result=parser.parse_grammar_lattice(
                lattice,max_items=20000,kbest_work_limit=100000)
            tree=result.best()
            parse_ms=(process_time_ns()-parse_start)/1e6
            witnessed=witnessed_matches(scan,cache,tree,lattice) if tree else 0
            selected_scan=SignatureScan(tuple(
                hint for hint,result in zip(attempted,replay)
                if result.status=="WITNESS"),
                scan.transitions,scan.saturated,scan.lexical_tokens)
            replay_witnessed=(witnessed_matches(
                selected_scan,cache,tree,lattice) if tree else 0)
            unique_spans={(hint.start_token,hint.end_token)
                          for hint in scan.matches}
            kinds=Counter(hint.root_category for hint in scan.matches)
            occurrence_by_length=Counter(
                str(hint.end_token-hint.start_token)
                for hint in scan.matches)
            witnessed_by_length={}
            if tree is not None:
                for size in range(2,args.max_signature_tokens+1):
                    selected=SignatureScan(tuple(
                        h for h in scan.matches
                        if h.end_token-h.start_token==size),
                        scan.transitions,scan.saturated,scan.lexical_tokens)
                    witnessed_by_length[str(size)]=witnessed_matches(
                        selected,cache,tree,lattice)
            rec={
                "book_id":heldout,"band":item["band"],"tokens":item["tokens"],
                "query_attempted":True,"hint_count":len(scan.matches),
                "hints_by_length":dict(occurrence_by_length),
                "witnesses_by_length":witnessed_by_length,
                "span_count":len(unique_spans),
                "signature_transitions":scan.transitions,
                "signature_budget_exceeded":scan.saturated,
                "scan_cpu_ms":round(scan_cpu_ms,5),
                "scan_wall_ms":round(scan_wall_ms,5),
                "parse_cpu_ms":round(parse_ms,5),
                "test_completed":result.completed,
                "forest_saturated":bool(result.stats.get("budget_exceeded")),
                "full_shape_witnesses":witnessed,
                "replay_eligible_count":len(eligible),
                "replay_attempted_count":len(attempted),
                "replay_skipped_count":len(eligible)-len(attempted),
                "replay_statuses":dict(replay_statuses),
                "replay_cpu_ms":round(replay_cpu_ms,5),
                "replay_rule_steps":sum(x.unification_attempts for x in replay),
                "replay_witnesses_confirmed_in_best":replay_witnessed,
                "root_hint_counts":dict(kinds),
                "matched_template_ids":sorted({h.template_id for h in scan.matches}),
            }
            rows.append(rec)
            output.write(json.dumps(rec,ensure_ascii=False)+"\n")
            if len(rows)%12==0:
                print("SIGNATURE_CACHE_PROGRESS",json.dumps({
                    "queries":len(rows),"hits":sum(r["hint_count"]>0 for r in rows),
                    "witnesses":sum(r["full_shape_witnesses"] for r in rows),
                }),flush=True)
    overall=aggregate(rows)
    report={
        "schema":"read-only-cross-author-subtree-signatures-v1",
        "sources":sources,
        "training_sources":training_sources,
        "hint_length_breakdown": {
            "hits":dict(sum((Counter(r["hints_by_length"]) for r in rows),
                            Counter())),
            "witnesses_in_best":dict(sum(
                (Counter(r["witnesses_by_length"]) for r in rows),
                Counter())),
        },
        "feature_replay": {
            "minimum_tokens":args.replay_min_tokens,
            "max_hints_per_sentence":args.replay_max_hints,
            "work_limit_per_hint":args.replay_work_limit,
            "selection":"longest eligible spans first, not selected by parse outcome",
        },
        "feature_replay_totals": {
            "eligible_hints":sum(r["replay_eligible_count"] for r in rows),
            "attempted_hints":sum(r["replay_attempted_count"] for r in rows),
            "skipped_hints":sum(r["replay_skipped_count"] for r in rows),
            "statuses":dict(sum(
                (Counter(r["replay_statuses"]) for r in rows),Counter())),
            "cpu_ms":round(sum(r["replay_cpu_ms"] for r in rows),4),
            "witnesses_confirmed_in_best":sum(
                r["replay_witnesses_confirmed_in_best"] for r in rows),
        },
        "training_by_heldout_book":training_info,
        "all":overall,
        "by_band":{label:aggregate([r for r in rows if r["band"]==label])
                   for label,_,_ in BANDS},
        "by_book":{str(book):aggregate([r for r in rows if r["book_id"]==book])
                   for book in holdout_books},
        "notes":[
            "Training observations are feature-unified canonical best trees, NOT human gold.",
            "Every held-out book is excluded from its own template cache.",
            "Training may be denser than evaluation, but held-out books remain entirely excluded.",
            "The cache records complete subtree rule-ID shapes, not text, lemmas, personal information, or semantic truths.",
            "The query recognizes all candidate POS alternatives without materializing their cross product.",
            "A signature hit is a HINT ONLY and never creates a parse or skips the canonical parser.",
            "Only complete held-out trees permit full-shape witness comparisons; other hits remain UNKNOWN.",
            "No timing speedup is claimed: the probe currently adds its measured cost on a hit or miss.",
            "The four novels are historically explored; independent authors are required before rollout.",
            "No lexical candidate, quote or punctuation has been modified or pruned.",
            "Fixed-shape feature witnesses are not contextual/exhaustive; this probe does NOT skip parser recognition.",
            "Replay CPU includes preparation of one candidate/span index per test sentence.",
            "Only bounded hints of length >= replay-min-tokens are checked; other hits remain UNKNOWN.",
        ],
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SIGNATURE_CACHE_FINAL",json.dumps(report),flush=True)


if __name__=="__main__":
    main()
