"""Out-of-author Gutenberg benchmark for the opt-in certified C/vector replay.

Entire novel texts are downloaded at runtime, never stored in the repository.
Candidate structures are learned ONLY on books by TRAIN_BOOKS authors.
Evaluation uses TEST_BOOKS (other authors), with no training overlap.
This measures native grammatical operations and end-to-end latency separately.
It does not claim that an automatically parsed sentence is gold syntax.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS, TEST_BOOKS, download, extract, spread_training,
    holdout_stratified, length_band,
)
from research.verbnet_lr.hybrid_vector import HybridVectorParser
from seman_parser.engine import Parser, ParserResources

ROOT=Path(__file__).resolve().parents[1]
FIELDS=("recognition_operations","partial_proposals","unification_attempts",
        "combinations_visited_total","nodes_visited_total","compact_analyses")


def _q(values, p):
    if not values:
        return None
    ordered=sorted(values)
    return round(ordered[int((len(ordered)-1)*p)],3)


def _tree(x):
    if x is None:
        return None
    leaf=x.lexical_candidate
    return (x.category,x.start,x.end,x.rule_id,x.features.as_dict(),
            x.syntax.as_dict(),
            (leaf.surface,leaf.category,leaf.lemma,leaf.sense_id) if leaf else None,
            tuple(_tree(c) for c in x.children))


def _parse(engine,sentence):
    started=perf_counter()
    result=engine.parse(sentence).result
    tree=result.best()
    alternatives=result.alternatives(limit=2)
    return {
        "complete":result.completed,
        "best":_tree(tree),
        "alternatives":tuple(_tree(a) for a in alternatives),
        "score":tree.score if tree else None,
        "forest":tuple(result.stats.get(k) for k in
                       ("forest_nodes","structural_derivations",
                        "partial_states","partial_derivations")),
        "lexical":tuple(sorted((c.span_start,c.span_end,c.category)
                                for c in result.lattice.candidates)),
        "operations":{k:result.stats.get(k,0) for k in FIELDS},
        "match_ms":result.stats.get("c_witness_match_ms",0),
        "reuse":result.stats.get("prepacked_witnesses",{}).get("reused",0),
        "incomplete":result.stats.get("budget_exceeded",False),
        "elapsed_ms":(perf_counter()-started)*1000,
    }


def run(wordnet_dir, *, max_train, per_book_per_band, length_max):
    metadata=[]
    training_books={}
    testing_books={}
    for book in (*TRAIN_BOOKS,*TEST_BOOKS):
        text,info=download(book)
        rows,counts=extract(book,text,length_min=4,length_max=length_max)
        info["extraction"]=counts
        metadata.append(info)
        (training_books if book.role=="train" else testing_books)[book.ebook_id]=rows
        print("BOOK "+str(book.ebook_id)+" "+book.role+
              " eligible="+str(len(rows)),flush=True)
    train=spread_training(training_books,max_train)
    holdout=holdout_stratified(testing_books,per_book_per_band=per_book_per_band)
    train_author={x["author"] for x in train}
    test_author={x["author"] for x in holdout}
    if not train or not holdout or train_author & test_author:
        raise RuntimeError("Empty split or authors leaked")
    normalized=lambda x: " ".join(x.casefold().split())
    prohibited={normalized(x["text"]) for x in holdout}
    train=[x for x in train if normalized(x["text"]) not in prohibited]
    if {normalized(x["text"]) for x in train} & prohibited:
        raise RuntimeError("Sentence leakage")

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    teacher=Parser(resources,cache_size=0)
    guide=HybridVectorParser(resources,cache_size=0)
    prepacked=HybridVectorParser(resources,cache_size=0,prepacked_witnesses=True)
    learned=0
    for i,row in enumerate(train,1):
        result=teacher.parse(row["text"])
        if result.result.completed and result.result.best() is not None:
            for engine in (guide,prepacked):
                engine.observe(result,source_id=f"{row['book_id']}:{row['ordinal']}")
            learned+=1
        if i%500==0:
            print("LEARN "+str(i)+" eligible_observations="+str(learned),
                  flush=True)
    assert guide.compile_guidance()==prepacked.compile_guidance()
    del teacher

    mismatches=[]
    metrics={mode:{"timings":[],"ops":Counter(),"reuse":0,"C_ms":0.,
                    "tested":0,"complete":0,"incomplete":0,
                    "by_length":defaultdict(Counter)}
             for mode in ("agenda_only","prepacked")}
    for index,row in enumerate(holdout,1):
        # Alternate A/B order across sentences to diminish warm-cache bias.
        arms=(("agenda_only",guide),("prepacked",prepacked))
        if index%2:
            arms=tuple(reversed(arms))
        snapshots={}
        for mode,engine in arms:
            entry=_parse(engine,row["text"])
            snapshots[mode]=entry
            m=metrics[mode]
            m["timings"].append(entry["elapsed_ms"])
            m["ops"].update(entry["operations"])
            m["reuse"]+=entry["reuse"]
            m["C_ms"]+=entry["match_ms"]
            m["tested"]+=1
            m["complete"]+=int(entry["complete"])
            m["incomplete"]+=int(entry["incomplete"])
            band=length_band(row["tokens"])
            m["by_length"][band]["tested"]+=1
            m["by_length"][band]["complete"]+=int(entry["complete"])
            m["by_length"][band]["unification_attempts"]+=entry["operations"]["unification_attempts"]
            m["by_length"][band]["combinations"]+=entry["operations"]["combinations_visited_total"]
        a,b=snapshots["agenda_only"],snapshots["prepacked"]
        for field in ("complete","best","alternatives","score",
                      "forest","lexical","incomplete"):
            if a[field]!=b[field]:
                mismatches.append({
                    "book_id":row["book_id"],"ordinal":row["ordinal"],
                    "tokens":row["tokens"],"field":field,
                })
        if index%100==0:
            print("EVAL "+str(index)+"/"+str(len(holdout))+
                  " parity_mismatches="+str(len(mismatches)),flush=True)

    summarized={}
    for mode,m in metrics.items():
        summarized[mode]={
            "tested":m["tested"],"complete":m["complete"],
            "budget_exceeded":m["incomplete"],
            "p50_ms":_q(m["timings"],.5),"p95_ms":_q(m["timings"],.95),
            "p99_ms":_q(m["timings"],.99),
            "total_elapsed_ms":round(sum(m["timings"]),2),
            "matcher_ms":round(m["C_ms"],2),
            "reused_witnesses":m["reuse"],
            "operations":dict(m["ops"]),
            "by_length":{k:dict(v) for k,v in sorted(m["by_length"].items())},
        }
    before=summarized["agenda_only"]["operations"]
    after=summarized["prepacked"]["operations"]
    return {
        "schema":"seman2-C-prepacked-Gutenberg-cross-author-v1",
        "books":metadata,
        "train_sentences":len(train),
        "train_candidate_parses":learned,
        "test_sentences":len(holdout),
        "train_authors":sorted(train_author),
        "test_authors":sorted(test_author),
        "samples_by_length":dict(Counter(length_band(r["tokens"]) for r in holdout)),
        "measurement":summarized,
        "saved_operations":{key:before[key]-after[key] for key in FIELDS},
        "parity_pass":not mismatches,
        "mismatches":mismatches,
        "limitations":[
            "Corpus segmentation is heuristic, not hand-labelled grammar.",
            "Candidate parse evidence is not external gold.",
            "Native operations exclude the extra C matcher work; latency includes it.",
            "Only unique context-independent derivations can be replayed.",
            "Other ambiguities remain in the original category-level vector forest.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-train",type=int,default=5000)
    p.add_argument("--per-book-per-band",type=int,default=125)
    p.add_argument("--length-max",type=int,default=45)
    args=p.parse_args()
    if min(args.max_train,args.per_book_per_band,args.length_max)<1:
        p.error("All budgets must be positive")
    report=run(args.wordnet_dir,max_train=args.max_train,
               per_book_per_band=args.per_book_per_band,
               length_max=args.length_max)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print("RESULT "+json.dumps({
        "parity":report["parity_pass"],
        "trained":report["train_candidate_parses"],
        "heldout":report["test_sentences"],
        "saved":report["saved_operations"],
        "measurements":report["measurement"],
        "mismatch_count":len(report["mismatches"]),
    }),flush=True)
    if not report["parity_pass"]:
        raise SystemExit("Canonical syntax or alternatives changed")


if __name__=="__main__":
    main()
