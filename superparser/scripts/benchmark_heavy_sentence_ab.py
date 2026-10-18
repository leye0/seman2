"""Paired A/B experiment: early lexical constraints and clause interfaces.

Only research routes are changed. Pinned cleaned novels; identical lexical
lattices per arm; both candidate strategies retain the canonical fallback.
No complete parse is assumed correct merely because it is completed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter_ns

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from scripts.benchmark_cleaned_four_novels_5k import sample_spread
from scripts.characterize_failed_10k import best_signature
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.vector_chart import VectorGrammar

ROOT=Path(__file__).resolve().parents[1]
BANDS=(("04-08",4,8),("09-16",9,16),("17-24",17,24),("25-32",25,32))
ARMS=("baseline","early","split","rescue")


def choose_cases(per_book_per_band):
    books={b.ebook_id:b for b in TRAIN_BOOKS}
    selected=[]
    source=[]
    for record in read_manifest()["books"]:
        book=books[record["ebook_id"]]
        text,info=load_cleaned(book)
        rows,_=extract(book,text,length_min=4,length_max=32)
        for band,lo,hi in BANDS:
            pool=[r for r in rows if lo<=r["tokens"]<=hi]
            n=min(per_book_per_band,len(pool))
            selected.extend({**r,"band":band} for r in sample_spread(pool,n))
            source.append({"book_id":book.ebook_id,"title":book.title,
                           "band":band,"eligible":len(pool),"sampled":n,
                           "sha256":info["sha256"]})
    return selected,source


def has_quotation(text):
    # Apostrophe-only contractions are not interpreted as double quotations.
    return any(x in text for x in ('"','“','”','‘','’'))


def early_filter_eligible(text,tokens):
    return len(tokens)>=17 and not has_quotation(text)


def split_plan(text,tokens,parser,*,allow_multiple=False):
    """Explore two lossless clause-interface routes, both grammar-validated.

    Comma-separated clause lists use the pre-existing conservative planner.
    A *single* coordinating conjunction can also be a safe boundary when
    the same compiled grammar verifies both segments and their composition.
    Apparent boundaries inside phrases simply fail and fall back. Never
    delete the separator or replace incomplete fragments with full clauses.
    """
    if len(tokens)<22 or has_quotation(text):
        return None
    if len(tokens)>=24 and text.count(",")>=2:
        plan=parser._clause_plan(text,tokens)
        if plan is not None:
            spans,_=plan
            lengths=[sum(start<=tok.start and tok.end<=end for tok in tokens)
                     for start,end in spans]
            if 2<=len(spans)<=4 and all(4<=n<=18 for n in lengths):
                return plan
    # Choose the least unbalanced coordination split. All surviving
    # candidates undergo the *same* clause grammar; no invented derivations.
    choices=[]
    for index,token in enumerate(tokens):
        if token.text.casefold() not in {"and","but","or","yet"}:
            continue
        if token.text.casefold() not in parser._coord_surfaces:
            continue
        left=tokens[:index]
        right=tokens[index+1:]
        if not (7<=len(left)<=24 and 7<=len(right)<=24):
            continue
        # Preserve commas and punctuation inside each original segment.
        spans=((left[0].start,left[-1].end),
               (right[0].start,right[-1].end))
        choices.append((abs(len(left)-len(right)),index,(spans,(token,))))
    if not choices or (len(choices)!=1 and not allow_multiple):
        # Ambiguous boundaries are only permitted *after* a budget-capped
        # failed baseline, never before a known-successful standard parse.
        return None
    return min(choices,key=lambda x:(x[0],x[1]))[2]


def rescue_eligible(baseline_result,text,tokens):
    """Never redo a successful parse; try recovery only after a budget failure."""
    return (not baseline_result["completed"]
            and (baseline_result["budget"] or baseline_result["kbest_budget"])
            and len(tokens)>=22 and not has_quotation(text))


def timed(action):
    start=perf_counter_ns()
    result=action()
    best=result.best() if result.completed else None
    ms=(perf_counter_ns()-start)/1e6
    stats=result.stats
    return {"ms":round(ms,5),"completed":best is not None,
            "signature":best_signature(best),
            "budget":bool(stats.get("budget_exceeded")),
            "kbest_budget":bool(stats.get("kbest_budget_exceeded")),
            "nodes":stats.get("forest_nodes",0),
            "partials":stats.get("partial_states",0),
            "recognition_ms":stats.get("recognition_ms",0),
            "best_ms":stats.get("best_ms",0),
            "dialogue_scoped":bool(stats.get("dialogue_scoped",False)),
            "early_pruned":stats.get("early_lexical_pruned",0)}


def quantile(values,q):
    data=sorted(values)
    if not data:return None
    x=(len(data)-1)*q
    i=int(x)
    return round(data[i]+(data[min(i+1,len(data)-1)]-data[i])*(x-i),4)


def cohort(rows,arm):
    t=[r[arm]["ms"] for r in rows]
    b=[r["baseline"]["ms"] for r in rows]
    return {
        "n":len(rows),
        "complete":sum(r[arm]["completed"] for r in rows),
        "rescued":sum(r[arm]["completed"] and not r["baseline"]["completed"] for r in rows),
        "lost":sum(r["baseline"]["completed"] and not r[arm]["completed"] for r in rows),
        "changed_signature":sum(r[arm]["completed"] and r["baseline"]["completed"]
            and r[arm]["signature"]!=r["baseline"]["signature"] for r in rows),
        "p50_ms":quantile(t,.5),"p95_ms":quantile(t,.95),
        "base_p50_ms":quantile(b,.5),"base_p95_ms":quantile(b,.95),
        "sum_ms":round(sum(t),2),
        "base_sum_ms":round(sum(b),2),
        "sum_ratio":round(sum(t)/sum(b),4) if sum(b) else None,
        "budget":sum(r[arm]["budget"] for r in rows),
        "slower_by_20pct":sum(r[arm]["ms"]>1.2*r["baseline"]["ms"] for r in rows),
    }


def summarize(rows,source):
    med=quantile([r["baseline"]["ms"] for r in rows],.5)
    groups={
        "all":rows,
        "fast_baseline_half":[r for r in rows if r["baseline"]["ms"]<=med],
        "slow_baseline_half":[r for r in rows if r["baseline"]["ms"]>med],
        "early_eligible":[r for r in rows if r["early_eligible"]],
        "split_eligible":[r for r in rows if r["split_eligible"]],
    }
    groups.update({"length_"+band:[r for r in rows if r["band"]==band]
                   for band,_,_ in BANDS})
    return {
        "schema":"heavy-sentence-paired-ab-v1","source":source,
        "groups":{name:{a:cohort(items,a) for a in ARMS}
                  for name,items in groups.items()},
        "split_routes":dict(Counter(r["split_route"] for r in rows)),
        "rescue_routes":dict(Counter(r["rescue_route"] for r in rows)),
        "notes":[
            "All three arms receive the same real novel text and prebuilt lattice.",
            "No modifications to canonical grammar or default parser.",
            "The early filter only applies to unquoted 17+ token sentences.",
            "Clause splitting only applies to unquoted 22+ token guarded lists or a single coordination.",
            "Speculative segment parses use a separate 4500-item forest cap and beam 4; failure falls back.",
            "Split reconstructions use the existing SegmentInterface assembly grammar.",
            "Completeness/signature matching are NOT human grammatical correctness.",
            "Both strategies report losses and structural changes before any promotion.",
            "Rescue only attempts a full-budget split after a baseline budget failure.",
            "Rescue never changes a completed baseline tree; additional cost belongs solely to hard failures.",
            "Observed-baseline fast/slow strata are offline labels, not runtime shortcuts.",
            "Parse and best materialization are timed; shared lexing excluded.",
        ],
    }


def run(args):
    selected,source=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=args.max_items)
    early_parser=Parser(resources,cache_size=0,max_items=args.max_items)
    split_parser=Parser(resources,cache_size=0,max_items=min(4500,args.max_items),beam=4)
    rescue_parser=Parser(resources,cache_size=0,max_items=args.max_items)
    early_parser._vector_grammar=VectorGrammar(
        parser._vector_grammar.grammar,early_lexical_filter=True)
    if parser._dialogue_vector_grammar is not None:
        early_parser._dialogue_vector_grammar=VectorGrammar(
            parser._dialogue_vector_grammar.grammar,
            early_lexical_filter=True,preserve_quote_delimiters=True)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with (args.out_dir/"sentences.jsonl").open("w",encoding="utf8",buffering=1) as stream:
        for i,row in enumerate(selected):
            text=row["text"]
            lattice=build_lattice(text,resources.lexicon,multiword_max=1)
            is_early=early_filter_eligible(text,lattice.tokens)
            plan=split_plan(text,lattice.tokens,parser)
            split_route=["not_eligible"]

            def baseline():
                return parser.parse_grammar_lattice(
                    lattice,max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit)

            def filter_first():
                if not is_early:return baseline()
                return early_parser.parse_grammar_lattice(
                    lattice,max_items=args.max_items,
                    kbest_work_limit=args.kbest_work_limit)

            def split_first():
                if plan is not None:
                    candidate=split_parser._parse_hierarchical(text,lattice.tokens,plan)
                    if candidate is not None and candidate.completed:
                        split_route[0]="segmented"
                        return candidate
                    split_route[0]="failed_then_fallback"
                return baseline()

            tasks=[("baseline",baseline),("early",filter_first),("split",split_first)]
            if i%2:tasks.reverse()
            observed={name:timed(callback) for name,callback in tasks}
            # Rescue mode executes *after* the same canonical baseline. It
            # never changes or reparses a successful case, so inexpensive
            # successful sentences retain their exact original analysis.
            rescued=dict(observed["baseline"])
            rescue_route="not_applicable"
            rescue_extra_ms=0.0
            if rescue_eligible(rescued,text,lattice.tokens):
                recovery_plan=split_plan(
                    text,lattice.tokens,rescue_parser,allow_multiple=True)
                if recovery_plan is not None:
                    rescue_route="attempted_fallback"
                    # No second canonical parse on failure: preserve the
                    # baseline result, adding only the speculative cost.
                    tick=perf_counter_ns()
                    candidate=rescue_parser._parse_hierarchical(
                        text,lattice.tokens,recovery_plan)
                    rescue_extra_ms=(perf_counter_ns()-tick)/1e6
                    if candidate is not None and candidate.completed:
                        best=candidate.best()
                        rescued["completed"]=best is not None
                        rescued["signature"]=best_signature(best)
                        rescued["budget"]=bool(candidate.stats.get("budget_exceeded"))
                        rescued["kbest_budget"]=bool(candidate.stats.get("kbest_budget_exceeded"))
                        rescue_route="rescued"
            rescued["ms"]=round(rescued["ms"]+rescue_extra_ms,5)
            observed["rescue"]=rescued
            record={"index":i,"book_id":row["book_id"],"ordinal":row["ordinal"],
                    "text":text,"sha256":sha256(text.encode()).hexdigest(),
                    "tokens":row["tokens"],"band":row["band"],
                    "quoted":has_quotation(text),"early_eligible":is_early,
                    "split_eligible":plan is not None,"split_route":split_route[0],
                    "rescue_route":rescue_route,"rescue_extra_ms":round(rescue_extra_ms,5),
                    **observed}
            rows.append(record)
            stream.write(json.dumps(record,ensure_ascii=False,default=str)+"\n")
            if (i+1)%args.checkpoint==0:
                print("HEAVY_AB_PROGRESS",json.dumps({"seen":i+1,
                      "completed":{a:sum(x[a]["completed"] for x in rows) for a in ARMS},
                      "segmented":sum(x["split_route"]=="segmented" for x in rows)}),
                      flush=True)
    summary=summarize(rows,source)
    (args.out_dir/"summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("HEAVY_AB_FINAL",json.dumps({"groups":summary["groups"],
          "split_routes":summary["split_routes"],
          "rescue_routes":summary["rescue_routes"]}),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--per-book-per-band",type=int,default=16)
    ap.add_argument("--max-items",type=int,default=20000)
    ap.add_argument("--kbest-work-limit",type=int,default=100000)
    ap.add_argument("--checkpoint",type=int,default=16)
    ap.add_argument("--out-dir",type=Path,required=True)
    run(ap.parse_args())


if __name__=="__main__":main()
