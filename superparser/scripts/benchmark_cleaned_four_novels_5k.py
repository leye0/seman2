"""Two-pass compiled snap on 5000 sentences from four local cleaned novels.

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
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from scripts.benchmark_snap_50k_two_pass import quantile
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice


ROOT=Path(__file__).resolve().parents[1]


def lexical_readings(item):
    if item.lexical_candidate is not None:
        c=item.lexical_candidate
        return ((c.span_start,c.span_end,c.category,c.lemma,
                 c.sense_ids,c.features.as_dict()),)
    return tuple(x for child in item.children for x in lexical_readings(child))


def _walk_rule_nodes(item):
    if item.rule_id is not None:
        yield item
    for ch in item.children:
        yield from _walk_rule_nodes(ch)


def source_candidates(item):
    if item.lexical_candidate is not None:
        return (item.lexical_candidate,)
    return tuple(c for child in item.children for c in source_candidates(child))


def alignment_diagnostic(item,lattice):
    leaves=[]
    def walk(node):
        if node.lexical_candidate is not None:
            leaves.append((node.start,node.end,node.category))
        else:
            for child in node.children:
                walk(child)
    walk(item)
    tokens=tuple(lattice.tokens)
    while tokens and tokens[-1].text in (".","!","?"):
        tokens=tokens[:-1]
    token_spans={(x.start,x.end):i for i,x in enumerate(tokens)}
    aligned=[token_spans.get((a,b)) for a,b,_ in leaves]
    counts=Counter()
    counts["token_count"]=len(tokens)
    counts["leaf_count"]=len(leaves)
    counts["aligned_leaves"]=sum(i is not None for i in aligned)
    counts["non_token_spans"]=sum(i is None for i in aligned)
    counts["unused_tokens"]=len(set(range(len(tokens)))-set(
        i for i in aligned if i is not None))
    counts["index_reordered"]=int(aligned!=sorted(
        (i for i in aligned if i is not None)))
    counts["root_starts_before_first_token"]=int(bool(tokens) and
        item.start<tokens[0].start)
    counts["root_ends_before_last_token"]=int(bool(tokens) and
        item.end<tokens[-1].end)
    return dict(counts)


def occurrence_readings(occ):
    return tuple(
        (c.span_start,c.span_end,c.category,c.lemma,
         c.sense_ids,c.features.as_dict())
        for c in occ.lexical_slots)


def sample_spread(rows, n):
    """Sample the full novel evenly, preserving local narrative order."""
    if n<0 or n>len(rows):
        raise ValueError(f"Need {n} distinct sentences, available {len(rows)}")
    indices=[((2*i+1)*len(rows))//(2*n) for i in range(n)] if n else []
    if len(set(indices))!=n:
        raise AssertionError("sampling duplicate")
    return [rows[i] for i in indices]


def choose_cleaned_5000(book_rows, size):
    ids=list(book_rows)
    if len(ids)!=4 or size<4:
        raise ValueError("Expected four books and at least four sentences")
    quota={id:size//4+int(i<size%4) for i,id in enumerate(ids)}
    chosen={id:sample_spread(book_rows[id],quota[id]) for id in ids}
    corpus=[]
    for i in range(max(quota.values())):
        for id in ids:
            if i<len(chosen[id]):
                corpus.append(chosen[id][i])
    assert len(corpus)==size
    return corpus,quota


def cleaned_5k_source(size,max_tokens):
    books={b.ebook_id:b for b in TRAIN_BOOKS}
    per_book={}
    meta=[]
    for record in read_manifest()["books"]:
        book=books[record["ebook_id"]]
        prose,info=load_cleaned(book)
        if not info["local_cleaned"]:
            raise AssertionError("Downloaded or unverified text must not be used")
        rows,counters=extract(book,prose,length_min=4,length_max=max_tokens)
        per_book[book.ebook_id]=rows
        meta.append({"id":book.ebook_id,"title":book.title,"author":book.author,
                     "sha256":info["sha256"],"clean_git_blob_sha":info["clean_git_blob_sha"],
                     "paragraphs":record["paragraphs"],"local_cleaned":True,
                     "eligible":len(rows),"extraction":counters})
    corpus,quota=choose_cleaned_5000(per_book,size)
    for row in meta:
        row["selected"]=quota[row["id"]]
    return corpus,meta


def dist(vals):
    return {"n":len(vals),"p50_ms":quantile(vals,.5) if vals else None,
            "p95_ms":quantile(vals,.95) if vals else None,
            "p99_ms":quantile(vals,.99) if vals else None,
            "max_ms":round(max(vals),4) if vals else None,
            "total_ms":round(sum(vals),4)}


def measure(wordnet_dir,*,size=5000,max_tokens=32,checkpoint=50,
            kbest_work_limit=100000):
    corpus,books=cleaned_5k_source(size,max_tokens)
    print("CORPUS",json.dumps({"kind":"locally_cleaned_four_books",
        "size":len(corpus),"books":books,
        "sampling":"equal authors, evenly spaced across each novel; round-robin",
        "network_download":False}),flush=True)

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    native=Parser(resources,cache_size=0,max_items=20000)
    memory=CompiledStructureReplayer(resources)
    source={}
    stats=Counter()
    by_book=defaultdict(Counter)
    book_timings=defaultdict(lambda:defaultdict(list))
    timings=defaultdict(list)
    indexing_ns=0
    alignment_failures=[]
    exact_replay_failures=[]

    for i,row in enumerate(corpus):
        book_id=str(row["book_id"])
        t=perf_counter_ns()
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        # NO per-sentence time limit: a slow grammatical analysis is
        # allowed to finish, even if it takes seconds or minutes.
        report=native._vector_grammar.parse_lattice(
            lattice,beam=native.beam,max_items=20000,
            goal_category=native.goal_category,
            kbest_work_limit=kbest_work_limit)
        stats["first_kbest_work_units"]+=report.stats.get("kbest_work_units",0)
        if report.stats.get("kbest_budget_exceeded"):
            stats["first_kbest_budget_exhausted"]+=1
            by_book[book_id]["first_kbest_budget_exhausted"]+=1
        if report.stats.get("budget_exceeded"):
            by_book[book_id]["first_forest_budget_exhausted"]+=1
        item=report.best() if report.completed else None
        if item is None:
            stats["first_incomplete"]+=1
        first_ms=(perf_counter_ns()-t)/1e6
        timings["first_pass_ms"].append(first_ms)
        book_timings[book_id]["first_pass_ms"].append(first_ms)
        stats["first_seen"]+=1
        by_book[book_id]["first_seen"]+=1
        by_book[book_id]["first_complete"]+=int(item is not None)
        if item is not None:
            stats["first_complete"]+=1
            start=perf_counter_ns()
            try:
                template_id=memory.observe(item,lattice=lattice)
                source[i]=(template_id,item,lexical_readings(item))
                stats["indexed"]+=1
                by_book[book_id]["indexed"]+=1
                if memory.plans[template_id] is not None:
                    stats["compiled_safe"]+=1
            except (ValueError,OverflowError) as exc:
                stats["not_indexable"]+=1
                stats["not_indexable_reason_"+str(exc)]+=1
                if len(alignment_failures)<12:
                    alignment_failures.append({
                        "sentence_number":i,
                        "reason":str(exc),
                        "alignment":alignment_diagnostic(item,lattice)
                    })
            indexing_ns+=perf_counter_ns()-start
        if (i+1)%checkpoint==0:
            print("TRAIN",json.dumps({
                "seen":i+1,"completed":stats["first_complete"],
                "indexed":stats["indexed"],"compiled_safe":stats["compiled_safe"],
                "unique_structures":len(memory.index.templates),
                "kbest_budget_exhausted":stats["first_kbest_budget_exhausted"]
            }),flush=True)

    # Different LexicalCandidate instances, same original text. No
    # full grammar reduction/materialization is EVER called on cache hits.
    for i,row in enumerate(corpus):
        book_id=str(row["book_id"])
        t=perf_counter_ns()
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        lex_ns=perf_counter_ns()-t
        start=perf_counter_ns()
        hit=memory.replay(lattice)
        match_ns=perf_counter_ns()-start
        timings["compiled_lookup_all_ms"].append(match_ns/1e6)
        timings["lexing_ms"].append(lex_ns/1e6)
        stats["replay_seen"]+=1
        by_book[book_id]["replay_seen"]+=1
        if hit.complete:
            total_ns=perf_counter_ns()-t
            occ=hit.occurrence
            stats["hits"]+=1
            by_book[book_id]["hits"]+=1
            book_timings[book_id]["hit_ms"].append(match_ns/1e6)
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
            book_timings[book_id]["second_pass_ms"].append(total_ns/1e6)
        else:
            stats["fallback"]+=1
            by_book[book_id]["fallback"]+=1
            stats["fallback_due_to_"+hit.reason]+=1
            report=native._vector_grammar.parse_lattice(
                lattice,beam=native.beam,max_items=20000,
                goal_category=native.goal_category,
                kbest_work_limit=kbest_work_limit)
            stats["fallback_kbest_work_units"]+=report.stats.get("kbest_work_units",0)
            if report.stats.get("kbest_budget_exceeded"):
                stats["fallback_kbest_budget_exhausted"]+=1
            if report.completed:
                stats["fallback_complete"]+=1
            total_ns=perf_counter_ns()-t
            timings["fallback_ms"].append(total_ns/1e6)
            timings["second_pass_ms"].append(total_ns/1e6)
            book_timings[book_id]["second_pass_ms"].append(total_ns/1e6)
            # Audit is intentionally outside the timed replay/fallback.
            if i in source:
                stats["indexed_but_missed"]+=1
        # INDEPENDENT self-replay audit. No oracle guides the actual matcher.
        if i in source:
            template_id=source[i][0]
            plan=memory.plans[template_id]
            if plan is None:
                stats["indexed_uncompiled"]+=1
                if len(exact_replay_failures)<12:
                    exact_replay_failures.append({
                        "sentence_number":i,"cause":"unsupported_plan",
                        "rules":list(
                            dict.fromkeys(rule.rule_id for rule in
                            _walk_rule_nodes(source[i][1])))[:20]})
            else:
                if memory.probe_original_template(lattice,template_id):
                    stats["own_compiled_fill_valid"]+=1
                else:
                    stats["own_compiled_fill_failed"]+=1
                    if len(exact_replay_failures)<12:
                        original_candidates=source_candidates(source[i][1])
                        forced=tuple({c.category:(c,)} for c in original_candidates)
                        exact_replay_failures.append({
                            "sentence_number":i,"cause":"fill_failed",
                            "original_selected_readings_valid":
                                memory._fill(plan,forced) is not None,
                            "candidate_count":len(original_candidates),
                            "slot_count":len(plan.slots),
                            "lexical_slot_differences":[
                                {
                                    "slot":j,
                                    "category":original.category,
                                    "original_feature_names":list(
                                        original.features.as_dict()),
                                    "original_lemma":original.lemma,
                                    "current_candidate_count":len(
                                        memory._lexical_slots(lattice)[j].get(
                                            original.category,())) if
                                            j<len(memory._lexical_slots(lattice)) else 0,
                                    "reading_still_in_lattice":any(
                                        c.span_start==original.span_start and
                                        c.span_end==original.span_end and
                                        c.category==original.category and
                                        c.lemma==original.lemma and
                                        c.features.as_dict()==original.features.as_dict()
                                        for c in lattice.candidates),
                                }
                                for j,original in enumerate(original_candidates)
                            ],
                            "required_features":tuple(tuple(slot.requires)
                                for slot in plan.slots),
                            "rules":list(plan.rules)[:20]})
            if hit.complete:
                stats["indexed_with_hit"]+=1
        if (i+1)%checkpoint==0:
            print("REPLAY",json.dumps({
                "seen":i+1,"hits":stats["hits"],"fallback":stats["fallback"],
                "hit_p50_ms":quantile(timings["hit_ms"],.5),
                "hit_p95_ms":quantile(timings["hit_ms"],.95),
                "hit_worst_ms":round(max(timings["hit_ms"]),5) if timings["hit_ms"] else None,
                "hit_over_1ms":stats["hit_over_1ms"],
                "indexed_but_missed":stats["indexed_but_missed"],
                "own_compiled_fill_valid":stats["own_compiled_fill_valid"]
            }),flush=True)

    percentiles={name:dist(data) for name,data in timings.items()}
    percentiles["combined_10000_passages_ms"]=dist(
        timings["first_pass_ms"]+timings["second_pass_ms"])
    by_author={}
    for book in books:
        key=str(book["id"])
        by_author[key]={"title":book["title"],"author":book["author"],
             "source_sha256":book["sha256"],"counts":dict(by_book[key]),
             "time":{k:dist(v) for k,v in book_timings[key].items()},
             "hit_rate_pct":round(100*by_book[key]["hits"]/
                                   max(1,by_book[key]["replay_seen"]),3)}

    baseline_total=sum(timings["first_pass_ms"])
    replay_total=sum(timings["second_pass_ms"])
    learning_ms=indexing_ns/1e6
    hit=stats["hits"]
    report={
        "schema":"compiled-tree-snap-four-cleaned-novels-5k-v1",
        "source":{"kind":"checked_in_cleaned_novels",
                  "sentences":size,"max_tokens":max_tokens,
                  "books":books,"sampling":"full-book spread, 1250 each at 5000"},
        "by_book":by_author,
        "training":dict(stats),
        "unique_structures":len(memory.index.templates),
        "alignment_rejection_samples":alignment_failures,
        "self_replay_failures":exact_replay_failures,
        "compiled_plans":sum(x is not None for x in memory.plans),
        "kbest_work_limit_per_sentence":kbest_work_limit,
        "uncertified_kbest_cases_are_not_counted_as_completed":True,
        "indexed_self_replayable_pct":round(
            100*stats["own_compiled_fill_valid"]/stats["indexed"],3)
            if stats["indexed"] else None,
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
            "original_indexed_all_self_replayable":
                stats["own_compiled_fill_valid"]==stats["indexed"],
        },
        "notes":[
            "Only safe precompiled atomic/variable equality plans can hit.",
            "Hit time includes index search, grammatical compatibility check and word overlay.",
            "Lexical segmentation and fallback are reported separately.",
            "The compiled occurrence references a shared original tree; it does not instantiate a ChartItem.",
            "Lexical parity compares selected lexemes to canonical VectorGrammar, not independent gold.",
            "A grammar-compatible structural pattern does not establish independent human semantic correctness.",
            "Sources are hash-verified local cleaned narrative paragraphs; no downloaded novel or table of contents.",
            "Combined 10000-pass p50 is calculated from all individual first- and second-pass times.",
            "One shared memory learns across authors, with deterministic round-robin interleaving.",
            "Full Layer 2 consumption has not yet been integrated or measured.",
            "Cross-template score competition is not solved by first eligible index hit.",
            "K-best effort ceiling is a computational budget, not a wall time timeout.",
            "If the effort ceiling is exhausted the case is explicitly marked unproven (incomplete).", 
        ]
    }
    report["pass"]=all(report["criteria"].values())
    print("FINAL",json.dumps(report,separators=(",",":")),flush=True)
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--size",type=int,default=5000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--kbest-work-limit",type=int,default=100000)
    ap.add_argument("--checkpoint",type=int,default=50)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    result=measure(args.wordnet_dir,size=args.size,max_tokens=args.max_tokens,
                   checkpoint=args.checkpoint,kbest_work_limit=args.kbest_work_limit)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    if not result["pass"]:
        raise SystemExit("FAIL: compiled structural replayer did not meet hard <1ms per complete hit")


if __name__=="__main__":
    main()
