"""C-only experiment: learn typed recursive grammar patterns from novel fragments.

No regex string backtracking, no arbitrary X*: recursively licensed original
grammar rules yield repetition, alternative productions yield alternation,
and variable features stay subject to the same Seman2 grammar unifier.

Test authors/books are completely held out. Evaluation distinguishes ANY
short-subtree hit from a NEW, previously unseen entire tree shape spanning
at least 5/8/12 tokens. Explicit budgets/truncations and time costs reported.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS, TEST_BOOKS, download, extract,
    spread_training, holdout_stratified, length_band
)
from research.verbnet_lr.hierarchical_pattern_memory import HierarchicalPatternMemory
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader

ROOT=Path(__file__).resolve().parents[1]


def rate(k,n):
    return round(100*k/n,2) if n else 0.0


def quantile(data,ratio):
    if not data:return None
    values=sorted(data)
    return round(values[int((len(values)-1)*ratio)],3)


def run(*,wordnet_dir,train_size=2000,eval_per_band=20,
        min_rule_support=2,max_span=18,max_expansions=20000,
        max_wall_ms=500,variants_per_cell=2):
    train_books={};test_books={};catalog=[]
    for book in (*TRAIN_BOOKS,*TEST_BOOKS):
        body,meta=download(book)
        rows,stats=extract(book,body,length_min=4,length_max=45)
        (train_books if book.role=="train" else test_books)[book.ebook_id]=rows
        catalog.append({"id":book.ebook_id,"role":book.role,
                        "sha256":meta["sha256"],
                        "candidate_sentences":stats["eligible"]})
        print("BOOK "+str(book.ebook_id)+" candidates="+str(stats["eligible"]),
              flush=True)
    training=spread_training(train_books,train_size)
    evaluation=holdout_stratified(test_books,per_book_per_band=eval_per_band)
    if len(training)!=train_size or not evaluation:
        raise ValueError("Not enough corpus sentences")
    if {x["author"] for x in training} & {x["author"] for x in evaluation}:
        raise RuntimeError("Held-out author leakage")

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    reader=SemanCompiledReader(resources,token_only_lattice=True)
    learner=HierarchicalPatternMemory(
        resources,min_rule_sentences=min_rule_support,max_span=max_span,
        max_expansions=max_expansions,max_wall_ms=max_wall_ms,
        variants_per_cell=variants_per_cell)
    stats=Counter()
    for i,case in enumerate(training,1):
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        result=reader.parse(case["text"],lattice=lattice,
                            capture_partials=True,max_partial_constituents=256)
        observation=learner.observe(
            result.partial_constituents,failed=not result.complete,sentence_id=i)
        stats["parsed_input_sentences"]+=1
        stats["full_sentence_success"]+=int(result.complete)
        stats["full_sentence_failed"]+=int(not result.complete)
        stats["failed_sentence_had_any_reduction"]+=int(
            not result.complete and bool(result.partial_constituents))
        stats["failed_sentence_reused_some_partial_tree"]+=int(
            not result.complete and observation["reused_subtree_shapes"]>0)
        stats["captured_local_reductions"]+=len(result.partial_constituents)
        stats["partial_capture_truncated"]+=int(result.partial_truncated)
        if i%500==0:
            print("TRAIN "+json.dumps({
                "seen":i,"full_succeeded":stats["full_sentence_success"],
                "used_pattern_rules":learner.summary()["active_rule_ids"],
                "learned_recursions":
                    len(learner.summary()["recursive_extension_rule_ids"]),
            }),flush=True)

    totals=Counter()
    by_length=defaultdict(Counter)
    by_book=defaultdict(Counter)
    categories=Counter()
    cutoffs=Counter()
    timings=[]
    longest_examples=Counter()
    for i,case in enumerate(evaluation,1):
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        result=reader.parse(case["text"],lattice=lattice)
        matched=learner.match(lattice,min_report_tokens=3)
        timings.append(matched.elapsed_ms)
        for reason in matched.cutoff_reasons:
            cutoffs[reason]+=1
        novelty=any(h.structurally_novel for h in matched.hits)
        for b in (totals,by_length[length_band(case["tokens"])],
                  by_book[str(case["book_id"])]):
            b["tested"]+=1
            b["baseline_full_sentence_success"]+=int(result.complete)
            b["any_hierarchical_subtree"]+=int(bool(matched.hits))
            b["any_unseen_tree_shape"]+=int(novelty)
            b["hit_at_least_5_tokens"]+=int(matched.count_at_least(5)>0)
            b["hit_at_least_8_tokens"]+=int(matched.count_at_least(8)>0)
            b["hit_at_least_12_tokens"]+=int(matched.count_at_least(12)>0)
            b["NEW_tree_at_least_5_tokens"]+=int(
                matched.count_at_least(5,novel=True)>0)
            b["NEW_tree_at_least_8_tokens"]+=int(
                matched.count_at_least(8,novel=True)>0)
            b["NEW_tree_at_least_12_tokens"]+=int(
                matched.count_at_least(12,novel=True)>0)
            b["budget_truncated"]+=int(matched.incomplete)
            b["grammar_unifications_attempted"]+=matched.expansions
            b["grammar_unifications_passed"]+=matched.successful_reductions
        if matched.hits:
            length=max(h.tokens for h in matched.hits)
            longest_examples[length]+=1
        for h in matched.hits:
            if h.tokens>=8 and h.structurally_novel:
                categories[h.category]+=1
        if i%40==0:
            print("EVAL "+json.dumps({
                "seen":i,
                "new_ge5":totals["NEW_tree_at_least_5_tokens"],
                "new_ge8":totals["NEW_tree_at_least_8_tokens"],
                "new_ge12":totals["NEW_tree_at_least_12_tokens"],
                "truncated":totals["budget_truncated"],
            }),flush=True)
    return {
        "schema":"seman2-hierarchical-grammar-pattern-C-v1",
        "book_catalog":catalog,
        "training_counts":dict(stats),
        "learned_pattern_system":learner.summary(),
        "heldout_counts":dict(totals),
        "heldout_by_length":{k:dict(v) for k,v in sorted(by_length.items())},
        "heldout_by_book":dict(by_book),
        "long_novel_tree_categories":dict(categories),
        "search_cutoff_reason_counts":dict(cutoffs),
        "longest_hit_length_distribution":dict(longest_examples),
        "latency_ms":{"p50":quantile(timings,.5),
                      "p95":quantile(timings,.95),
                      "p99":quantile(timings,.99)},
        "budget":{"max_span":max_span,"max_expansions":max_expansions,
                  "max_wall_ms":max_wall_ms,
                  "variants_per_cell":variants_per_cell,
                  "min_rule_support":min_rule_support},
        "interpretation":[
            "Hierarchical alternation = alternative ORIGINAL observed grammar rules with same LHS.",
            "Hierarchical repetition = reuse of an observed ORIGINAL recursive grammar rule, e.g. NP -> NP PP; not regex backtracking.",
            "Option-like repetition requires both base and recursive productions observed in different sentences.",
            "Every accepted subtree is constructed by original typed grammar rule unification; lexical senses remain alternatives.",
            "Novel structural hit = a complete tree rule-shape never observed in training; this is not independent grammatical gold.",
            "Corpus heldout authors: Jane Eyre (Bronte), Middlemarch (Eliot); no word identity is cached.",
            "Grammar-rule activation requires evidence from at least two different training sentences.",
            "Large numbers of valid local subtrees do NOT mean globally correct attachment or semantic interpretation.",
            "Beam, finite-width chart, search budget and time cutoff can hide additional valid candidates.",
            "This experiment does not prove safety on grammatical negative controls or a production p95 target.",
            "The experiment compares new hierarchical composition to whole-sentence completion ONLY, not to a fully optimized exact-subtree memory.",
        ]
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--train",type=int,default=2000)
    p.add_argument("--eval-per-band",type=int,default=20)
    p.add_argument("--max-expansions",type=int,default=20000)
    p.add_argument("--max-wall-ms",type=int,default=500)
    p.add_argument("--max-span",type=int,default=18)
    p.add_argument("--variants-per-cell",type=int,default=2)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=run(wordnet_dir=a.wordnet_dir,
               train_size=a.train,eval_per_band=a.eval_per_band,
               max_expansions=a.max_expansions,
               max_wall_ms=a.max_wall_ms,max_span=a.max_span,
               variants_per_cell=a.variants_per_cell)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print("FINAL "+json.dumps({
        "training":report["training_counts"],
        "patterns":report["learned_pattern_system"],
        "holdout":report["heldout_counts"],
        "latency_ms":report["latency_ms"],
        "cutoff_reasons":report["search_cutoff_reason_counts"],
    }),flush=True)


if __name__=="__main__":
    main()
