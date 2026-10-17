"""Seman2 canonical-vector replay experiment, with honest positive control.

1) Read genuine Gutenberg phrases using the canonical VectorGrammar Parser.
2) Keep its *actual ParseResult*, not a C guess, in the existing text cache.
3) Train C only from complete grammatical candidates from pass one.
4) Repeat the exact same phrases with uncached vector, the exact cache,
   and C-guided vector without a text cache.
5) Compare grammar, lexical ambiguity, tree, syntax, and wall-clock costs.

Exact-text memoization is explicitly labelled a cheating POSITIVE CONTROL:
it proves a completed earlier result can be retrieved, not that grammar
generalizes. C is measured separately; a slower C is reported as slower.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from time import perf_counter

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS, download, extract, spread_training,
)
from research.verbnet_lr.hybrid_vector import HybridVectorParser
from seman_parser.engine import Parser, ParserResources

ROOT=Path(__file__).resolve().parents[1]


def quantile(values, q):
    if not values:
        return None
    ordered=sorted(values)
    at=(len(ordered)-1)*q
    low=int(at)
    high=min(low+1,len(ordered)-1)
    return round(ordered[low]+(ordered[high]-ordered[low])*(at-low),4)


def describe(values):
    return {
        "n":len(values),
        "p50_ms":quantile(values,.5),
        "p75_ms":quantile(values,.75),
        "p90_ms":quantile(values,.90),
        "p95_ms":quantile(values,.95),
        "total_ms":round(sum(values),3),
        "mean_ms":round(sum(values)/len(values),4) if values else None,
    }


def freeze(value):
    if isinstance(value,dict):
        return tuple(sorted((str(k),freeze(v)) for k,v in value.items()))
    if isinstance(value,(tuple,list)):
        return tuple(freeze(x) for x in value)
    return value


def whole_tree(node):
    if node is None:
        return None
    leaf=node.lexical_candidate
    return (
        node.category,node.start,node.end,node.rule_id,
        freeze(node.features.as_dict()),freeze(node.syntax.as_dict()),
        (leaf.span_start,leaf.span_end,leaf.category,leaf.lemma,
         leaf.sense_id,freeze(leaf.features.as_dict())) if leaf else None,
        tuple(whole_tree(child) for child in node.children),
    )


def signature(result):
    root=result.best()
    lattice=result.lattice
    return {
        "complete":result.completed,
        "tree":whole_tree(root),
        "score":round(root.score,8) if root else None,
        "lexical":tuple(sorted(((
            c.span_start,c.span_end,c.category,c.lemma,
            freeze(c.features.as_dict()),
        ) for c in lattice.candidates), key=repr)),
        "forest":(
            result.stats.get("forest_nodes"),
            result.stats.get("structural_derivations"),
            result.stats.get("partial_states"),
            result.stats.get("partial_derivations"),
        ),
        "budget_exceeded":bool(result.stats.get("budget_exceeded",False)),
    }


def _select(*, per_band, max_tokens):
    by_book={}
    metadata=[]
    for book in TRAIN_BOOKS:
        text,info=download(book)
        rows,counts=extract(book,text,length_min=4,length_max=max_tokens)
        by_book[book.ebook_id]=rows
        metadata.append({
            "id":book.ebook_id,"author":book.author,
            "source_sha256":info["sha256"],"eligible":len(rows),
            "extraction":counts,
        })
        print("BOOK",book.ebook_id,len(rows),flush=True)
    chosen=defaultdict(list)
    fingerprints=set()
    # Take a broad, deterministic mix across books and narrative positions.
    for row in spread_training(by_book,sum(len(a) for a in by_book.values())):
        key=" ".join(row["text"].casefold().split())
        if key in fingerprints:
            continue
        fingerprints.add(key)
        band="04-12" if row["tokens"]<=12 else "13-"+str(max_tokens)
        if len(chosen[band])<per_band:
            chosen[band].append(row)
        if all(len(chosen[b])>=per_band for b in
               ("04-12","13-"+str(max_tokens))):
            break
    if len(chosen["04-12"])!=per_band or len(chosen["13-"+str(max_tokens)])!=per_band:
        raise RuntimeError("Insufficient distinct corpus sentences in one length band")
    selected=chosen["04-12"]+chosen["13-"+str(max_tokens)]
    # Keep actual provenance and length but never embed Gutenberg prose in report.
    return selected,metadata


def run(wordnet_dir, *, per_band=60, max_tokens=18,
        max_items=50000, matcher_ms=30, checkpoint=20):
    if per_band<1 or max_tokens<=12 or matcher_ms<1 or max_items<1:
        raise ValueError("Invalid run budgets")
    selected,books=_select(per_band=per_band,max_tokens=max_tokens)
    print("INPUTS",len(selected),flush=True)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    cached=Parser(resources,cache_size=max(2*len(selected),2048),
                  max_items=max_items)
    baseline=Parser(resources,cache_size=0,max_items=max_items)
    hybrid=HybridVectorParser(resources,cache_size=0,
                              max_items=max_items,prepacked_witnesses=True)
    hybrid.patterns.max_wall_ms=matcher_ms

    saved=[]
    train_ms=[]
    study_ms=[]
    outcomes=Counter()
    for i,row in enumerate(selected,1):
        t0=perf_counter()
        trained=cached.parse(row["text"])
        train_ms.append((perf_counter()-t0)*1000)
        saved.append((trained.result,signature(trained.result)))
        outcomes["first_complete"]+=int(trained.result.completed)
        outcomes["first_budget_exceeded"]+=int(bool(
            trained.result.stats.get("budget_exceeded")))
        start=perf_counter()
        if trained.result.completed:
            info=hybrid.observe(trained,source_id=str(i))
            outcomes["C_training_candidates"]+=int(info["learned"])
        study_ms.append((perf_counter()-start)*1000)
        if i%checkpoint==0:
            print("TRAIN",i,"complete",outcomes["first_complete"],flush=True)
    t0=perf_counter()
    guidance=hybrid.compile_guidance()
    compile_ms=(perf_counter()-t0)*1000
    print("TRAINED",json.dumps({
        "complete":outcomes["first_complete"],
        "C_candidates":outcomes["C_training_candidates"],
        "guidance":guidance,
        "C_patterns":hybrid.patterns.summary(),
    }),flush=True)

    times={name:[] for name in ("canonical","exact_cache","C_vector")}
    matches=Counter()
    by_band=defaultdict(Counter)
    curve=[]
    for i,row in enumerate(selected,1):
        # Rotate order to reduce always-first bias.
        order=("canonical","C_vector","exact_cache") if i%2 else (
            "C_vector","exact_cache","canonical")
        observed={}
        for name in order:
            t0=perf_counter()
            if name=="canonical":
                report=baseline.parse(row["text"])
            elif name=="C_vector":
                report=hybrid.parse(row["text"])
            else:
                report=cached.parse(row["text"])
            elapsed=(perf_counter()-t0)*1000
            times[name].append(elapsed)
            observed[name]=(report.result,signature(report.result))
        original,signature_first=saved[i-1]
        canonical,sig_can=observed["canonical"]
        c_result,sig_c=observed["C_vector"]
        exact,sig_exact=observed["exact_cache"]

        matches["tested"]+=1
        matches["exact_object_recovered"]+=int(exact is original)
        matches["exact_complete_recovered"]+=int(
            original.completed and exact is original)
        matches["canonical_completed"]+=int(canonical.completed)
        matches["C_completed"]+=int(c_result.completed)
        matches["first_vs_canonical_same"]+=int(signature_first==sig_can)
        matches["cache_equals_original"]+=int(sig_exact==signature_first)
        matches["C_tree_equal"]+=int(sig_c["tree"]==sig_can["tree"])
        matches["C_syntax_parity"]+=int(
            (sig_c["tree"] is not None and sig_can["tree"] is not None
             and sig_c["tree"]==sig_can["tree"])
            or (sig_c["tree"] is None and sig_can["tree"] is None))
        matches["C_complete_parity"]+=int(sig_c["complete"]==sig_can["complete"])
        matches["C_lexical_parity"]+=int(sig_c["lexical"]==sig_can["lexical"])
        matches["C_forest_parity"]+=int(sig_c["forest"]==sig_can["forest"])
        matches["C_budget_parity"]+=int(
            sig_c["budget_exceeded"]==sig_can["budget_exceeded"])
        witness=c_result.stats.get("prepacked_witnesses",{})
        matches["C_certified"]+=witness.get("certified",0)
        matches["C_reused"]+=witness.get("reused",0)
        matches["C_match_cutoffs"]+=int(bool(c_result.stats.get("c_witness_incomplete")))
        band="04-12" if row["tokens"]<=12 else "13-"+str(max_tokens)
        by_band[band]["tested"]+=1
        by_band[band]["first_complete"]+=int(original.completed)
        by_band[band]["canonical_complete"]+=int(canonical.completed)
        by_band[band]["C_complete"]+=int(c_result.completed)
        by_band[band]["C_tree_equal"]+=int(sig_c["tree"]==sig_can["tree"])
        by_band[band]["C_reused"]+=witness.get("reused",0)
        # Detect whether any token lacks even one lexical analysis.
        tokens=canonical.lattice.tokens
        coverage={(candidate.span_start,candidate.span_end)
                  for candidate in canonical.lattice.candidates}
        by_band[band]["sentences_with_lexical_gaps"]+=int(any(
            (tok.start,tok.end) not in coverage for tok in tokens
            if tok.text not in (".","!","?")))

        if i%checkpoint==0 or i==len(selected):
            base=sum(times["canonical"])
            memo=sum(times["exact_cache"])
            c_cost=sum(times["C_vector"])
            learning=sum(study_ms)+compile_ms
            curve.append({
                "sentences":i,
                "canonical_cumulative_s":round(base/1000,5),
                "memo_cumulative_s":round(memo/1000,5),
                "C_cumulative_s":round(c_cost/1000,5),
                "memo_savings_pct":round(100*(base-memo)/base,3) if base else 0.,
                "C_savings_pct":round(100*(base-c_cost)/base,3) if base else 0.,
                "C_amortized_savings_pct":round(
                    100*(base-c_cost-learning)/base,3) if base else 0.,
                "C_reused_subtrees":matches["C_reused"],
                "C_tree_equal":matches["C_tree_equal"],
                "exact_recalled":matches["exact_object_recovered"],
            })
            print("CURVE",json.dumps(curve[-1],separators=(",",":")),flush=True)

    baseline_total=sum(times["canonical"])
    exact_total=sum(times["exact_cache"])
    c_total=sum(times["C_vector"])
    c_training=sum(study_ms)+compile_ms
    report={
        "schema":"seman2-canonical-vector-repeat-v1",
        "corpus":{"sentences":len(selected),"per_band":per_band,
                  "max_tokens":max_tokens,"books":books,
                  "identical_text_and_order":True},
        "modes":{
            "canonical":"Fresh canonical VectorGrammar, no text cache",
            "exact_cache":"Parser's ordinary exact text ParseResult cache: intentionally cheating",
            "C_vector":"Trained C witness matcher + canonical packed VectorGrammar; no text cache",
        },
        "first_pass":{
            "canonical_cache_warming":describe(train_ms),
            "C_candidate_training":describe(study_ms),
            "C_compile_ms":round(compile_ms,4),
            "first_complete":outcomes["first_complete"],
            "first_budget_exceeded":outcomes["first_budget_exceeded"],
            "C_training_candidates":outcomes["C_training_candidates"],
            "C_summary":hybrid.guidance_summary(),
        },
        "second_pass":{
            "timing":{k:describe(v) for k,v in times.items()},
            "counts":dict(matches),
            "by_length":{k:dict(v) for k,v in by_band.items()},
            "exact_cache_hit_pct":round(
                100*matches["exact_object_recovered"]/len(selected),3),
            "exact_complete_recovery_pct":round(
                100*matches["exact_complete_recovered"]/
                outcomes["first_complete"],3) if outcomes["first_complete"] else None,
            "exact_cache_net_saving_pct":round(
                100*(baseline_total-exact_total)/baseline_total,3),
            "C_net_saving_pct":round(
                100*(baseline_total-c_total)/baseline_total,3),
            "C_amortized_net_saving_pct":round(
                100*(baseline_total-c_total-c_training)/baseline_total,3),
        },
        "curve":curve,
        "cautions":[
            "Text caching is not structural learning and cannot generalize.",
            "Completion alone is not an independently validated correct parse.",
            "First pass incomplete outputs are cached too, clearly distinguish them.",
            "C witness cost, lexicalization and fallback are all timed end-to-end.",
            "Comparing two candidate trees is not comparing either to human gold.",
            "Full alternative-forest counts are checked, but deep equivalence of every k-best tree is not established by a single best-tree comparison.",
            "This single CI run is not a confidence interval.",
        ],
    }
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--wordnet-dir",required=True)
    parser.add_argument("--per-band",type=int,default=60)
    parser.add_argument("--max-tokens",type=int,default=18)
    parser.add_argument("--max-items",type=int,default=50000)
    parser.add_argument("--matcher-ms",type=int,default=30)
    parser.add_argument("--checkpoint",type=int,default=20)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    r=run(a.wordnet_dir,per_band=a.per_band,max_tokens=a.max_tokens,
          max_items=a.max_items,matcher_ms=a.matcher_ms,checkpoint=a.checkpoint)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("FINAL",json.dumps({
        "corpus_size":r["corpus"]["sentences"],
        "first":{k:v for k,v in r["first_pass"].items() if k not in (
            "canonical_cache_warming","C_candidate_training","C_summary")},
        "second":r["second_pass"],
    },separators=(",",":")),flush=True)
    # A result with fewer than 100% exact cache recovery is a correctness failure.
    if r["second_pass"]["exact_cache_hit_pct"]!=100.:
        raise SystemExit("ERROR: Positive control failed to retrieve every exact input")


if __name__=="__main__":
    main()
