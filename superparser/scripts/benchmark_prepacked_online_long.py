"""Measure *actual progressive online* parsing cost over many Gutenberg sentences.

Both readers process every same sentence. C sees only PAST candidate parses.
No fixed pretraining split, no future information, no cached answers.
Net savings INCLUDE online observation, C matching, and index recompilation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract, spread_training
from research.verbnet_lr.hybrid_vector import HybridVectorParser
from seman_parser.engine import Parser, ParserResources

ROOT=Path(__file__).resolve().parents[1]


def shape(node):
    if node is None:
        return None
    candidate=node.lexical_candidate
    if candidate is not None:
        return ("leaf", node.start, node.end, node.category, candidate.lemma,
                candidate.sense_id, node.features.as_dict())
    return (node.category,node.rule_id,node.start,node.end,node.features.as_dict(),
            tuple(shape(child) for child in node.children))


def run(wordnet_dir, *, max_sentences=20000, max_tokens=24, checkpoint=500,
        recompile_every=500, max_items=50000):
    if min(max_sentences,max_tokens,checkpoint,recompile_every,max_items)<1:
        raise ValueError("Budgets must be positive")
    books={}
    metadata=[]
    for book in TRAIN_BOOKS:
        core,info=download(book)
        rows,counts=extract(book,core,length_min=4,length_max=max_tokens)
        books[book.ebook_id]=rows
        metadata.append({
            "id":book.ebook_id,"author":book.author,"sha256":info["sha256"],
            "available":len(rows),"source_url":info["url"],"extraction":counts,
        })
        print("BOOK "+str(book.ebook_id)+" eligible="+str(len(rows)),flush=True)
    chosen=spread_training(books,max_sentences)
    if len(chosen)!=max_sentences:
        raise ValueError(f"Need {max_sentences} sentences, found {len(chosen)}")
    # De-duplicate across books, unlike the underlying per-book extractor.
    seen=set()
    stream=[]
    for row in chosen:
        norm=" ".join(row["text"].casefold().split())
        if norm in seen:continue
        seen.add(norm)
        stream.append(row)
    print("STREAM "+json.dumps({
        "available":len(stream),"authors":len({r["author"] for r in stream}),
        "token_bands":dict(Counter("04-12" if r["tokens"]<=12 else "13-24"
                                    for r in stream)),
    }),flush=True)

    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    canonical=Parser(resources,cache_size=0,max_items=max_items)
    adaptive=HybridVectorParser(
        resources,cache_size=0,max_items=max_items,
        prepacked_witnesses=True,min_rule_sentences=2,
    )
    history=[]
    count=0
    seen_sources=0
    mismatches=0
    baseline_time=0.
    adaptive_parse_time=0.
    adaptive_learning_time=0.
    baseline_unify=0
    adaptive_unify=0
    baseline_recognition=0
    adaptive_recognition=0
    reused=0
    certified=0
    c_match_time=0.
    last=None

    for row in stream:
        count+=1
        text=row["text"]
        # Alternate wall-clock order, mitigating process/warm-cache trends.
        if count%2:
            arms=(("hybrid",adaptive),("baseline",canonical))
        else:
            arms=(("baseline",canonical),("hybrid",adaptive))
        results={}
        elapsed={}
        for label,reader in arms:
            start=perf_counter()
            report=reader.parse(text)
            elapsed[label]=(perf_counter()-start)*1000.
            results[label]=report

        old=results["baseline"].result
        new=results["hybrid"].result
        baseline_time+=elapsed["baseline"]
        adaptive_parse_time+=elapsed["hybrid"]
        baseline_unify+=old.stats.get("unification_attempts",0)
        adaptive_unify+=new.stats.get("unification_attempts",0)
        baseline_recognition+=old.stats.get("recognition_operations",0)
        adaptive_recognition+=new.stats.get("recognition_operations",0)
        witness=new.stats.get("prepacked_witnesses",{})
        reused+=witness.get("reused",0)
        certified+=witness.get("certified",0)
        c_match_time+=new.stats.get("c_witness_match_ms",0.)

        # Parity is checked BEFORE learning the present observation.
        if (
            old.completed!=new.completed
            or (old.best().score if old.best() else None)!=
               (new.best().score if new.best() else None)
            or shape(old.best())!=shape(new.best())
            or old.stats.get("forest_nodes")!=new.stats.get("forest_nodes")
            or old.stats.get("structural_derivations")!=
               new.stats.get("structural_derivations")
        ):
            mismatches+=1
        started=perf_counter()
        result=adaptive.observe(
            results["hybrid"],
            source_id=f"{row['book_id']}:{row['ordinal']}",
            evidence="candidate",
        )
        seen_sources+=int(result["learned"])
        if count%recompile_every==0:
            adaptive.compile_guidance()
        adaptive_learning_time+=(perf_counter()-started)*1000.

        if count%checkpoint==0 or count==len(stream):
            hybrid_all=adaptive_parse_time+adaptive_learning_time
            point={
                "sentences":count,
                "learned":seen_sources,
                "learned_rules":adaptive.guidance_summary()["rules_with_support"],
                "baseline_total_ms":round(baseline_time,3),
                "hybrid_parse_total_ms":round(adaptive_parse_time,3),
                "hybrid_learning_total_ms":round(adaptive_learning_time,3),
                "hybrid_total_ms":round(hybrid_all,3),
                "net_saved_ms":round(baseline_time-hybrid_all,3),
                "relative_net_saving_pct":round(100*(baseline_time-hybrid_all)/baseline_time,3)
                   if baseline_time else 0.,
                "base_unifications":baseline_unify,
                "hybrid_unifications":adaptive_unify,
                "saved_unifications":baseline_unify-adaptive_unify,
                "baseline_recognition":baseline_recognition,
                "hybrid_recognition":adaptive_recognition,
                "certified_C_witnesses":certified,
                "reused_C_witnesses":reused,
                "C_match_total_ms":round(c_match_time,3),
                "parity_mismatches":mismatches,
            }
            history.append(point)
            print("CURVE "+json.dumps(point,separators=(",",":")),flush=True)
    return {
        "schema":"seman2-online-progressive-long-parsing-v1",
        "source":"Gutenberg novels in TRAIN_BOOKS; author-separated test not claimed",
        "metadata":metadata,
        "processed_sentences":count,
        "checkpoint_every":checkpoint,
        "recompile_every":recompile_every,
        "curve":history,
        "parity_pass":mismatches==0,
        "limitations":[
            "No complete independently gold-standard parse annotation.",
            "Grammar-derived candidate feedback is not manually verified.",
            "Savings compare cumulative end-to-end parsing plus learning, not an extrapolation.",
            "One timed run with alternating order: p-values or confidence intervals not supplied.",
            "Rerun multiple permutations to establish statistical robustness.",
            "Recognition remains canonical; structural witness replay may be too conservative.",
            "The same observation never trains the model before its own parse.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-sentences",type=int,default=20000)
    p.add_argument("--max-tokens",type=int,default=24)
    p.add_argument("--checkpoint",type=int,default=500)
    p.add_argument("--recompile-every",type=int,default=500)
    a=p.parse_args()
    result=run(a.wordnet_dir,max_sentences=a.max_sentences,
               max_tokens=a.max_tokens,checkpoint=a.checkpoint,
               recompile_every=a.recompile_every)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print("FINAL "+json.dumps({
        "processed":result["processed_sentences"],
        "parity":result["parity_pass"],
        "last":result["curve"][-1] if result["curve"] else None,
    }),flush=True)
    if not result["parity_pass"]:
        raise SystemExit("Syntax/tree parity failure")


if __name__=="__main__":
    main()
