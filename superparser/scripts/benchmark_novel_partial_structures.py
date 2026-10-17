"""Evaluate locally unified grammar subtrees salvaged from FAILED novels.

Train and test books/authors are disjoint. Fast compiled L-R remains unchanged
unless opt-in capture_partials=True. A captured subtree is tentative grammar
evidence, and on unseen text its original rule tree MUST unify again.
Neither exact word identity nor arbitrary lexical-ambiguity equality is used.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS,TEST_BOOKS,download,extract,spread_training,
    holdout_stratified,length_band
)
from research.verbnet_lr.partial_structure_memory import PartialStructureMemory
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader

ROOT=Path(__file__).resolve().parents[1]


def run(wordnet_dir,*,train_size=3500,eval_per_band=40,
        min_partial_tokens=2,max_partial_tokens=12,
        max_validations=96):
    if train_size<1 or eval_per_band<1:
        raise ValueError("positive sample counts required")
    training={}
    testing={}
    catalog=[]
    for book in (*TRAIN_BOOKS,*TEST_BOOKS):
        core,meta=download(book)
        sentences,stats=extract(book,core,length_min=4,length_max=45)
        (training if book.role=="train" else testing)[book.ebook_id]=sentences
        catalog.append({"id":book.ebook_id,"role":book.role,
                        "sha256":meta["sha256"],
                        "fragments":stats["fragments"],
                        "candidates":stats["eligible"]})
    observed=spread_training(training,train_size)
    heldout=holdout_stratified(testing,
                               per_book_per_band=eval_per_band)
    if len(observed)!=train_size:
        raise RuntimeError("Not enough training observations")
    if not heldout:
        raise RuntimeError("No heldout prose extracted")
    train_author={x["author"] for x in observed}
    if train_author & {x["author"] for x in heldout}:
        raise RuntimeError("Author level leakage")

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    reader=SemanCompiledReader(resources,token_only_lattice=True)
    memory=PartialStructureMemory(resources,min_tokens=min_partial_tokens,
                                   max_tokens=max_partial_tokens)
    train=Counter()
    train_by_length=defaultdict(Counter)
    train_elapsed=[]
    known_at_half=None
    for i,case in enumerate(observed,1):
        t0=perf_counter()
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        report=reader.parse(case["text"],lattice=lattice,
                            capture_partials=True,max_partial_constituents=256)
        p=memory.observe(report.partial_constituents,lattice,
                         sentence_id=i,failed=not report.complete)
        band=length_band(case["tokens"])
        for bucket in (train,train_by_length[band]):
            bucket["seen"]+=1
            bucket["complete"]+=int(report.complete)
            bucket["failed"]+=int(not report.complete)
            bucket["has_completed_reductions"]+=int(bool(report.partial_constituents))
            bucket["failed_has_completed_reductions"]+=int(
                not report.complete and bool(report.partial_constituents))
            bucket["failed_has_salvageable_2plus_token_subtrees"]+=int(
                not report.complete and p["source_shapes"]>0)
            bucket["failed_reuses_previously_stored_subtree"]+=int(
                not report.complete and p["repeated"])
            bucket["new_distinct_subtrees"]+=p["unique_added"]
            bucket["partial_capture_truncated"]+=int(report.partial_truncated)
        train_elapsed.append((perf_counter()-t0)*1000)
        if i==train_size//2:
            known_at_half=memory.summary()
        if i%1000==0:
            print("TRAIN "+json.dumps({
                "seen":i,
                "fully_parsed":train["complete"],
                "failed_with_salvage":train["failed_has_salvageable_2plus_token_subtrees"],
                "failed_reusing_prior_subtree":train["failed_reuses_previously_stored_subtree"],
                "patterns":memory.summary()["unique_complete_subtree_shapes"],
            }),flush=True)

    evaluation=Counter()
    by_length=defaultdict(Counter)
    by_book=defaultdict(Counter)
    root_hit=Counter()
    unseen_chars=set()
    errors=[]
    eval_elapsed=[]
    for i,case in enumerate(heldout,1):
        t0=perf_counter()
        lattice=build_lattice(case["text"],resources.lexicon,multiword_max=1)
        raw=reader.parse(case["text"],lattice=lattice,
                         capture_partials=True)
        reuse=memory.match(lattice,max_validations=max_validations)
        wall=(perf_counter()-t0)*1000
        eval_elapsed.append(wall)
        band=length_band(case["tokens"])
        for bucket in (evaluation,by_length[band],by_book[str(case["book_id"])]):
            bucket["tested"]+=1
            bucket["fully_parsed"]+=int(raw.complete)
            bucket["failed"]+=int(not raw.complete)
            bucket["failed_with_local_reductions"]+=int(
                not raw.complete and bool(raw.partial_constituents))
            bucket["retrieval_with_compatible_category_sequence"]+=int(
                reuse.compatible_windows>0)
            bucket["retrieval_with_grammar_unified_subtree"]+=int(
                reuse.grammar_validated_windows>0)
            bucket["FAILED_clause_but_reusable_grammar_subtree"]+=int(
                not raw.complete and reuse.grammar_validated_windows>0)
            bucket["matched_grammar_subtree_windows"]+=reuse.grammar_validated_windows
            bucket["candidate_windows"]+=reuse.compatible_windows
            bucket["validation_budget_truncated"]+=int(reuse.incomplete)
            bucket["reused_token_positions"]+=reuse.covered_tokens
        for _,_,cat in reuse.matched_spans:
            root_hit[cat]+=1
        if i%100==0:
            print("EVAL "+json.dumps({
                "seen":i,
                "failed_but_retrievable":
                    evaluation["FAILED_clause_but_reusable_grammar_subtree"],
                "grammar_validated_windows":
                    evaluation["matched_grammar_subtree_windows"],
                "budget_truncated":evaluation["validation_budget_truncated"],
            }),flush=True)
    return {
        "schema":"seman2-partial-grammar-reuse-v1",
        "catalog":catalog,
        "train_size":len(observed),
        "test_size":len(heldout),
        "train_counts":dict(train),
        "train_by_length":{k:dict(v) for k,v in sorted(train_by_length.items())},
        "halfway_cache":known_at_half,
        "cache":memory.summary(),
        "heldout_counts":dict(evaluation),
        "heldout_by_length":{k:dict(v) for k,v in sorted(by_length.items())},
        "heldout_by_book":{k:dict(v) for k,v in by_book.items()},
        "heldout_reused_root_counts":dict(root_hit),
        "max_validation_windows_per_sentence":max_validations,
        "max_partial_span_tokens":max_partial_tokens,
        "min_partial_span_tokens":min_partial_tokens,
        "important_limitations":[
            "Only completed real L-R grammar reductions are captured, not unanalysed spans.",
            "The enclosing sentence can fail even when a local reduction unifies; locally unified does not mean semantically correct.",
            "The original L-R parser is single-path; it does NOT enumerate alternative attachment trees in one sentence.",
            "All stored trees are candidate evidence. No partial structure is independently gold-verified.",
            "Heldout retrieval re-unifies remembered rule trees on new lexical candidates, not just POS sequence.",
            "Measured heldout success means one locally compatible grammar subtree, NOT a completed grammatical sentence.",
            "Heldout novels and authors are absent from training; corpus sentence splitting is heuristic.",
            "The guard for complete CLAUSE acceptability is not proof of a local NP/VP subtree; no local construction guard is used.",
            "Only 2 to 12 word contiguous subtrees are stored; longer constituent coverage needs a separate experiment.",
            "Revalidation and truncation costs are offline research, not production performance.",
            "Per-position alternative candidate sets are never equated; original lexical lattice is preserved.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--train",type=int,default=3500)
    p.add_argument("--eval-per-band",type=int,default=40)
    p.add_argument("--max-validations",type=int,default=96)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=run(a.wordnet_dir,train_size=a.train,
               eval_per_band=a.eval_per_band,max_validations=a.max_validations)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print("FINAL "+json.dumps({
        "training":result["train_counts"],
        "stored":result["cache"],
        "holdout":result["heldout_counts"],
        "by_length":result["heldout_by_length"],
        "by_book":result["heldout_by_book"],
    }),flush=True)


if __name__=="__main__":
    main()
