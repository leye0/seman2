"""Corrected Gutenberg experiment: parse EVERY train sentence, then 10% audit.

The previous 60k run skipped lexing, snapping and L-R for 54k/60k inputs.
This is the intended ONLINE experiment: every selected novel observation
builds the entire lexical candidate lattice, queries the full-structure index,
falls back to L-R on a miss, and adds completed L-R derivations as CANDIDATES.
Only the independent Earley teacher is 1-in-10 sampled.

Reports count lexical-pattern repetition separately from full-tree snaps,
grammatical parsing, teacher verification, and actual syntax conformity.
No book text is written to results or committed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, SnappingResearchReader,
)
from research.verbnet_lr.sampled_teacher import VerificationSamplingQueue
from research.verbnet_lr.compatible_category_sequences import CompatibleCategorySequenceIndex
from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS, TEST_BOOKS, download, extract, spread_training,
)
from scripts.benchmark_snap_novels import _seed, _evaluate, _test_set, _normalized
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


def _percentile(data,portion):
    if not data:
        return None
    data = sorted(data)
    return round(data[min(len(data)-1,int((len(data)-1)*portion))],5)


def _novels():
    catalog=[]
    train={}
    holdout={}
    for book in (*TRAIN_BOOKS,*TEST_BOOKS):
        core,meta=download(book)
        cases,counts=extract(book,core,length_min=4,length_max=45)
        meta["extraction"]=counts
        catalog.append(meta)
        (train if book.role=="train" else holdout)[book.ebook_id]=cases
        print(f"BOOK {book.ebook_id} {book.title} eligible={counts['eligible']}",
              flush=True)
    return train,holdout,catalog


def run(*,wordnet_dir,max_train=50_000,
        milestones=(0,5_000,20_000,50_000),
        sample_every=10,teacher_seconds=.055,seed_seconds=.35,
        per_book_band=75,full_holdout=True,max_teacher_tokens=32):
    milestones=tuple(sorted(set(milestones)))
    if (max_train<1 or not milestones or milestones[0]!=0
            or milestones[-1]>max_train or sample_every<1
            or teacher_seconds<=0 or seed_seconds<=0 or per_book_band<1):
        raise ValueError("Invalid benchmark budgets or milestones")
    train,heldout,catalog=_novels()
    annotated=[json.loads(row) for row in
               (ROOT/"data/syntax_correctness_validation.jsonl")
               .read_text(encoding="utf8").splitlines() if row.strip()]
    eval_cases=[r for r in annotated if r.get("split")!="dev"]
    negatives=[json.loads(row) for row in
               (ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl")
               .read_text(encoding="utf8").splitlines() if row.strip()]
    forbidden={_normalized(row["text"]) for row in annotated+negatives}
    forbidden.update(_normalized(row["contrast"]) for row in negatives)
    for cases in heldout.values():
        forbidden.update(_normalized(row["text"]) for row in cases)
    seen=set()
    usable={}
    removed=Counter()
    for book_id,rows in train.items():
        selected=[]
        for row in rows:
            normalized=_normalized(row["text"])
            if normalized in forbidden or normalized in seen:
                removed["duplicate_or_test_overlap"]+=1
                continue
            seen.add(normalized)
            selected.append(row)
        usable[book_id]=selected
    training=spread_training(usable,max_train)
    if len(training)<milestones[-1]:
        raise RuntimeError(f"Need {milestones[-1]} cases, have {len(training)}")
    if {x["author"] for x in training} & {
            b.author for b in TEST_BOOKS}:
        raise RuntimeError("Author leakage into held-out novels")
    if {_normalized(r["text"]) for r in training} & forbidden:
        raise RuntimeError("Leaked holdout text into training")

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    index=FullStructureSnapIndex(resources)
    seeded,_=_seed(index,resources,seed_seconds)
    starter_templates=len(index.templates)
    sampler=VerificationSamplingQueue(
        every=sample_every,phase=0,max_pending=2)
    reader=SnappingResearchReader(
        resources,index=index,
        fallback=SemanCompiledReader(resources,token_only_lattice=True),
        sampler=sampler)
    lexical_patterns=CompatibleCategorySequenceIndex()
    data=Counter()
    lengths=defaultdict(Counter)
    timings=[]
    reports=[]

    def record(n):
        print("EVAL "+str(n)+" input="+str(len(training))
              +" templates="+str(len(index.templates)),flush=True)
        novel_holdout=_test_set(heldout,per_book_band)
        snap_eval=_evaluate(
            index,resources,novel_holdout,eval_cases,negatives)
        full_eval = (_evaluate(
            index,resources,
            [r for rows in heldout.values() for r in rows],
            eval_cases,negatives)
            if full_holdout and n in (0,milestones[-1]) else None)
        full_shapes=Counter(t.categories for t in index.templates)
        totals=sum(x.candidate_observations+x.grammar_witness_observations+
                   x.verified_observations for x in index.templates)
        entry={
            "observed":n,
            "sentence_operation_counts":dict(data),
            "full_structure_cache":index.summary(),
            "distinct_category_sequences_in_templates":len(full_shapes),
            "template_sequences_shared_by_multiple_trees":sum(
                v>1 for v in full_shapes.values()),
            "max_trees_sharing_one_category_sequence":max(
                full_shapes.values(),default=0),
            "total_cached_structure_observations":totals,
            "compatible_category_enumerations":{
                "observations_with_at_least_one_prior_compatible_sequence":
                    data["compatible_category_sequence_repeat"],
                "total_prior_observations_compatible_across_queries":
                    data["compatible_prior_observation_pairs"],
                "index":lexical_patterns.summary(),
                "definition":"Exists one shared full positional category assignment with an earlier sentence; other readings never prevent compatibility. A lexical retrieval signal, not a grammar-verified tree.",
            },
            "by_token_length":{k:dict(v) for k,v in sorted(lengths.items())},
            "sampler":sampler.summary(),
            "teacher_skipped_due_to_long_sentences":data["teacher_too_long"],
            "training_hybrid_latency_ms":{
                "p50":_percentile(timings,.50),
                "p95":_percentile(timings,.95),
                "p99":_percentile(timings,.99),
            },
            "stratified_600_novel_holdout":snap_eval,
            "entire_two_novels_holdout":full_eval,
        }
        reports.append(entry)
        print("MILESTONE "+json.dumps({
            "observed":n,"snaps":data["snap_hit"],
            "lr_completed":data["lr_complete"],
            "compatible_sequence_repeats":
                data["compatible_category_sequence_repeat"],
            "compatible_prior_pairs":
                data["compatible_prior_observation_pairs"],
            "patterns":len(index.templates),
            "teacher_witnesses":sampler.grammar_witnesses,
            "novel_snaps_600":snap_eval["novel_holdout"]["snapped"],
            "all_novel_snaps":(
                full_eval["novel_holdout"]["snapped"]
                if full_eval else None),
            "false_accepts":snap_eval["negative_false_accepts_24"],
        }),flush=True)

    record(0)
    for number,case in enumerate(training,1):
        text=case["text"]
        started=perf_counter()
        # CRUCIAL: lexicalize and parse *every* selected sentence.
        lattice=build_lattice(text,resources.lexicon,multiword_max=1)
        # Union possible choices at each token, intersect compatible
        # observations across positions; no eager Cartesian product.
        lexical_match=lexical_patterns.observe(
            lexical_patterns.lattice_slots(lattice))
        data["compatible_category_sequence_repeat"]+=int(
            lexical_match.has_match)
        data["compatible_prior_observation_pairs"]+=(
            lexical_match.compatible_prior_observations)
        before=len(index.templates)
        result,route=reader.parse(
            text,learn_candidate=True,lattice=lattice)
        elapsed=(perf_counter()-started)*1000
        timings.append(elapsed)
        data["processed_with_lattice_and_parser"]+=1
        data["snap_hit" if route=="snap" else "lr_attempt"]+=1
        if result.complete:
            data["completed"]+=1
            if route!="snap":
                data["lr_complete"]+=1
        else:
            data["incomplete"]+=1
        if len(index.templates)>before:
            data["new_full_tree_from_lr"]+=1
        if result.complete and route!="snap" and len(index.templates)==before:
            data["lr_complete_but_not_added"]+=1
        band=("04-12" if case["tokens"]<=12 else
              "13-24" if case["tokens"]<=24 else
              "25-40" if case["tokens"]<=40 else "41-45")
        lengths[band]["seen"]+=1
        lengths[band]["candidate_sequence_repeat"]+=int(
            lexical_match.has_match)
        lengths[band]["snapped"]+=int(route=="snap")
        lengths[band]["completed"]+=int(result.complete)

        # The reader has enqueued *exactly* one event per sample_every.
        # Execute slow Earley only after all fast-parser timing is recorded.
        if sampler.pending:
            if case["tokens"]>max_teacher_tokens:
                # This is a skipped deep verification, not a failed grammar.
                sampler._pending.popleft()
                sampler.processed+=1
                data["teacher_too_long"]+=1
            else:
                n_before=len(index.templates)
                report=sampler.drain_teacher(
                    index,max_cases=1,max_seconds=teacher_seconds)
                if report["grammar_witnesses"]:
                    data["earley_found"]+=1
                    if len(index.templates)>n_before:
                        data["new_full_tree_from_earley"]+=1
                else:
                    data["earley_unknown_or_unsupported"]+=1
        if number%5_000==0:
            print("TRAIN "+json.dumps({
                "seen":number,"snaps":data["snap_hit"],
                "lr_complete":data["lr_complete"],
                "lattices":data["processed_with_lattice_and_parser"],
                "compatible_category_sequence_repeats":
                    data["compatible_category_sequence_repeat"],
                "earley_found":data["earley_found"],
                "templates":len(index.templates),
            }),flush=True)
        if number in milestones:
            record(number)

    return {
        "schema":"seman2-gutenberg-all-sentences-online-snap-v1",
        "goal":"Measure compatibility of all possible lexical-category enumerations across ALL input sentences, separately from whole-tree snapping.",
        "catalog":catalog,
        "seed":seeded,
        "initial_templates":starter_templates,
        "books_training":[b.ebook_id for b in TRAIN_BOOKS],
        "books_testing":[b.ebook_id for b in TEST_BOOKS],
        "input_train_candidates":sum(len(cases) for cases in usable.values()),
        "training_count":len(training),
        "train_exclusions":dict(removed),
        "novel_test_pool":[{"book_id":id,"count":len(cases)}
                           for id,cases in heldout.items()],
        "sample_every":sample_every,
        "max_teacher_tokens":max_teacher_tokens,
        "teacher_seconds":teacher_seconds,
        "checkpoints":reports,
        "limitations":[
            "All training sentences get lexical lattice, snap and L-R fallback; only 1/10 is deeply sampled.",
            "Successful L-R fallbacks create provisional candidate whole-tree patterns; no independent gold claimed.",
            "Candidate category sequences match existentially across all lexical alternatives; this is not grammatical validation.",
            "Strict structures include full grammar rule IDs and all attachment topology; may over-distinguish linguistic skeletons.",
            "Public-domain prose extraction is heuristic; not manually verified segmentation.",
            "Cross-author heldout novels lack explicit syntactic gold; matches measure recognition, not linguistic accuracy.",
            "Seman2 small explicit-gold set and negatives must not be used for training or ranking.",
            "Bounded Earley is not grammatical ground truth and UNKNOWN is not evidence of agrammaticality.",
            "Workload measured on GitHub CI hardware with opt-in research-only parser.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--max-train",type=int,default=50_000)
    p.add_argument("--milestones",default="0,5000,20000,50000")
    p.add_argument("--every",type=int,default=10)
    p.add_argument("--teacher-seconds",type=float,default=.055)
    p.add_argument("--per-book-band",type=int,default=75)
    p.add_argument("--max-teacher-tokens",type=int,default=32)
    p.add_argument("--skip-full-holdout",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=run(wordnet_dir=a.wordnet_dir,max_train=a.max_train,
               milestones=tuple(int(x) for x in a.milestones.split(",")),
               sample_every=a.every,teacher_seconds=a.teacher_seconds,
               per_book_band=a.per_book_band,
               max_teacher_tokens=a.max_teacher_tokens,
               full_holdout=not a.skip_full_holdout)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print("FINAL "+json.dumps({
        "training_count":report["training_count"],
        "latest":report["checkpoints"][-1]["sentence_operation_counts"],
        "templates":report["checkpoints"][-1]["full_structure_cache"],
        "candidate_sequence_matches":report["checkpoints"][-1]["compatible_category_enumerations"],
    }),flush=True)


if __name__=="__main__":
    main()
