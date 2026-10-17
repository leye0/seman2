"""Actual 2,000-sentence Gutenberg two-pass compiled structure snap benchmark.

Pass 1: canonical VectorGrammar, observe real grammar derivations, compile
structural plans once. Pass 2: lex original text again, read ONLY compiled
plans from the positional index, overlay new lexical candidates, do not
reduce or materialize grammatical trees. On misses use canonical vector
fallback, timed separately. Syntax structure is shared; phrase words are
fresh lexical candidates.

Measurements and fidelity audits are outside timed replay on hits. A strict
1ms hit budget applies to COMPLETE occurrence assembly, not bare ID lookup.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter_ns, perf_counter
import json

from research.verbnet_lr.compiled_structure_snap import CompiledStructureReplayer
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract
from scripts.benchmark_snap_50k_two_pass import deadline, Deadline, quantile
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice


ROOT=Path(__file__).resolve().parents[1]


def lexical_readings(item):
    if item.lexical_candidate is not None:
        c=item.lexical_candidate
        return ((c.span_start,c.span_end,c.category,c.lemma,
                 c.sense_ids,c.features.as_dict()),)
    return tuple(x for child in item.children for x in lexical_readings(child))


def occurrence_readings(occ):
    return tuple(
        (c.span_start,c.span_end,c.category,c.lemma,
         c.sense_ids,c.features.as_dict())
        for c in occ.lexical_slots)


def measure(wordnet_dir,*,size=2000,max_tokens=32,timeout=.35,checkpoint=250):
    # ONE genuine novel, not mixed Gutenberg texts; order in the novel retained.
    novel=TRAIN_BOOKS[0]
    raw,info=download(novel)
    corpus,corpus_stats=extract(novel,raw,length_min=4,length_max=max_tokens)
    if len(corpus)<size:
        raise RuntimeError(f"Only {len(corpus)} eligible novel sentences (need {size})")
    corpus=corpus[:size]
    print("CORPUS",json.dumps({
        "book_id":novel.ebook_id,"book":novel.title,"sentences":len(corpus),
        "raw_sha256":info["sha256"],"extraction":corpus_stats
    }),flush=True)

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    native=Parser(resources,cache_size=0,max_items=20000)
    memory=CompiledStructureReplayer(resources)
    source={}
    stats=Counter()
    timings=defaultdict(list)
    indexing_ns=0

    for i,row in enumerate(corpus):
        t=perf_counter_ns()
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        try:
            with deadline(timeout):
                report=native._vector_grammar.parse_lattice(
                    lattice,beam=native.beam,max_items=20000,
                    goal_category=native.goal_category)
                item=report.best() if report.completed else None
        except Deadline:
            item=None
            stats["first_timeout"]+=1
        timings["first_pass_ms"].append((perf_counter_ns()-t)/1e6)
        stats["first_seen"]+=1
        if item is not None:
            stats["first_complete"]+=1
            start=perf_counter_ns()
            try:
                template_id=memory.observe(item,lattice=lattice)
                source[i]=(template_id,item,lexical_readings(item))
                stats["indexed"]+=1
                if memory.plans[template_id] is not None:
                    stats["compiled_safe"]+=1
            except (ValueError,OverflowError):
                stats["not_indexable"]+=1
            indexing_ns+=perf_counter_ns()-start
        if (i+1)%checkpoint==0:
            print("TRAIN",json.dumps({
                "seen":i+1,"completed":stats["first_complete"],
                "indexed":stats["indexed"],"compiled_safe":stats["compiled_safe"],
                "unique_structures":len(memory.index.templates)
            }),flush=True)

    # Different LexicalCandidate instances, same original text. No
    # full grammar reduction/materialization is EVER called on cache hits.
    for i,row in enumerate(corpus):
        t=perf_counter_ns()
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        lex_ns=perf_counter_ns()-t
        start=perf_counter_ns()
        hit=memory.replay(lattice,max_templates_checked=32)
        match_ns=perf_counter_ns()-start
        timings["compiled_lookup_all_ms"].append(match_ns/1e6)
        timings["lexing_ms"].append(lex_ns/1e6)
        stats["replay_seen"]+=1
        if hit.complete:
            total_ns=perf_counter_ns()-t
            occ=hit.occurrence
            stats["hits"]+=1
            timings["hit_ms"].append(match_ns/1e6)
            timings["hit_including_lex_ms"].append(total_ns/1e6)
            stats["hit_over_1ms"]+=int(match_ns>1_000_000)
            stored=source.get(i)
            if stored is not None:
                stats["hit_on_indexed"]+=1
                stats["same_template_id"]+=int(stored[0]==occ.structure_id)
                stats["shared_structure_identity"]+=int(
                    occ.structure is memory.index.templates[occ.structure_id].shape)
                stats["selected_lexical_same"]+=int(
                    stored[2]==occurrence_readings(occ))
            else:
                stats["hit_not_stored_on_this_pass"]+=1
            timings["second_pass_ms"].append(total_ns/1e6)
        else:
            stats["fallback"]+=1
            stats["fallback_due_to_"+hit.reason]+=1
            try:
                with deadline(timeout):
                    report=native._vector_grammar.parse_lattice(
                        lattice,beam=native.beam,max_items=20000,
                        goal_category=native.goal_category)
                    if report.completed:
                        stats["fallback_complete"]+=1
            except Deadline:
                stats["fallback_timeout"]+=1
            total_ns=perf_counter_ns()-t
            timings["fallback_ms"].append(total_ns/1e6)
            timings["second_pass_ms"].append(total_ns/1e6)
        if (i+1)%checkpoint==0:
            print("REPLAY",json.dumps({
                "seen":i+1,"hits":stats["hits"],"fallback":stats["fallback"],
                "hit_p50_ms":quantile(timings["hit_ms"],.5),
                "hit_p95_ms":quantile(timings["hit_ms"],.95),
                "hit_worst_ms":round(max(timings["hit_ms"]),5) if timings["hit_ms"] else None,
                "hit_over_1ms":stats["hit_over_1ms"]
            }),flush=True)

    percentiles={
        name:{"p50_ms":quantile(data,.5),
              "p95_ms":quantile(data,.95),
              "p99_ms":quantile(data,.99),
              "max_ms":round(max(data),4) if data else None,
              "total_ms":round(sum(data),4),
              "n":len(data)}
        for name,data in timings.items()
    }
    baseline_total=sum(timings["first_pass_ms"])
    replay_total=sum(timings["second_pass_ms"])
    learning_ms=indexing_ns/1e6
    hit=stats["hits"]
    report={
        "schema":"compiled-tree-overlay-gutenberg-single-novel-2k-v1",
        "source":{"id":novel.ebook_id,"title":novel.title,
                  "sha256":info["sha256"],"sentences":size,
                  "max_tokens":max_tokens},
        "training":dict(stats),
        "unique_structures":len(memory.index.templates),
        "compiled_plans":sum(x is not None for x in memory.plans),
        "time":percentiles,
        "reuse":{
            "cached_hit_rate_pct":round(100*hit/size,3),
            "same_template_id_pct":round(100*stats["same_template_id"]/stats["hit_on_indexed"],3)
                  if stats["hit_on_indexed"] else None,
            "lexical_parity_pct":round(100*stats["selected_lexical_same"]/stats["hit_on_indexed"],3)
                  if stats["hit_on_indexed"] else None,
            "structure_pointer_shared_pct":round(
                100*stats["shared_structure_identity"]/stats["hit_on_indexed"],3)
                  if stats["hit_on_indexed"] else None,
        },
        "savings":{
            "first_pass_vector_total_s":round(baseline_total/1000,4),
            "replay_total_s":round(replay_total/1000,4),
            "replay_saved_pct":round(100*(baseline_total-replay_total)/baseline_total,3),
            "two_pass_saved_pct":round(100*(
                baseline_total-replay_total-learning_ms)/(2*baseline_total),3),
        },
        "criteria":{
            "max_hit_ms":1.0,
            "all_hits_under_1ms":stats["hit_over_1ms"]==0,
            "hit_p95_under_1ms":bool(hit and percentiles["hit_ms"]["p95_ms"]<1.0),
            "has_real_hits":hit>0,
        },
        "notes":[
            "Only safe precompiled atomic/variable equality plans can hit.",
            "Hit time includes index search, grammatical compatibility check and word overlay.",
            "Lexical segmentation and fallback are reported separately.",
            "The compiled occurrence references a shared original tree; it does not instantiate a ChartItem.",
            "Lexical parity compares selected lexemes to canonical VectorGrammar, not independent gold.",
            "A grammar-compatible structural pattern does not establish independent human semantic correctness.",
            "Full Layer 2 consumption has not yet been integrated or measured.",
            "Cross-template score competition is not solved by first eligible index hit.",
        ]
    }
    report["pass"]=all(report["criteria"].values())
    print("FINAL",json.dumps(report,separators=(",",":")),flush=True)
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--size",type=int,default=2000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--parse-timeout",type=float,default=.35)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    result=measure(args.wordnet_dir,size=args.size,max_tokens=args.max_tokens,
                   timeout=args.parse_timeout)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    if not result["pass"]:
        raise SystemExit("FAIL: compiled structural replayer did not meet hard <1ms per complete hit")


if __name__=="__main__":
    main()
